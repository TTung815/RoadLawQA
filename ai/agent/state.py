# -*- coding: utf-8 -*-
"""
Shared Agent Workflow State
Defines the state contract for conversational legal RAG orchestration.
"""
from typing import Dict, List, Optional, TypedDict
from ai.retrieval.base import RetrievedChunk


class AgentState(TypedDict, total=False):
    """
    Typed dictionary for service orchestration and future workflow nodes.

    Workflow representation:
    user + history -> contextualize -> retrieve -> grade -> rewrite if needed -> generate -> citation verify -> final answer
    """
    user_query: str
    chat_history: List[Dict[str, str]]
    standalone_query: Optional[str]
    retrieved_chunks: List[RetrievedChunk]
    evidence_sufficient: Optional[bool]
    evidence_reason: Optional[str]
    rewritten_query: Optional[str]
    retrieval_attempts: int
    retrieval_queries: List[str]
    draft_answer: Optional[str]
    citation_valid: Optional[bool]
    final_answer: Optional[str]
