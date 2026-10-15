"""Inspect retrieval/context and timings without initializing an LLM provider."""

import time

from ai.agent.evidence import evidence_payload
from ai.diagnostics import PipelineError, TRACE
from ai.retrieval.neighborhood import LegalNeighborhoodExpander


async def inspect_retrieval(retriever, query: str, top_k: int = 10) -> dict:
    trace = []
    token = TRACE.set(trace)
    started = time.perf_counter()
    try:
        initial = await retriever.search(query, top_k)
        selection = await LegalNeighborhoodExpander(
            retriever.fetch_article, combination_lookup=retriever.fetch_combination_rules
        ).expand_references(initial, question=query)
        chunks = list({c.id: c for c in [*initial, *selection.chunks]}.values())
        contexts = evidence_payload(chunks)
        return {"query": query, "top_k": top_k, "llm_calls": 0,
                "devices": dict(getattr(retriever, "runtime_devices", {})),
                "initial_chunk_ids": [c.id for c in initial], "added_chunk_ids": [c.id for c in selection.chunks],
                "chunks": [c.model_dump(mode="json") for c in chunks], "context_preview": contexts,
                "timings_ms": {**{e["stage"]: e["duration_ms"] for e in trace if e.get("event") == "timing"},
                               "context_lookup": selection.lookup_ms,
                               "total_including_initialization": (time.perf_counter() - started) * 1000},
                "note": "Điểm reranker/hybrid dùng xếp hạng, không phải xác suất đúng. Lần đầu gồm tải tài nguyên."}
    except Exception as exc:
        raise PipelineError("retrieval_inspection", type(exc).__name__) from exc
    finally:
        TRACE.reset(token)
