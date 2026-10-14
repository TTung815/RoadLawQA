"""Negative legal support cannot be inferred from missing or related sources."""

import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer, GeneratedAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from ai.agent.evidence_grader import EvidenceGrade
from backend.services.answer import AnswerService
from tests.unit.test_agentic_retrieval import ScriptedProvider, chunk, make_service
from tests.unit.test_grounded_answer import qa_service, semantic

QUESTION = "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?"
NEGATIVE = "Hành vi này không bị tước giấy phép lái xe."


def grade(state):
    return {"sufficient": True, "reason": "Provider assessment.", "coverage": [
        {"aspect": "additional_sanction", "covered": True, "support_state": state},
    ]}


@pytest.mark.asyncio
async def test_explicit_positive_sanction_can_be_published():
    source = chunk("suspension")
    source.text = source.enriched_text = "Người thực hiện hành vi này bị tước giấy phép lái xe."
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade("positive_support"))],
                                      [[source]], max_attempts=1)
    provider = ScriptedProvider([
        (GeneratedAnswer, {"claims": [{"text": "Hành vi này bị tước giấy phép lái xe.",
                                  "chunk_ids": [source.id], "support_state": "positive_support"}]}),
        (SemanticVerification, semantic(1)),
    ])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.status == "answered"
    assert result.answer.claims[0].support_state == "positive_support"
    assert result.verification.assessments[0].support_state == "positive_support"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Người thực hiện hành vi này bị phạt tiền.",
    "Người thực hiện hành vi này bị phạt tiền và trừ điểm giấy phép lái xe.",
])
@pytest.mark.parametrize("state", ["unknown", "negative_support"])
async def test_missing_sanction_and_related_sanctions_remain_unknown(text, state):
    source = chunk("related")
    source.text = source.enriched_text = text
    source.metadata["structural_context"] = {"complete_clause_chunk_ids": [source.id]}
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade(state))], [[source]], max_attempts=1)
    provider = ScriptedProvider([])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.retrieval.grade.coverage[0].support_state == "unknown"
    assert result.retrieval.grade.coverage[0].covered is False
    assert result.verification.status == "not_run"
    assert provider.calls == []


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
@pytest.mark.parametrize("state", ["unknown", "negative_support"])
async def test_generator_negative_or_unknown_claim_never_reaches_public_answer(state):
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade("positive_support"))],
                                      [[chunk("source")]], max_attempts=1)
    provider = ScriptedProvider([(GeneratedAnswer, {"claims": [
        {"text": NEGATIVE, "chunk_ids": ["source"], "support_state": state},
    ]})] * 2)
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.semantic_valid is False
    assert len(provider.calls) == 2
    assert result.repair_attempts == 1


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
async def test_current_suspension_scope_remains_insufficient_with_complete_clause_leaves():
    anchor = chunk("red-light")
    anchor.text = anchor.enriched_text = "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông."
    provisions = [chunk("15-a"), chunk("15-b"), chunk("15-c")]
    provisions[0].text = "Hành vi tại điểm e khoản 5 bị tịch thu thiết bị."
    provisions[1].text = "Hành vi tại khoản 12 bị tước giấy phép lái xe."
    provisions[2].text = "Hành vi tại khoản 11, khoản 13, khoản 14 bị tước giấy phép lái xe."
    for source in provisions:
        source.enriched_text = source.text
        source.metadata["structural_context"] = {
            "complete_clause_chunk_ids": [item.id for item in provisions],
            "purpose": "additional_sanction_applicability",
        }
    retrieval, _, retriever, _ = make_service([(EvidenceGrade, grade("negative_support"))],
                                             [[anchor, *provisions]], max_attempts=1)
    provider = ScriptedProvider([])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert len(result.evidence_citations) == 4
    assert retriever.calls == [(QUESTION, 10)]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_missing_support_labels_fail_closed_at_grading_and_generation():
    response = grade("positive_support")
    del response["coverage"][0]["support_state"]
    result = EvidenceGrade.model_validate(response)
    assert result.sufficient is False
    assert result.coverage[0].support_state == "unknown"
    draft = DraftAnswer(claims=[{"text": NEGATIVE, "chunk_ids": ["source"]}])
    provider = ScriptedProvider([])
    verification = await CitationVerifier(provider).verify(QUESTION, draft, [chunk("source")])
    assert verification.status == "failed"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_independent_assessment_blocks_mislabeled_negative_publication():
    draft = {"claims": [{"text": NEGATIVE, "chunk_ids": ["money"],
                         "support_state": "positive_support"}]}
    response = semantic(1)
    response["assessments"][0]["support_state"] = "negative_support"
    service, provider, _, _ = qa_service(draft, verification=response)
    result = await service.answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.assessments[0].support_state == "unknown"
    assert result.verification.assessments[0].supported is False
    assert len(provider.calls) == 2


def test_positive_label_cannot_override_uncovered_evidence():
    response = grade("positive_support")
    response["coverage"][0]["covered"] = False
    result = EvidenceGrade.model_validate(response)
    assert result.sufficient is False
    assert result.coverage[0].support_state == "unknown"
