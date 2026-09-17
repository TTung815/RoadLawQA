"""Offline QA regressions with the real orchestration and scripted boundaries."""

import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from ai.agent.evidence_grader import EvidenceGrade
from ai.agent.query_rewriter import RewrittenQuery
from ai.agent.range_coverage import RangeCoverage
from backend.dependencies.answer import get_answer_service
from backend.main import create_app
from backend.services.answer import AnswerService
from tests.unit.test_agentic_retrieval import chunk, make_service, ScriptedProvider

QUESTION = "Ô tô vi phạm bị phạt tiền và trừ điểm giấy phép lái xe thế nào?"
COMPLETE = {
    "sufficient": True, "reason": "Both requested consequences are supported.",
    "coverage": [{"aspect": aspect, "covered": True, "support_state": "positive_support"}
                 for aspect in ["monetary_penalty", "license_points"]],
}
DRAFT = {"claims": [
    {"support_state": "positive_support", "text": "Bị phạt tiền theo mức trong nguồn.", "chunk_ids": ["money"]},
    {"support_state": "positive_support", "text": "Bị trừ điểm giấy phép lái xe theo nguồn.", "chunk_ids": ["points"]},
]}


def semantic(count, supported=True, complete=True):
    return {"assessments": [
        {"claim_index": index, "supported": supported,
         "support_state": "positive_support" if supported else "unknown",
         "reason": "Supported by attached source." if supported else "Attached source does not support the claim."}
        for index in range(count)],
        "answer_complete": complete, "completeness_reason": "Question coverage checked."}


def qa_service(draft=DRAFT, verification=None, sufficient=True):
    grade = COMPLETE if sufficient else {
        "sufficient": False, "reason": "License evidence is missing.",
        "coverage": [{"aspect": "monetary_penalty", "covered": True, "support_state": "positive_support"},
                     {"aspect": "license_points", "covered": False}],
    }
    evidence = [chunk("money"), chunk("points")] if sufficient else [chunk("money")]
    retrieval, grading, retriever, _ = make_service([(EvidenceGrade, grade)], [evidence], max_attempts=1)
    script = [(DraftAnswer, draft)]
    if verification is not False:
        script.append((SemanticVerification, semantic(len(draft["claims"])) if verification is None else verification))
    provider = ScriptedProvider(script if sufficient else [])
    return (AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)),
            provider, grading, retriever)


@pytest.mark.asyncio
async def test_sufficient_evidence_generates_and_verifies_server_rendered_citations():
    service, provider, _, _ = qa_service()
    result = await service.answer(QUESTION, top_k=3)
    assert result.status == "answered"
    assert result.verification.provenance_valid is True
    assert result.verification.semantic_valid is True
    assert result.verification.answer_complete is True
    assert result.answer.claims[0].citations[0].model_dump() == {
        "chunk_id": "money", "citation": "Test citation money"}
    assert "Căn cứ pháp lý: Test citation points" in result.answer.text
    assert [item.chunk_id for item in result.evidence_citations] == ["money", "points"]
    assert [call["schema"] for call in provider.calls] == [DraftAnswer, SemanticVerification]
    generation, verification = [call["payload"] for call in provider.calls]
    assert generation["question"] == verification["question"] == QUESTION
    assert generation["required_aspects"] == ["monetary_penalty", "license_points"]
    assert [item["id"] for item in generation["chunks"]] == ["money", "points"]
    assert [item["id"] for item in verification["claims"][0]["cited_chunks"]] == ["money"]
    assert [item["id"] for item in verification["claims"][1]["cited_chunks"]] == ["points"]
    assert all(value >= 0 for value in result.timings.model_dump().values())
    assert all(value >= 0 for value in result.retrieval.timings.model_dump().values())
    assert result.timings.total_ms >= result.retrieval.timings.total_ms
    assert result.repair_attempts == 0


