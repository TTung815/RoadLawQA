"""Native Weaviate hybrid retrieval over versioned, structure-aware legal chunks."""

import asyncio
import math
import re
import time

from ai.diagnostics import record, traced
from ai.retrieval.base import RetrievedChunk, Retriever
from ai.retrieval.query_expansion import checked_expansion, question_focus, rerank_question
from ingestion.structured_corpus import lexical_text, load_bundle, DEFAULT_BUNDLE
from ingestion.structured_index import COLLECTION, DEFAULT_INDEX, properties, verify_index


def map_unit(unit: dict, score: float = 0.0, **retrieval) -> RetrievedChunk:
    return RetrievedChunk(id=unit["id"], text=unit["text"], enriched_text=unit["embedding_text"],
                          citation=unit["metadata"]["display_citation"], score=score,
                          metadata={**unit["metadata"], "processed_id": unit["id"], **retrieval})


def age_penalty_focus(query: str) -> str | None:
    """Search the age condition when a penalty scenario includes an age.

    This is a retrieval facet, not a legal inference: no age threshold, document
    or answer is selected here. The original scenario remains a search view and
    is passed unchanged to generation/verification.
    """
    if not re.search(r"\b(?:phạt|xử phạt|xử lý vi phạm)\b", query, re.I):
        return None
    ages = re.findall(r"(?:từ\s+đủ\s+|dưới\s+|trên\s+|đủ\s+)?\d+\s*tuổi", query, re.I)
    if not ages and not re.search(r"độ tuổi|chưa thành niên|chưa đủ tuổi|con (?:của )?tôi|\bcháu\b|trẻ em", query, re.I):
        return None
    return "Điều kiện độ tuổi chịu xử phạt vi phạm hành chính, cảnh cáo và phạt tiền. " + "; ".join(ages)


