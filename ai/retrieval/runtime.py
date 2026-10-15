"""Serving retriever opened lazily (or by warm-up): index, embedder and reranker load once."""

import asyncio
import time
import threading

from ai.diagnostics import record
from ai.retrieval.base import Retriever
from ingestion.legal_registry import read_json


class LazyRetriever(Retriever):
    """Serving owns one lazily opened, read-only resource set."""

    def __init__(self):
        self._retriever = self._client = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._retriever is None:
                from types import SimpleNamespace
                from configs.settings import Settings
                from ingestion.structured_corpus import DEFAULT_BUNDLE
                config = Settings()
                # The corpus manifest locks the embedding model its vectors were built with.
                manifest = read_json(DEFAULT_BUNDLE / "manifest.json")
                settings = SimpleNamespace(
                    host=config.weaviate_host, port=config.weaviate_port,
                    grpc_port=config.weaviate_grpc_port,
                    embedding_revision=manifest["embedding_revision"],
                    reranker_revision=config.reranker_revision,
                    retrieval_backend=config.retrieval_backend, hybrid_alpha=config.hybrid_alpha,
                    hybrid_candidate_limit=config.hybrid_candidate_limit,
                    compound_candidate_limit=config.compound_candidate_limit,
                    reranker_batch_size=config.reranker_batch_size,
                    embedding_device=config.embedding_device, reranker_device=config.reranker_device,
                )
                self._retriever, self._client = load_retriever(settings)
            return self._retriever

    async def search(self, query: str, top_k: int = 10, *, retrieval_query: str | None = None):
        started = time.perf_counter()
        retriever = await asyncio.to_thread(self._load)
        record("resource_initialization", event="timing", duration_ms=(time.perf_counter() - started) * 1000)
        options = {"retrieval_query": retrieval_query} if retrieval_query else {}
        return await retriever.search(query, top_k, **options)

    @property
    def loaded(self) -> bool:
        # Readiness must not initialize resources as a side effect.
        return self._retriever is not None

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


def load_retriever(settings):
    """Open the existing structured index read-only; shared by API and evaluation."""
    if getattr(settings, "retrieval_backend", "structured") != "structured":
        raise ValueError("only the structured retrieval backend is supported")
    from ai.retrieval.structured import load_structured_retriever
    return load_structured_retriever(settings)
