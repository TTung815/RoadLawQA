"""Phase 3 design provenance, replay-pool separation and held-out leakage gates."""

import copy
import shutil

import pytest
from pydantic import ValidationError

from evaluation import current_law_dataset as draft
from evaluation import phase3_design as design
from evaluation import reviewed_current_law_dataset as reviewed
from evaluation.dataset_schema import AnswerFacet, EvidenceGroup
from ingestion.legal_registry import read_json


@pytest.fixture(scope="module")
def context():
    parents = {int(case.source.historical_id): case for case in (
        reviewed.ReviewedCase.model_validate_json(line)
        for line in (reviewed.DEFAULT_DIR / "cases.jsonl").read_text().splitlines())}
    chunks = {chunk["id"]: chunk for chunk in read_json(draft.DEFAULT_OUTPUT)["chunks"]}
    plan = design.DesignPlan.model_validate(read_json(design.DEFAULT_DIR / "plan.json"))
    cases = [design.make_development(recipe, parents, chunks) for recipe in plan.development_recipes]
    return parents, chunks, cases


def test_phase3_packet_verifies_and_keeps_scoring_closed():
    report = design.verify_bundle()
    assert report["scoring_ready"] is report["benchmark_c0_c4_ready"] is False
    assert report["development_approved"] == report["held_out_authored"] == 0
    assert report["model_runs"] == report["production_writes"] == 0
    assert reviewed.verify_bundle()["coverage"]["review_status"] == {"approved": 50}


def test_new_cases_do_not_forge_history_or_inherit_approval(context):
    parents, _, cases = context
    assert len(cases) == 16
    for case in cases:
        parent = parents[case.recipe.parent]
        assert case.family_id == parent.family_id
        assert case.split == "legacy" and case.exposure == "historically_used"
        assert case.suite == "development"
        assert case.gold.review.status == "needs_review"
        assert case.gold.review.reviewer is case.gold.review.reviewed_on is None
        assert case.open_review_items
        assert case.parent_case_sha256 == design.digest(parent.model_dump(mode="json"))
        assert case.gold.reference_answer == parent.gold.reference_answer
        assert parent.split == "legacy" and parent.gold.review.status == "approved"
        assert "source" not in case.model_dump()


def test_partial_replay_does_not_change_full_corpus_gold(context):
    _, _, cases = context
    for partial, control in ((cases[0], cases[1]), (cases[2], cases[3])):
        assert partial.gold.publication.disposition == control.gold.publication.disposition == "publish"
        assert partial.stage_probe.expected_pool_coverage == "insufficient"
        assert partial.stage_probe.missing_facet_ids
        assert control.stage_probe.expected_pool_coverage == "sufficient"
        assert not control.stage_probe.missing_facet_ids
    assert cases[0].stage_probe.missing_facet_ids == ["f2"]


def test_irrelevant_locators_cannot_cover_parent_facets(context):
    parents, chunks, cases = context
    for case in cases[4:6]:
        pool = design.ordered_pool(case.stage_probe.evidence_batches)
        assert all(identity in chunks for identity in pool)
        assert case.stage_probe.missing_facet_ids == design.missing_facets(parents[case.recipe.parent], pool)
        assert case.stage_probe.expected_pool_coverage == "insufficient"
        assert not set(pool) & set(design.support_ids(parents[case.recipe.parent]))


def test_accumulation_grades_ordered_union_not_last_batch(context):
    parents, _, cases = context
    case = cases[6]
    batches = case.stage_probe.evidence_batches
    assert len(batches) == 2
    assert design.missing_facets(parents[8], batches[-1])
    assert not design.missing_facets(parents[8], design.ordered_pool(batches))
    assert design.ordered_pool([batches[0], batches[0], batches[1]]) == design.ordered_pool(batches)


def test_multi_turn_and_temporal_drafts_keep_parent_scope(context):
    parents, _, cases = context
    assert cases[8].chat_history[-1].content == parents[5].query
    assert cases[9].chat_history[0].content == parents[3].query
    assert cases[9].chat_history[-1].content == parents[8].query
    assert cases[8].query != parents[5].query
    assert all(message.role == "user" for c in cases for message in c.chat_history)
    assert cases[14].temporal_provenance == parents[9].temporal_provenance
    assert cases[14].query == parents[9].query
    assert cases[14].gold.review.status == "needs_review"


