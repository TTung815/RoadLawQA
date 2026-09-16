# -*- coding: utf-8 -*-
"""
Legacy Retriever Adapter
Adapts existing backend.retriever_custom.retrieve into the V2 Retriever interface.
Uses lazy import to ensure zero model loading or Weaviate connection at import time.
"""
import asyncio
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from ai.retrieval.base import RetrievedChunk, Retriever


class LegacyRetrieverAdapter(Retriever):
    """
    Adapter implementing the V2 Retriever interface around the baseline
    backend.retriever_custom.retrieve function.
    """

    def __init__(self, retrieve_fn: Optional[Callable[..., Any]] = None):
        """
        Args:
            retrieve_fn: Optional custom/mock callable for retrieve. If None,
                         backend.retriever_custom.retrieve is imported lazily.
        """
        self._retrieve_fn = retrieve_fn

    def _resolve_retrieve_fn(self) -> Callable[..., Any]:
        if self._retrieve_fn is None:
            # Lazy import: models and Weaviate connection only happen here
            from backend.retriever_custom import retrieve
            self._retrieve_fn = retrieve
        return self._retrieve_fn

    def _sync_search(self, query: str, top_k: int) -> Any:
        # First-use import and retrieval both run in the worker thread.
        fn = self._resolve_retrieve_fn()
        return fn(query, k=top_k, raw=True)

    async def search(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """
        Execute search using the legacy hybrid retrieval + Cross-Encoder reranker.
        """
        raw_results = await asyncio.to_thread(self._sync_search, query, top_k)

        chunks: List[RetrievedChunk] = []
        if not raw_results:
            return chunks

        for item in raw_results:
            props = item.get("props", {})
            citation = str(props.get("display_citation") or "").strip()
            text = str(props.get("text") or "").strip()
            enriched_text = str(props.get("enriched_text") or "").strip()
            if props.get("id"):
                chunk_id = str(props["id"])
            else:
                identity = {
                    key: str(props.get(key) or "").strip()
                    for key in (
                        "law", "chapter", "section", "article_no", "article_title",
                        "clause_no", "point", "clause_head", "display_citation",
                        "text", "enriched_text",
                    )
                }
                payload = json.dumps(identity, sort_keys=True, ensure_ascii=False)
                chunk_id = "chunk_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

            # Rerank score takes precedence if available, otherwise hybrid/dense score
            score_val = item.get("rerank_score", item.get("score", 0.0))
            try:
                score = float(score_val)
            except (ValueError, TypeError):
                score = 0.0

            metadata: Dict[str, Any] = {
                "law": props.get("law", ""),
                "chapter": props.get("chapter", ""),
                "section": props.get("section", ""),
                "article_no": props.get("article_no", ""),
                "article_title": props.get("article_title", ""),
                "clause_no": props.get("clause_no"),
                "point": props.get("point", ""),
                "clause_head": props.get("clause_head", ""),
                "raw_score": item.get("score"),
                "rerank_score": item.get("rerank_score"),
            }

            chunks.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    enriched_text=enriched_text,
                    citation=citation,
                    score=score,
                    metadata=metadata,
                )
            )

        return chunks
