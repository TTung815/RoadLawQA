"""Build/verify current-law candidate drafts without approving gold or running models.

This is a separate contract from Phase 0 historical recovery. It permits query
revisions and selected scoring subsets while retaining all original source rows.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
import gzip
import hashlib
import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import Field, model_validator

from evaluation.current_law_snapshot import (
    DEFAULT_RECEIPT, DEFAULT_SNAPSHOT_MANIFEST, verify_frozen_snapshot,
)
from evaluation.dataset import (
    historical_run, normalize_text, parse_citations, parse_historical_csv,
    question_key, regression_strings, QUERY_TYPES,
)
from evaluation.dataset_schema import (
    EvaluationCase, LabelModel, Text, require_scoring_gold,
)
from evaluation.snapshot import digest
from ingestion.current_law_corpus import CORPUS_ID, DEFAULT_OUTPUT, LEGAL_AS_OF
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json, write_json
from ingestion.shadow_index import (
    DEFAULT_OUTPUT_DIR, deterministic_uuid, verify_shadow_bundle,
    verify_shadow_records,
)


DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets/current_law_20260922"
DEFAULT_LABELS = DEFAULT_DIR / "draft_labels.json"
SOURCE = PROJECT_ROOT / "evaluation/datasets/historical_50/historical_candidates.csv"
SOURCE_MANIFEST = SOURCE.with_name("source_manifest.json")
PROTOCOL = PROJECT_ROOT / "docs/BENCHMARK_PROTOCOL.md"
PILOT_IDS = (1, 2, 5, 7, 9, 16, 23, 36, 43, 48)
DRAFT_ON = date(2026, 10, 9)
AUTHOR = "Codex — technical draft; independent legal review pending"
OUTPUT_NAMES = {
    "cases.jsonl", "evidence_catalog.json", "audit.json", "AUDIT.md", "PILOT.md",
    "case.schema.json",
}


class DraftFacet(LabelModel):
    kind: Literal[
        "rule", "definition", "money", "license_points", "additional_sanction",
        "condition", "exception", "reasoning", "temporal", "uncertainty",
    ]
    description: Text
    chunk_ids: list[Text] = Field(default_factory=list)
    role: Literal["support", "context"] = "support"
    support_state: Literal["positive_support", "unknown"] = "positive_support"

    @model_validator(mode="after")
    def supported_facets_need_evidence(self):
        if len(self.chunk_ids) != len(set(self.chunk_ids)):
            raise ValueError("duplicate facet chunk IDs")
        if self.support_state == "positive_support" and (
            not self.chunk_ids or self.role != "support"
        ):
            raise ValueError("positive support needs support references")
        return self


class DraftLabel(LabelModel):
    historical_id: int = Field(ge=1, le=50)
    action: Literal["keep", "edit", "drop"]
    query: Text
    rationale: Text
    query_type: Literal["factual", "penalty", "scenario"]
    type_revision_reason: str | None = None
    family_id: Text
    tags: list[Text] = Field(min_length=1)
    reference_answer: Text
    facets: list[DraftFacet] = Field(min_length=1)
    disposition: Literal["publish", "conditional", "abstain"]
    publication_rationale: Text
    expected_coverage: Literal["sufficient", "insufficient", "conditional"]
    temporal_basis: Literal["frozen_corpus", "explicit_date"] = "frozen_corpus"
    as_of_date: date | None = None
    external_evidence_needed: list[Text] = Field(default_factory=list)
    review_items: list[Text] = Field(min_length=1)


class CandidateRevision(LabelModel):
    action: Literal["keep", "edit", "drop"]
    original_query: Text
    rationale: Text
    type_revision_reason: str | None = None
    drafted_by: Text
    drafted_on: date


class CurrentLawCase(EvaluationCase):
    snapshot_id: Literal[CORPUS_ID] = CORPUS_ID
    legal_as_of: Literal[LEGAL_AS_OF] = LEGAL_AS_OF
    revision: CandidateRevision
    family_id: Text
    challenge_tags: list[Text] = Field(min_length=1)
    pilot: bool
    open_review_items: list[Text] = Field(default_factory=list)


def load_snapshot_context() -> tuple[dict, dict[str, dict]]:
    verify_frozen_snapshot()
    manifest = verify_shadow_bundle()
    snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
    for item in snapshot["processed_corpus"]["inputs"].values():
        if file_digest(PROJECT_ROOT / item["path"]) != item["sha256"]:
            raise ValueError("frozen source input changed")
    registry = read_json(PROJECT_ROOT / "data/legal_sources/registry.json")
    for document in registry["documents"]:
        if document["document_id"] not in {"49-vbhn-vpqh", "55-vbhn-vpqh", "168-2024-nd-cp", "238-2026-nd-cp"}:
            continue
        for artifact in (document["source"], document["extraction"]):
            path = artifact.get("raw_path", artifact.get("path"))
            if file_digest(PROJECT_ROOT / path) != artifact["sha256"]:
                raise ValueError("registered legal source artifact changed")
    corpus = read_json(DEFAULT_OUTPUT)
    with gzip.open(DEFAULT_OUTPUT_DIR / "indexed.json.gz", "rt", encoding="utf-8") as stream:
        records = json.load(stream)
    if not verify_shadow_records(corpus, records)["passed"]:
        raise ValueError("shadow replay membership does not match current-law corpus")
    fingerprint = {
        "objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])),
        "schema_sha256": digest(read_json(DEFAULT_OUTPUT_DIR / "schema.json")),
    }
    if fingerprint != snapshot["shadow_resources"]["collection_fingerprint"]:
        raise ValueError("shadow replay fingerprint differs from frozen snapshot")
    if fingerprint != manifest["collection_fingerprint"]:
        raise ValueError("shadow manifest fingerprint differs from replay")
    return snapshot, {chunk["id"]: chunk for chunk in corpus["chunks"]}


def evidence_reference(chunk: dict, role: str) -> dict:
    # Runtime ID is the stable shadow chunk_id, not a legacy serving adapter hash.
    return {
        "processed_id": chunk["id"], "runtime_id": chunk["id"],
        "uuid": deterministic_uuid(chunk["id"]),
        "citation": chunk["display_citation"], "law": chunk["law"],
        "article": chunk["article_no"], "clause": chunk["clause_no"],
        "point": chunk["point"],
        "text_sha256": hashlib.sha256(chunk["text"].encode()).hexdigest(),
        "role": role,
    }


def validate_case(case: CurrentLawCase, chunks: dict[str, dict], row: dict, record: int) -> None:
    original = normalize_text(row["Question"])
    if (
        case.source.raw_fields != row
        or case.source.csv_record != record
        or case.source.historical_id != row["STT"].strip()
        or case.source.sha256 != file_digest(SOURCE)
        or case.source.file != str(SOURCE.relative_to(PROJECT_ROOT))
        or case.id != f"current_law_{int(row['STT']):03d}"
        or case.revision.original_query != original
        or case.legacy_answer != normalize_text(row["Gold_answer"])
        or case.legacy_gold_citations_raw != (normalize_text(row.get("Gold_citations", "")) or None)
        or case.legacy_gold_citations != parse_citations(row.get("Gold_citations", ""))
        or (case.historical_run.model_dump() if case.historical_run else None) != historical_run(row)
        or case.split != "legacy" or case.exposure != "historically_used"
        or case.pilot != (int(row["STT"]) in PILOT_IDS)
    ):
        raise ValueError(f"historical provenance changed: {case.id}")
    if case.revision.action == "keep" and case.query != original:
        raise ValueError("keep case changed its query")
    if case.revision.action == "edit" and case.query == original:
        raise ValueError("edit case did not change its query")
    if case.query_type != QUERY_TYPES[normalize_text(row["Type"])]:
        if not case.revision.type_revision_reason:
            raise ValueError("query type revision lacks reason")
    if case.revision.action == "drop" and case.gold.review.status != "excluded":
        raise ValueError("drop case must be excluded")
    if case.revision.action != "drop" and case.gold.review.status == "excluded":
        raise ValueError("excluded case lacks drop decision")
    if case.gold.review.status == "approved" and case.open_review_items:
        raise ValueError("approved case retains unresolved review items")
    if case.gold.temporal_basis == "unresolved" or not case.gold.reference_answer:
        raise ValueError("draft gold lacks answer or temporal basis")
    groups = {group.id: group for group in case.gold.evidence_groups}
    for group in groups.values():
        for ref in group.references:
            if ref.processed_id not in chunks:
                raise ValueError("evidence absent from frozen corpus")
            chunk = chunks[ref.processed_id]
            if ref.model_dump() != evidence_reference(chunk, ref.role):
                raise ValueError("evidence reference changed")
            if ref.role == "support" and not chunk["publication_eligible"]:
                raise ValueError("blocked chunk used as support")
    for facet in case.gold.required_facets:
        if facet.support_state == "positive_support":
            if not facet.evidence_group_ids or not any(
                all(ref.role == "support" for ref in groups[group_id].references)
                for group_id in facet.evidence_group_ids
            ):
                raise ValueError("positive facet lacks support group")
    if case.gold.publication.disposition == "publish":
        if case.gold.expected_coverage != "sufficient" or case.gold.external_evidence_needed:
            raise ValueError("publish expectation lacks complete scope")
        if any(f.required and f.support_state != "positive_support" for f in case.gold.required_facets):
            raise ValueError("publish expectation has unsupported required facets")
        if {"missing_facts", "temporal_gap", "negative_conclusion"} & set(case.challenge_tags):
            raise ValueError("publish expectation bypasses a safety gate")
    if "answered" in case.gold.publication.allowed_statuses:
        if case.gold.publication.disposition != "publish":
            raise ValueError("conditional draft cannot authorize unsupported answered status")
    if (
        case.gold.temporal_basis == "explicit_date"
        and str(case.gold.as_of_date) != LEGAL_AS_OF
        and case.gold.publication.disposition != "abstain"
    ):
        raise ValueError("date outside snapshot cutoff needs temporal abstention in this dataset")
    if case.gold.publication.disposition == "abstain" and case.gold.expected_coverage != "insufficient":
        raise ValueError("abstain expectation must have insufficient coverage")


def make_case(label: DraftLabel, row: dict, record: int, chunks: dict[str, dict]) -> CurrentLawCase:
    groups, facets = [], []
    for number, facet in enumerate(label.facets, start=1):
        group_id = f"g{number}"
        if facet.chunk_ids:
            groups.append({
                "id": group_id, "description": facet.description, "match": "all",
                "references": [evidence_reference(chunks[identity], facet.role) for identity in facet.chunk_ids],
            })
        facets.append({
            "id": f"f{number}", "kind": facet.kind, "description": facet.description,
            "required": True, "support_state": facet.support_state,
            "evidence_group_ids": [group_id] if facet.chunk_ids else [],
        })
    case = CurrentLawCase.model_validate({
        "id": f"current_law_{label.historical_id:03d}",
        "split": "legacy", "exposure": "historically_used",
        "query_type": label.query_type, "query": label.query,
        "source": {
            "file": str(SOURCE.relative_to(PROJECT_ROOT)), "sha256": file_digest(SOURCE),
            "csv_record": record, "historical_id": row["STT"].strip(), "raw_fields": row,
        },
        "legacy_answer": normalize_text(row["Gold_answer"]),
        "legacy_gold_citations_raw": normalize_text(row.get("Gold_citations", "")) or None,
        "legacy_gold_citations": parse_citations(row.get("Gold_citations", "")),
        "historical_run": historical_run(row),
        "gold": {
            "review": {
                "status": "excluded" if label.action == "drop" else "needs_review",
                "notes": [label.rationale, "Draft written from snapshot evidence; no independent legal approval."],
            },
            "reference_answer": label.reference_answer,
            "temporal_basis": label.temporal_basis, "as_of_date": label.as_of_date,
            "evidence_groups": groups, "required_facets": facets,
            "expected_coverage": label.expected_coverage,
            "publication": {
                "disposition": label.disposition,
                "allowed_statuses": ["answered"] if label.disposition == "publish" else ["insufficient_evidence"],
                "rationale": label.publication_rationale,
            },
            "external_evidence_needed": label.external_evidence_needed,
            "failure_categories": ["expected_abstention"] if label.disposition == "abstain" else [],
        },
        "revision": {
            "action": label.action, "original_query": normalize_text(row["Question"]),
            "rationale": label.rationale, "type_revision_reason": label.type_revision_reason,
            "drafted_by": AUTHOR, "drafted_on": DRAFT_ON,
        },
        "family_id": label.family_id, "challenge_tags": label.tags,
        "pilot": label.historical_id in PILOT_IDS,
        "open_review_items": label.review_items,
    })
    validate_case(case, chunks, row, record)
    return case


def coverage_report(cases: Sequence[CurrentLawCase]) -> dict:
    retained = [case for case in cases if case.revision.action != "drop"]
    return {
        "count": len(cases),
        "decisions": dict(Counter(case.revision.action for case in cases)),
        "query_types": dict(Counter(case.query_type for case in retained)),
        "publication": dict(Counter(case.gold.publication.disposition for case in retained)),
        "tags": dict(sorted(Counter(tag for case in retained for tag in set(case.challenge_tags)).items())),
        "families": dict(sorted(Counter(case.family_id for case in retained).items())),
        "review_status": dict(Counter(case.gold.review.status for case in cases)),
    }


def require_current_law_scoring(cases: Sequence[CurrentLawCase], chunks: dict[str, dict]) -> None:
    """Selection need not have 50 cases; every selected case must be approved."""
    if any(case.revision.action == "drop" for case in cases):
        raise ValueError("excluded candidates cannot enter scoring")
    require_scoring_gold(list(cases))
    rows = parse_historical_csv(SOURCE.read_bytes())
    originals = {row["STT"].strip(): (record, row) for record, row in enumerate(rows, start=2)}
    for case in cases:
        record, row = originals[case.source.historical_id]
        validate_case(case, chunks, row, record)


def render_case(case: CurrentLawCase, chunks: dict[str, dict]) -> list[str]:
    lines = [
        f"## Câu {int(case.source.historical_id):02d} — {case.revision.action}", "",
        f"- Gốc: {case.revision.original_query}",
        f"- Query audit: {case.query}", f"- Lý do: {case.revision.rationale}",
        f"- Loại/family: {case.query_type} / {case.family_id}",
        f"- Tags: {', '.join(case.challenge_tags)}",
        f"- Expectation: {case.gold.publication.disposition}; coverage={case.gold.expected_coverage}; "
        f"allowed={','.join(case.gold.publication.allowed_statuses)}",
        f"- Temporal: {case.gold.temporal_basis}; cutoff={case.legal_as_of}; explicit_date={case.gold.as_of_date}",
        f"- Review: {case.gold.review.status}; drafted={case.revision.drafted_on}; author={AUTHOR}",
        "", "Đáp án tham chiếu **draft**:", "", case.gold.reference_answer or "", "",
        "Required facets:", "",
    ]
    for facet in case.gold.required_facets:
        lines.append(f"- {facet.id} [{facet.kind}/{facet.support_state}]: {facet.description} "
                     f"(groups: {','.join(facet.evidence_group_ids) or 'none'})")
    lines.extend(["", "Evidence (nội dung/context đầy đủ ở evidence_catalog.json):", ""])
    for group in case.gold.evidence_groups:
        for ref in group.references:
            chunk = chunks[ref.processed_id]
            lines.append(f"- {group.id}/{ref.role}: `{ref.processed_id}` — {ref.citation}; "
                         f"eligible={chunk['publication_eligible']}; operations={','.join(chunk['operation_ids']) or 'none'}")
    if case.gold.external_evidence_needed:
        lines.extend(["", "Dependency chưa có:", "", *[f"- {x}" for x in case.gold.external_evidence_needed]])
    lines.extend(["", "Điểm reviewer cần chốt:", "", *[f"- {x}" for x in case.open_review_items], ""])
    return lines


def make_artifacts(labels_path: Path = DEFAULT_LABELS) -> dict[str, object]:
    snapshot, chunks = load_snapshot_context()
    source_manifest = read_json(SOURCE_MANIFEST)
    if file_digest(SOURCE) != source_manifest["sha256"]:
        raise ValueError("historical source CSV changed")
    rows = parse_historical_csv(SOURCE.read_bytes())
    labels = [DraftLabel.model_validate(value) for value in read_json(labels_path)]
    by_id = {label.historical_id: label for label in labels}
    if len(labels) != 50 or set(by_id) != set(range(1, 51)):
        raise ValueError("candidate decisions must cover 1..50 exactly once")
    # Validate pilot first; only then expand the same schema/gates to all candidates.
    indexed_rows = {int(row["STT"]): (record, row) for record, row in enumerate(rows, start=2)}
    pilot = [
        make_case(by_id[identity], indexed_rows[identity][1], indexed_rows[identity][0], chunks)
        for identity in PILOT_IDS
    ]
    cases = [make_case(by_id[int(row["STT"])], row, record, chunks) for record, row in enumerate(rows, start=2)]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("duplicate case IDs")
    query_keys = [question_key(case.query) for case in cases if case.revision.action != "drop"]
    if len(set(query_keys)) != len(query_keys):
        raise ValueError("duplicate retained queries")
    used = sorted({ref.processed_id for case in cases for group in case.gold.evidence_groups for ref in group.references})
    catalog = {
        "snapshot_id": CORPUS_ID,
        "runtime_id_basis": "stable shadow chunk_id; not legacy serving adapter hash",
        "chunks": [chunks[identity] for identity in used],
        "context_hashes": {identity: digest({key: chunks[identity][key] for key in (
            "text", "clause_head", "enriched_text", "source_spans", "temporal_status", "publication_eligible",
        )}) for identity in used},
    }
    overlap = []
    strings = regression_strings(PROJECT_ROOT)
    for case in cases:
        key = question_key(case.query)
        hits = []
        for path, text in strings:
            if min(len(key), len(text)) / max(len(key), len(text)) < .65:
                continue
            similarity = SequenceMatcher(None, key, text, autojunk=False).ratio()
            if similarity >= .72:
                hits.append({"file": path, "similarity": round(similarity, 4)})
        if hits:
            overlap.append({"case_id": case.id, "matches": sorted(hits, key=lambda hit: -hit["similarity"])[:3]})
    selected = [case for case in cases if case.revision.action != "drop" and case.gold.review.status == "approved"]
    scoring_ready = False
    if selected:
        require_current_law_scoring(selected, chunks)
        scoring_ready = True
    report = {
        "schema_version": 1, "snapshot_id": CORPUS_ID, "legal_as_of": LEGAL_AS_OF,
        "drafted_on": str(DRAFT_ON), "drafted_by": AUTHOR,
        "technical_integrity_passed": True, "official_scoring_ready": scoring_ready,
        "approved_selected_ids": [case.id for case in selected],
        "coverage": coverage_report(cases), "pilot": coverage_report(pilot),
        "pilot_ids": list(PILOT_IDS), "evidence_chunk_count": len(used),
        "pilot_schema_provenance_passed": True, "pilot_semantic_approval": False,
        "model_runs": 0, "production_writes": 0, "held_out_created": False,
        "regression_overlap_candidates": overlap,
        "regression_overlap_method": "normalized SequenceMatcher >=0.72; manual semantic review required",
        "coverage_gaps": [
            "No unseen held-out cases; revised historical questions remain exposed.",
            "No multi-turn cases or complete temporal boundary suite for 2028/2029.",
            "No independent legal gold review; pilot only checks schema/provenance.",
            "Missing dependencies and negative-support provenance intentionally remain blocked.",
        ],
    }
    header = [
        "# Audit 50 historical candidates — current-law draft", "",
        f"Cutoff: {LEGAL_AS_OF}. Audit date: {DRAFT_ON}. Snapshot: `{CORPUS_ID}`.", "",
        "Technical integrity đạt; **0 gold được phê duyệt**. Chưa chạy model/C0–C4.",
        "CSV gốc giữ nguyên. Tất cả query dẫn xuất vẫn historically_used/legacy.", "",
        "| Chỉ số | Kết quả |", "| --- | --- |",
        f"| Candidate audited | {len(cases)} |",
        f"| Giữ / sửa / loại | {report['coverage']['decisions'].get('keep', 0)} / "
        f"{report['coverage']['decisions'].get('edit', 0)} / {report['coverage']['decisions'].get('drop', 0)} |",
        f"| Publish / conditional / abstain (draft) | {report['coverage']['publication'].get('publish', 0)} / "
        f"{report['coverage']['publication'].get('conditional', 0)} / {report['coverage']['publication'].get('abstain', 0)} |",
        f"| Gold approved | {len(selected)} |",
        f"| Evidence chunks | {len(used)} |", "",
        "## Bảng quyết định", "",
        "| ID | Decision | Type | Expectation | Family | Pilot |", "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        header.append(f"| {int(case.source.historical_id):02d} | {case.revision.action} | {case.query_type} | "
                      f"{case.gold.publication.disposition} | {case.family_id} | {'yes' if case.pilot else ''} |")
    header.extend(["", "Gap/giới hạn:", "", *[f"- {x}" for x in report["coverage_gaps"]], ""])
    header.extend(["## Ma trận coverage thực tế", "", "| Tag | Số case |", "| --- | --- |"])
    header.extend(f"| {tag} | {count} |" for tag, count in report["coverage"]["tags"].items())
    header.append("")
    for case in cases:
        header.extend(render_case(case, chunks))
    pilot_lines = [
        "# Pilot protocol — 10 candidate", "",
        "Pilot chạy trước full build, cùng schema và snapshot evidence gate.",
        "Kết quả: schema/provenance đạt; chưa independent legal approval, chưa chạy model.", "",
        "Findings đã áp dụng vào protocol/full audit:", "",
        "- Câu 1 bỏ số hiệu khỏi query tự nhiên; số hiệu nằm trong evidence.",
        "- Câu 2 giữ definition; không ép tất cả query thành scenario.",
        "- Câu 5 tiền và điểm cần hai leaf, hai facet riêng.",
        "- Câu 7 thêm rõ xe gia đình; giữ quy tắc/ngoại lệ và amendment provenance.",
        "- Câu 9 giữ ngày 2025; cutoff snapshot không chứng minh lịch sử, expected abstain.",
        "- Câu 16 giữ thiếu dữ kiện có chủ đích để kiểm tra conditional/exception.",
        "- Câu 23 có căn cứ từng hành vi và nguyên tắc trừ điểm, nhưng tổng hợp tiền cần dependency.",
        "- Câu 36 đóng hai đầu khoảng số; mức tiền không tự chứng minh mức điểm.",
        "- Câu 43 tuổi lái xe và tuổi chịu xử phạt khác nhau; không suy mức tiền từ nguồn tuổi lái xe.",
        "- Câu 48 thiếu tình trạng phanh/lái và cảnh báo; phải nêu điều kiện, không khẳng định hợp pháp.",
        "- Leaf context có mức tiền/giới hạn số người; lưu full enriched context và hash để review.", "",
    ]
    for case in pilot:
        pilot_lines.extend(render_case(case, chunks))
    artifacts: dict[str, object] = {
        "cases.jsonl": "".join(case.model_dump_json() + "\n" for case in cases),
        "evidence_catalog.json": catalog, "audit.json": report,
        "AUDIT.md": "\n".join(header) + "\n", "PILOT.md": "\n".join(pilot_lines) + "\n",
        "case.schema.json": CurrentLawCase.model_json_schema(),
    }
    hashes = {name: hashlib.sha256(artifact_bytes(value)).hexdigest() for name, value in artifacts.items()}
    hashes["draft_labels.json"] = file_digest(labels_path)
    artifacts["manifest.json"] = {
        "format_version": 1, "dataset_id": "current_law_20260922_candidates_v1",
        "status": "draft_needs_independent_review", "legal_as_of": LEGAL_AS_OF,
        "source": {"path": str(SOURCE.relative_to(PROJECT_ROOT)), "sha256": file_digest(SOURCE),
                   "source_manifest_sha256": file_digest(SOURCE_MANIFEST)},
        "snapshot": {"id": CORPUS_ID, "manifest_sha256": file_digest(DEFAULT_SNAPSHOT_MANIFEST),
                     "receipt_sha256": file_digest(DEFAULT_RECEIPT),
                     "collection_fingerprint": snapshot["shadow_resources"]["collection_fingerprint"]},
        "protocol": {"path": str(PROTOCOL.relative_to(PROJECT_ROOT)), "sha256": file_digest(PROTOCOL)},
        "builder": {"path": str(Path(__file__).relative_to(PROJECT_ROOT)), "sha256": file_digest(Path(__file__))},
        "schema_sha256": file_digest(PROJECT_ROOT / "evaluation/dataset_schema.py"),
        "artifacts": hashes, "official_scoring_ready": scoring_ready,
        "benchmark_or_c0_c4_run": False, "production_index_changed": False,
    }
    return artifacts


def artifact_bytes(value: object) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_bundle(directory: Path = DEFAULT_DIR, labels: Path = DEFAULT_LABELS) -> dict:
    artifacts = make_artifacts(labels)
    if any((directory / name).exists() for name in artifacts):
        raise FileExistsError("dataset artifacts exist; verify or create a new version")
    directory.mkdir(parents=True, exist_ok=True)
    if labels.resolve() != (directory / "draft_labels.json").resolve():
        target = directory / "draft_labels.json"
        if target.exists():
            raise FileExistsError("output already has draft labels")
        target.write_bytes(labels.read_bytes())
    for name, value in artifacts.items():
        (directory / name).write_bytes(artifact_bytes(value))
    return artifacts["audit.json"]


def verify_bundle(directory: Path = DEFAULT_DIR) -> dict:
    expected = make_artifacts(directory / "draft_labels.json")
    for name, value in expected.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != artifact_bytes(value):
            raise ValueError(f"current-law dataset artifact changed: {name}")
    cases = [CurrentLawCase.model_validate_json(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
    if len(cases) != 50:
        raise ValueError("missing candidate decision")
    return expected["audit.json"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    args = parser.parse_args(argv)
    report = build_bundle(args.directory, args.labels) if args.action == "build" else verify_bundle(args.directory)
    print(json.dumps({key: report[key] for key in (
        "technical_integrity_passed", "official_scoring_ready", "coverage", "pilot_ids",
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