def test_pool_coverage_respects_all_any_and_context(context):
    parents, _, _ = context
    case = parents[5].model_copy(deep=True)
    refs = [ref for group in case.gold.evidence_groups for ref in group.references]
    case.gold.evidence_groups = [EvidenceGroup(id="g", description="fixture", match="all", references=refs)]
    case.gold.required_facets = [AnswerFacet(id="f", kind="rule", description="fixture",
                                            support_state="positive_support", evidence_group_ids=["g"])]
    pool = [refs[0].processed_id]
    assert design.missing_facets(case, pool) == ["f"]
    case.gold.evidence_groups[0].match = "any"
    assert design.missing_facets(case, pool) == []
    case.gold.evidence_groups[0].references[0].role = "context"
    assert design.missing_facets(case, pool) == ["f"]


def test_replay_rejects_blocked_or_empty_evidence(context, monkeypatch):
    parents, chunks, cases = context
    altered = copy.deepcopy(chunks)
    identity = cases[1].stage_probe.evidence_batches[0][0]
    altered[identity]["publication_eligible"] = False
    with pytest.raises(ValueError):
        design.make_development(cases[1].recipe, parents, altered)
    monkeypatch.setattr(design, "support_ids", lambda *args: [])
    with pytest.raises(ValueError):
        design.make_development(cases[0].recipe, parents, chunks)


def test_coverage_is_inventory_not_measured_system_result(context):
    parents, chunks, cases = context
    report = design.coverage_report(list(parents.values()), cases, chunks)
    assert report["legacy"]["multi_turn_cases"] == 0
    assert report["legacy"]["count"] == 50
    assert report["development"]["modes"] == {"fixed_evidence": 7, "rewrite_probe": 1, "end_to_end": 8}
    assert report["development"]["multi_turn_cases"] == 2
    assert report["held_out"]["authored"] == 0
    assert report["system_results"] is None
    assert len(report["blocked_context_inventory"]) == 10
    assert all(not item["support_allowed"] for item in report["blocked_context_inventory"])


def proposal_data():
    return {"id": "sealed_1", "family_id": "new_family", "article_keys": ["new_doc:d1"],
            "parent_case_ids": [], "content_sha256": "a" * 64,
            "author": "author", "reviewer": "reviewer", "custodian": "custodian",
            "reviewed_on": "2026-10-11", "semantic_overlap_reviewed": True,
            "exposure_inventory_reviewed": True, "tuning_exposed": False, "used_for_selection": False}


@pytest.mark.parametrize("field,value", [
    ("family_id", "old_family"), ("article_keys", ["old_doc:d1"]),
    ("parent_case_ids", ["parent"]), ("author", "reviewer"), ("custodian", "tuner"),
    ("semantic_overlap_reviewed", False), ("exposure_inventory_reviewed", False),
    ("tuning_exposed", True), ("used_for_selection", True),
])
def test_held_out_screen_rejects_detectable_leakage(field, value):
    inventory = {"families": ["old_family"], "articles": ["old_doc:d1"]}
    data = proposal_data()
    design.screen_held_out(design.HeldOutProposal.model_validate(data), inventory, "tuner")
    data[field] = value
    with pytest.raises(ValueError):
        design.screen_held_out(design.HeldOutProposal.model_validate(data), inventory, "tuner")


def test_draft_contract_rejects_forged_approval_and_pool_on_e2e(context):
    _, _, cases = context
    data = cases[0].model_dump(mode="json")
    data["gold"]["review"] = {"status": "approved", "reviewer": "fake", "reviewed_on": "2026-10-11"}
    with pytest.raises(ValidationError):
        design.DevelopmentCase.model_validate(data)
    data = cases[10].model_dump(mode="json")
    data["stage_probe"]["evidence_batches"] = [["fake"]]
    with pytest.raises(ValidationError):
        design.DevelopmentCase.model_validate(data)


def test_design_never_overwrites_existing_outputs(monkeypatch):
    before = (design.DEFAULT_DIR / "manifest.json").read_bytes()
    monkeypatch.setattr(design, "make_artifacts", lambda directory: {"manifest.json": {}})
    with pytest.raises(FileExistsError):
        design.build_bundle()
    assert (design.DEFAULT_DIR / "manifest.json").read_bytes() == before


def test_design_artifact_tampering_fails_verification(tmp_path, monkeypatch):
    copied = tmp_path / "packet"
    shutil.copytree(design.DEFAULT_DIR, copied)
    expected = design.make_artifacts()
    monkeypatch.setattr(design, "make_artifacts", lambda directory: expected)
    (copied / "coverage.json").write_text("{}")
    with pytest.raises(ValueError):
        design.verify_bundle(copied)
