"""Create-only owner-reviewed gold versions; no ingestion, models or index writes."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import Field, model_validator

from evaluation import current_law_dataset as draft
from evaluation.dataset_schema import LabelModel, SHA256, Text, require_scoring_gold
from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json


DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets/current_law_20260922_reviewed_v1"
PROTOCOL = PROJECT_ROOT / "docs/BENCHMARK_PROTOCOL_REVIEWED_V1.md"
DATASET_ID = "current_law_20260922_reviewed_v1"
RECEIPT = "freeze_receipt.json"
INPUT_FILES = ("review_feedback.txt", "review_authorization.md", "review_decisions.json", "source_recovery.json")
ALLOWED_UPDATES = {
    "query", "revision.rationale", "challenge_tags", "gold.reference_answer",
    "gold.required_facets", "gold.evidence_groups", "gold.expected_coverage",
    "gold.publication", "gold.temporal_basis", "gold.as_of_date", "gold.failure_categories",
}


class TemporalRule(LabelModel):
    chunk_id: Text
    text_sha256: SHA256
    context_sha256: SHA256
    base_document_id: Text
    base_url: Text
    base_locator: Text
    base_pdf_page: int = Field(ge=1)
    base_rule_text: Text
    findings: list[Text] = Field(min_length=1)


class TemporalReview(LabelModel):
    status: Literal["approved"]
    reviewer: Text
    reviewed_on: date
    valid_from: date
    verified_through: date
    result_date: date
    rules: list[TemporalRule] = Field(min_length=1)

    @model_validator(mode="after")
    def interval_order(self):
        if not self.valid_from <= self.result_date <= self.verified_through:
            raise ValueError("result date outside reviewed temporal interval")
        if len({rule.chunk_id for rule in self.rules}) != len(self.rules):
            raise ValueError("duplicate temporal rule")
        return self


class Decision(LabelModel):
    historical_id: int = Field(ge=1, le=50)
    status: Literal["approved"]
    basis: Literal["explicit_feedback", "feedback_and_followup", "followup_resolution"]
    notes: list[Text] = Field(min_length=1)
    reviewer_notes: list[Text] = Field(default_factory=list)
    updates: dict[str, object] = Field(default_factory=dict)
    temporal_provenance: TemporalReview | None = None

    @model_validator(mode="after")
    def constrain_changes(self):
        if not set(self.updates) <= ALLOWED_UPDATES:
            raise ValueError("review updates cannot mutate historical provenance or approval identity")
        return self


class ReviewPacket(LabelModel):
    dataset_id: Literal[DATASET_ID]
    reviewer: Text
    reviewed_on: date
    review_scope: Text
    parent_manifest_sha256: SHA256
    feedback_sha256: SHA256
    authorization_sha256: SHA256
    decisions: list[Decision] = Field(min_length=50, max_length=50)

    @model_validator(mode="after")
    def all_decisions(self):
        if {item.historical_id for item in self.decisions} != set(range(1, 51)):
            raise ValueError("review must identify each candidate exactly once")
        return self


class ReviewedCase(draft.CurrentLawCase):
    parent_case_sha256: SHA256
    review_decision_sha256: SHA256
    adjudicated_by: Text
    adjudicated_on: date
    reviewer_notes: list[Text] = Field(default_factory=list)
    temporal_provenance: TemporalReview | None = None


def context_hash(chunk: dict) -> str:
    return digest({key: chunk[key] for key in (
        "text", "clause_head", "enriched_text", "source_spans", "temporal_status", "publication_eligible",
    )})


def verify_supporting_sources() -> None:
    registry = read_json(PROJECT_ROOT / "data/legal_sources/registry.json")
    for document in registry["documents"]:
        extraction = document.get("extraction") or {}
        path = extraction.get("supporting_input_path")
        expected = extraction.get("supporting_input_sha256")
        if path and expected and file_digest(PROJECT_ROOT / path) != expected:
            raise ValueError("registered supporting legal source changed")


def validate_temporal_review(case: ReviewedCase, chunks: dict[str, dict]) -> None:
    review = case.temporal_provenance
    if review is None:
        raise ValueError("historical publication needs approved temporal provenance")
    if review.reviewer != case.gold.review.reviewer or review.reviewed_on != case.gold.review.reviewed_on:
        raise ValueError("temporal approval differs from case reviewer/date")
    if not review.valid_from <= case.gold.as_of_date <= review.verified_through <= date.fromisoformat(draft.LEGAL_AS_OF):
        raise ValueError("query date outside reviewed temporal interval or frozen cutoff")
    support_ids = {ref.processed_id for group in case.gold.evidence_groups
                   for ref in group.references if ref.role == "support"}
    if {rule.chunk_id for rule in review.rules} != support_ids:
        raise ValueError("temporal review must cover all and only support rules")
    for rule in review.rules:
        chunk = chunks[rule.chunk_id]
        if rule.text_sha256 != hashlib.sha256(chunk["text"].encode()).hexdigest() or rule.context_sha256 != context_hash(chunk):
            raise ValueError("temporal rule differs from frozen source/context")
        if not chunk["publication_eligible"] or chunk["active_at_cutoff"] is not True:
            raise ValueError("temporal review cannot unblock a blocked rule")
        if not chunk["effective_from"] or review.valid_from < date.fromisoformat(chunk["effective_from"]):
            raise ValueError("temporal review predates source effective interval")
        if chunk["effective_to"] and review.verified_through >= date.fromisoformat(chunk["effective_to"]):
            raise ValueError("temporal review exceeds source effective interval")
        if rule.base_document_id not in chunk["lineage_document_ids"]:
            raise ValueError("temporal comparison lacks frozen lineage")
        if not rule.base_url.startswith("https://datafiles.chinhphu.vn/"):
            raise ValueError("temporal comparison must identify official source")
        if draft.normalize_text(rule.base_rule_text) != draft.normalize_text(chunk["text"]):
            raise ValueError("compared rule text differs from snapshot rule")


def validate_reviewed_case(case: ReviewedCase, chunks: dict[str, dict], row: dict, record: int) -> None:
    # Retain every draft safety/provenance check. Only its blanket date inequality
    # restriction is superseded, AFTER explicit case-scoped continuity review.
    proxy = case
    historical_publication = (
        case.gold.temporal_basis == "explicit_date"
        and str(case.gold.as_of_date) != draft.LEGAL_AS_OF
        and case.gold.publication.disposition != "abstain"
    )
    if historical_publication:
        validate_temporal_review(case, chunks)
        proxy = case.model_copy(deep=True)
        proxy.gold.as_of_date = date.fromisoformat(draft.LEGAL_AS_OF)
    elif case.temporal_provenance is not None:
        raise ValueError("unexpected temporal exception on a non-historical publication")
    draft.validate_case(proxy, chunks, row, record)
    require_scoring_gold([case])


def make_reviewed_case(parent: draft.CurrentLawCase, decision: Decision, packet: ReviewPacket,
                       chunks: dict[str, dict], row: dict, record: int) -> ReviewedCase:
    if int(parent.source.historical_id) != decision.historical_id:
        raise ValueError("review decision belongs to another case")
    data = parent.model_dump(mode="json")
    for path, value in decision.updates.items():
        target = data
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    data["gold"]["review"] = {
        "status": decision.status, "reviewer": packet.reviewer,
        "reviewed_on": str(packet.reviewed_on), "notes": decision.notes,
    }
    data["open_review_items"] = []
    data.update({
        "parent_case_sha256": digest(parent.model_dump(mode="json")),
        "review_decision_sha256": digest(decision.model_dump(mode="json")),
        "adjudicated_by": "Codex — áp dụng owner review, không phải reviewer độc lập thứ hai",
        "adjudicated_on": str(packet.reviewed_on), "reviewer_notes": decision.reviewer_notes,
        "temporal_provenance": decision.temporal_provenance.model_dump(mode="json") if decision.temporal_provenance else None,
    })
    case = ReviewedCase.model_validate(data)
    validate_reviewed_case(case, chunks, row, record)
    return case


def render_case(case: ReviewedCase, chunks: dict[str, dict]) -> list[str]:
    lines = [f"## Câu {int(case.source.historical_id):02d}", "",
             f"**Câu hỏi:** {case.query}", "", "**Đáp án tham chiếu:**", "",
             case.gold.reference_answer, "", f"- Nhãn: {case.gold.publication.disposition}",
             f"- Duyệt: {case.gold.review.reviewer}; ngày {case.gold.review.reviewed_on}", "",
             "Ý bắt buộc cần trả lời:", ""]
    lines.extend(f"- {facet.description}" for facet in case.gold.required_facets)
    lines.extend(["", "Căn cứ đối chiếu (nội dung đầy đủ trong evidence_catalog.json):", ""])
    refs = {ref.processed_id: ref for group in case.gold.evidence_groups for ref in group.references}
    for identity, ref in refs.items():
        chunk = chunks[identity]
        spans = "; ".join(f"{span['path']}:{span['line_start']}–{span['line_end']}" for span in chunk["source_spans"])
        lines.append(f"- {ref.citation} ({ref.role}); `{identity}`; nguồn {spans}")
    if case.temporal_provenance:
        lines.extend(["", f"Hiệu lực đã review riêng: {case.temporal_provenance.valid_from}–"
                      f"{case.temporal_provenance.verified_through}; mốc kết quả {case.temporal_provenance.result_date}."])
    if case.reviewer_notes:
        lines.extend(["", "Ghi chú reviewer — không phải nội dung bắt buộc của đáp án:", ""])
        lines.extend(f"- {note}" for note in case.reviewer_notes)
    lines.extend(["", "Quyết định review:", "", *[f"- {note}" for note in case.gold.review.notes], ""])
    return lines


def make_artifacts(directory: Path = DEFAULT_DIR) -> dict[str, object]:
    draft.verify_bundle()
    verify_supporting_sources()
    snapshot, chunks = draft.load_snapshot_context()
    packet = ReviewPacket.model_validate(read_json(directory / "review_decisions.json"))
    if packet.parent_manifest_sha256 != file_digest(draft.DEFAULT_DIR / "manifest.json"):
        raise ValueError("review targets a different draft manifest")
    if packet.feedback_sha256 != file_digest(directory / "review_feedback.txt") or packet.authorization_sha256 != file_digest(directory / "review_authorization.md"):
        raise ValueError("review authorization/feedback changed")
    parents = [draft.CurrentLawCase.model_validate_json(line) for line in (draft.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]
    originals = {row["STT"].strip(): (record, row) for record, row in enumerate(
        draft.parse_historical_csv(draft.SOURCE.read_bytes()), start=2)}
    decisions = {str(item.historical_id): item for item in packet.decisions}
    cases = [make_reviewed_case(parent, decisions[parent.source.historical_id], packet, chunks,
                               originals[parent.source.historical_id][1], originals[parent.source.historical_id][0])
             for parent in parents]
    if len({draft.question_key(case.query) for case in cases}) != len(cases):
        raise ValueError("duplicate reviewed queries")
    require_scoring_gold(cases)
    used = sorted({ref.processed_id for case in cases for group in case.gold.evidence_groups for ref in group.references})
    catalog = {"snapshot_id": draft.CORPUS_ID, "chunks": [chunks[identity] for identity in used],
               "context_hashes": {identity: context_hash(chunks[identity]) for identity in used}}
    changes = [{"id": case.id, "query_changed": case.query != parent.query,
                "answer_changed": case.gold.reference_answer != parent.gold.reference_answer,
                "old_expectation": parent.gold.publication.disposition,
                "new_expectation": case.gold.publication.disposition,
                "updated_fields": sorted(decisions[case.source.historical_id].updates)}
               for parent, case in zip(parents, cases)]
    report = {"dataset_id": DATASET_ID, "legal_as_of": draft.LEGAL_AS_OF,
              "reviewer": packet.reviewer, "reviewed_on": str(packet.reviewed_on),
              "review_scope": packet.review_scope, "technical_integrity_passed": True,
              "scoring_gold_ready": True, "benchmark_c0_c4_ready": False,
              "coverage": draft.coverage_report(cases), "evidence_chunk_count": len(used),
              "pilot_ids": list(draft.PILOT_IDS), "changes": changes,
              "temporal_review_case_ids": [case.id for case in cases if case.temporal_provenance],
              "model_runs": 0, "production_writes": 0, "additional_documents_indexed": 0,
              "held_out_created": False, "remaining_gates": ["Phase 3 regression/challenge and unseen held-out", "Phase 4 runner and fixed-evidence replay"],
              "limitations": ["Owner-reviewed internal benchmark; reviewer professional legal qualifications not asserted.",
                              "All historical cases remain exposed/legacy, not unseen held-out.",
                              "Conditional/abstain labels reflect frozen corpus and existing serving safety policy."]}
    lines = ["# Gold đã review — current-law v1", "", f"Ngày duyệt: {packet.reviewed_on}; cutoff corpus: {draft.LEGAL_AS_OF}.", "",
             "50 câu được chủ dự án duyệt qua feedback và chốt phương án sửa. Không có lượt review luật sư bổ sung được giả định.",
             "Dataset gold gate đạt; C0–C4 chưa được mở. Bản draft/CSV/snapshot giữ nguyên.", "",
             "| ID | Nhãn | Sửa query so với draft | Sửa đáp án |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {int(case.source.historical_id):02d} | {case.gold.publication.disposition} | "
                 f"{'Có' if change['query_changed'] else 'Không'} | {'Có' if change['answer_changed'] else 'Không'} |"
                 for case, change in zip(cases, changes))
    lines.append("")
    for case in cases:
        lines.extend(render_case(case, chunks))
    artifacts = {"cases.jsonl": "".join(case.model_dump_json() + "\n" for case in cases),
                 "evidence_catalog.json": catalog, "audit.json": report,
                 "REVIEWED.md": "\n".join(lines) + "\n", "case.schema.json": ReviewedCase.model_json_schema()}
    artifacts["manifest.json"] = {
        "format_version": 1, "dataset_id": DATASET_ID, "status": "owner_reviewed",
        "legal_as_of": draft.LEGAL_AS_OF, "reviewed_on": str(packet.reviewed_on),
        "parent": {"path": str(draft.DEFAULT_DIR.relative_to(PROJECT_ROOT)), "manifest_sha256": packet.parent_manifest_sha256},
        "snapshot": {"id": draft.CORPUS_ID, "manifest_sha256": file_digest(draft.DEFAULT_SNAPSHOT_MANIFEST),
                     "receipt_sha256": file_digest(draft.DEFAULT_RECEIPT), "fingerprint": snapshot["shadow_resources"]["collection_fingerprint"]},
        "protocol": {"base_sha256": file_digest(draft.PROTOCOL), "reviewed_path": str(PROTOCOL.relative_to(PROJECT_ROOT)), "reviewed_sha256": file_digest(PROTOCOL)},
        "builder": {"path": str(Path(__file__).relative_to(PROJECT_ROOT)), "sha256": file_digest(Path(__file__))},
        "artifacts": {name: hashlib.sha256(draft.artifact_bytes(value)).hexdigest() for name, value in artifacts.items()},
        "inputs": {name: file_digest(directory / name) for name in INPUT_FILES},
        "scoring_gold_ready": True, "benchmark_c0_c4_ready": False,
    }
    return artifacts


def build_bundle(directory: Path = DEFAULT_DIR) -> dict:
    artifacts = make_artifacts(directory)
    if (directory / RECEIPT).exists() or any((directory / name).exists() for name in artifacts):
        raise FileExistsError("reviewed artifacts exist; verify or create a new dataset version")
    for name, value in artifacts.items():
        (directory / name).write_bytes(draft.artifact_bytes(value))
    return artifacts["audit.json"]


def receipt_for(directory: Path) -> dict:
    manifest = read_json(directory / "manifest.json")
    return {"dataset_id": DATASET_ID, "status": "frozen", "frozen_on": manifest["reviewed_on"],
            "manifest_sha256": file_digest(directory / "manifest.json"),
            "artifact_hashes": {**manifest["inputs"], **manifest["artifacts"]},
            "snapshot": manifest["snapshot"], "scoring_gold_ready": True,
            "benchmark_c0_c4_ready": False, "model_runs": 0, "production_writes": 0}


def verify_bundle(directory: Path = DEFAULT_DIR, *, require_frozen: bool = True) -> dict:
    expected = make_artifacts(directory)
    for name, value in expected.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != draft.artifact_bytes(value):
            raise ValueError(f"reviewed dataset artifact changed: {name}")
    if require_frozen:
        path = directory / RECEIPT
        if not path.is_file() or path.read_bytes() != draft.artifact_bytes(receipt_for(directory)):
            raise ValueError("reviewed dataset is not frozen or receipt changed")
    return expected["audit.json"]


def freeze_bundle(directory: Path = DEFAULT_DIR) -> dict:
    report = verify_bundle(directory, require_frozen=False)
    if (directory / RECEIPT).exists():
        raise FileExistsError("freeze receipt exists; verify instead of overwriting")
    (directory / RECEIPT).write_bytes(draft.artifact_bytes(receipt_for(directory)))
    return report


def require_reviewed_scoring(directory: Path = DEFAULT_DIR, selected_ids: Sequence[str] | None = None) -> list[ReviewedCase]:
    """A frozen gold gate, not permission to bypass downstream benchmark gates."""
    verify_bundle(directory)
    cases = [ReviewedCase.model_validate_json(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
    if selected_ids is not None:
        if len(set(selected_ids)) != len(selected_ids) or not set(selected_ids) <= {case.id for case in cases}:
            raise ValueError("invalid scoring selection")
        by_id = {case.id: case for case in cases}
        cases = [by_id[identity] for identity in selected_ids]
    require_scoring_gold(cases)
    return cases


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "freeze", "verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    report = {"build": build_bundle, "freeze": freeze_bundle, "verify": verify_bundle}[args.action](args.directory)
    print(json.dumps({key: report[key] for key in (
        "dataset_id", "scoring_gold_ready", "benchmark_c0_c4_ready", "coverage", "temporal_review_case_ids",
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
