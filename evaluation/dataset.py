"""Recover the historical CSV and audit draft labels against a frozen corpus.

No provider, tokenizer, retrieval, live database or spreadsheet authoring required.
Run: python -m evaluation.dataset recover --source <csv> --snapshot <bundle> --output <new-dir>
Run: python -m evaluation.dataset audit --dataset <dir> --snapshot <bundle>
"""

import argparse
import ast
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata

from evaluation.dataset_schema import EvaluationCase, FAILURE_CATEGORIES
from evaluation.snapshot import PROJECT_ROOT, file_digest, read_json, require_trusted_snapshot, write_json


HEADERS = ["STT", "Type", "Question", "Gold_answer"]
FULL_HEADERS = ["STT", "Type", "Question", "Gold_answer", "Gold_citations", "Model_answer",
                "Model_citations", "retriever_sources", "", "Legal_accuracy", "Legal_citation",
                "Relevance", "Total Score", "", "", "TỔNG KẾT", "TYPE", "SỐ CÂU HỎI",
                "LEGAL ACCURACY", "LEGAL CITATION", "RELEVANCE", "SCORES"]
RUN_FIELDS = ("Gold_citations", "Model_answer", "Model_citations", "retriever_sources",
              "Legal_accuracy", "Legal_citation", "Relevance", "Total Score")
QUERY_TYPES = {"tra cứu sự thật": "factual", "tra cứu chế tài": "penalty", "tình huống/suy luận": "scenario"}


def normalize_text(text: str) -> str:
    # CSV contains both actual newlines and literal escaped export newlines.
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def question_key(text: str) -> str:
    return " ".join(normalize_text(text).casefold().split())


def parse_historical_csv(payload: bytes) -> list[dict[str, str]]:
    records = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True))
    if not records:
        raise ValueError("Historical CSV is empty")
    header, values = records[0], records[1:]
    if header not in (HEADERS, FULL_HEADERS):
        raise ValueError("Expected the reduced 4-column or complete 22-column historical sheet")
    if any(len(row) != len(header) for row in values):
        raise ValueError("Historical CSV row width differs from its header")
    fields = HEADERS if header == HEADERS else [*HEADERS, *RUN_FIELDS]
    positions = list(range(4)) if header == HEADERS else [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]
    rows = [{field: row[position] for field, position in zip(fields, positions)} for row in values]
    if len(rows) != 50:
        raise ValueError(f"Historical recovery requires exactly 50 records, found {len(rows)}")
    ids = []
    for row in rows:
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in HEADERS):
            raise ValueError("CSV has a missing or empty core cell")
        required_history = ("Gold_citations", "Model_answer", "retriever_sources",
                            "Legal_accuracy", "Legal_citation", "Relevance", "Total Score")
        if header == FULL_HEADERS and any(not row[key].strip() for key in required_history):
            raise ValueError("Complete historical sheet has a missing required history cell")
        identity = row["STT"].strip()
        if not identity.isascii() or not identity.isdigit() or str(int(identity)) != identity:
            raise ValueError("Historical IDs must be canonical integers")
        ids.append(int(identity))
        if normalize_text(row["Type"]) not in QUERY_TYPES:
            raise ValueError(f"Unknown historical question type: {row['Type']}")
    if sorted(ids) != list(range(1, 51)):
        raise ValueError("Historical IDs must contain 1..50 exactly once")
    return rows


def parse_citations(raw: str) -> list[str]:
    citations = []
    for line in normalize_text(raw).splitlines():
        value = re.sub(r"^\s*-\s*", "", line).strip()
        value = value.strip("[]").strip().strip('"').strip()
        if value:
            citations.append(value)
    return citations


def parse_score(value: str) -> float:
    return float(value.strip().replace(",", "."))


def historical_run(row: dict[str, str]):
    if "Model_answer" not in row:
        return None
    return {"model_answer": normalize_text(row["Model_answer"]),
            "model_citations_raw": normalize_text(row["Model_citations"]) or None,
            "retriever_sources_raw": normalize_text(row["retriever_sources"]),
            "legal_accuracy": parse_score(row["Legal_accuracy"]),
            "legal_citation": parse_score(row["Legal_citation"]),
            "relevance": parse_score(row["Relevance"]),
            "total_score": parse_score(row["Total Score"])}


