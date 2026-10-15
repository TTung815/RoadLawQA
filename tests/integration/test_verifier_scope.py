"""Opt-in live regression for an unnecessary repair seen in a chat follow-up."""

import os

import pytest

from ai.agent.answer_generator import AnswerClaim, DraftAnswer
from ai.agent.citation_verifier import CitationVerifier
from ai.llm.factory import create_provider
from ai.retrieval.structured import map_unit
from configs.settings import Settings
from ingestion.structured_corpus import load_bundle


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("ROADLAWQA_LIVE_LLM_TESTS") != "1",
                    reason="Set ROADLAWQA_LIVE_LLM_TESTS=1 to allow billed provider calls")
@pytest.mark.parametrize("asks_other_action", [False, True])
async def test_verifier_requires_neighboring_action_only_when_asked(asks_other_action):
    locators = ["d7-k6-pa", "d7-k8-pb", "d7-k9-pd", "d7-k9-pđ"]
    units = load_bundle()["chunks"]
    chunks = [map_unit(next(u for u in units if
              f"nd168-effective-as-of-2026-09-22-{locator}" in u["metadata"]["source_processed_ids"]))
              for locator in locators]
    statements = [
        "Người lái xe máy có nồng độ cồn nhưng chưa vượt quá 50 mg/100 ml máu hoặc chưa vượt quá 0,25 mg/l khí thở bị phạt 2–3 triệu đồng.",
        "Nếu nồng độ cồn vượt quá 50 đến 80 mg/100 ml máu hoặc vượt quá 0,25 đến 0,4 mg/l khí thở, mức phạt là 6–8 triệu đồng.",
        "Nếu nồng độ cồn vượt quá 80 mg/100 ml máu hoặc vượt quá 0,4 mg/l khí thở, mức phạt là 8–10 triệu đồng.",
    ]
    draft = DraftAnswer(claims=[AnswerClaim(text=text, chunk_ids=[source.id],
                                          support_state="positive_support")
                                for text, source in zip(statements, chunks[:3], strict=True)])
    question = "Người điều khiển xe máy vi phạm quy định về nồng độ cồn khi tham gia giao thông bị phạt bao nhiêu?"
    if asks_other_action:
        question += " Còn hành vi không chấp hành yêu cầu kiểm tra nồng độ cồn bị phạt bao nhiêu?"
    result = await CitationVerifier(create_provider(Settings())).verify(question, draft, chunks)
    assert result.semantic_valid is True
    if asks_other_action:
        assert result.status == "failed" and result.answer_complete is False
    else:
        assert result.status == "passed" and result.answer_complete is True


def pedestrian_exception_case(scope: str):
    """Observed omission plus valid general and explicitly narrowed counterparts."""
    units = load_bundle()["chunks"]
    chunks = [map_unit(next(u for u in units if
              f"nd168-effective-as-of-2026-09-22-{locator}" in u["metadata"]["source_processed_ids"]))
              for locator in ("d10-k1-pb", "d10-k2-pa")]
    question = "Người đi bộ không chấp hành hiệu lệnh đèn tín hiệu bị phạt bao nhiêu?"
    text = "Người đi bộ không chấp hành hiệu lệnh đèn tín hiệu bị phạt 150.000–250.000 đồng"
    if scope == "preserved":
        text += ", trừ hành vi quy định tại điểm a khoản 2 Điều 10."
    elif scope == "excluded_by_facts":
        question = "Người đi bộ vượt đèn đỏ trên đường phố trong khu dân cư, không phải đường cao tốc, bị phạt bao nhiêu?"
        text = "Trong tình huống bạn nêu, người đi bộ bị phạt 150.000–250.000 đồng."
    elif scope != "omitted":
        raise ValueError("Unknown exception probe")
    draft = DraftAnswer(claims=[AnswerClaim(text=text, chunk_ids=[chunks[0].id],
                                          support_state="positive_support")])
    return question, draft, chunks


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("ROADLAWQA_LIVE_LLM_TESTS") != "1",
                    reason="Set ROADLAWQA_LIVE_LLM_TESTS=1 to allow billed provider calls")
@pytest.mark.parametrize("scope", ["omitted", "preserved", "excluded_by_facts"])
async def test_verifier_checks_explicit_exception_without_demanding_irrelevant_ones(scope):
    question, draft, chunks = pedestrian_exception_case(scope)
    result = await CitationVerifier(create_provider(Settings())).verify(question, draft, chunks)
    if scope == "omitted":
        assert result.status == "failed" and result.assessments[0].supported is False
    else:
        assert result.status == "passed" and result.semantic_valid is True
