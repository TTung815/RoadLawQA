"""Regressions for stale gold, optional evidence and conditional response scoring."""

import json
import shutil

import pytest

from evaluation import core_runner as runner
from evaluation import core_scoring as scoring
from evaluation import revised_current_law_dataset as dataset
from evaluation.core_schema import Question, RunPlan, RunSettings, SemanticReview
from evaluation.phase3_design import missing_facets
from evaluation.snapshot import digest
from ingestion.legal_registry import file_digest


@pytest.fixture(scope="module")
def cases():
    return {case.id: case for case in dataset.load_cases()}


def test_previously_abstaining_cases_have_supported_required_facets(cases):
    for number in (10, 23, 29, 43):
        case = cases[f"current_law_{number:03d}"]
        assert case.gold.publication.disposition == "publish"
        refs = [r.processed_id for g in case.gold.evidence_groups for r in g.references]
        assert not missing_facets(case, refs)
    assert any(r.processed_id.endswith("-d5-k2") for g in cases["current_law_023"].gold.evidence_groups for r in g.references)
    age_refs = {r.processed_id for g in cases["current_law_043"].gold.evidence_groups for r in g.references}
    assert age_refs == {"90-vbhn-vpqh-2026-d5-k1-pa", "90-vbhn-vpqh-2026-d11-k5"}


def test_unrequested_sanction_and_definition_do_not_reduce_coverage(cases):
    for number, core_source in [(49, "55-vbhn-vpqh-d12-k1"), (50, "55-vbhn-vpqh-d33-k1-pc")]:
        case = cases[f"current_law_{number:03d}"]
        assert not missing_facets(case, [core_source])
        assert len(scoring.gold_view(case.gold)["facets"]) < len(case.gold.required_facets)
    assert "f2" in scoring.gold_view(cases["current_law_018"].gold)["facets"]


def test_v2_tamper_is_rejected(tmp_path):
    target = tmp_path / "labels"
    shutil.copytree(dataset.DEFAULT_DIR, target)
    with (target / "cases.jsonl").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="artifact changed"):
        dataset.load_cases(target)


def test_question_plan_and_gold_are_bound_to_v2_without_answer_leakage(cases, monkeypatch):
    monkeypatch.setattr(dataset, "load_cases", lambda: list(cases.values()))
    questions, binding, version = runner.questions_for("reviewed")
    assert version == dataset.DATASET_ID
    assert binding == file_digest(dataset.DEFAULT_DIR / "manifest.json")
    assert len(questions) == 50
    assert "hai hàng ghế" in questions[6].current_query
    assert "không gây tai nạn" in questions[12].current_query
    assert "tay phải" in questions[32].current_query
    assert "reference_answer" not in questions[0].model_dump()
    plan = RunPlan(suite="reviewed", dataset_version=version, dataset_binding=binding,
                   snapshot_sha256="0" * 64, code_hashes={}, questions=questions,
                   settings=RunSettings(model="fake", embedding_revision="fake", reranker_revision="fake"))
    assert len(scoring.load_gold(plan)) == 50
    plan.dataset_version = "current_law_20260922_reviewed_v1"
    with pytest.raises(ValueError, match="version mismatch"):
        scoring.load_gold(plan)


def fixture_run(tmp_path, case, status):
    chunk = next(iter(dataset.source_chunks().values()))
    from evaluation.core_runtime import map_chunk
    retrieved = map_chunk(chunk).model_dump(mode="json")
    output = {"status": status, "retrieval": {"chunks": [retrieved]},
              "answer": {"text": "Synthetic scorer fixture, not a legal answer.", "claims": [{
                  "text": "Synthetic claim.", "citations": [{"chunk_id": retrieved["id"],
                                                              "citation": chunk["display_citation"]}]}]}}
    plan = RunPlan(suite="reviewed", dataset_version=dataset.DATASET_ID, dataset_binding="0" * 64,
                   snapshot_sha256="0" * 64, code_hashes={},
                   questions=[Question(id=case.id, current_query=case.query)],
                   settings=RunSettings(model="fake", embedding_revision="fake", reranker_revision="fake"))
    record = {"id": case.id, "mode": "end_to_end", "execution_kind": "live", "output": output,
              "error": None, "elapsed_ms": 1, "usage": {"llm_calls": 0, "input_tokens": None,
              "output_tokens": None, "cost_usd": None}}
    record["result_sha256"] = digest(record)
    (tmp_path / "results.jsonl").write_text(json.dumps(record) + "\n")
    return plan, record


@pytest.mark.parametrize("appropriate,facet_score,expected,pending", [
    (True, 1, 1, 0), (False, 1, 0, 0), (None, 1, 0, 1), (True, .5, 0, 0),
])
def test_conditional_status_requires_semantic_approval_and_complete_facets(
        tmp_path, monkeypatch, cases, appropriate, facet_score, expected, pending):
    case = cases["current_law_044"]
    plan, record = fixture_run(tmp_path, case, "needs_clarification")
    monkeypatch.setattr(scoring, "verify_run", lambda _: (plan, [record]))
    item = scoring.gold_view(case.gold)
    monkeypatch.setattr(scoring, "load_gold", lambda *_: {case.id: item})
    review = SemanticReview(id=case.id, result_sha256=record["result_sha256"], reviewer="test",
                            facet_scores={f: facet_score for f in item["facets"]}, citation_support=True,
                            safe_publication=True, response_appropriate=appropriate,
                            notes="Synthetic labels test scorer gates, not model/legal quality.")
    path = tmp_path / "reviews.jsonl"
    path.write_text(review.model_dump_json()+"\n")
    report = scoring.score_run(tmp_path, path)["modes"]["end_to_end"]
    assert report["all_required_pass_confirmed_over_all"]["numerator"] == expected
    assert report["semantic_pending"] == pending


def test_age_review_packet_contains_added_sources_and_status_criteria(tmp_path, monkeypatch, cases):
    case = cases["current_law_043"]
    plan, record = fixture_run(tmp_path, case, "answered")
    monkeypatch.setattr(scoring, "verify_run", lambda _: (plan, [record]))
    monkeypatch.setattr(scoring, "load_gold", lambda *_: {case.id: scoring.gold_view(case.gold)})
    packet = tmp_path / "packet"
    scoring.make_review_packet(tmp_path, packet)
    text = (packet / "REVIEW.md").read_text()
    assert "khoản 5 Điều 11" in text and "90/VBHN-VPQH" in text
    assert "response_appropriate" in text
    template = json.loads((packet / "reviews_template.jsonl").read_text())
    assert template["response_appropriate"] is None