def frozen_index(snapshot: Path) -> tuple[dict, dict]:
    processed = {row["processed_id"]: row for row in read_json(snapshot / "processed.json")}
    mapping = {}
    for row in read_json(snapshot / "id_mapping.json"):
        if row["processed_id"] in mapping:
            raise ValueError("Ambiguous processed-to-runtime evidence mapping")
        mapping[row["processed_id"]] = row
    return processed, mapping


def evidence_reference(identity: str, processed: dict, mapping: dict, role="support") -> dict:
    if identity not in processed or identity not in mapping:
        raise ValueError(f"Draft evidence is absent from frozen snapshot: {identity}")
    props = processed[identity]["properties"]
    linked = mapping[identity]
    return {"processed_id": identity, "runtime_id": linked["runtime_id"], "uuid": linked["uuid"],
            "citation": linked["citation"], "law": props["law"], "article": props["article_no"],
            "clause": props["clause_no"], "point": props["point"],
            "text_sha256": hashlib.sha256(props["text"].encode()).hexdigest(), "role": role}


def recover_cases(rows: list[dict], source: str, checksum: str, snapshot: Path, labels: list[dict],
                  audits: list[dict] | None = None) -> list[EvaluationCase]:
    by_id = {str(label["historical_id"]): label for label in labels}
    if len(labels) != 50 or set(by_id) != {str(i) for i in range(1, 51)}:
        raise ValueError("Draft labels must cover 1..50 exactly once")
    audit_by_id = {str(item["historical_id"]): item for item in (audits or [])}
    if audits is not None and (len(audits) != 50 or set(audit_by_id) != {str(i) for i in range(1, 51)}):
        raise ValueError("Technical audit must cover 1..50 exactly once")
    processed, mapping = frozen_index(snapshot)
    cases = []
    for record, row in enumerate(rows, start=2):
        identity = row["STT"].strip()
        label = by_id[identity]
        technical_audit = audit_by_id.get(identity)
        if technical_audit is not None:
            technical_audit = {key: value for key, value in technical_audit.items() if key != "historical_id"}
        groups = []
        for group in label["evidence_groups"]:
            groups.append({"id": group["id"], "description": group["description"], "match": group.get("match", "all"),
                           "references": [evidence_reference(ref, processed, mapping, group.get("role", "support"))
                                          for ref in group["processed_ids"]]})
        flags = list(label.get("audit_flags", []))
        if any(normalize_text(row[key]) != row[key] for key in ("Question", "Gold_answer")):
            flags.append("export_text_normalized")
        citation_text = row.get("Gold_citations", row["Gold_answer"])
        if not re.search(r"điều\s+\d+", citation_text, re.IGNORECASE):
            flags.append("legacy_citation_missing")
        case = EvaluationCase.model_validate({
            "id": f"legacy_{int(identity):03d}", "split": "legacy", "exposure": "historically_used",
            "query_type": QUERY_TYPES[normalize_text(row["Type"])], "query": normalize_text(row["Question"]),
            "source": {"file": source, "sha256": checksum, "csv_record": record, "historical_id": identity,
                       "raw_fields": row}, "legacy_answer": normalize_text(row["Gold_answer"]),
            "legacy_gold_citations_raw": normalize_text(row["Gold_citations"]) if "Gold_citations" in row else None,
            "legacy_gold_citations": parse_citations(row["Gold_citations"]) if "Gold_citations" in row else [],
            "historical_run": historical_run(row),
            "gold": {"review": {"status": "needs_review", "notes": label.get("review_notes", [])},
                     "reference_answer": label.get("reference_answer"), "temporal_basis": "unresolved",
                     "evidence_groups": groups, "required_facets": label["required_facets"],
                     "publication": label.get("publication", {"disposition": "unassigned", "allowed_statuses": [],
                         "rationale": "Chưa duyệt nhãn công bố/từ chối theo corpus đóng băng và chính sách V2."}),
                     "external_evidence_needed": label.get("external_evidence_needed", []),
                     "failure_categories": label.get("failure_categories", []),
                     "technical_audit": technical_audit},
            "audit_flags": flags})
        cases.append(case)
    return cases


def regression_strings(root: Path) -> list[tuple[str, str]]:
    """Overlap candidates only: string similarity is not proof of semantic leakage."""
    strings = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and 25 <= len(node.value) <= 1500:
                strings.append((str(path.relative_to(root)), question_key(node.value)))
    return strings


