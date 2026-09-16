# -*- coding: utf-8 -*-
"""
Unit Tests for AgentState Contract
Validates structural schema and field expectations without asserting TypedDict runtime defaults.
"""
from ai.agent.state import AgentState
from ai.retrieval.base import RetrievedChunk


def test_agent_state_annotations_contract():
    expected_fields = {
        "user_query",
        "chat_history",
        "standalone_query",
        "retrieved_chunks",
        "evidence_sufficient",
        "evidence_reason",
        "rewritten_query",
        "retrieval_attempts",
        "draft_answer",
        "citation_valid",
        "final_answer",
    }

    actual_fields = set(AgentState.__annotations__.keys())
    assert expected_fields.issubset(actual_fields), f"Missing fields: {expected_fields - actual_fields}"


def test_agent_state_instantiation_contract():
    chunk = RetrievedChunk(
        id="c1",
        text="text",
        enriched_text="enriched",
        citation="citation",
        score=0.9,
    )

    state: AgentState = {
        "user_query": "Vượt đèn đỏ phạt bao nhiêu?",
        "chat_history": [{"role": "user", "content": "Xin chào"}],
        "standalone_query": "Mức phạt vượt đèn đỏ xe máy",
        "retrieved_chunks": [chunk],
        "evidence_sufficient": True,
        "evidence_reason": "Có quy định mức phạt tại Nghị định 168",
        "rewritten_query": None,
        "retrieval_attempts": 1,
        "draft_answer": "Phạt từ 800.000 đến 1.000.000 VNĐ",
        "citation_valid": True,
        "final_answer": "Mức phạt là 800.000 - 1.000.000 VNĐ (khoản 4 Điều 6 NĐ 168/2024)",
    }

    assert state["user_query"] == "Vượt đèn đỏ phạt bao nhiêu?"
    assert len(state["retrieved_chunks"]) == 1
    assert state["evidence_sufficient"] is True
    assert state["retrieval_attempts"] == 1

