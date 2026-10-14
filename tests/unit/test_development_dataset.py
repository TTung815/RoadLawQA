"""Completed exposed drafts: numeric boundaries, blocked-context probes and review scope."""

import copy
from datetime import date, timedelta
import shutil

import pytest
from pydantic import ValidationError

from evaluation import current_law_dataset as draft
from evaluation import development_dataset as development
from evaluation import phase3_design as design
from evaluation import reviewed_current_law_dataset as reviewed
from ingestion.legal_registry import read_json


@pytest.fixture(scope="module")
def context():
    chunks = {chunk["id"]: chunk for chunk in read_json(draft.DEFAULT_OUTPUT)["chunks"]}
    cases = [development.DevelopmentDraftCase.model_validate_json(line) for line in
             (development.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]
    labels = [development.NumericLabel.model_validate(value) for value in
              read_json(development.DEFAULT_DIR / "numeric_labels.json")]
    return chunks, cases, labels


def test_completed_packet_verifies_but_does_not_open_scoring():
    report = development.verify_bundle()
    assert report["authored_case_count"] == 54
    assert report["numeric_count"] == 4 and report["guard_count"] == 34
    assert report["blocked_locator_count"] == 10 and report["future_boundary_count"] == 8
    assert report["gold_review_status"] == {"needs_review": 54}
    assert report["review_groups"] == 7
    assert report["modes"] == {"fixed_evidence": 7, "rewrite_probe": 1, "end_to_end": 12, "publication_guard_probe": 34}
    assert report["scoring_ready"] is report["benchmark_c0_c4_ready"] is False
    assert report["system_stage_results"] is None
    assert report["model_runs"] == report["production_writes"] == report["held_out_authored"] == 0


def test_numeric_answers_come_from_three_distinct_source_branches(context):
    chunks, cases, labels = context
    numbers = {label.excess_kmh: label for label in labels}
    assert numbers[9].money_min == 800000
    assert numbers[10].money_min == numbers[20].money_min == 4000000
    assert numbers[21].money_min == 6000000
    assert len({label.chunk_id for label in labels}) == 3
    numeric = [case for case in cases if case.origin_kind == "reviewed_numeric_derivative"]
    for label, case in zip(labels, numeric):
        development.validate_numeric(label, chunks[label.chunk_id])
        assert case.family_id == "car_speed_10_20"
        assert case.split == "legacy" and case.exposure == "historically_used"
        assert case.gold.publication.disposition == "publish"
        assert {f.kind for f in case.gold.required_facets} == {"condition", "money"}
        assert case.gold.review.status == "needs_review"


@pytest.mark.parametrize("label_index,excess", [(0, 10), (1, 9), (1, 21), (3, 20)])
def test_open_closed_numeric_boundaries_reject_wrong_source(context, label_index, excess):
    chunks, _, labels = context
    altered = labels[label_index].model_copy(update={"excess_kmh": excess})
    with pytest.raises(ValueError):
        development.validate_numeric(altered, chunks[altered.chunk_id])


def test_numeric_amount_query_and_answer_are_not_trusted_blindly(context):
    chunks, _, labels = context
    for changes in ({"money_min": 1}, {"query": "fixture"}, {"reference_answer": "fixture"}):
        altered = labels[0].model_copy(update=changes)
        with pytest.raises(ValueError):
            development.validate_numeric(altered, chunks[altered.chunk_id])
    blocked = copy.deepcopy(chunks[labels[0].chunk_id])
    blocked["publication_eligible"] = False
    with pytest.raises(ValueError):
        development.validate_numeric(labels[0], blocked)


def test_all_blocked_locators_have_cutoff_and_exact_boundary_offsets(context):
    chunks, cases, _ = context
    cutoff = date.fromisoformat(draft.LEGAL_AS_OF)
    guard = [case for case in cases if case.origin_kind == "snapshot_guard"]
    blocked = {identity for identity, chunk in chunks.items() if not chunk["publication_eligible"]}
    assert {case.origin_id for case in guard} == blocked
    assert sum(case.boundary_date is None for case in guard) == 10
    for identity in blocked:
        selected = [case for case in guard if case.origin_id == identity]
        assert sum(case.boundary_date is None for case in selected) == 1
        for anchor in development.future_boundaries(chunks[identity]):
            anchored = [case for case in selected if case.boundary_date == anchor]
            assert {case.boundary_offset_days for case in anchored} == {-1, 0, 1}
            assert {case.gold.as_of_date for case in anchored} == {anchor + timedelta(days=d) for d in (-1, 0, 1)}
            assert anchor > cutoff
    assert all(case.boundary_date is None for case in guard if chunks[case.origin_id]["temporal_status"] == "repealed")


def test_guards_remain_context_only_before_on_and_after_future_anchor(context):
    chunks, cases, _ = context
    for case in cases:
        development.validate_case(case, chunks)
        if case.origin_kind == "snapshot_guard":
            assert case.split == "regression" and case.exposure == "known_regression"
            assert case.gold.publication.disposition == "abstain"
            assert all(ref.role == "context" for group in case.gold.evidence_groups for ref in group.references)
            assert all(f.support_state == "unknown" for f in case.gold.required_facets)
            assert case.stage_probe.expected_pool_coverage == "insufficient"
            assert case.temporal_provenance is None


def test_guard_rejects_wrong_date_pool_expectation_or_source_hash(context):
    chunks, cases, _ = context
    case = next(case for case in cases if case.boundary_date is not None)
    altered = case.model_copy(deep=True)
    altered.gold.as_of_date += timedelta(days=10)
    with pytest.raises(ValueError):
        development.validate_case(altered, chunks)
    altered = case.model_copy(deep=True)
    altered.stage_probe.expected_pool_coverage = "sufficient"
    with pytest.raises(ValueError):
        development.validate_case(altered, chunks)
    altered = case.model_copy(update={"origin_sha256": "0" * 64})
    with pytest.raises(ValueError):
        development.validate_case(altered, chunks)


def test_blocked_context_cannot_be_recast_as_positive_support(context):
    chunks, cases, _ = context
    case = next(case for case in cases if case.origin_kind == "snapshot_guard")
    altered = case.model_copy(deep=True)
    altered.gold.evidence_groups[0].references[0].role = "support"
    with pytest.raises(ValidationError):
        development.DevelopmentDraftCase.model_validate(altered.model_dump())
    numeric = next(case for case in cases if case.origin_kind == "reviewed_numeric_derivative")
    altered = numeric.model_copy(deep=True)
    ref_type = type(altered.gold.evidence_groups[0].references[0])
    altered.gold.evidence_groups[0].references[0] = ref_type.model_validate(draft.evidence_reference(chunks[case.origin_id], "support"))
    with pytest.raises(ValueError):
        development.validate_case(altered, chunks)


def test_parent_design_content_is_exact_not_new_independent_approval(context):
    _, cases, _ = context
    original = [design.DevelopmentCase.model_validate_json(line) for line in
                (design.DEFAULT_DIR / "development_cases.jsonl").read_text().splitlines()]
    for case, parent in zip(cases[:16], original):
        assert case.gold == parent.gold
        assert case.query == parent.query and case.chat_history == parent.chat_history
        assert case.temporal_provenance == parent.temporal_provenance
        assert case.origin_sha256 == development.digest(parent.model_dump(mode="json"))
        assert case.gold.review.reviewer is None


def test_seven_review_groups_cover_every_case_once_with_hash(context):
    _, cases, _ = context
    groups = development.review_groups(cases)
    assert [group["id"] for group in groups] == ["A1", "A2", "A3", "A4", "B1", "B2", "C1"]
    assert [len(group["case_ids"]) for group in groups] == [1, 1, 1, 1, 1, 1, 48]
    assert all(group["status"] == "needs_review" and group["reviewer"] is None for group in groups)
    members = [identity for group in groups for identity in group["case_ids"]]
    assert len(set(members)) == len(cases)
    for group in groups:
        selected = [case for case in cases if case.review_group_id == group["id"]]
        assert group["content_sha256"] == development.digest([case.model_dump(mode="json") for case in selected])


def test_held_out_exclusion_inventory_includes_numeric_and_blocked_context(context):
    _, cases, _ = context
    inventory = read_json(development.DEFAULT_DIR / "exposure_inventory.json")
    assert {case.family_id for case in cases} <= set(inventory["families"])
    assert {case.origin_id for case in cases if case.origin_kind == "snapshot_guard"} <= set(inventory["evidence_ids"])
    assert reviewed.verify_bundle()["coverage"]["review_status"] == {"approved": 50}


def test_build_never_overwrites_and_artifact_tampering_fails(tmp_path, monkeypatch):
    before = (development.DEFAULT_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(development, "make_artifacts", lambda directory: {"manifest.json": {}})
    with pytest.raises(FileExistsError):
        development.build_bundle()
    assert (development.DEFAULT_DIR / "manifest.json").read_bytes() == before
    copied = tmp_path / "packet"
    shutil.copytree(development.DEFAULT_DIR, copied)
    monkeypatch.setattr(development, "make_artifacts", lambda directory: {"cases.jsonl": "expected"})
    (copied / "cases.jsonl").write_text("tampered")
    with pytest.raises(ValueError):
        development.verify_bundle(copied)


def test_new_draft_cannot_forge_approval_or_unseen_split(context):
    _, cases, _ = context
    altered = cases[0].model_dump(mode="json")
    altered["gold"]["review"] = {"status": "approved", "reviewer": "fake", "reviewed_on": "2026-10-11"}
    with pytest.raises(ValidationError):
        development.DevelopmentDraftCase.model_validate(altered)
    altered = cases[0].model_dump(mode="json")
    altered["split"] = "held_out"
    altered["exposure"] = "unseen"
    with pytest.raises(ValidationError):
        development.DevelopmentDraftCase.model_validate(altered)
