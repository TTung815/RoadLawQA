# -*- coding: utf-8 -*-
"""
Core Retrieval Abstractions
Defines the canonical data model (RetrievedChunk) and abstract Retriever interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """
    Standard retrieved chunk data contract across all retrieval implementations.
    """
    id: str
    text: str
    enriched_text: str
    citation: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Retriever(ABC):
    """
    Abstract base interface for all retrievers (dense, sparse, hybrid, graph).
    """

    @abstractmethod
    async def search(self, query: str, top_k: int = 5, *, retrieval_query: str | None = None) -> List[RetrievedChunk]:
        """
        Asynchronously search for relevant chunks given a query.

        Args:
            query: The user search query or contextualized query string.
            top_k: Number of highest ranking chunks to return.
            retrieval_query: Optional search paraphrase, combined within the candidate budget.

        Returns:
            A list of RetrievedChunk objects ordered by relevance score descending.
        """
        pass