@pytest.mark.asyncio
async def test_insufficient_retrieval_skips_generation_and_preserves_evidence():
    service, provider, _, _ = qa_service(sufficient=False)
    result = await service.answer(QUESTION)
    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.verification.status == "not_run"
    assert provider.calls == []
    assert [item.chunk_id for item in result.evidence_citations] == ["money"]
    assert result.retrieval.grade.missing_aspects == ["license_points"]
    assert "không có nghĩa chế tài không tồn tại" in result.message
    assert result.timings.generation_ms == result.timings.verification_ms == 0


@pytest.mark.asyncio
async def test_clause_membership_cannot_authorize_a_negative_answer():
    anchor, provision_a, provision_b = chunk("anchor"), chunk("provision-a"), chunk("provision-b")
    for provision in (provision_a, provision_b):
        provision.metadata["structural_context"] = {
            "complete_clause_chunk_ids": ["provision-a", "provision-b"],
            "purpose": "additional_sanction_applicability",
        }
    grade = {"sufficient": True, "reason": "Complete applicability evidence supplied.",
             "coverage": [{"aspect": "additional_sanction", "covered": True, "support_state": "negative_support"}]}
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade)],
                                      [[anchor, provision_a, provision_b]], max_attempts=1)
    provider = ScriptedProvider([])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(
        "Hành vi này có bị tước giấy phép lái xe không?")
    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.retrieval.grade.coverage[0].support_state == "unknown"
    assert result.verification.status == "not_run"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_fabricated_citation_fails_without_semantic_call_or_draft_publication():
    service, provider, _, _ = qa_service(
        {"claims": [{"support_state": "positive_support", "text": "Một nhận định.", "chunk_ids": ["invented"]}]}, verification=False)
    result = await service.answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.provenance_valid is False
    assert result.verification.semantic_valid is None
    assert "outside final evidence" in result.verification.issues[0]
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_valid_id_unsupported_claim_fails_and_no_repair_loop_occurs():
    service, provider, _, _ = qa_service(verification=semantic(2, supported=False))
    result = await service.answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.provenance_valid is True
    assert result.verification.semantic_valid is False
    assert result.repair_attempts == 0
    assert len(provider.calls) == 2
    assert provider.script == []


@pytest.mark.asyncio
async def test_complementary_retry_leaves_reach_generation_and_claim_verification():
    gap = {"sufficient": False, "reason": "Missing license consequences.", "coverage": [
        {"aspect": "monetary_penalty", "covered": True, "support_state": "positive_support"}, {"aspect": "license_points", "covered": False}]}
    retrieval, _, retriever, _ = make_service([
        (EvidenceGrade, gap), (RewrittenQuery, {"rewritten_query": "Ô tô vi phạm bị trừ điểm GPLX thế nào?"}),
        (EvidenceGrade, COMPLETE),
    ], [[chunk("money")], [chunk("points")]])
    draft = {"claims": [{"support_state": "positive_support", "text": "Có cả tiền phạt và hậu quả GPLX theo các nguồn.",
                         "chunk_ids": ["money", "points"]}]}
    provider = ScriptedProvider([(DraftAnswer, draft), (SemanticVerification, semantic(1))])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.status == "answered"
    assert result.retrieval.selected_attempt == 2
    assert len(retriever.calls) == 2
    assert [item["id"] for item in provider.calls[0]["payload"]["chunks"]] == ["money", "points"]
    assert [item["id"] for item in provider.calls[1]["payload"]["claims"][0]["cited_chunks"]] == ["money", "points"]
    assert [citation.chunk_id for citation in result.answer.claims[0].citations] == ["money", "points"]


