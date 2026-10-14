"""Current-law revisions, frozen evidence and approval gates, without model runs."""

import copy
import pytest
from pydantic import ValidationError

from evaluation import current_law_dataset as dataset
from ingestion.legal_registry import read_json


@pytest.fixture(scope="module")
def context():
    corpus = read_json(dataset.DEFAULT_OUTPUT)
    chunks = {chunk["id"]: chunk for chunk in corpus["chunks"]}
    rows = dataset.parse_historical_csv(dataset.SOURCE.read_bytes())
    labels = {item["historical_id"]: dataset.DraftLabel.model_validate(item)
              for item in read_json(dataset.DEFAULT_LABELS)}
    cases = [dataset.make_case(labels[int(row["STT"])], row, record, chunks)
             for record, row in enumerate(rows, start=2)]
    return chunks, rows, labels, cases


def test_current_law_bundle_reproduces_and_remains_unapproved():
    report = dataset.verify_bundle()
    assert report["technical_integrity_passed"]
    assert report["pilot_schema_provenance_passed"]
    assert report["pilot_semantic_approval"] is False
    assert report["official_scoring_ready"] is False
    assert report["approved_selected_ids"] == []
    assert report["coverage"]["count"] == 50
    assert report["coverage"]["decisions"] == {"edit": 32, "keep": 18}
    assert report["coverage"]["review_status"] == {"needs_review": 50}
    assert report["pilot_ids"] == list(dataset.PILOT_IDS)
    assert report["pilot"]["count"] == 10


def test_revision_keeps_source_history_and_never_creates_unseen_cases(context):
    _, rows, _, cases = context
    first = cases[0]
    assert first.query != dataset.normalize_text(rows[0]["Question"])
    assert first.revision.original_query == dataset.normalize_text(rows[0]["Question"])
    assert first.source.raw_fields == rows[0]
    assert first.gold.review.reviewer is None
    assert first.revision.drafted_on.isoformat() == "2026-10-09"
    assert all(c.split == "legacy" and c.exposure == "historically_used" for c in cases)
    assert cases[8].gold.temporal_basis == "explicit_date"
    assert str(cases[8].gold.as_of_date) == "2025-02-01"
    assert cases[8].gold.publication.disposition == "abstain"
    assert cases[35].family_id == cases[44].family_id
    changed = first.model_dump()
    changed["split"] = "held_out"
    with pytest.raises(ValidationError, match="Held-out cases must be unseen"):
        dataset.CurrentLawCase.model_validate(changed)


def test_keep_cannot_hide_question_revision(context):
    chunks, rows, labels, _ = context
    bad = labels[1].model_copy(update={"action": "keep"})
    with pytest.raises(ValueError, match="keep case changed"):
        dataset.make_case(bad, rows[0], 2, chunks)


def test_changed_evidence_and_blocked_support_fail_closed(context):
    chunks, rows, _, cases = context
    altered = cases[0].model_copy(deep=True)
    altered.gold.evidence_groups[0].references[0].text_sha256 = "0" * 64
    with pytest.raises(ValueError, match="evidence reference changed"):
        dataset.validate_case(altered, chunks, rows[0], 2)
    blocked = copy.deepcopy(chunks)
    identity = altered.gold.evidence_groups[0].references[0].processed_id
    blocked[identity]["publication_eligible"] = False
    with pytest.raises(ValueError, match="blocked chunk used as support"):
        dataset.validate_case(cases[0], blocked, rows[0], 2)


def test_publication_cannot_use_context_or_missing_dependency(context):
    chunks, rows, labels, _ = context
    bad = labels[43].model_copy(update={"disposition": "publish", "expected_coverage": "sufficient"})
    with pytest.raises(ValueError, match="publish expectation lacks complete scope"):
        dataset.make_case(bad, rows[42], 44, chunks)
    unsupported = labels[1].model_copy(deep=True)
    unsupported.facets[0].role = "context"
    unsupported.facets[0].support_state = "unknown"
    with pytest.raises(ValueError, match="unsupported required facets"):
        dataset.make_case(unsupported, rows[0], 2, chunks)


def test_scoring_allows_approved_subset_but_never_pending_or_excluded(context):
    chunks, rows, labels, cases = context
    with pytest.raises(ValueError, match="Gold is not approved"):
        dataset.require_current_law_scoring(cases[:1], chunks)
    approved = cases[0].model_dump()
    approved["gold"]["review"].update({
        "status": "approved", "reviewer": "Synthetic unit-test reviewer",
        "reviewed_on": "2026-10-09",
    })
    selected = dataset.CurrentLawCase.model_validate(approved)
    with pytest.raises(ValueError, match="unresolved review items"):
        dataset.require_current_law_scoring([selected], chunks)
    approved["open_review_items"] = []
    selected = dataset.CurrentLawCase.model_validate(approved)
    dataset.require_current_law_scoring([selected], chunks)
    dropped = labels[1].model_copy(update={"action": "drop"})
    excluded = dataset.make_case(dropped, rows[0], 2, chunks)
    with pytest.raises(ValueError, match="excluded candidates"):
        dataset.require_current_law_scoring([excluded], chunks)


def test_bundle_tampering_is_rejected_without_overwriting(tmp_path):
    # Only copy labels: recomputation is read-only and missing/mutated output fails.
    labels = tmp_path / "draft_labels.json"
    labels.write_bytes(dataset.DEFAULT_LABELS.read_bytes())
    (tmp_path / "cases.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="artifact changed: cases.jsonl"):
        dataset.verify_bundle(tmp_path)
    assert (tmp_path / "cases.jsonl").read_text() == "{}\n"


def test_bundle_builder_never_overwrites_existing_dataset():
    before = (dataset.DEFAULT_DIR / "cases.jsonl").read_bytes()
    with pytest.raises(FileExistsError, match="dataset artifacts exist"):
        dataset.build_bundle()
    assert (dataset.DEFAULT_DIR / "cases.jsonl").read_bytes() == before
