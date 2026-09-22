"""Audit nguồn text dùng cho corpus hiện hành mà không chạm index production."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from ingestion.corpus_refresh import audit_article_sequence, extract_document_sections
from ingestion.docx_text import extract_document_text, extract_footnote_audit
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json, write_json


DEFAULT_OUTPUT = PROJECT_ROOT / "data/legal_sources/source_extraction_review.json"
ND168_DIR = PROJECT_ROOT / "data/raw/legal/168-2024-nd-cp"
DOCX_SOURCES = {
    "49-vbhn-vpqh": {
        "article_count": 86,
        "footnote_count": 41,
    },
    "55-vbhn-vpqh": {
        "article_count": 89,
        "footnote_count": 47,
    },
}


def normalize_legal_text(text: str) -> str:
    """Chuẩn hóa khác biệt trình bày PDF, không sửa nội dung pháp lý."""
    text = unicodedata.normalize("NFC", text).replace("\f", "\n")
    text = re.sub(r"(?m)^.*CÔNG BÁO/Số.*$", "", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    text = re.sub(
        r"\(Xem tiếp Công báo số 77 \+ 78\).*?\(Tiếp theo Công báo số 75 \+ 76\)",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"TM\. CHÍNH PHỦ.*$", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^(\s*Mục\s+\d+)\.(?=\s|$)", r"\1", text)
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_text(pdf_path: Path) -> str:
    """Trích text layer bằng Poppler; thất bại rõ nếu công cụ chưa được cài."""
    with tempfile.TemporaryDirectory(prefix="roadlawqa-source-review-") as temp_dir:
        output = Path(temp_dir) / "source.txt"
        try:
            subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Cần cài pdftotext (Poppler) để chạy audit PDF") from exc
        return output.read_text(encoding="utf-8", errors="strict")


def audit_official_docx(document_id: str, expected: dict) -> dict:
    source_dir = PROJECT_ROOT / "data/raw/legal" / document_id
    docx_path = source_dir / "supporting.docx"
    text_path = source_dir / "supporting-text.txt"
    footnote_path = source_dir / "footnotes.json"
    extracted = extract_document_text(docx_path)
    committed = text_path.read_text(encoding="utf-8", errors="strict")
    footnotes = extract_footnote_audit(docx_path)
    footnotes["source_docx"] = str(docx_path.relative_to(PROJECT_ROOT))
    committed_footnotes = read_json(footnote_path)
    structure = audit_article_sequence(document_id, text_path)
    checks = {
        "docx_reextracts_byte_identically": extracted == committed,
        "article_sequence_complete": structure["passed"],
        "article_count_expected": structure["unique_articles"] == expected["article_count"],
        "footnotes_reextract_identically": footnotes == committed_footnotes,
        "footnote_count_expected": footnotes["footnote_count"] == expected["footnote_count"],
        "all_footnote_references_resolved": not footnotes["unresolved_reference_ids"],
        "no_unreferenced_footnotes": not footnotes["unreferenced_footnote_ids"],
    }
    return {
        "document_id": document_id,
        "selected_extraction": "official_docx_body_text",
        "source_docx": {
            "path": str(docx_path.relative_to(PROJECT_ROOT)),
            "sha256": file_digest(docx_path),
        },
        "extracted_text": {
            "path": str(text_path.relative_to(PROJECT_ROOT)),
            "sha256": file_digest(text_path),
            "article_count": structure["unique_articles"],
        },
        "footnotes": {
            "path": str(footnote_path.relative_to(PROJECT_ROOT)),
            "sha256": file_digest(footnote_path),
            "count": footnotes["footnote_count"],
            "reference_count": footnotes["reference_count"],
        },
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }


def audit_nd168_owner_text() -> dict:
    owner_path = ND168_DIR / "supporting-text.txt"
    official_paths = [ND168_DIR / "congbao-part-1.pdf", ND168_DIR / "congbao-part-2.pdf"]
    official_text = "\n".join(extract_pdf_text(path) for path in official_paths)
    owner_sections = extract_document_sections(owner_path.read_text(encoding="utf-8"), 55)
    official_sections = extract_document_sections(official_text, 55)
    comparisons = []
    for owner, official in zip(owner_sections, official_sections, strict=True):
        matches = normalize_legal_text(owner["text"]) == normalize_legal_text(official["text"])
        comparisons.append({"article": owner["article"], "normalized_match": matches})
    checks = {
        "owner_text_has_articles_1_to_55": [row["article"] for row in owner_sections]
        == list(range(1, 56)),
        "official_congbao_has_articles_1_to_55": [row["article"] for row in official_sections]
        == list(range(1, 56)),
        "all_55_articles_match_after_layout_normalization": all(
            row["normalized_match"] for row in comparisons
        ),
    }
    return {
        "document_id": "168-2024-nd-cp",
        "selected_extraction": "owner_provided_text_verified_against_official_congbao",
        "owner_text": {
            "path": str(owner_path.relative_to(PROJECT_ROOT)),
            "sha256": file_digest(owner_path),
            "article_count": len(owner_sections),
        },
        "official_congbao_parts": [
            {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": file_digest(path),
            }
            for path in official_paths
        ],
        "normalization_scope": [
            "Unicode NFC và khoảng trắng/ngắt trang",
            "header, số trang và đoạn nối hai số Công báo",
            "dấu chấm trình bày sau tiêu đề Mục",
            "gạch nối từ bị tách ở cuối dòng PDF",
            "khối chữ ký sau Điều 55",
        ],
        "article_comparison": comparisons,
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }


def build_review() -> dict:
    reviews = [
        *(audit_official_docx(document_id, expected) for document_id, expected in DOCX_SOURCES.items()),
        audit_nd168_owner_text(),
    ]
    return {
        "schema_version": 1,
        "review_id": "current-law-source-extraction-review-2026-09-22",
        "reviewed_on": "2026-09-22",
        "reviewer": "Codex",
        "purpose": "Xác nhận text đầu vào có thể tái tạo và đủ cấu trúc trước khi tạo corpus/index.",
        "documents": reviews,
        "status": "passed" if all(review["status"] == "passed" for review in reviews) else "failed",
        "production_index_touched": False,
        "legal_interpretation_reviewed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit extraction 49, 55 và 168")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    review = build_review()
    write_json(args.output, review)
    print(f"Source extraction review: {review['status']} -> {args.output}")
    return 0 if review["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
