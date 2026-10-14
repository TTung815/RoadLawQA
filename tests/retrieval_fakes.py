"""Callback retriever for API contract tests, with no live default."""

import asyncio
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from ai.retrieval.base import RetrievedChunk, Retriever


class CallbackRetriever(Retriever):
    """Adapt a deterministic callback to the Retriever contract in API tests."""

    def __init__(self, retrieve_fn: Callable[..., Any]):
        """Require an explicit fake; tests cannot fall through to live resources."""
        self._retrieve_fn = retrieve_fn

    def _sync_search(self, query: str, top_k: int) -> Any:
        # Match the async serving boundary without blocking the event loop.
        fn = self._retrieve_fn
        return fn(query, k=top_k, raw=True)

    async def search(self, query: str, top_k: int = 5) -> List[RetrievedChunk]:
        """Execute the injected callback and map its fixture rows."""
        raw_results = await asyncio.to_thread(self._sync_search, query, top_k)

        return self.map_results(raw_results)

    @staticmethod
    def map_results(raw_results: Any) -> List[RetrievedChunk]:
        """Map indexed properties consistently for search and structural lookup."""
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
