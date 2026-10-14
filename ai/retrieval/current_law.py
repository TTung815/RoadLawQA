"""Current-law hybrid retrieval shared by serving and evaluation; lazy model loading."""

import asyncio
import time
import threading
from typing import Any

from ai.agent.evidence import publishable_chunk
from ai.diagnostics import traced, record
from ai.retrieval.base import RetrievedChunk, Retriever
from ai.retrieval.query_expansion import checked_expansion, rerank_question
from evaluation.legacy_probe import load_bm25, runtime_id
from ingestion.legal_registry import PROJECT_ROOT, read_json
from ingestion.shadow_index import DEFAULT_OUTPUT_DIR, SHADOW_COLLECTION, index_properties


class LazyCurrentLawRetriever(Retriever):
    """Serving owns one lazily opened, read-only resource set."""

    def __init__(self):
        self._retriever = self._client = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._retriever is None:
                from types import SimpleNamespace
                from configs.settings import Settings
                from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST
                config = Settings()
                snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
                settings = SimpleNamespace(
                    host=config.weaviate_host, port=config.weaviate_port,
                    grpc_port=config.weaviate_grpc_port,
                    embedding_revision=snapshot["shadow_resources"]["embedding"]["revision"],
                    reranker_revision=config.reranker_revision,
                    retrieval_backend=config.retrieval_backend, hybrid_alpha=config.hybrid_alpha,
                    hybrid_candidate_limit=config.hybrid_candidate_limit,
                    compound_candidate_limit=config.compound_candidate_limit,
                    reranker_batch_size=config.reranker_batch_size,
                    embedding_device=config.embedding_device, reranker_device=config.reranker_device,
                )
                self._retriever, self._client = load_current_retriever(settings)
            return self._retriever

    async def search(self, query: str, top_k: int = 10, *, retrieval_query: str | None = None):
        started = time.perf_counter()
        retriever = await asyncio.to_thread(self._load)
        record("resource_initialization", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        options = {"retrieval_query": retrieval_query} if retrieval_query else {}
        return await retriever.search(query, top_k, **options)

    @property
    def runtime_devices(self) -> dict[str, str]:
        # Inspection must not initialize resources as a side effect.
        return dict(getattr(self._retriever, "runtime_devices", {}))

    async def fetch_article(self, law: str, article_no: str):
        retriever = await asyncio.to_thread(self._load)
        return await retriever.fetch_article(law, article_no)

    async def fetch_combination_rules(self, laws: list[str]):
        retriever = await asyncio.to_thread(self._load)
        return await retriever.fetch_combination_rules(laws)

    def close(self):
        with self._lock:
            if self._client is not None:
                self._client.close()
            self._retriever = self._client = None


def map_chunk(chunk: dict, score: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(id=runtime_id(chunk), text=chunk["text"], enriched_text=chunk["enriched_text"],
                          citation=chunk["display_citation"], score=score,
                          metadata={**{k: v for k, v in chunk.items() if k not in {"id", "text", "enriched_text"}},
                                    "processed_id": chunk["id"]})


def hybrid_candidates(rows: list[dict], lexical: list[tuple[int, float]], dense: list[tuple[dict, float]],
                      alpha: float, limit: int) -> list[tuple[dict, float]]:
    """Merge candidates by source ID, preserving distinct leaves with one citation."""
    maximum = max((score for _, score in lexical), default=0.0)
    by_id = {rows[i]["id"]: score / (maximum + 1e-8) for i, score in lexical}
    result = [(chunk, alpha * score + (1 - alpha) * by_id.get(chunk["id"], 0.0))
              for chunk, score in dense]
    seen = {chunk["id"] for chunk, _ in dense}
    result.extend((rows[i], (1 - alpha) * by_id[rows[i]["id"]])
                  for i, _ in lexical if rows[i]["id"] not in seen)
    return sorted(result, key=lambda pair: pair[1], reverse=True)[:limit]


def search_alpha(query: str) -> float:
    import re
    if re.search(r"\b(?:Chương|Mục|Điều|Khoản|Điểm)\s+[IVXLC\d]+", query, re.I):
        return 0.30
    if re.search(r"\d+\s*(?:giờ|km/h|triệu|nghìn|đồng|ngày|tháng|năm|%|cm3|cc|tấn|km|m|kW|điểm)\b", query, re.I):
        return 0.40
    return 0.75


class CurrentLawRetriever(Retriever):
    def __init__(self, chunks: list[dict], collection: Any, bm25: Any, embedder: Any, reranker: Any,
                 runtime_devices: dict[str, str] | None = None):
        self.rows = chunks
        self.by_id = {c["id"]: c for c in chunks}
        self.collection, self.bm25, self.embedder, self.reranker = collection, bm25, embedder, reranker
        self.runtime_devices = dict(runtime_devices or {})

    def _candidates(self, query: str, count: int) -> list[tuple[dict, float]]:
        import numpy as np
        from pyvi import ViTokenizer
        started = time.perf_counter()
        scores = self.bm25.get_scores(ViTokenizer.tokenize(query).split())
        lexical = [(int(i), float(scores[i])) for i in np.argsort(-scores)[:count]]
        record("bm25", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        vector = self.embedder.encode([query], normalize_embeddings=True)[0].tolist()
        record("query_embedding", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        response = self.collection.query.near_vector(near_vector=vector, limit=count,
                                                     return_metadata=["distance"])
        record("vector_search", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        dense = []
        for obj in response.objects:
            chunk = self.by_id[obj.properties["chunk_id"]]
            if obj.properties != index_properties(chunk):
                raise ValueError("shadow search returned changed properties")
            distance = obj.metadata.distance
            dense.append((chunk, 1.0 - distance if distance is not None else 0.0))
        dense = [(c, score) for c, score in dense if publishable_chunk(map_chunk(c))]
        lexical = [(i, score) for i, score in lexical if publishable_chunk(map_chunk(self.rows[i]))]
        return hybrid_candidates(self.rows, lexical, dense, search_alpha(query), count)

    def _search(self, query: str, top_k: int, retrieval_query: str | None = None) -> list[RetrievedChunk]:
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        expansion, reason = checked_expansion(query, retrieval_query)
        count = min(top_k * 4, 30)
        queries = [query, expansion] if expansion else [query]
        pools = [self._candidates(view, count) for view in queries]
        merged = {}
        for position in range(count):
            for pool in pools:
                if position < len(pool) and len(merged) < count:
                    item = pool[position]
                    merged.setdefault(item[0]["id"], item)
        candidates = list(merged.values())
        record("hybrid_queries", event="selection", retrieval_queries=queries, expansion_reason=reason)
        if not candidates:
            return []
        started = time.perf_counter()
        ranks = self.reranker.predict([[rerank_question(query, expansion), c["enriched_text"]] for c, _ in candidates])
        record("rerank", event="timing", duration_ms=(time.perf_counter() - started) * 1000, candidates=len(candidates))
        ranked = sorted(zip(candidates, ranks, strict=True), key=lambda x: float(x[1]), reverse=True)
        return [map_chunk(chunk, float(rank)) for ((chunk, _), rank) in ranked[:top_k]]

    @traced("retrieval_search")
    async def search(self, query: str, top_k: int = 10, *, retrieval_query: str | None = None) -> list[RetrievedChunk]:
        return await asyncio.to_thread(self._search, query, top_k, retrieval_query)


    async def fetch_combination_rules(self, laws: list[str]):
        """Read explicit multi-violation rules in retrieved documents, without LLMs.

        No document/article numbers or legal consequences are encoded here.
        Selection is not a determination that the rule applies to the question.
        """
        import re
        return [map_chunk(row) for row in self.rows if row["law"] in laws
                and row.get("publication_eligible") is not False and row.get("active_at_cutoff") is not False
                and re.search(r"nhiều hành vi|nhiều lần|cùng một lần", row["text"], re.I)
                and re.search(r"xử phạt|phạt tiền|trừ điểm", row["text"], re.I)]

    async def fetch_article(self, law: str, article_no: str):
        laws = {row["law"] for row in self.rows}
        candidates = [law] if law in laws else [name for name in laws if law.casefold() in name.casefold()]
        if len(candidates) != 1:
            return []
        return [map_chunk(row) for row in self.rows if row["law"] == candidates[0]
                and str(row["article_no"]) == str(article_no)
                and row.get("publication_eligible") is not False and row.get("active_at_cutoff") is not False]


def load_current_retriever(settings):
    """Open the existing frozen index read-only; shared by API and evaluation."""
    if getattr(settings, "retrieval_backend", "frozen") == "structured":
        from ai.retrieval.structured import load_structured_retriever
        return load_structured_retriever(settings)
    from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST, verify_frozen_snapshot
    from evaluation.snapshot import digest
    from ai.retrieval.devices import resolve_device
    from ingestion.shadow_index import connect_local, export_collection, load_embedder, model_provenance

    embedding_device = resolve_device(getattr(settings, "embedding_device", "cpu"))
    reranker_device = resolve_device(getattr(settings, "reranker_device", "cpu"))
    verify_frozen_snapshot()
    snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
    chunks = read_json(PROJECT_ROOT / snapshot["processed_corpus"]["path"])["chunks"]
    client = connect_local(settings.host, settings.port, settings.grpc_port)
    try:
        # Never create/rebuild; verify the entire existing shadow export before using it.
        if not client.collections.exists(SHADOW_COLLECTION):
            raise ValueError("frozen shadow collection is unavailable")
        collection = client.collections.get(SHADOW_COLLECTION)
        records, schema = export_collection(collection)
        actual = {"objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])), "schema_sha256": digest(schema)}
        if actual != snapshot["shadow_resources"]["collection_fingerprint"]:
            raise ValueError("live shadow no longer matches the frozen snapshot")
        embedder = load_embedder()
        embedder.to(embedding_device)
        if model_provenance(embedder)["revision"] != settings.embedding_revision:
            raise ValueError("embedding revision differs from locked settings")
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=reranker_device,
                                revision=settings.reranker_revision, local_files_only=True)
        if getattr(reranker.model.config, "_commit_hash", None) != settings.reranker_revision:
            raise ValueError("reranker revision differs from locked settings")
        reranker.model.to(reranker_device)
        bm25 = load_bm25(DEFAULT_OUTPUT_DIR / "bm25_index.pkl")
        return CurrentLawRetriever(chunks, collection, bm25, embedder, reranker,
                                   {"embedding": str(embedder.device),
                                    "reranker": str(next(reranker.model.parameters()).device),
                                    "hybrid_search": "cpu"}), client
    except Exception:
        client.close()
        raise