@pytest.mark.asyncio
@pytest.mark.parametrize("collapsed", [False, True])
async def test_numeric_boundary_is_visible_to_verifier_and_collapse_is_rejected(collapsed):
    # Scope is the generator/verifier boundary; retrieval range proof has its own tests.
    lower, upper = chunk("lower"), chunk("upper")
    lower.text = lower.enriched_text = "Ô tô: từ 10 km/h đến 20 km/h; phạt mức A, trừ 02 điểm."
    upper.text = upper.enriched_text = "Ô tô: trên 20 km/h đến 35 km/h; phạt mức B, trừ 04 điểm."
    question = "Ô tô vượt tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?"
    draft = DraftAnswer(claims=[
        {"support_state": "positive_support", "text": "Từ 20 đến 35 km/h đều bị trừ 04 điểm." if collapsed else
                 "Đúng 20 km/h: mức A, trừ 02 điểm; trên 20 đến 35 km/h: mức B, trừ 04 điểm.",
         "chunk_ids": ["lower", "upper"]}])
    provider = ScriptedProvider([(SemanticVerification, semantic(1, supported=not collapsed))])
    result = await CitationVerifier(provider).verify(question, draft, [lower, upper], ["threshold_range"])
    assert result.status == ("failed" if collapsed else "passed")
    attached = provider.calls[0]["payload"]["claims"][0]["cited_chunks"]
    assert [item["text"] for item in attached] == [lower.text, upper.text]
    assert provider.calls[0]["payload"]["question"] == question
    assert "đúng B" in provider.calls[0]["prompt"]


def inclusive_range_evidence():
    lower, upper = chunk("lower"), chunk("upper")
    for item in (lower, upper):
        item.metadata.update(article_no="99", article_title="Test vehicle sanctions")
    lower.text = lower.enriched_text = "Ô tô: từ 10 km/h đến 20 km/h; hậu quả A."
    upper.text = upper.enriched_text = "Ô tô: trên 20 km/h đến 35 km/h; hậu quả B."
    proof = RangeCoverage(question_quote="từ 20 đến 35 km/h", unit="km/h", leaves=[
        {"chunk_id": "lower", "range_quote": "từ 10 km/h đến 20 km/h", "compatible": True},
        {"chunk_id": "upper", "range_quote": "trên 20 km/h đến 35 km/h", "compatible": True},
    ])
    return "Ô tô vượt tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?", [lower, upper], proof


@pytest.mark.asyncio
async def test_reproduced_upper_only_answer_fails_deterministically_for_missing_boundary_source():
    question, evidence, proof = inclusive_range_evidence()
    draft = DraftAnswer(claims=[{"support_state": "positive_support", "text": "Trên 20 đến 35 km/h: hậu quả B.", "chunk_ids": ["upper"]}])
    provider = ScriptedProvider([])
    result = await CitationVerifier(provider).verify(question, draft, evidence, ["threshold_range"], proof)
    assert result.status == "failed"
    assert result.provenance_valid is True
    assert result.answer_complete is False
    assert "lower" in result.issues[0]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_generation_receives_proven_point_boundary_and_open_upper_branch():
    question, evidence, proof = inclusive_range_evidence()
    provider = ScriptedProvider([(DraftAnswer, {"claims": [
        {"support_state": "positive_support", "text": "Đúng 20: hậu quả A; trên 20 đến 35: hậu quả B.", "chunk_ids": ["lower", "upper"]}]})])
    await AnswerGenerator(provider).generate(question, evidence, ["threshold_range"], proof)
    branches = provider.calls[0]["payload"]["required_range"]["branches"]
    assert branches[0]["requested_intersection"] == {
        "lower": "20", "upper": "20", "lower_closed": True, "upper_closed": True}
    assert branches[1]["requested_intersection"] == {
        "lower": "20", "upper": "35", "lower_closed": False, "upper_closed": True}


@pytest.mark.asyncio
async def test_real_qa_orchestration_carries_range_proof_to_both_llm_stages():
    question, evidence, proof = inclusive_range_evidence()
    grade = {"sufficient": True, "reason": "Joint numeric coverage supported.",
             "coverage": [{"aspect": "subject_violation", "covered": True, "support_state": "positive_support"},
                          {"aspect": "threshold_range", "covered": True, "support_state": "positive_support"}],
             "range_coverage": proof.model_dump()}
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade)], [evidence], max_attempts=1)
    draft = {"claims": [{"support_state": "positive_support", "text": "Đúng 20: hậu quả A; trên 20 đến 35: hậu quả B.",
                         "chunk_ids": ["lower", "upper"]}]}
    response = semantic(1)
    response["range_assessments"] = [
        {"branch_index": index, "addressed": True, "reason": "Correct branch answered."}
        for index in [0, 1]]
    provider = ScriptedProvider([(DraftAnswer, draft), (SemanticVerification, response)])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(question)
    assert result.status == "answered"
    assert provider.calls[0]["payload"]["required_range"] == provider.calls[1]["payload"]["required_range"]
    assert [item.chunk_id for item in result.verification.range_assessments] == ["lower", "upper"]


