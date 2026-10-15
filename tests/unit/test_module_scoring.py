import math
from types import SimpleNamespace

import pytest

from evaluation.module_scoring import rank_metrics, gold_units, facet_coverage, score_ranking
from evaluation import revised_current_law_dataset as labels


def test_worked_example_same_hit_better_recall_and_rank():
    before = [f"x{i}" for i in range(40)]
    before[7], before[13] = "A", "B"
    after = ["A", "B"] + [i for i in before if i not in {"A", "B"}]
    a, b = rank_metrics(before, {"A", "B"}, 10), rank_metrics(after, {"A", "B"}, 10)
    assert a == {"hit": 1, "recall": .5, "rr": .125,
                 "ndcg": (1/math.log2(9))/(1+1/math.log2(3))}
    assert b == {"hit": 1, "recall": 1, "rr": 1, "ndcg": 1}


def test_empty_gold_is_na_but_missing_relevant_in_pool_is_zero():
    assert all(v is None for v in rank_metrics(["a"], set(), 10).values())
    assert all(v == 0 for v in rank_metrics([], {"a"}, 10).values())
    with pytest.raises(ValueError):
        rank_metrics(["a", "a"], {"a"}, 10)


def fake_gold():
    # A+B are alternatives for one facet; C+D jointly support another.
    def ref(id_): return SimpleNamespace(processed_id=id_, role="support")
    return SimpleNamespace(evidence_groups=[
        SimpleNamespace(id="g1", match="any", references=[ref("a"), ref("b")]),
        SimpleNamespace(id="g2", match="all", references=[ref("c"), ref("d")]),
        SimpleNamespace(id="g3", match="all", references=[ref("e")])], required_facets=[
        SimpleNamespace(id="f1", required=True, support_state="positive_support", evidence_group_ids=["g1"]),
        SimpleNamespace(id="f2", required=True, support_state="positive_support", evidence_group_ids=["g2"]),
        SimpleNamespace(id="optional", required=False, support_state="positive_support", evidence_group_ids=["g3"])])


def units():
    return {identity: {"id": identity, "metadata": {"source_processed_ids": leaves,
            "publication_eligible": True, "active_at_cutoff": True}}
            for identity, leaves in [("A", ["a"]), ("B", ["b"]), ("CD", ["c", "d"]), ("E", ["e"])]}


def test_structured_dedup_optional_exclusion_and_any_all_coverage():
    corpus = units()
    mapping = {leaf: id_ for id_, u in corpus.items() for leaf in u["metadata"]["source_processed_ids"]}
    gold = fake_gold()
    assert gold_units(gold, mapping) == {"A", "B", "CD"}
    assert facet_coverage(gold, ["A"], corpus) == .5
    assert facet_coverage(gold, ["A", "CD"], corpus) == 1
    assert rank_metrics(["A", "CD"], gold_units(gold, mapping), 10)["recall"] == pytest.approx(2/3)
    with pytest.raises(ValueError, match="missing"):
        gold_units(gold, {"a": "A"})


def test_reranker_cannot_claim_sources_outside_candidate_pool():
    trace = {"candidate_ids": ["A", "B"], "reranked": [{"chunk_id": "CD"}, {"chunk_id": "A"}],
             "top_k": 1, "selected_ids": ["CD"]}
    with pytest.raises(ValueError, match="same unique"):
        score_ranking(trace, fake_gold(), units(), 1)
    trace["reranked"] = [{"chunk_id": "B"}, {"chunk_id": "A"}]
    with pytest.raises(ValueError, match="top-k"):
        score_ranking(trace, fake_gold(), units(), 1)
    trace["selected_ids"] = ["B"]
    assert score_ranking(trace, fake_gold(), units(), 1)["candidate_recall"] == pytest.approx(2/3)


def test_frozen_v2_gold_maps_all_required_support_to_structured_units():
    from ingestion.structured_corpus import load_bundle
    corpus = {u["id"]: u for u in load_bundle()["chunks"]}
    mapping = {leaf: u["id"] for u in corpus.values() for leaf in u["metadata"]["source_processed_ids"]}
    for case in labels.load_cases():
        relevant = gold_units(case.gold, mapping)
        assert relevant
        assert facet_coverage(case.gold, list(relevant), corpus) == 1
