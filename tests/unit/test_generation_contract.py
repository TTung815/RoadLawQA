"""Prevent contradictory response kinds before they require a whole draft repair."""

import pytest
from pydantic import ValidationError

from ai.agent.answer_generator import DraftAnswer, GeneratedAnswer
from ai.agent.citation_verifier import CitationVerifier
from ai.llm.openai import strict_json_schema
from tests.unit.test_agentic_retrieval import ScriptedProvider, chunk


CLAIM = {"text": "Quy tắc theo nguồn.", "chunk_ids": ["rule"], "support_state": "positive_support"}


@pytest.mark.parametrize("kind,claims,limits,questions", [
    ("complete", [CLAIM], [], []),
    ("partial", [CLAIM], ["Chưa có nguồn về phần còn lại."], []),
    ("clarification", [], ["Chưa biết loại phương tiện."], ["Bạn đi loại xe nào?"]),
    ("abstain", [], ["Chưa có quy định áp dụng trong nguồn."], []),
])
def test_valid_response_kinds_preserve_flat_diagnostic_contract(kind, claims, limits, questions):
    flat = dict(response_kind=kind, claims=claims, limitations=limits, follow_up_questions=questions)
    result = GeneratedAnswer.model_validate({"answer": flat})
    assert DraftAnswer.model_validate(result.answer.model_dump()).model_dump() == flat


@pytest.mark.parametrize("kind,claims,limits,questions", [
    ("partial", [CLAIM], [], []),  # Observed red-light draft triggered an avoidable repair.
    ("partial", [], ["Nguồn thiếu."], []),
    ("complete", [], [], []),
    ("complete", [CLAIM], ["Chưa trả lời đủ."], []),
    ("complete", [CLAIM], [], ["Bạn đi loại xe nào?"]),
    ("clarification", [], ["Chưa biết loại xe."], []),
    ("clarification", [], [], ["Loại xe nào?"]),
    ("abstain", [CLAIM], ["Nguồn thiếu."], []),
    ("abstain", [], ["Nguồn thiếu."], ["Loại xe nào?"]),
    ("abstain", [], ["  "], []),
])
def test_inconsistent_drafts_are_rejected_without_relabeling(kind, claims, limits, questions):
    with pytest.raises(ValidationError):
        GeneratedAnswer.model_validate({"answer": dict(response_kind=kind, claims=claims,
                                       limitations=limits, follow_up_questions=questions)})


def test_provider_schema_contains_response_kind_constraints():
    schema = strict_json_schema(GeneratedAnswer)
    assert schema["type"] == "object" and "anyOf" not in schema
    branches = schema["properties"]["answer"]["anyOf"]
    assert len(branches) == 4
    partial = schema["$defs"]["PartialAnswer"]
    assert partial["properties"]["limitations"]["minItems"] == 1
    assert partial["properties"]["claims"]["minItems"] == 1
    assert set(partial["required"]) == set(partial["properties"])
    assert schema["$defs"]["CompleteAnswer"]["properties"]["limitations"]["maxItems"] == 0


@pytest.mark.asyncio
async def test_verifier_still_blocks_old_empty_draft_without_a_provider_call():
    provider = ScriptedProvider([])
    result = await CitationVerifier(provider).verify("Quy tắc?", DraftAnswer(claims=[]), [chunk("rule")])
    assert result.status == "failed" and not provider.calls


@pytest.mark.asyncio
async def test_provider_ignoring_partial_contract_cannot_publish_or_trigger_hidden_retry():
    import httpx
    from backend.dependencies.answer import get_chat_service
    from backend.main import create_app
    from tests.unit.test_grounded_answer import qa_service, QUESTION

    draft = {"claims": [CLAIM], "response_kind": "partial", "limitations": []}
    service, provider, _, _ = qa_service(draft, verification=False)
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/answer", json={"current_query": QUESTION})
    assert response.status_code == 502
    assert response.json()["stage"] == "generation"
    assert "Quy tắc theo nguồn" not in response.text
    assert len(provider.calls) == 1