def legal_locator(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    normalized = unicodedata.normalize("NFC", text).casefold()
    law = ("ND168-2024" if "168/2024" in normalized else
           "L36-2024-QH15" if "36/2024" in normalized or "trật tự, an toàn" in normalized else
           "L35-2024-QH15" if "35/2024" in normalized or "luật đường bộ" in normalized else None)
    # Parenthetical prose may itself mention a point and must not alter the locator.
    citation = normalized.split("(", 1)[0]
    def value(pattern):
        match = re.search(pattern, citation)
        return match.group(1) if match else None
    return law, value(r"điều\s*([0-9]+)"), value(r"khoản\s*([0-9]+)"), value(r"điểm\s*([a-zđ])")


def reference_locator(ref) -> tuple[str | None, str | None, str | None, str | None]:
    law = ("ND168-2024" if "168/2024" in ref.law else
           "L36-2024-QH15" if "36/2024" in ref.law else
           "L35-2024-QH15" if "35/2024" in ref.law else None)
    return law, ref.article, ref.clause, ref.point


def locator_covers(reference, citation) -> bool:
    return all(wanted is None or str(actual).casefold() == str(wanted).casefold()
               for actual, wanted in zip(reference, citation))


def audit_cases(cases: list[EvaluationCase], snapshot: Path, root: Path = PROJECT_ROOT) -> dict:
    processed, mapping = frozen_index(snapshot)
    issues = []
    ids = Counter(case.id for case in cases)
    queries = defaultdict(list)
    corpus_references = 0
    for case in cases:
        queries[question_key(case.query)].append(case.id)
        for group in case.gold.evidence_groups:
            for ref in group.references:
                expected = evidence_reference(ref.processed_id, processed, mapping, ref.role)
                if ref.model_dump() != expected:
                    issues.append({"case_id": case.id, "category": "evidence_reference_changed", "processed_id": ref.processed_id})
                corpus_references += 1
    duplicate_queries = [values for values in queries.values() if len(values) > 1]
    duplicate_ids = [key for key, count in ids.items() if count > 1]
    candidates = []
    strings = regression_strings(root)
    for case in cases:
        key = question_key(case.query)
        hits = []
        for file, text in strings:
            if min(len(key), len(text)) / max(len(key), len(text)) < .65:
                continue
            score = SequenceMatcher(None, key, text, autojunk=False).ratio()
            if score >= .72:
                hits.append({"file": file, "similarity": round(score, 4), "text": text})
        if hits:
            unique = {(hit["file"], hit["text"]): hit for hit in hits}
            candidates.append({"case_id": case.id, "matches": sorted(unique.values(), key=lambda hit: -hit["similarity"])[:3]})
    flags = defaultdict(list)
    for case in cases:
        for flag in case.audit_flags:
            flags[flag].append(case.id)
    pending = [case.id for case in cases if case.gold.review.status == "needs_review"]
    approved = [case.id for case in cases if case.gold.review.status == "approved"]
    citation_cases = sum(bool(case.legacy_gold_citations) for case in cases)
    citation_count = sum(len(case.legacy_gold_citations) for case in cases)
    observed_runs = sum(case.historical_run is not None for case in cases)
    technical_status = Counter(case.gold.technical_audit.status for case in cases if case.gold.technical_audit)
    unmapped_citations = []
    for case in cases:
        references = [reference_locator(ref) for group in case.gold.evidence_groups for ref in group.references]
        for citation in case.legacy_gold_citations:
            locator = legal_locator(citation)
            if None in locator[:2] or not any(locator_covers(ref, locator) for ref in references):
                unmapped_citations.append({"case_id": case.id, "citation": citation, "locator": locator})
    return {"schema_version": 1, "cases": len(cases), "query_types": dict(Counter(c.query_type for c in cases)),
            "splits": dict(Counter(c.split for c in cases)), "review_status": dict(Counter(c.gold.review.status for c in cases)),
            "duplicate_ids": duplicate_ids, "duplicate_queries": duplicate_queries,
            "evidence_reference_occurrences": corpus_references, "evidence_reference_issues": issues,
            "audit_flags": dict(sorted(flags.items())), "regression_overlap_candidates": candidates,
            "historical_gold_citation_cases": citation_cases,
            "historical_gold_citation_count": citation_count,
            "historical_gold_citations_unmapped": unmapped_citations,
            "historical_run_records": observed_runs,
            "technical_audit_status": dict(technical_status),
            "technical_audit_cases": sum(technical_status.values()),
            "regression_overlap_method": "NFC/case/whitespace normalization; exact/SequenceMatcher >=0.72; candidates need manual semantic review",
            "pending_gold_ids": pending, "approved_gold_ids": approved,
            "dataset_integrity_passed": len(cases) == 50 and not (duplicate_ids or duplicate_queries or issues),
            "official_scoring_ready": len(cases) == 50 and len(approved) == 50 and citation_cases == 50 and not (duplicate_ids or duplicate_queries or issues or unmapped_citations),
            "scope": "Frozen corpus only; no assertion that historical answers reflect current amended law.",
            "failure_categories": list(FAILURE_CATEGORIES)}


def load_cases(path: Path) -> list[EvaluationCase]:
    return [EvaluationCase.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_bundle(directory: Path, snapshot: Path, root: Path = PROJECT_ROOT) -> dict:
    frozen = require_trusted_snapshot(snapshot, root)
    manifest = read_json(directory / "manifest.json")
    if manifest.get("format_version") != 1 or not str(manifest.get("dataset_id", "")).startswith("historical_50_"):
        raise ValueError("Unsupported historical dataset manifest")
    if manifest["snapshot_manifest_sha256"] != file_digest(snapshot / "manifest.json"):
        raise ValueError("Dataset points to a different baseline snapshot")
    base_artifacts = {"source.csv", "cases.jsonl", "case.schema.json", "draft_labels.json", "audit.json", "AUDIT.md"}
    optional_artifacts = {"technical_audit.json"}
    for name, checksum in manifest["artifacts"].items():
        if name not in base_artifacts | optional_artifacts:
            raise ValueError("Unknown dataset artifact")
        if file_digest(directory / name) != checksum:
            raise ValueError(f"Dataset artifact changed: {name}")
    if set(manifest["artifacts"]) not in (base_artifacts, base_artifacts | optional_artifacts):
        raise ValueError("Incomplete dataset inventory")
    if manifest["collection_fingerprint"] != frozen["collection_fingerprint"]:
        raise ValueError("Dataset corpus fingerprint changed")
    cases = load_cases(directory / "cases.jsonl")
    rows = parse_historical_csv((directory / "source.csv").read_bytes())
    if manifest["source_sha256"] != file_digest(directory / "source.csv"):
        raise ValueError("Historical source checksum changed")
    originals = {row["STT"].strip(): (record, row) for record, row in enumerate(rows, start=2)}
    for case in cases:
        record, row = originals[case.source.historical_id]
        if (case.source.raw_fields != row or case.source.csv_record != record or
                case.source.sha256 != file_digest(directory / "source.csv") or
                case.query != normalize_text(row["Question"]) or case.legacy_answer != normalize_text(row["Gold_answer"]) or
                case.legacy_gold_citations != (parse_citations(row["Gold_citations"]) if "Gold_citations" in row else []) or
                case.historical_run != EvaluationCase.model_validate({**case.model_dump(), "historical_run": historical_run(row)}).historical_run or
                case.id != f"legacy_{int(case.source.historical_id):03d}" or case.split != "legacy" or
                case.exposure != "historically_used" or case.query_type != QUERY_TYPES[normalize_text(row["Type"])]):
            raise ValueError("Recovered case no longer matches its historical source row")
    report = audit_cases(cases, snapshot, root)
    if not report["dataset_integrity_passed"]:
        raise ValueError("Recovered dataset failed integrity audit")
    return report


def render_audit(cases: list[EvaluationCase], report: dict, labels: list[dict]) -> str:
    lines = [
        "# Audit kỹ thuật 50 câu lịch sử",
        "",
        "Báo cáo này chỉ kiểm tra tính toàn vẹn import. Answer và citation cũ không",
        "phải gold hiện hành và sẽ được làm lại sau khi current-law snapshot được freeze.",
        "",
        "## Kết quả",
        "",
        f"- Số câu: {report['cases']}.",
        f"- Phân bố: {report['query_types']}.",
        f"- Trùng ID/câu hỏi: {len(report['duplicate_ids'])}/{len(report['duplicate_queries'])}.",
        f"- Lỗi evidence reference: {len(report['evidence_reference_issues'])}.",
        f"- Gold sẵn sàng chấm: {'có' if report['official_scoring_ready'] else 'không'}.",
        "",
        "## Việc tiếp theo",
        "",
        "Sau khi Pha 1 hoàn tất, duyệt lại từng câu theo luật hiện hành: giữ, sửa",
        "hoặc loại; sau đó viết lại answer, citation, facets và publication label.",
        "",
    ]
    findings = []
    for label in labels:
        for finding in label.get("findings", []):
            findings.append(
                f"- Câu {int(label['historical_id']):02d}: "
                f"{finding['description'].replace('|', '/')}"
            )
    if findings:
        lines.extend(["## Ghi chú import cần nhớ", "", *findings, ""])
    return "\n".join(lines) + "\n"


def recover(source: Path, snapshot: Path, output: Path, labels_path: Path | None = None, root: Path = PROJECT_ROOT,
            dataset_id: str = "historical_50_candidates", source_url: str | None = None,
            technical_audit_path: Path | None = None) -> dict:
    if labels_path is None:
        raise ValueError("Phải truyền --labels; không tự dùng ground truth lịch sử")
    frozen = require_trusted_snapshot(snapshot, root)
    payload = source.read_bytes()
    rows = parse_historical_csv(payload)
    labels = read_json(labels_path)
    audits = read_json(technical_audit_path) if technical_audit_path else None
    cases = recover_cases(rows, source.name, hashlib.sha256(payload).hexdigest(), snapshot, labels, audits)
    report = audit_cases(cases, snapshot, root)
    if not report["dataset_integrity_passed"]:
        raise ValueError("Historical recovery failed dataset integrity audit")
    # All inputs are checked before writing. Never overwrite an existing dataset.
    output.mkdir(parents=True, exist_ok=False)
    (output / "source.csv").write_bytes(payload)
    (output / "draft_labels.json").write_bytes(labels_path.read_bytes())
    if technical_audit_path:
        (output / "technical_audit.json").write_bytes(technical_audit_path.read_bytes())
    (output / "cases.jsonl").write_text("".join(case.model_dump_json() + "\n" for case in cases), encoding="utf-8")
    write_json(output / "case.schema.json", EvaluationCase.model_json_schema())
    write_json(output / "audit.json", report)
    (output / "AUDIT.md").write_text(render_audit(cases, report, labels), encoding="utf-8")
    manifest = {"format_version": 1, "dataset_id": dataset_id, "source_original_name": source.name,
                "source_url": source_url,
                "source_sha256": hashlib.sha256(payload).hexdigest(), "snapshot_manifest_sha256": file_digest(snapshot / "manifest.json"),
                "collection_fingerprint": frozen["collection_fingerprint"], "recovery_module_sha256": file_digest(Path(__file__)),
                "schema_module_sha256": file_digest(Path(__file__).with_name("dataset_schema.py")),
                "source_claim": "Owner-supplied historical benchmark; 50 rows and 15/15/20 distribution agree with README. Original relevance/run logs not recovered.",
                "historical_metrics_reproduced": False, "artifacts": {path.name: file_digest(path) for path in sorted(output.iterdir())}}
    write_json(output / "manifest.json", manifest)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    recovery = actions.add_parser("recover")
    recovery.add_argument("--source", type=Path, required=True)
    recovery.add_argument("--snapshot", type=Path, required=True)
    recovery.add_argument("--output", type=Path, required=True)
    recovery.add_argument("--labels", type=Path, required=True)
    recovery.add_argument("--dataset-id", default="historical_50_candidates")
    recovery.add_argument("--source-url")
    recovery.add_argument("--technical-audit", type=Path)
    audit = actions.add_parser("audit")
    audit.add_argument("--dataset", type=Path, required=True)
    audit.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    report = (recover(args.source, args.snapshot, args.output, args.labels, dataset_id=args.dataset_id,
                      source_url=args.source_url, technical_audit_path=args.technical_audit) if args.action == "recover"
              else audit_bundle(args.dataset, args.snapshot))
    print(json.dumps({key: report[key] for key in ("cases", "query_types", "dataset_integrity_passed", "official_scoring_ready")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
