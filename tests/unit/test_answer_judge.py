"""Rubric judge labels are derived in code and comparable with owner-approved reviews."""

import json

import pytest

from evaluation.answer_judge import (RubricJudgment, agreement, derive_label, human_label, judged_case,
                                     response_view, summarize, validate, wilson)


def record():
    chunk = {"id": "s1", "enriched_text": "Phạt tiền từ 4.000.000 đồng đến 6.000.000 đồng."}
    return {"id": "q1", "result_sha256": "h1", "error": None, "output": {
        "status": "answered", "limitations": [], "follow_up_questions": [],
        "answer": {"claims": [{"text": "Phạt 4–6 triệu đồng.", "citations": [{"chunk_id": "s1"}]}]},
        "retrieval": {"chunks": [chunk]}},
        "diagnostics": [{"stage": "generation", "event": "draft", "draft": {
            "claims": [{"text": "Phạt 4–6 triệu đồng.", "chunk_ids": ["s1"]}], "limitations": ["Chưa rõ điểm."],
            "follow_up_questions": [], "response_kind": "partial"}}]}


def judgment(**changes):
    value = {"facets": [{"id": "f1", "score": 1, "reason": "ok"}], "incorrect_statements": [],
             "misgrounded_claims": [], "status_criteria_met": True, "status_reason": "ok", **changes}
    return RubricJudgment.model_validate(value)


@pytest.mark.parametrize("scores, status_ok, hallucinated, has_claims, label", [
    ([1, 1], True, False, True, "correct"),
    ([1, 1], False, False, True, "status_issue"),
    ([1, 0], True, False, True, "incomplete"),
    ([0], True, False, True, "not_answered"),
    ([1], True, False, False, "not_answered"),
    # A wrong statement outranks every other label, even with full facet scores.
    ([1, 1], True, True, True, "hallucinated"),
])
def test_label_is_derived_from_facets_status_and_errors(scores, status_ok, hallucinated, has_claims, label):
    assert derive_label(scores, status_ok, hallucinated, has_claims) == label


def test_draft_view_is_scored_before_verification_with_its_own_status():
    final, draft = response_view(record(), "final"), response_view(record(), "draft")
    assert final["status"] == "answered" and draft["status"] == "partial_answer"
    assert draft["limitations"] == ["Chưa rõ điểm."] and draft["sources"] == final["sources"]
    # A gold that only allows "answered" makes the draft's partial status an issue.
    assert judged_case(judgment(), draft, ["answered"])["label"] == "status_issue"
    assert judged_case(judgment(), final, ["answered"])["label"] == "correct"


def test_incorrect_statement_must_quote_the_response_verbatim():
    view = response_view(record(), "final")
    validate(judgment(incorrect_statements=[{"quote": "Phạt 4–6 triệu", "reason": "x"}]), ["f1"], view)
    with pytest.raises(ValueError):
        validate(judgment(incorrect_statements=[{"quote": "Phạt 10 triệu", "reason": "x"}]), ["f1"], view)
    with pytest.raises(ValueError):
        validate(judgment(), ["f1", "f2"], view)


def test_owner_reviews_of_the_reviewed_50_map_to_the_approved_label_counts():
    from pathlib import Path
    path = Path("outputs/evaluation/rag-modules-v2-20261014-v1/review/reviews_ai.jsonl")
    if not path.exists():
        pytest.skip("local run artifacts are not distributed with the repository")
    labels = [human_label(json.loads(line)) for line in path.read_text().splitlines()]
    assert {label: labels.count(label) for label in set(labels)} == {
        "correct": 44, "status_issue": 1, "incomplete": 4, "not_answered": 1}


def test_summary_reports_wilson_intervals_and_agreement(tmp_path):
    cases = [{"id": f"q{i}", "result_sha256": f"h{i}", "error": None,
              "judged": {"label": "correct" if i < 9 else "incomplete", "facet_score": 1, "facet_count": 1,
                         "status_ok": True, "hallucinated": False}} for i in range(10)]
    report = summarize(cases)
    assert report["accuracy"] == .9 and report["hallucination_rate"] == 0
    assert report["hallucination_ci95"][1] == pytest.approx(wilson(0, 10)[1]) and report["hallucination_ci95"][1] > .25
    reviews = tmp_path / "reviews.jsonl"
    reviews.write_text("".join(json.dumps({"id": f"q{i}", "result_sha256": f"h{i}", "facet_scores": {"f1": 1},
                                           "citation_support": True, "safe_publication": True,
                                           "response_appropriate": True}) + "\n" for i in range(10)))
    result = agreement(cases, reviews)
    assert result["label_agreement"] == .9 and result["disagreements"] == [
        {"id": "q9", "human": "correct", "judge": "incomplete"}]