@pytest.mark.asyncio
@pytest.mark.parametrize("addressed", [True, False])
async def test_branch_assessment_overrides_optimistic_global_completeness(addressed):
    question, evidence, proof = inclusive_range_evidence()
    draft = DraftAnswer(claims=[{"support_state": "positive_support", "text": "Đúng 20: hậu quả A; trên 20 đến 35: hậu quả B.",
                                "chunk_ids": ["lower", "upper"]}])
    response = semantic(1)
    response["range_assessments"] = [
        {"branch_index": 0, "addressed": addressed, "reason": "Point boundary checked."},
        {"branch_index": 1, "addressed": True, "reason": "Open interval checked."},
    ]
    provider = ScriptedProvider([(SemanticVerification, response)])
    result = await CitationVerifier(provider).verify(question, draft, evidence, ["threshold_range"], proof)
    assert result.status == ("passed" if addressed else "failed")
    assert result.answer_complete is addressed
    assert result.semantic_valid is True  # Individual claims can be true but incomplete.
    assert provider.calls[0]["payload"]["required_range"]["branches"][0]["chunk_id"] == "lower"


@pytest.mark.asyncio
@pytest.mark.parametrize("indices", [[], [1], [0, 0], [0, 2], [0, 1, 2]])
async def test_each_required_range_branch_needs_exactly_one_verifier_assessment(indices):
    question, evidence, proof = inclusive_range_evidence()
    draft = DraftAnswer(claims=[{"support_state": "positive_support", "text": "Đúng 20: hậu quả A; trên 20 đến 35: hậu quả B.",
                                "chunk_ids": ["lower", "upper"]}])
    response = semantic(1)
    response["range_assessments"] = [{"branch_index": index, "addressed": True, "reason": "Checked."} for index in indices]
    provider = ScriptedProvider([(SemanticVerification, response)])
    result = await CitationVerifier(provider).verify(question, draft, evidence, ["threshold_range"], proof)
    assert result.status == "failed"
    assert result.semantic_valid is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["generator", "verifier", "retrieval"])
async def test_provider_and_retrieval_failures_propagate(stage):
    service, provider, grading, _ = qa_service()
    if stage == "generator":
        provider.script[0] = (DraftAnswer, RuntimeError("generator unavailable"))
    elif stage == "verifier":
        provider.script[1] = (SemanticVerification, RuntimeError("verifier unavailable"))
    else:
        grading.script[0] = (EvidenceGrade, RuntimeError("retrieval grading unavailable"))
    with pytest.raises(RuntimeError, match="unavailable"):
        await service.answer(QUESTION)
    assert len(provider.calls) == {"generator": 1, "verifier": 2, "retrieval": 0}[stage]