class StructuredRetriever(Retriever):
    def __init__(self, units: list[dict], collection, embedder, reranker, alpha: float = 0.5,
                 candidate_limit: int = 20, compound_candidate_limit: int = 32,
                 runtime_devices: dict[str, str] | None = None):
        if not 20 <= candidate_limit <= compound_candidate_limit <= 40:
            raise ValueError("candidate limits must satisfy 20 <= base <= compound <= 40")
        self.units, self.collection, self.embedder, self.reranker = units, collection, embedder, reranker
        self.by_id = {u["id"]: u for u in units}
        self.alpha = alpha
        self.candidate_limit = candidate_limit
        self.compound_candidate_limit = compound_candidate_limit
        self.runtime_devices = dict(runtime_devices or {})

    def _exact_candidates(self, query: str) -> list[dict]:
        """Only an explicit, unambiguous document + article can add direct lookup candidates."""
        article = re.search(r"\bđiều\s+(\d+)\b", query, re.I)
        if not article:
            return []
        docs = {u["metadata"]["document_id"] for u in self.units}
        matches = [doc for doc in docs if (doc.split('-')[0].isdigit() and '-vbhn-' in doc and
                   re.search(rf"\b{doc.split('-')[0]}\s*/\s*VBHN", query, re.I)) or
                   (doc.startswith("nd168") and re.search(r"\b168\s*/\s*2024", query))]
        if len(matches) != 1:
            return []
        clause = re.search(r"\bkhoản\s+(\d+[a-z]?)\b", query, re.I)
        point = re.search(r"\bđiểm\s+([a-zđ]\d?)\b", query, re.I)
        return [u for u in self.units if self._eligible(u) and u["metadata"]["document_id"] == matches[0]
                and u["metadata"]["article_no"] == article[1]
                and (not clause or u["metadata"]["clause_no"] == clause[1] or u["metadata"]["granularity"] == "article")
                and (not point or u["metadata"]["point"] in {None, point[1].casefold()})][:20]

    @staticmethod
    def _eligible(unit: dict) -> bool:
        return unit["metadata"]["publication_eligible"] and unit["metadata"]["active_at_cutoff"]

    def _search(self, query: str, top_k: int, retrieval_query: str | None = None) -> list[RetrievedChunk]:
        from weaviate.classes.query import Filter, HybridFusion, MetadataQuery
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        compound = bool(re.search(r"\b(?:đồng thời|cùng lúc)\b|\bvừa\b.+\bvừa\b", query, re.I))
        count = min(max(top_k * 4, self.compound_candidate_limit if compound else self.candidate_limit), 40)
        age_focus = age_penalty_focus(query)
        focus = age_focus or question_focus(query)
        focus_label = "age_penalty" if age_focus else "question_focus"
        expansion, reason = checked_expansion(query, retrieval_query)
        # Keep age coverage in the same second view, never add a third search.
        secondary = (expansion + "\n" + age_focus if age_focus else expansion) if expansion else focus
        secondary_label = "query_expansion" if expansion else focus_label
        queries = [query, secondary] if secondary else [query]
        ranking_query = focus or rerank_question(query, expansion)
        started = time.perf_counter()
        vectors = self.embedder.encode(queries, normalize_embeddings=True)
        record("query_embedding", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        pools, scores = [], {}
        for view, vector in zip(queries, vectors, strict=True):
            response = self.collection.query.hybrid(
                query=lexical_text(view), vector=vector.tolist(), query_properties=["lexical_text"],
                alpha=self.alpha, fusion_type=HybridFusion.RELATIVE_SCORE, limit=count,
                filters=(Filter.by_property("publication_eligible").equal(True) &
                         Filter.by_property("active_at_cutoff").equal(True) &
                         Filter.by_property("legal_as_of").equal("2026-09-22")),
                return_metadata=MetadataQuery(score=True, explain_score=True))
            pool = []
            for obj in response.objects:
                unit = self.by_id[obj.properties["chunk_id"]]
                if obj.properties != properties(unit) or not self._eligible(unit):
                    raise ValueError("native hybrid returned changed or blocked content")
                pool.append(unit)
                scores.setdefault(unit["id"], {
                    "hybrid_score": obj.metadata.score, "hybrid_explanation": obj.metadata.explain_score,
                    "hybrid_query_view": "original" if view == query else secondary_label})
            pools.append(pool)
        record("native_hybrid", event="timing", duration_ms=(time.perf_counter() - started) * 1000,
               candidates=sum(len(pool) for pool in pools), query_views=len(queries), alpha=self.alpha,
               retrieval_queries=queries, expansion_reason=reason)
        # Interleave views and deduplicate inside the same rerank budget. The
        # original view keeps the scenario; the focus represents the question.
        # At most two native searches; the optional rewrite came from routing.
        candidates = {}
        for position in range(count):
            for pool in pools:
                if position < len(pool) and len(candidates) < count:
                    unit = pool[position]
                    candidates[unit["id"]] = unit
        for unit in self._exact_candidates(query):
            candidates[unit["id"]] = unit
            scores.setdefault(unit["id"], {})["exact_lookup"] = True
        if not candidates:
            return []
        # At most 40 hybrid + 20 explicit candidates, one bounded rerank pass.
        units = list(candidates.values())
        started = time.perf_counter()
        ranks = self.reranker.predict([[ranking_query, u["embedding_text"]] for u in units])
        record("rerank", event="timing", duration_ms=(time.perf_counter() - started) * 1000,
               candidates=len(units), compound_query=compound, question_focus=bool(focus),
               age_penalty_focus=bool(age_focus))
        if not all(math.isfinite(float(x)) for x in ranks):
            raise ValueError("non-finite reranker score")
        ordered = sorted(zip(units, ranks, strict=True), key=lambda x: float(x[1]), reverse=True)
        return [map_unit(u, float(rank), rerank_query_view=focus_label if focus else secondary_label if expansion else "original",
                         **scores[u["id"]]) for u, rank in ordered[:top_k]]

    @traced("retrieval_search")
    async def search(self, query: str, top_k: int = 5, *, retrieval_query: str | None = None):
        return await asyncio.to_thread(self._search, query, top_k, retrieval_query)

    async def fetch_article(self, law: str, article_no: str):
        laws = {u["metadata"]["law"] for u in self.units}
        matches = [name for name in laws if law.casefold() in name.casefold()]
        if len(matches) != 1:
            return []
        return [map_unit(u) for u in self.units if self._eligible(u) and u["metadata"]["law"] == matches[0]
                and u["metadata"]["article_no"] == str(article_no)]

    async def fetch_combination_rules(self, laws: list[str]):
        return [map_unit(u) for u in self.units if self._eligible(u) and u["metadata"]["law"] in laws
                and re.search(r"nhiều hành vi|nhiều lần|cùng một lần", u["text"], re.I)
                and re.search(r"xử phạt|phạt tiền|trừ điểm", u["text"], re.I)]


def load_structured_retriever(settings):
    from sentence_transformers import CrossEncoder
    from ai.retrieval.reranking import LengthBatchedReranker
    from ai.retrieval.devices import resolve_device
    from ingestion.legal_registry import read_json, file_digest
    from ingestion.shadow_index import connect_local, load_embedder, model_provenance
    embedding_device = resolve_device(getattr(settings, "embedding_device", "cpu"))
    reranker_device = resolve_device(getattr(settings, "reranker_device", "cpu"))
    corpus = load_bundle()
    expected = getattr(settings, "retrieval_corpus_sha256", None)
    if expected and expected != file_digest(DEFAULT_BUNDLE / "chunks.json"):
        raise ValueError("structured corpus differs from execution plan")
    expected_index = getattr(settings, "retrieval_index_sha256", None)
    if expected_index and expected_index != file_digest(DEFAULT_INDEX / "index.json"):
        raise ValueError("structured index differs from execution plan")
    client = connect_local(settings.host, settings.port, settings.grpc_port)
    try:
        if not client.collections.exists(COLLECTION):
            raise ValueError("Build the structured collection before serving")
        collection = client.collections.get(COLLECTION)
        receipt = verify_index(collection)
        embedder = load_embedder()
        # Query inference can move device without rebuilding the frozen vectors.
        # The corpus/index builder keeps its original, recorded CPU behavior.
        embedder.to(embedding_device)
        if model_provenance(embedder)["revision"] != settings.embedding_revision or receipt["embedding"]["revision"] != settings.embedding_revision:
            raise ValueError("embedding revision differs from execution settings")
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=reranker_device, revision=settings.reranker_revision,
                               local_files_only=True)
        if getattr(reranker.model.config, "_commit_hash", None) != settings.reranker_revision:
            raise ValueError("reranker revision differs from execution settings")
        # This CrossEncoder version moves weights only on first predict().
        # Place them now so runtime device reporting reflects real parameters.
        reranker.model.to(reranker_device)
        return StructuredRetriever(
            corpus["chunks"], collection, embedder,
            LengthBatchedReranker(reranker, getattr(settings, "reranker_batch_size", 4)),
            getattr(settings, "hybrid_alpha", 0.5), getattr(settings, "hybrid_candidate_limit", 20),
            getattr(settings, "compound_candidate_limit", 32),
            {"embedding": str(embedder.device),
             "reranker": str(next(reranker.model.parameters()).device),
             "hybrid_search": "cpu"}), client
    except Exception:
        client.close()
        raise
