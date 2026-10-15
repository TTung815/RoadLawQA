"""Negative legal support cannot be inferred from missing or related sources."""

import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer, GeneratedAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from backend.services.answer import AnswerService
from tests.unit.fakes import ScriptedProvider, chunk, semantic
from tests.unit.test_grounded_answer import qa_service

QUESTION = "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?"
NEGATIVE = "Hành vi này không bị tước giấy phép lái xe."


@pytest.mark.asyncio
async def test_fake_explicit_completeness_is_not_production_authority():
    # Synthetic fixture only: no production component currently creates or
    # validates this kind of exhaustive applicable-rule provenance.
    source = chunk("test-only-exclusion")
    source.text = source.enriched_text = "Trong phạm vi giả lập này, chế tài không áp dụng."
    source.metadata["fake_applicable_rule_scope"] = {
        "exhaustive": True, "scope": "test-only conduct and regulation version",
        "examined_rule_ids": [source.id], "resolved_references": True,
    }
    draft = DraftAnswer(claims=[{"text": NEGATIVE, "chunk_ids": [source.id],
                                "support_state": "negative_support"}])
    provider = ScriptedProvider([])
    result = await CitationVerifier(provider).verify(QUESTION, draft, [source])
    assert result.status == "failed"
    assert result.provenance_valid is True  # Citation exists; negative authority does not.
    assert result.semantic_valid is False
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unknown", "negative_support", None])
async def test_semantic_support_state_overrides_optimistic_supported_flag(state):
    # The generator's positive label must not bind the independent assessor.
    draft = DraftAnswer(claims=[{"text": NEGATIVE, "chunk_ids": ["source"],
                                "support_state": "positive_support"}])
    assessment = semantic(1)
    if state is None:
        del assessment["assessments"][0]["support_state"]
    else:
        assessment["assessments"][0]["support_state"] = state
    provider = ScriptedProvider([(SemanticVerification, assessment)])
    result = await CitationVerifier(provider).verify(QUESTION, draft, [chunk("source")])
    assert result.status == "failed"
    assert result.semantic_valid is False
    assert result.assessments[0].supported is False
    assert result.assessments[0].support_state == "unknown"


@pytest.mark.asyncio
async def test_independent_assessment_blocks_mislabeled_negative_publication():
    draft = {"claims": [{"text": NEGATIVE, "chunk_ids": ["money"],
                         "support_state": "positive_support"}]}
    response = semantic(1)
    response["assessments"][0]["support_state"] = "negative_support"
    service, provider, _ = qa_service(draft, verification=response)
    result = await service.answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.assessments[0].support_state == "unknown"
    assert result.verification.assessments[0].supported is False
    assert len(provider.calls) == 2