@pytest.mark.asyncio
@pytest.mark.parametrize("indices", [[], [0], [0, 0], [0, 2], [0, 1, 2]])
async def test_missing_duplicate_or_invented_verifier_assessments_fail_closed(indices):
    response = semantic(2)
    response["assessments"] = [dict(response["assessments"][0], claim_index=index) for index in indices]
    service, provider, _, _ = qa_service(verification=response)
    result = await service.answer(QUESTION)
    assert result.status == "verification_failed"
    assert result.answer is None
    assert result.verification.semantic_valid is None
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_supported_claims_with_incomplete_answer_are_not_published():
    service, _, _, _ = qa_service(verification=semantic(2, complete=False))
    result = await service.answer(QUESTION)
    assert result.verification.semantic_valid is True
    assert result.verification.answer_complete is False
    assert result.answer is None


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [
    {"claims": []},
    {"claims": [{"support_state": "positive_support", "text": "Mức phạt được quy định tại Điều 999.", "chunk_ids": ["money"]}]},
    {"claims": [{"support_state": "positive_support", "text": "Bị phạt theo nguồn.", "chunk_ids": ["money", "money"]}]},
])
async def test_empty_draft_inline_reference_and_duplicate_id_fail_without_verifier(draft):
    service, provider, _, _ = qa_service(draft, verification=False)
    result = await service.answer(QUESTION)
    assert result.verification.status == "failed"
    assert result.answer is None
    assert len(provider.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("sufficient", [True, False])
async def test_answer_api_observable_success_and_insufficiency(sufficient):
    service, _, _, retriever = qa_service(sufficient=sufficient)
    app = create_app()
    app.dependency_overrides[get_answer_service] = lambda: service
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/answer", json={"current_query": QUESTION, "top_k": 3})
    assert response.status_code == 200
    result = response.json()
    assert result["retrieval"]["original_query"] == result["retrieval"]["standalone_query"] == QUESTION
    assert result["retrieval"]["grade"]["sufficient"] is sufficient
    assert result["status"] == ("answered" if sufficient else "insufficient_evidence")
    assert result["repair_attempts"] == 0
    assert result["evidence_citations"]
    assert "generation_ms" in result["timings"]
    assert "grading_ms" in result["retrieval"]["timings"]
    assert retriever.calls == [(QUESTION, 3)]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["generator", "verifier"])
async def test_answer_api_provider_failure_is_server_error_without_legal_answer(stage):
    service, provider, _, _ = qa_service()
    index, schema = (0, DraftAnswer) if stage == "generator" else (1, SemanticVerification)
    provider.script[index] = (schema, RuntimeError("provider unavailable"))
    app = create_app()
    app.dependency_overrides[get_answer_service] = lambda: service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/answer", json={"current_query": QUESTION})
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


@pytest.mark.asyncio
async def test_missing_citation_metadata_fails_before_semantic_verification():
    evidence = chunk("money")
    evidence.citation = " "
    draft = DraftAnswer(claims=[{"support_state": "positive_support", "text": "Một nhận định.", "chunk_ids": ["money"]}])
    provider = ScriptedProvider([])
    result = await CitationVerifier(provider).verify(QUESTION, draft, [evidence])
    assert result.status == "failed"
    assert "missing citation metadata" in result.issues[0]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_duplicate_final_evidence_ids_are_rejected_without_verifier_call():
    draft = DraftAnswer(claims=[{"support_state": "positive_support", "text": "Một nhận định.", "chunk_ids": ["money"]}])
    provider = ScriptedProvider([])
    with pytest.raises(ValueError, match="unique chunk IDs"):
        await CitationVerifier(provider).verify(QUESTION, draft, [chunk("money"), chunk("money")])
    assert provider.calls == []


def test_qa_workflow_runs_without_network_models_or_api_keys():
    script = '''
import asyncio, importlib.abc, socket, sys
blocked = ('backend.retriever_custom', 'backend.generator', 'torch',
           'sentence_transformers', 'weaviate', 'google.generativeai', 'google.genai')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Unexpected resource import: ' + fullname)
sys.meta_path.insert(0, Guard())
def no_network(*args, **kwargs):
    raise AssertionError('Unexpected network connection')
socket.create_connection = socket.socket.connect = socket.socket.connect_ex = no_network
from tests.unit.test_grounded_answer import qa_service, QUESTION
service, provider, _, _ = qa_service()
assert asyncio.run(service.answer(QUESTION)).status == 'answered'
assert not any(name in sys.modules for name in blocked)
'''
    env = dict(os.environ)
    env.pop("GEMINI_API_KEY", None)
    env.pop("GEMINI_API_KEYS", None)
    subprocess.run([sys.executable, "-B", "-c", script], env=env,
                   cwd=Path(__file__).resolve().parents[2], check=True)
