"""Tạo báo cáo readiness cho Pha 1 mà không chạm index production.

Đây là bước audit nguồn và cấu trúc. Nó cố ý không tạo effective view hoặc
chunks khi amendment map và text nguồn chưa được legal review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ingestion.legal_registry import (
    DEFAULT_AMENDMENTS,
    DEFAULT_REGISTRY,
    PROJECT_ROOT,
    AmendmentMap,
    Registry,
    audit_registry,
    file_digest,
    read_json,
    write_json,
)


ARTICLE_RE = re.compile(r"^[^\w\n]{0,8}Điều\s+(\d+)\.\s*(.*)$", re.MULTILINE)
EXPECTED_ARTICLES = {
    "49-vbhn-vpqh": 86,
    "55-vbhn-vpqh": 89,
    "168-2024-nd-cp": 55,
    "238-2026-nd-cp": 21,
}
def article_headings(text: str) -> list[dict]:
    return [
        {"article": int(match.group(1)), "title": re.sub(r"\s+", " ", match.group(2)).strip()}
        for match in ARTICLE_RE.finditer(text)
    ]


def select_document_headings(headings: list[dict], expected_last: int) -> tuple[list[dict], list[dict]]:
    """Chọn chuỗi Điều cấp văn bản, bỏ Điều được trích trong footnote/replacement."""
    selected: list[dict] = []
    ignored: list[dict] = []
    expected = 1
    for heading in headings:
        if heading["article"] == expected and expected <= expected_last:
            selected.append(heading)
            expected += 1
        else:
            ignored.append(heading)
    return selected, ignored


def audit_article_sequence(document_id: str, path: Path) -> dict:
    all_headings = article_headings(path.read_text(encoding="utf-8", errors="strict"))
    headings, ignored = select_document_headings(all_headings, EXPECTED_ARTICLES[document_id])
    numbers = [heading["article"] for heading in headings]
    expected = list(range(1, EXPECTED_ARTICLES[document_id] + 1))
    return {
        "document_id": document_id,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": file_digest(path),
        "heading_occurrences": len(all_headings),
        "selected_document_headings": len(numbers),
        "ignored_embedded_headings": ignored,
        "unique_articles": len(set(numbers)),
        "first_article": min(numbers) if numbers else None,
        "last_article": max(numbers) if numbers else None,
        "missing_articles": sorted(set(expected) - set(numbers)),
        "duplicate_articles": sorted({number for number in numbers if numbers.count(number) > 1}),
        "passed": numbers == expected,
        "headings": headings,
    }


def extract_amendment_sections(text: str, amendment_map: AmendmentMap) -> list[dict]:
    """Tách 21 Điều cấp cao nhất của NĐ238 và nối các operation locator."""
    lines = text.splitlines()
    starts: list[tuple[int, int, str]] = []
    expected = 1
    for index, line in enumerate(lines):
        match = ARTICLE_RE.match(line)
        if match and int(match.group(1)) == expected:
            starts.append((expected, index, match.group(2).strip()))
            expected += 1
            if expected == 22:
                break
    if expected != 22:
        raise ValueError(f"Text NĐ238 chỉ tách được Điều 1–{expected - 1}")

    operation_ids: dict[int, list[str]] = {}
    for operation in amendment_map.operations:
        operation_ids.setdefault(operation.amendment_article, []).append(operation.operation_id)
    sections: list[dict] = []
    for position, (article, start, title) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        section_text = "\n".join(lines[start:end]).strip() + "\n"
        sections.append(
            {
                "amendment_article": article,
                "title": title,
                "source_line_start": start + 1,
                "source_line_end": end,
                "text_sha256": hashlib.sha256(section_text.encode("utf-8")).hexdigest(),
                "operation_ids": operation_ids.get(article, []),
                "text": section_text,
            }
        )
    return sections


def extract_document_sections(text: str, expected_last: int) -> list[dict]:
    """Tách chuỗi Điều cấp văn bản theo line anchor."""
    lines = text.splitlines()
    starts: list[tuple[int, int, str]] = []
    expected = 1
    for index, line in enumerate(lines):
        match = ARTICLE_RE.match(line)
        if match and int(match.group(1)) == expected:
            starts.append((expected, index, match.group(2).strip()))
            expected += 1
            if expected == expected_last + 1:
                break
    if expected != expected_last + 1:
        raise ValueError(f"Chỉ tách được Điều 1–{expected - 1}, cần 1–{expected_last}")
    sections: list[dict] = []
    for position, (article, start, title) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        section_text = "\n".join(lines[start:end]).strip() + "\n"
        sections.append(
            {
                "article": article,
                "title": title,
                "source_line_start": start + 1,
                "source_line_end": end,
                "text_sha256": hashlib.sha256(section_text.encode("utf-8")).hexdigest(),
                "text": section_text,
            }
        )
    return sections


def build_amendment_review_packet(
    base_text: str,
    amendment_sections: list[dict],
    amendment_map: AmendmentMap,
    source_evidence: dict,
) -> dict:
    """Ghép base article, operation và nguyên văn Điều sửa đổi để review."""
    base = {
        section["article"]: section
        for section in extract_document_sections(
            base_text, EXPECTED_ARTICLES["168-2024-nd-cp"]
        )
    }
    amendments = {
        section["amendment_article"]: section for section in amendment_sections
    }
    source_locator_checks = [
        {
            "operation_id": operation.operation_id,
            "marker": f"Điều {operation.target_article}",
            "passed": f"Điều {operation.target_article}"
            in amendments[operation.amendment_article]["text"],
        }
        for operation in amendment_map.operations
    ]
    locator_normalization_passed = all(
        "Điều" not in (operation.target_clause or "")
        and "Điều" not in (operation.target_point or "")
        for operation in amendment_map.operations
    )
    targets: list[dict] = []
    for target_article in sorted({operation.target_article for operation in amendment_map.operations}):
        operations = [
            operation
            for operation in amendment_map.operations
            if operation.target_article == target_article
        ]
        source_articles = sorted({operation.amendment_article for operation in operations})
        targets.append(
            {
                "target_document_id": amendment_map.base_document_id,
                "target_article": target_article,
                "base_section": base[target_article],
                "operations": [
                    operation.model_dump(mode="json") for operation in operations
                ],
                "amendment_sections": [
                    amendments[article] for article in source_articles
                ],
                "review_status": (
                    "approved"
                    if all(operation.review_status == "approved" for operation in operations)
                    else "pending"
                ),
                "review_notes": [
                    "Đã đối chiếu locator kỹ thuật với DOCX chính thức; legal review "
                    "của effective text vẫn là gate riêng."
                ],
            }
        )
    technical_checks = {
        "all_operations_approved_for_transcription": all(
            operation.review_status == "approved" for operation in amendment_map.operations
        ),
        "all_target_articles_exist_in_base": all(
            operation.target_article in base for operation in amendment_map.operations
        ),
        "all_source_sections_reference_target_article": all(
            check["passed"] for check in source_locator_checks
        ),
        "no_cross_article_text_in_locator_fields": locator_normalization_passed,
        "official_docx_provenance_approved": (
            source_evidence["official_docx_review_status"] == "approved"
        ),
    }
    technical_review_passed = all(technical_checks.values())
    return {
        "schema_version": 1,
        "packet_id": "nd168-nd238-amendment-review-2026-09-22",
        "legal_as_of": amendment_map.legal_as_of.isoformat(),
        "base_document_id": amendment_map.base_document_id,
        "amending_document_id": amendment_map.amending_document_id,
        "purpose": (
            "Đối chiếu từng Điều gốc với amendment locator và nguyên văn Điều sửa đổi; "
            "không phải effective view và không được index."
        ),
        "technical_review": {
            "status": "approved" if technical_review_passed else "pending",
            "reviewer": "Codex — đối chiếu provenance, cấu trúc và locator kỹ thuật",
            "reviewed_on": "2026-09-22",
            "operation_count": len(amendment_map.operations),
            "target_article_count": len(targets),
            "source_evidence": source_evidence,
            "checks": technical_checks,
            "failed_source_locator_checks": [
                check for check in source_locator_checks if not check["passed"]
            ],
            "limitations": [
                "Effective view không phải văn bản hợp nhất chính thức.",
                "Các locator future/mixed vẫn phải tuân thủ publication_eligible.",
            ],
        },
        "legal_review": amendment_map.legal_review.model_dump(mode="json"),
        "targets": targets,
    }


def build_reports(
    project_root: Path = PROJECT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    amendments_path: Path = DEFAULT_AMENDMENTS,
) -> tuple[dict, dict, list[dict], dict, str]:
    # Import cục bộ để tránh vòng import: validator dùng các hàm tách Điều ở module này.
    from ingestion.amendment_validator import audit_amendment_locators
    from ingestion.effective_view import build_effective_view

    registry = Registry.model_validate(read_json(registry_path))
    amendment_map = AmendmentMap.model_validate(read_json(amendments_path))
    registry_audit = audit_registry(project_root, registry_path, amendments_path)
    locator_audit = audit_amendment_locators(
        project_root, registry_path, amendments_path
    )
    _, effective_view_manifest = build_effective_view(
        project_root, registry_path, amendments_path
    )

    documents = {document.document_id: document for document in registry.documents}
    structure: list[dict] = []
    for document_id in EXPECTED_ARTICLES:
        document = documents[document_id]
        if not document.extraction:
            raise ValueError(f"{document_id}: thiếu extraction")
        path = project_root / document.extraction.path
        result = audit_article_sequence(document_id, path)
        structure.append(result)

    operation_count_by_article = {
        str(article): sum(
            operation.amendment_article == article for operation in amendment_map.operations
        )
        for article in range(1, 20)
    }
    target_articles = sorted({operation.target_article for operation in amendment_map.operations})
    base_articles = set(range(1, EXPECTED_ARTICLES["168-2024-nd-cp"] + 1))
    amendment_inventory = {
        "operation_count": len(amendment_map.operations),
        "operation_count_by_amendment_article": operation_count_by_article,
        "target_articles": target_articles,
        "unknown_target_articles": sorted(set(target_articles) - base_articles),
        "all_amending_articles_1_to_19_covered": all(operation_count_by_article.values()),
        "legal_review_status": amendment_map.legal_review.status,
    }
    amendment_document = documents["238-2026-nd-cp"]
    if not amendment_document.extraction:
        raise ValueError("238-2026-nd-cp: thiếu supporting text")
    amendment_text_path = project_root / amendment_document.extraction.path
    amendment_sections = extract_amendment_sections(
        amendment_text_path.read_text(encoding="utf-8", errors="strict"),
        amendment_map,
    )
    base_document = documents["168-2024-nd-cp"]
    if not base_document.extraction:
        raise ValueError("168-2024-nd-cp: thiếu supporting text")
    review_packet = build_amendment_review_packet(
        (project_root / base_document.extraction.path).read_text(
            encoding="utf-8", errors="strict"
        ),
        amendment_sections,
        amendment_map,
        {
            "official_page": amendment_document.extraction.supporting_input_url,
            "official_docx_sha256": amendment_document.extraction.supporting_input_sha256,
            "extracted_text_sha256": amendment_document.extraction.sha256,
            "official_docx_review_status": amendment_document.extraction.review.status,
        },
    )
    amendment_inventory["section_count"] = len(amendment_sections)
    amendment_inventory["sections_sha256"] = hashlib.sha256(
        json.dumps(amendment_sections, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    structure_passed = all(result["passed"] for result in structure)
    technical_source_gate_passed = (
        registry_audit["artifact_integrity_passed"]
        and structure_passed
        and locator_audit["status"] == "passed"
        and effective_view_manifest["status"]
        in {"technical_build_passed_legal_review_pending", "approved_for_snapshot_freeze"}
        and not amendment_inventory["unknown_target_articles"]
        and amendment_inventory["all_amending_articles_1_to_19_covered"]
    )
    readiness = {
        "schema_version": 1,
        "phase": "legal_corpus_refresh_scope_audit",
        "legal_as_of": registry.legal_as_of.isoformat(),
        "technical_source_gate_passed": technical_source_gate_passed,
        "freeze_eligible": registry_audit["freeze_eligible"] and technical_source_gate_passed,
        "production_index_touched": False,
        "historical_baseline_touched": False,
        "registry_audit": registry_audit,
        "locator_audit": {
            "status": locator_audit["status"],
            "summary": locator_audit["summary"],
            "legal_review_status": locator_audit["legal_review_status"],
            "freeze_allowed": locator_audit["freeze_allowed"],
        },
        "effective_view": {
            "status": effective_view_manifest["status"],
            "summary": effective_view_manifest["summary"],
            "legal_review_status": effective_view_manifest["legal_review_status"],
            "freeze_eligible": effective_view_manifest["freeze_eligible"],
        },
        "structure": [
            {key: value for key, value in result.items() if key != "headings"}
            for result in structure
        ],
        "amendment_inventory": amendment_inventory,
        "blocking_reasons": [
            reason
            for condition, reason in [
                (
                    registry.scope_review.status != "approved",
                    "Phạm vi/cutoff chưa có review được ghi nhận trong registry.",
                ),
                (
                    bool(registry_audit["pending_documents"]),
                    "Metadata hoặc extraction của nguồn ingest chưa được duyệt.",
                ),
                (
                    amendment_map.legal_review.status != "approved",
                    "Amendment map 168+238 chưa được legal review.",
                ),
                (
                    bool(registry_audit["blocking_amendment_operations"]),
                    "Replacement/removal text của amendment operations chưa được duyệt.",
                ),
                (
                    locator_audit["status"] != "passed",
                    "Locator hoặc phrase anchor của overlay 168+238 chưa hợp lệ.",
                ),
                (
                    effective_view_manifest["status"]
                    not in {"technical_build_passed_legal_review_pending", "approved_for_snapshot_freeze"},
                    "Effective view 168+238 chưa build thành công.",
                ),
                (
                    not structure_passed,
                    "Chuỗi Điều trong ít nhất một nguồn không liên tục hoặc bị trùng.",
                ),
            ]
            if condition
        ],
        "next_gate": (
            "Tạo processed corpus, shadow Weaviate/BM25 và receipt trước khi freeze snapshot."
            if amendment_map.legal_review.status == "approved"
            else "Duyệt pháp lý effective view 168+238 trước khi freeze và chunk/index."
        ),
    }
    inventory = {
        "schema_version": 1,
        "registry_id": registry.registry_id,
        "legal_as_of": registry.legal_as_of.isoformat(),
        "documents": [
            {
                "document_id": document.document_id,
                "symbol": document.symbol,
                "status_at_cutoff": document.status_at_cutoff,
                "roles": document.roles,
                "scope_decision": document.scope.decision,
                "official_source": document.source.model_dump(mode="json"),
                "extraction": document.extraction.model_dump(mode="json")
                if document.extraction
                else None,
                "metadata_review": document.metadata_review.model_dump(mode="json"),
            }
            for document in registry.documents
        ],
    }
    markdown = render_markdown(readiness)
    return readiness, inventory, amendment_sections, review_packet, markdown


def render_markdown(readiness: dict) -> str:
    state = "ĐẠT" if readiness["technical_source_gate_passed"] else "CHƯA ĐẠT"
    freeze = "ĐỦ ĐIỀU KIỆN" if readiness["freeze_eligible"] else "BỊ CHẶN"
    lines = [
        "# Báo cáo refresh corpus pháp luật",
        "",
        f"- Mốc pháp lý: `{readiness['legal_as_of']}`",
        f"- Gate nguồn kỹ thuật: **{state}**",
        f"- Freeze current-law snapshot: **{freeze}**",
        "- Production index bị thay đổi: **không**",
        "- Baseline lịch sử Pha 0 bị thay đổi: **không**",
        "",
        "## Kiểm tra cấu trúc nguồn",
        "",
        "| Văn bản | Số Điều | Khoảng | Kết quả |",
        "| --- | ---: | --- | --- |",
    ]
    for row in readiness["structure"]:
        result = "đạt" if row["passed"] else "lỗi"
        lines.append(
            f"| {row['document_id']} | {row['unique_articles']} | "
            f"{row['first_article']}–{row['last_article']} | {result} |"
        )
    lines.extend(
        [
            "",
            "DOCX 238 do chủ dự án cung cấp đã được đối chiếu byte-for-byte với file",
            "DOCX trên trang Công báo điện tử. PDF chính thức vẫn được giữ làm artifact",
            "canonical song song để bảo toàn provenance.",
            "",
            "## Inventory sửa đổi 168 + 238",
            "",
            f"- Số operation locator: {readiness['amendment_inventory']['operation_count']}.",
            "- Đã bao phủ các Điều 1–19 của phần sửa đổi: "
            + ("có." if readiness["amendment_inventory"]["all_amending_articles_1_to_19_covered"] else "chưa."),
            "- Đây chưa phải effective text đã được duyệt.",
            "",
        ]
    )
    if readiness["blocking_reasons"]:
        lines.extend(["## Điều kiện còn chặn freeze", ""])
        lines.extend(f"- {reason}" for reason in readiness["blocking_reasons"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit readiness của corpus pháp luật hiện hành")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs/corpus-refresh",
    )
    parser.add_argument("--require-freeze-ready", action="store_true")
    args = parser.parse_args()
    readiness, inventory, amendment_sections, review_packet, markdown = build_reports()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "readiness.json", readiness)
    write_json(args.output_dir / "source-inventory.json", inventory)
    write_json(
        args.output_dir / "amendment-sections.json",
        {
            "schema_version": 1,
            "source_document_id": "238-2026-nd-cp",
            "legal_as_of": readiness["legal_as_of"],
            "sections": amendment_sections,
        },
    )
    write_json(args.output_dir / "amendment-review-packet.json", review_packet)
    (args.output_dir / "legal-diff.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(readiness, ensure_ascii=False, indent=2))
    if args.require_freeze_ready and not readiness["freeze_eligible"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
