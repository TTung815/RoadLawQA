"""Bounded workflow tests with scripted provider and retriever, without external I/O."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai.agent.contextualizer import ContextualizedQuery, QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter, RewrittenQuery
from ai.llm.base import LLMProvider
from ai.retrieval.base import RetrievedChunk, Retriever
from backend.services.agentic_retrieval import AgenticRetrievalService

QUESTION = "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?"
REWRITTEN = "Chế tài tước giấy phép lái xe đối với người điều khiển ô tô vượt đèn đỏ?"
GAP = "Missing license-suspension evidence for cars running red lights."


class ScriptedProvider(LLMProvider):
    def __init__(self, script, events=None):
        self.script = list(script)
        self.calls = []
        self.events = events if events is not None else []

    async def generate(self, *args, **kwargs):
        pytest.fail("The workflow must use structured generation exclusively")

    async def generate_structured(self, messages, response_schema, temperature=0.1, **kwargs):
        assert temperature == 0.0
        assert kwargs == {}
        assert [message.role for message in messages] == ["system", "user"]
        self.calls.append({
            "schema": response_schema,
            "prompt": messages[0].content,
            "payload": json.loads(messages[1].content),
        })
        self.events.append(response_schema.__name__)
        assert self.script, "Unexpected extra LLM call"
        expected, result = self.script.pop(0)
        assert response_schema is expected
        if isinstance(result, Exception):
            raise result
        return response_schema(**result)


class ScriptedRetriever(Retriever):
    def __init__(self, batches, events=None):
        self.batches = list(batches)
        self.calls = []
        self.events = events if events is not None else []

    async def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        self.events.append("retrieve")
        assert self.batches, "Unexpected extra retrieval attempt"
        result = self.batches.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def chunk(identifier, score=0.5):
    return RetrievedChunk(
        id=identifier, text="Test-only legal passage", enriched_text="Test-only legal context",
        citation=f"Test citation {identifier}", score=score,
        metadata={"law": "Test law", "raw_score": 0.1, "rerank_score": score},
    )


def make_service(script, batches, max_attempts=2):
    events = []
    provider = ScriptedProvider(script, events)
    retriever = ScriptedRetriever(batches, events)
    service = AgenticRetrievalService(
        QueryContextualizer(provider), retriever, EvidenceGrader(provider),
        QueryRewriter(provider), max_attempts=max_attempts,
    )
    return service, provider, retriever, events


@pytest.mark.asyncio
async def test_first_attempt_sufficient_returns_without_rewrite():
    evidence = [chunk("first")]
    service, provider, retriever, events = make_service([
        (EvidenceGrade, {"sufficient": True, "reason": "Requested sanction is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ], [evidence])
    result = await service.retrieve(QUESTION, top_k=3)
    assert retriever.calls == [(QUESTION, 3)]
    assert events == ["retrieve", "EvidenceGrade"]
    assert provider.script == []
    assert result.chunks == evidence
    assert result.grade.sufficient is True
    assert result.retrieval_attempts == 1
    assert result.retrieval_queries == [QUESTION]
    assert result.rewritten_query is None
    assert result.selected_attempt == 1
    assert result.attempts[0].chunk_ids == ["first"]
    assert result.attempts[0].citations == ["Test citation first"]


@pytest.mark.asyncio
async def test_weak_then_successful_retry_grades_original_need_both_times():
    first, second = [chunk("first", 100.0)], [chunk("second", -5.0)]
    service, provider, retriever, events = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
        (EvidenceGrade, {"sufficient": True, "reason": "Requested sanction is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ], [first, second])
    result = await service.retrieve(QUESTION, top_k=4)
    assert retriever.calls == [(QUESTION, 4), (REWRITTEN, 4)]
    assert events == ["retrieve", "EvidenceGrade", "RewrittenQuery", "retrieve", "EvidenceGrade"]
    assert [call["payload"]["question"] for call in provider.calls] == [QUESTION] * 3
    assert provider.calls[1]["payload"] == {
        "question": QUESTION, "retrieval_query": QUESTION, "evidence_gap": GAP, "missing_aspects": ["additional_sanction"],
    }
    assert result.chunks == first + second
    assert result.grade.sufficient is True
    assert result.retrieval_attempts == 2
    assert result.retrieval_queries == [QUESTION, REWRITTEN]
    assert result.rewritten_query == REWRITTEN
    assert result.selected_attempt == 2
    assert [attempt.grade.sufficient for attempt in result.attempts] == [False, True]


@pytest.mark.asyncio
async def test_two_weak_attempts_stop_and_return_accumulated_evidence():
    first, second = [chunk("first")], [chunk("second")]
    service, provider, retriever, _ = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
        (EvidenceGrade, {"sufficient": False, "reason": "Still missing the requested sanction.", "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
    ], [first, second])
    result = await service.retrieve(QUESTION)
    assert len(retriever.calls) == 2
    assert len(provider.calls) == 3
    assert result.retrieval_attempts == 2
    assert result.grade.sufficient is False
    assert result.grade.reason == "Still missing the requested sanction."
    assert result.chunks == first + second
    assert result.selected_attempt == 2


@pytest.mark.asyncio
async def test_empty_first_attempt_is_deterministically_weak_then_retries():
    second = [chunk("second")]
    service, provider, retriever, events = make_service([
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
        (EvidenceGrade, {"sufficient": True, "reason": "Requested sanction is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ], [[], second])
    result = await service.retrieve(QUESTION)
    assert len(retriever.calls) == 2
    assert events == ["retrieve", "RewrittenQuery", "retrieve", "EvidenceGrade"]
    assert result.attempts[0].grade.sufficient is False
    assert result.attempts[0].grade.reason == "No legal chunks were retrieved."
    assert result.attempts[0].chunk_ids == []
    assert result.chunks == second


@pytest.mark.asyncio
async def test_both_attempts_empty_stop_without_grader_calls():
    service, provider, retriever, events = make_service([
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
    ], [[], []])
    result = await service.retrieve(QUESTION)
    assert events == ["retrieve", "RewrittenQuery", "retrieve"]
    assert result.grade.sufficient is False
    assert result.chunks == []
    assert result.retrieval_attempts == 2
    assert result.selected_attempt == 2
    assert len(retriever.calls) == 2


@pytest.mark.asyncio
async def test_empty_retry_keeps_earlier_weak_chunks_and_their_grade():
    first = [chunk("first")]
    service, _, _, _ = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
    ], [first, []])
    result = await service.retrieve(QUESTION)
    assert result.chunks == first
    assert result.grade.reason == GAP
    assert result.grade.sufficient is False
    assert result.selected_attempt == 1
    assert result.retrieval_attempts == 2
    assert result.attempts[1].grade.reason == GAP
    assert result.attempts[1].evidence_chunk_ids == ["first"]


@pytest.mark.asyncio
async def test_one_attempt_limit_returns_weak_evidence_without_rewrite():
    service, provider, retriever, _ = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
    ], [[chunk("first")]], max_attempts=1)
    result = await service.retrieve(QUESTION)
    assert result.grade.sufficient is False
    assert result.rewritten_query is None
    assert result.retrieval_attempts == 1
    assert len(provider.calls) == len(retriever.calls) == 1


@pytest.mark.asyncio
async def test_unchanged_rewrite_still_obeys_attempt_limit():
    service, _, retriever, _ = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": QUESTION}),
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
    ], [[chunk("first")], [chunk("second")]])
    result = await service.retrieve(QUESTION)
    assert result.retrieval_queries == [QUESTION, QUESTION]
    assert len(retriever.calls) == 2
    assert result.grade.sufficient is False


@pytest.mark.parametrize("limit", [0, 3, -1, True, 1.5, "2"])
def test_invalid_attempt_limit_is_rejected_before_io(limit):
    with pytest.raises(ValueError, match="max_attempts"):
        make_service([], [], max_attempts=limit)


@pytest.mark.asyncio
async def test_history_is_contextualized_once_and_intent_survives_retry():
    current = "Ô tô vượt đèn đỏ thì sao?"
    history = [{"role": "user", "content": "Xe máy vượt đèn đỏ có bị tước giấy phép lái xe không?"}]
    service, provider, retriever, events = make_service([
        (ContextualizedQuery, {"standalone_query": QUESTION}),
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
        (EvidenceGrade, {"sufficient": True, "reason": "Requested sanction is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ], [[chunk("first")], [chunk("second")]])
    result = await service.retrieve(current, history)
    assert events[0] == "ContextualizedQuery"
    assert events.count("ContextualizedQuery") == 1
    assert provider.calls[0]["payload"] == {"current_query": current, "chat_history": history}
    assert result.original_query == current
    assert result.standalone_query == QUESTION
    assert retriever.calls == [(QUESTION, 10), (REWRITTEN, 10)]
    assert all(term in result.rewritten_query for term in ("ô tô", "vượt đèn đỏ", "tước giấy phép lái xe"))


@pytest.mark.asyncio
async def test_numeric_constraints_are_passed_to_rewrite_and_second_retrieval():
    question = "Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?"
    rewritten = "Mức xử phạt đối với ô tô vượt quá tốc độ từ 20 đến 35 km/h?"
    gap = "Missing penalty evidence for the requested car speed range."
    service, provider, retriever, _ = make_service([
        (EvidenceGrade, {"sufficient": False, "reason": gap, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": rewritten}),
        (EvidenceGrade, {"sufficient": True, "reason": "Requested range is supported.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ], [[chunk("first")], [chunk("second")]])
    result = await service.retrieve(question)
    assert provider.calls[1]["payload"]["question"] == question
    assert provider.calls[1]["payload"]["evidence_gap"] == gap
    assert retriever.calls[1][0] == rewritten
    assert all(term in result.rewritten_query for term in ("ô tô", "vượt quá tốc độ", "20 đến 35 km/h"))


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["contextualizer", "first-retrieval", "grader", "rewriter", "second-retrieval", "second-grader"])
async def test_infrastructure_failures_propagate_without_additional_attempts(stage):
    failure = RuntimeError(f"{stage} unavailable")
    batches = [[chunk("first")], [chunk("second")]]
    script = [
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
        (RewrittenQuery, {"rewritten_query": REWRITTEN}),
        (EvidenceGrade, {"sufficient": True, "reason": "Sufficient.", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]}),
    ]
    history = []
    expected_retrievals = 1
    if stage == "contextualizer":
        script = [(ContextualizedQuery, failure)]
        history = [{"role": "user", "content": QUESTION}]
        expected_retrievals = 0
    elif stage == "first-retrieval":
        batches[0] = failure
    elif stage == "grader":
        script[0] = (EvidenceGrade, failure)
    elif stage == "rewriter":
        script[1] = (RewrittenQuery, failure)
    elif stage == "second-retrieval":
        batches[1] = failure
        expected_retrievals = 2
    elif stage == "second-grader":
        script[2] = (EvidenceGrade, failure)
        expected_retrievals = 2
    service, _, retriever, _ = make_service(script, batches)
    with pytest.raises(RuntimeError, match=stage):
        await service.retrieve(QUESTION, history)
    assert len(retriever.calls) == expected_retrievals


def test_agentic_retry_workflow_isolated_from_models_network_and_api_key():
    script = '''
import asyncio
import importlib.abc
import socket
import sys
blocked = ('backend.retriever_custom', 'backend.generator', 'torch',
           'sentence_transformers', 'weaviate', 'google.generativeai', 'google.genai')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Unexpected resource import: ' + fullname)
sys.meta_path.insert(0, Guard())
def no_network(*args, **kwargs):
    raise AssertionError('Unexpected network connection')
socket.create_connection = no_network
socket.socket.connect = no_network
socket.socket.connect_ex = no_network
from tests.unit.test_agentic_retrieval import make_service, chunk, QUESTION, REWRITTEN, GAP
from ai.agent.evidence_grader import EvidenceGrade
from ai.agent.query_rewriter import RewrittenQuery
service, provider, retriever, events = make_service([
    (EvidenceGrade, {'sufficient': False, 'reason': GAP, 'coverage': [{'aspect': 'additional_sanction', 'covered': False}]}),
    (RewrittenQuery, {'rewritten_query': REWRITTEN}),
    (EvidenceGrade, {'sufficient': True, 'reason': 'Sufficient.', 'coverage': [{'aspect': 'additional_sanction', 'covered': True, 'support_state': 'positive_support'}]}),
], [[chunk('first')], [chunk('second')]])
result = asyncio.run(service.retrieve(QUESTION))
assert result.retrieval_attempts == 2
assert result.grade.sufficient is True
assert len(provider.calls) == 3
assert not any(name in sys.modules for name in blocked)
'''
    env = dict(os.environ)
    env.pop("GEMINI_API_KEY", None)
    subprocess.run(
        [sys.executable, "-B", "-c", script], env=env,
        cwd=Path(__file__).resolve().parents[2], check=True,
    )


@pytest.mark.asyncio
async def test_complementary_speed_evidence_is_graded_and_returned_together():
    question = 'Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?'
    rewritten = 'Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị trừ điểm giấy phép lái xe và xử phạt bổ sung thế nào?'
    monetary, license = chunk('monetary'), chunk('license')
    coverage = [
        {'aspect': 'monetary_penalty', 'covered': True, 'support_state': 'positive_support'},
        {'aspect': 'license_points', 'covered': False},
        {'aspect': 'additional_sanction', 'covered': False},
        {'aspect': 'subject_violation', 'covered': True, 'support_state': 'positive_support'},
        {'aspect': 'threshold_range', 'covered': True, 'support_state': 'positive_support'},
    ]
    complete = [dict(item, covered=True, support_state="positive_support") for item in coverage]
    service, provider, retriever, _ = make_service([
        (EvidenceGrade, {'sufficient': True, 'reason': 'Missing license consequences.', 'coverage': coverage}),
        (RewrittenQuery, {'rewritten_query': rewritten}),
        (EvidenceGrade, {'sufficient': True, 'reason': 'Complementary evidence covers the original need.', 'coverage': complete}),
    ], [[monetary], [license]])
    result = await service.retrieve(question)
    assert provider.calls[1]['payload']['missing_aspects'] == ['license_points', 'additional_sanction']
    assert provider.calls[1]['payload']['question'] == question
    assert [item['id'] for item in provider.calls[0]['payload']['chunks']] == ['monetary']
    assert [item['id'] for item in provider.calls[2]['payload']['chunks']] == ['monetary', 'license']
    assert provider.calls[2]['payload']['question'] == question
    assert retriever.calls == [(question, 10), (rewritten, 10)]
    assert result.chunks == [monetary, license]
    assert result.attempts[0].grade.sufficient is False
    assert result.attempts[1].grade.sufficient is True
    assert result.attempts[1].chunk_ids == ['license']
    assert result.attempts[1].evidence_chunk_ids == ['monetary', 'license']
    assert result.selected_attempt == 2
    assert result.grade.sufficient is True
    assert provider.script == []


@pytest.mark.asyncio
async def test_dedup_preserves_first_occurrence_and_distinct_chunks_with_same_citation():
    first, duplicate, second = chunk('first', 100), chunk('first', -100), chunk('second')
    second.citation = first.citation  # Different leaves/windows may share a citation.
    service, provider, _, _ = make_service([
        (EvidenceGrade, {'sufficient': False, 'reason': GAP, 'coverage': [{'aspect': 'additional_sanction', 'covered': False}]}),
        (RewrittenQuery, {'rewritten_query': REWRITTEN}),
        (EvidenceGrade, {'sufficient': True, 'reason': 'Combined evidence.', 'coverage': [{'aspect': 'additional_sanction', 'covered': True, 'support_state': 'positive_support'}]}),
    ], [[first, duplicate], [duplicate, second, second]])
    result = await service.retrieve(QUESTION)
    assert result.chunks == [first, second]
    assert result.chunks[0].score == 100
    assert [item['id'] for item in provider.calls[0]['payload']['chunks']] == ['first']
    assert [item['id'] for item in provider.calls[2]['payload']['chunks']] == ['first', 'second']


@pytest.mark.asyncio
async def test_duplicate_only_retry_preserves_evidence_and_grade_without_regrading():
    first = chunk('first')
    service, provider, retriever, _ = make_service([
        (EvidenceGrade, {'sufficient': False, 'reason': GAP, 'coverage': [{'aspect': 'additional_sanction', 'covered': False}]}),
        (RewrittenQuery, {'rewritten_query': REWRITTEN}),
    ], [[first], [chunk('first', 999)]])
    result = await service.retrieve(QUESTION)
    assert result.chunks == [first]
    assert result.grade == result.attempts[1].grade == result.attempts[0].grade
    assert result.selected_attempt == 1
    assert result.attempts[1].evidence_chunk_ids == ['first']
    assert len(retriever.calls) == 2
    assert len(provider.calls) == 2
