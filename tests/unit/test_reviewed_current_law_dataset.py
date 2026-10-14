"""Owner review, scoped temporal continuity and immutable dataset freeze gates."""

import copy
from datetime import date
import shutil

import pytest
from pydantic import ValidationError

from evaluation import current_law_dataset as draft
from evaluation import reviewed_current_law_dataset as reviewed
from ingestion.legal_registry import read_json


@pytest.fixture(scope="module")
def context():
    chunks = {chunk["id"]: chunk for chunk in read_json(draft.DEFAULT_OUTPUT)["chunks"]}
    rows = draft.parse_historical_csv(draft.SOURCE.read_bytes())
    cases = [reviewed.ReviewedCase.model_validate_json(line)
             for line in (reviewed.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]
    packet = reviewed.ReviewPacket.model_validate(read_json(reviewed.DEFAULT_DIR / "review_decisions.json"))
    return chunks, rows, cases, packet


def test_reviewed_freeze_verifies_without_opening_benchmark_gates():
    report = reviewed.verify_bundle()
    assert report["coverage"]["count"] == 50
    assert report["coverage"]["review_status"] == {"approved": 50}
    assert report["coverage"]["publication"] == {"publish": 41, "abstain": 4, "conditional": 5}
    assert report["scoring_gold_ready"] is True
    assert report["benchmark_c0_c4_ready"] is False
    assert report["model_runs"] == report["production_writes"] == report["additional_documents_indexed"] == 0
    assert report["temporal_review_case_ids"] == ["current_law_009"]
    assert draft.verify_bundle()["coverage"]["review_status"] == {"needs_review": 50}


def test_owner_review_preserves_history_and_records_delegated_revisions(context):
    chunks, rows, cases, packet = context
    assert all(case.gold.review.reviewer == packet.reviewer for case in cases)
    assert all(case.gold.review.reviewed_on == date(2026, 10, 11) for case in cases)
    assert all(not case.open_review_items for case in cases)
    assert all(case.split == "legacy" and case.exposure == "historically_used" for case in cases)
    for record, (case, row) in enumerate(zip(cases, rows), start=2):
        assert case.source.raw_fields == row
        reviewed.validate_reviewed_case(case, chunks, row, record)
    assert packet.decisions[23].basis == "followup_resolution"
    assert cases[0].reviewer_notes
    assert cases[3].gold.temporal_basis == cases[10].gold.temporal_basis == "frozen_corpus"
    assert cases[22].gold.external_evidence_needed
    assert cases[42].gold.external_evidence_needed


def test_historical_publication_requires_case_scoped_temporal_provenance(context):
    chunks, rows, cases, _ = context
    case = cases[8]
    assert case.gold.as_of_date == date(2025, 2, 1)
    assert case.gold.publication.disposition == "publish"
    assert case.temporal_provenance.result_date == date(2026, 2, 1)
    # The old draft gate remains conservative; the reviewed gate needs proof.
    with pytest.raises(ValueError, match="date outside snapshot cutoff"):
        draft.validate_case(case, chunks, rows[8], 10)
    missing = case.model_copy(update={"temporal_provenance": None}, deep=True)
    with pytest.raises(ValueError, match="approved temporal provenance"):
        reviewed.validate_reviewed_case(missing, chunks, rows[8], 10)


def test_temporal_proof_rejects_hash_scope_lineage_and_interval_changes(context):
    chunks, rows, cases, _ = context
    for field, value, message in [
        ("context_sha256", "0" * 64, "frozen source/context"),
        ("base_document_id", "unreviewed-law", "frozen lineage"),
        ("base_rule_text", "unverified wording", "rule text differs"),
    ]:
        altered = cases[8].model_copy(deep=True)
        setattr(altered.temporal_provenance.rules[0], field, value)
        with pytest.raises(ValueError, match=message):
            reviewed.validate_reviewed_case(altered, chunks, rows[8], 10)
    altered = cases[8].model_copy(deep=True)
    altered.temporal_provenance.valid_from = date(2025, 3, 1)
    with pytest.raises(ValueError, match="query date outside"):
        reviewed.validate_reviewed_case(altered, chunks, rows[8], 10)
    altered = cases[8].model_copy(deep=True)
    altered.temporal_provenance.rules = []
    with pytest.raises(ValueError, match="all and only support"):
        reviewed.validate_reviewed_case(altered, chunks, rows[8], 10)


def test_reviewed_gate_still_rejects_blocked_support_and_open_items(context):
    chunks, rows, cases, _ = context
    blocked = copy.deepcopy(chunks)
    ref = cases[0].gold.evidence_groups[0].references[0]
    blocked[ref.processed_id]["publication_eligible"] = False
    with pytest.raises(ValueError, match="blocked chunk"):
        reviewed.validate_reviewed_case(cases[0], blocked, rows[0], 2)
    altered = cases[0].model_copy(update={"open_review_items": ["unresolved"]})
    with pytest.raises(ValueError, match="unresolved review items"):
        reviewed.validate_reviewed_case(altered, chunks, rows[0], 2)


def test_equipment_case_uses_article_15_and_overlay_case_keeps_amendment(context):
    chunks, _, cases, _ = context
    equipment = {ref.processed_id for group in cases[23].gold.evidence_groups for ref in group.references}
    assert equipment == {"nd168-effective-as-of-2026-09-22-d15-k1"}
    assert "equipment" in cases[23].challenge_tags
    refs = [ref.processed_id for group in cases[41].gold.evidence_groups for ref in group.references]
    decree = chunks[next(identity for identity in refs if identity.endswith("-d6-k7-pc"))]
    assert "a19-p04-nd168-d6-k7-c" in decree["operation_ids"]
    assert cases[41].gold.publication.disposition == "conditional"
    assert "238/2026" in cases[41].gold.reference_answer


def test_review_packet_cannot_overwrite_history_or_forge_reviewer_fields(context):
    _, _, _, packet = context
    for path in ("source.raw_fields", "gold.review", "split", "revision.original_query"):
        data = packet.decisions[0].model_dump()
        data["updates"] = {path: "forged"}
        with pytest.raises(ValidationError, match="cannot mutate historical provenance"):
            reviewed.Decision.model_validate(data)


def test_supporting_docx_hash_is_checked_separately(tmp_path, monkeypatch):
    source = tmp_path / "changed.docx"
    source.write_bytes(b"changed")
    registry = {"documents": [{"extraction": {
        "supporting_input_path": str(source), "supporting_input_sha256": "0" * 64,
    }}]}
    monkeypatch.setattr(reviewed, "read_json", lambda path: registry)
    with pytest.raises(ValueError, match="supporting legal source changed"):
        reviewed.verify_supporting_sources()


def test_bundle_tampering_and_missing_receipt_fail_closed(tmp_path):
    copied = tmp_path / "reviewed"
    shutil.copytree(reviewed.DEFAULT_DIR, copied)
    (copied / reviewed.RECEIPT).rename(copied / "receipt.backup")
    with pytest.raises(ValueError, match="not frozen"):
        reviewed.verify_bundle(copied)
    (copied / "receipt.backup").rename(copied / reviewed.RECEIPT)
    (copied / "review_feedback.txt").write_text("tampered\n")
    with pytest.raises(ValueError, match="authorization/feedback changed"):
        reviewed.verify_bundle(copied)


def test_reviewed_build_and_freeze_never_overwrite(monkeypatch):
    before = (reviewed.DEFAULT_DIR / reviewed.RECEIPT).read_bytes()
    # Integrity is tested above; isolate create-only behavior here.
    monkeypatch.setattr(reviewed, "make_artifacts", lambda directory: {"cases.jsonl": "changed"})
    with pytest.raises(FileExistsError, match="artifacts exist"):
        reviewed.build_bundle()
    monkeypatch.setattr(reviewed, "verify_bundle", lambda *args, **kwargs: {})
    with pytest.raises(FileExistsError, match="receipt exists"):
        reviewed.freeze_bundle()
    assert (reviewed.DEFAULT_DIR / reviewed.RECEIPT).read_bytes() == before


def test_scoring_selection_requires_frozen_unique_nonempty_approved_subset(monkeypatch):
    selected = reviewed.require_reviewed_scoring(selected_ids=["current_law_009"])
    assert len(selected) == 1
    monkeypatch.setattr(reviewed, "verify_bundle", lambda directory: {})
    for ids in (["unknown"], ["current_law_001", "current_law_001"]):
        with pytest.raises(ValueError, match="invalid scoring selection"):
            reviewed.require_reviewed_scoring(selected_ids=ids)
    with pytest.raises(ValueError, match="nonempty subset"):
        reviewed.require_reviewed_scoring(selected_ids=[])
