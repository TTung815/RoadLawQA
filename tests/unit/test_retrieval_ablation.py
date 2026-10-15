"""Ablation scoring without Weaviate/models: each alpha keeps its own native order."""

import pytest

from ai.diagnostics import record
from ai.retrieval.structured import map_unit
from evaluation import retrieval_ablation
from evaluation import revised_current_law_dataset as revised
from evaluation.module_scoring import gold_units
from ingestion.structured_corpus import load_bundle


class FakeRetriever:
    """Native order puts gold first only for alpha 0.5; rerank always does."""

    candidate_limit, compound_candidate_limit, runtime_devices = 20, 32, {"reranker": "fake"}

    def __init__(self):
        self.alpha = None
        units = load_bundle()["chunks"]
        self.units = {u["id"]: u for u in units}
        self.filler = [u["id"] for u in units if u["metadata"]["publication_eligible"]][:20]
        mapping = {leaf: u["id"] for u in units for leaf in u["metadata"]["source_processed_ids"]}
        self.gold = {c.query: sorted(gold_units(c.gold, mapping)) for c in revised.load_cases()}

    async def search(self, query, top_k=10):
        gold = self.gold[query]
        rest = [i for i in self.filler if i not in gold][:20 - len(gold)]
        native = gold + rest if self.alpha == .5 else rest + gold
        reranked = gold + rest
        record("retrieval_ranking", event="result", candidate_ids=native,
               reranked=[{"chunk_id": i, "score": 1.0} for i in reranked], selected_ids=reranked[:top_k])
        record("rerank", event="timing", duration_ms=1.0)
        return [map_unit(self.units[i]) for i in reranked[:top_k]]

    async def fetch_article(self, law, article_no):
        return []

    async def fetch_combination_rules(self, laws):
        return []


@pytest.mark.asyncio
async def test_each_alpha_scores_its_native_order_and_the_reranked_pool():
    report = await retrieval_ablation.evaluate(FakeRetriever(), [0.0, 0.5])
    bm25, hybrid = report["configs"]
    assert (bm25["label"], hybrid["label"]) == ("BM25 (sparse)", "Hybrid α=0.5")
    assert hybrid["metrics"]["no_rerank"]["10"]["recall"] == 1
    assert bm25["metrics"]["no_rerank"]["1"]["hit"] < 1
    assert bm25["metrics"]["rerank"]["10"]["recall"] == hybrid["metrics"]["rerank"]["10"]["recall"] == 1
    assert bm25["cases"] == 50 and bm25["final_evidence"]["facet_coverage"] == 1
    assert "Recall@10" in retrieval_ablation.render(report)
