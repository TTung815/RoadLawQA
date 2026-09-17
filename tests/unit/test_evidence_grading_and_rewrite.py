"""Structured component contracts and validation, with no real LLM calls."""

from pydantic import ValidationError
import pytest

from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter, RewrittenQuery
from ai.prompts.evidence_grading import EVIDENCE_GRADING_PROMPT
from ai.prompts.query_rewrite import QUERY_REWRITE_PROMPT
from tests.unit.test_agentic_retrieval import GAP, QUESTION, REWRITTEN, ScriptedProvider, chunk


@pytest.mark.asyncio
async def test_grader_sends_original_question_and_legal_context_without_similarity_scores():
    evidence = chunk("first", score=1000.0)
    provider = ScriptedProvider([
        (EvidenceGrade, {"sufficient": False, "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]}),
    ])
    result = await EvidenceGrader(provider).grade(QUESTION, [evidence])
    call = provider.calls[0]
    assert call["prompt"] == EVIDENCE_GRADING_PROMPT
    assert call["payload"]["question"] == QUESTION
    assert call["payload"]["chunks"] == [{
        "id": "first", "text": evidence.text, "enriched_text": evidence.enriched_text,
        "citation": evidence.citation, "metadata": {"law": "Test law"},
    }]
    assert result.sufficient is False
    assert result.reason == GAP
    assert evidence.metadata["rerank_score"] == 1000.0


@pytest.mark.asyncio
async def test_empty_evidence_does_not_invoke_llm():
    provider = ScriptedProvider([])
    grade = await EvidenceGrader(provider).grade(QUESTION, [])
    assert grade.sufficient is False
    assert grade.reason == "No legal chunks were retrieved."
    assert provider.calls == []


@pytest.mark.asyncio
async def test_rewriter_receives_gap_and_stable_question_as_structured_data():
    provider = ScriptedProvider([(RewrittenQuery, {"rewritten_query": REWRITTEN})])
    grade = EvidenceGrade(sufficient=False, reason=GAP, coverage=[{"aspect": "additional_sanction", "covered": False}])
    result = await QueryRewriter(provider).rewrite(QUESTION, QUESTION, grade)
    assert result.rewritten_query == REWRITTEN
    assert provider.calls[0]["prompt"] == QUERY_REWRITE_PROMPT
    assert provider.calls[0]["payload"] == {
        "question": QUESTION, "retrieval_query": QUESTION, "evidence_gap": GAP, "missing_aspects": ["additional_sanction"],
    }


@pytest.mark.parametrize("values", [
    {"sufficient": False},
    {"sufficient": True, "reason": "   ", "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "positive_support"}]},
    {"sufficient": "true", "reason": "Ambiguous boolean"},
    {"sufficient": 1, "reason": "Not a boolean"},
])
def test_grade_requires_real_boolean_and_nonempty_reason(values):
    with pytest.raises(ValidationError):
        EvidenceGrade(**({"coverage": [{"aspect": "subject_violation", "covered": True, "support_state": "positive_support"}]} | values))


@pytest.mark.asyncio
async def test_blank_rewrite_fails_validation():
    provider = ScriptedProvider([(RewrittenQuery, {"rewritten_query": "  \n  "})])
    with pytest.raises(ValidationError):
        await QueryRewriter(provider).rewrite(QUESTION, QUESTION, EvidenceGrade(sufficient=False, reason=GAP, coverage=[{"aspect": "additional_sanction", "covered": False}]))


@pytest.mark.asyncio
async def test_invalid_grade_fails_before_routing():
    provider = ScriptedProvider([(EvidenceGrade, {"sufficient": "yes", "reason": GAP, "coverage": [{"aspect": "additional_sanction", "covered": False}]})])
    with pytest.raises(ValidationError):
        await EvidenceGrader(provider).grade(QUESTION, [chunk("first")])


@pytest.mark.parametrize('coverage', [
    [],
    [{'aspect': 'license_points', 'covered': 'true'}],
    [{'aspect': 'license_points', 'covered': True, 'support_state': 'positive_support'}, {'aspect': 'license_points', 'covered': False}],
])
def test_sufficient_grade_requires_nonempty_unique_and_strict_coverage(coverage):
    with pytest.raises(ValidationError):
        EvidenceGrade(sufficient=True, reason='Supported', coverage=coverage)


@pytest.mark.asyncio
async def test_missing_coverage_in_provider_response_is_not_silently_accepted():
    provider = ScriptedProvider([(EvidenceGrade, {'sufficient': True, 'reason': 'Relevant chunks.'})])
    with pytest.raises(ValidationError):
        await EvidenceGrader(provider).grade(QUESTION, [chunk('first')])


@pytest.mark.asyncio
async def test_broad_speed_sanction_grade_cannot_override_missing_license_coverage():
    question = 'Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?'
    provider = ScriptedProvider([(EvidenceGrade, {
        'sufficient': True,  # Reproduce an optimistic provider flag despite a gap.
        'reason': 'Monetary penalty available; license point consequence unsupported.',
        'coverage': [
            {'aspect': 'monetary_penalty', 'covered': True, 'support_state': 'positive_support'},
            {'aspect': 'license_points', 'covered': False},
            {'aspect': 'subject_violation', 'covered': True, 'support_state': 'positive_support'},
            {'aspect': 'threshold_range', 'covered': True, 'support_state': 'positive_support'},
        ],
    })])
    grade = await EvidenceGrader(provider).grade(question, [chunk('monetary')])
    assert grade.sufficient is False
    assert grade.missing_aspects == ['license_points']
    assert provider.calls[0]['payload']['question'] == question


@pytest.mark.asyncio
@pytest.mark.parametrize('question,aspect,covered', [
    ('Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị phạt bao nhiêu tiền?', 'monetary_penalty', True),
    ('Ô tô vượt quá tốc độ từ 20 đến 35 km/h có bị trừ điểm GPLX không?', 'license_points', False),
    ('Ô tô vượt đèn đỏ có bị tước GPLX không?', 'additional_sanction', False),
])
async def test_explicit_sanction_intents_use_their_required_coverage(question, aspect, covered):
    provider = ScriptedProvider([(EvidenceGrade, {
        'sufficient': covered, 'reason': 'Explicit requested consequence assessed.',
        'coverage': [{'aspect': aspect, 'covered': covered, 'support_state': 'positive_support' if covered else 'unknown'}],
    })])
    grade = await EvidenceGrader(provider).grade(question, [chunk('monetary')])
    assert grade.sufficient is covered
    assert grade.missing_aspects == ([] if covered else [aspect])
