"""Audit locator và anchor của overlay Nghị định 168 + 238.

Module chỉ đọc nguồn đã đăng ký và tạo biên bản kỹ thuật. Nó không dựng
effective view, không sửa raw text và không chạm index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from ingestion.corpus_refresh import extract_amendment_sections, extract_document_sections
from ingestion.docx_text import extract_document_text
from ingestion.legal_registry import (
    DEFAULT_AMENDMENTS,
    DEFAULT_REGISTRY,
    PROJECT_ROOT,
    AmendmentMap,
    Registry,
    file_digest,
    read_json,
    write_json,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "data/legal_sources/nd168_locator_audit.json"
CLAUSE_RE = re.compile(r"^(\d+[a-z]?)\.\s")
POINT_RE = re.compile(r"^([a-zđ]\d?)\)\s", re.IGNORECASE)

# Điều 19 thực hiện patch cụm từ. Anchor phải có trong đúng locator của bản 168.
ARTICLE_19_ANCHORS = {
    "p01": ["xe được kéo khi kéo nhau"],
    "p02": ["chỉ được phép chuyển sang một làn đường liền kề"],
    "p03": ["đối với loại phương tiện đang điều khiển"],
    "p04": ["làn dừng xe khẩn cấp"],
    "p05": ["điểm đ"],
    "p06": ["xe ô tô kinh doanh vận tải"],
    "p07": ["điểm h"],
    "p08": ["Điều 29", "điểm n khoản 7"],
    "p09": ["khoản 2"],
    "p10": [
        "chở người trên nóc xe; để người đu bám ở cửa xe, bên ngoài thành xe "
        "khi xe đang chạy"
    ],
    "p11": ["giấy chứng nhận kiểm định"],
    "p12a": ["giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường"],
    "p12b": ["điểm e, điểm g khoản 7;"],
    "p13": ["tại nơi phát hiện vi phạm"],
    "p14": ["Điểm g khoản 5;"],
    "p15": ["điểm m khoản 3 Điều 6,"],
    "p16": ["trực thuộc trung ương"],
}


def normalize_for_match(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def display_path(path: Path, project_root: Path) -> str:
    return str(path.relative_to(project_root)) if path.is_relative_to(project_root) else str(path)


def parse_base_locators(text: str, expected_last: int = 55) -> dict[tuple, str]:
    """Tách text thành locator Điều/khoản/điểm đủ cho audit patch."""
    sections = extract_document_sections(text, expected_last)
    locators: dict[tuple, list[str]] = {}
    for section in sections:
        article = section["article"]
        current = (article, None, None)
        locators[current] = [f"Điều {article}. {section['title']}"]
        for raw_line in section["text"].splitlines()[1:]:
            line = raw_line.strip()
            if not line:
                continue
            clause = CLAUSE_RE.match(line)
            point = POINT_RE.match(line)
            if clause:
                current = (article, clause.group(1).lower(), None)
                locators[current] = [line]
            elif point and current[1] is not None:
                current = (article, current[1], point.group(1).lower())
                locators[current] = [line]
            else:
                locators[current].append(line)
    return {locator: "\n".join(lines) for locator, lines in locators.items()}


def _anchors_for(operation_id: str) -> list[str]:
    for item, anchors in ARTICLE_19_ANCHORS.items():
        if f"-{item}-" in operation_id:
            return anchors
    return []


def audit_amendment_locators(
    project_root: Path = PROJECT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    amendments_path: Path = DEFAULT_AMENDMENTS,
) -> dict:
    registry = Registry.model_validate(read_json(registry_path))
    amendment_map = AmendmentMap.model_validate(read_json(amendments_path))
    documents = {document.document_id: document for document in registry.documents}
    base_document = documents[amendment_map.base_document_id]
    amending_document = documents[amendment_map.amending_document_id]
    if not base_document.extraction or not amending_document.extraction:
        raise ValueError("Nguồn 168/238 phải có extraction")

    base_path = project_root / base_document.extraction.path
    amendment_path = project_root / amending_document.extraction.path
    base_text = base_path.read_text(encoding="utf-8", errors="strict")
    amendment_text = amendment_path.read_text(encoding="utf-8", errors="strict")
    locators = parse_base_locators(base_text)
    amendment_sections = {
        section["amendment_article"]: section["text"]
        for section in extract_amendment_sections(amendment_text, amendment_map)
    }

    operation_results = []
    for operation in amendment_map.operations:
        locator = (
            operation.target_article,
            operation.target_clause,
            operation.target_point,
        )
        target_exists = locator in locators
        if operation.operation == "add":
            parent = (
                (operation.target_article, operation.target_clause, None)
                if operation.target_point
                else (operation.target_article, None, None)
            )
            locator_check = not target_exists and parent in locators
            locator_expectation = "target_missing_parent_exists"
        else:
            locator_check = target_exists
            locator_expectation = "target_exists"

        source_marker = f"Điều {operation.target_article}"
        source_reference_check = source_marker in amendment_sections[operation.amendment_article]
        anchors = _anchors_for(operation.operation_id)
        anchor_results = []
        target_text = locators.get(locator, "")
        for anchor in anchors:
            anchor_results.append(
                {
                    "anchor": anchor,
                    "exact_match": anchor in target_text,
                    "normalized_match": normalize_for_match(anchor)
                    in normalize_for_match(target_text),
                }
            )
        anchors_passed = all(item["normalized_match"] for item in anchor_results)
        if operation.amendment_article == 19 and operation.operation != "repeal" and not anchors:
            anchors_passed = False

        passed = locator_check and source_reference_check and anchors_passed
        operation_results.append(
            {
                "operation_id": operation.operation_id,
                "operation": operation.operation,
                "amendment_article": operation.amendment_article,
                "target": {
                    "article": operation.target_article,
                    "clause": operation.target_clause,
                    "point": operation.target_point,
                },
                "locator_expectation": locator_expectation,
                "target_exists": target_exists,
                "locator_check_passed": locator_check,
                "source_reference_check_passed": source_reference_check,
                "anchors": anchor_results,
                "anchors_passed": anchors_passed,
                "passed": passed,
            }
        )

    supporting_docx_path = amending_document.extraction.supporting_input_path
    extracted_docx_matches = False
    if supporting_docx_path:
        regenerated = extract_document_text(project_root / supporting_docx_path)
        extracted_docx_matches = hashlib.sha256(regenerated.encode("utf-8")).hexdigest() == file_digest(
            amendment_path
        )

    failures = [result for result in operation_results if not result["passed"]]
    normalized_only = [
        {
            "operation_id": result["operation_id"],
            "anchor": anchor["anchor"],
        }
        for result in operation_results
        for anchor in result["anchors"]
        if anchor["normalized_match"] and not anchor["exact_match"]
    ]
    passed = not failures and extracted_docx_matches
    return {
        "schema_version": 1,
        "audit_id": "nd168-nd238-leaf-locator-audit-2026-09-22",
        "legal_as_of": registry.legal_as_of.isoformat(),
        "status": "passed" if passed else "failed",
        "scope": "Kiểm tra locator lá, source reference và phrase anchor; không phải legal review.",
        "inputs": {
            "base_text_path": display_path(base_path, project_root),
            "base_text_sha256": file_digest(base_path),
            "amendment_text_path": display_path(amendment_path, project_root),
            "amendment_text_sha256": file_digest(amendment_path),
            "amendment_map_path": display_path(amendments_path, project_root),
            "amendment_map_sha256": file_digest(amendments_path),
        },
        "summary": {
            "operation_count": len(operation_results),
            "passed_operations": len(operation_results) - len(failures),
            "failed_operations": len(failures),
            "target_article_count": len(
                {operation.target_article for operation in amendment_map.operations}
            ),
            "parsed_base_locator_count": len(locators),
            "docx_extraction_reproducible": extracted_docx_matches,
            "normalized_only_anchor_matches": normalized_only,
        },
        "failures": failures,
        "operations": operation_results,
        "legal_review_status": amendment_map.legal_review.status,
        "freeze_allowed": passed and amendment_map.legal_review.status == "approved",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit locator NĐ168 + NĐ238")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--amendments", type=Path, default=DEFAULT_AMENDMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit_amendment_locators(PROJECT_ROOT, args.registry, args.amendments)
    write_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("status", "summary", "freeze_allowed")}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
