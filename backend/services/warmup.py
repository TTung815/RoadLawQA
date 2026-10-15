"""Load serving retrieval in the background at startup, never blocking requests."""

import logging
import time

from ai.retrieval.runtime import LazyRetriever

logger = logging.getLogger("uvicorn.error")
# A short generic query: loads the index, embedder and reranker and runs one
# rerank pass so the first user question does not pay the device warm-up.
WARMUP_QUERY = "Đi xe máy không đội mũ bảo hiểm bị phạt bao nhiêu?"


async def warm_up(retriever: LazyRetriever, state: dict) -> None:
    state["warmup"] = "running"
    started = time.perf_counter()
    try:
        await retriever.search(WARMUP_QUERY, top_k=1)
    except Exception as exc:
        # Requests still lazy-load later; log only the error type, never its text.
        state["warmup"] = "failed"
        logger.warning("Retrieval warm-up failed (%s); models load on the first question.", type(exc).__name__)
        return
    state["warmup"] = "done"
    logger.info("Retrieval warm-up finished in %.1fs; devices %s.",
                time.perf_counter() - started, retriever.runtime_devices)
