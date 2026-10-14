"""Search paraphrases remain bounded and cannot replace the answer question."""

from types import SimpleNamespace

import pytest

from ai.agent.conversation_router import ConversationDecision, ConversationRouter
from ai.retrieval.query_expansion import checked_expansion
from ai.retrieval.structured import StructuredRetriever
from tests.unit.test_agentic_retrieval import ScriptedProvider, chunk
from tests.unit.test_retrieval_selection import Embedder, native_response
from ingestion.structured_corpus import load_bundle, lexical_text


@pytest.mark.parametrize("original,expansion,reason", [
    ("Xe máy có cần mũ bảo hiểm?", " XE MÁY có cần mũ bảo hiểm! ", "duplicate"),
    ("Tôi 15 tuổi bị phạt không?", "Tôi 16 tuổi chịu xử phạt không?", "changed_numbers"),
    ("Tôi dưới 16 tuổi bị phạt không?", "Người chưa thành niên chịu xử phạt không?", "changed_numbers"),
    ("Vượt đèn đỏ bị phạt bao nhiêu?", "Theo Điều 6, phạt 20 triệu đồng", "changed_numbers"),
    ("Vượt đèn đỏ bị phạt bao nhiêu?", "x" * 801, "too_long"),
    ("Vượt đèn đỏ bị phạt bao nhiêu?", "  ", "empty"),
    ("Tôi không vượt đèn đỏ, chỉ vượt xe thì có bị phạt không?",
     "Mức xử phạt đối với hành vi vượt xe khi tham gia giao thông đường bộ", "changed_negation"),
    ("Tôi chưa đủ tuổi lái xe, bị xử lý thế nào?",
     "Tôi đủ tuổi lái xe, bị xử lý thế nào?", "changed_negation"),
])
def test_rejected_expansion_falls_back_without_a_retry(original, expansion, reason):
    assert checked_expansion(original, expansion) == (None, reason)


@pytest.mark.asyncio
@pytest.mark.parametrize("intent,expansion,expected", [
    ("legal", "Người 15 tuổi không đội mũ bảo hiểm có bị xử phạt không?", True),
    ("legal", "Người 16 tuổi không đội mũ bảo hiểm có bị xử phạt không?", False),
    ("out_of_scope", "Người 15 tuổi không đội mũ bảo hiểm có bị xử phạt không?", False),
])
async def test_router_accepts_only_bounded_legal_expansion(intent, expansion, expected):
    original = "15 tuổi đi xe không đội mũ có bị phạt không?"
    provider = ScriptedProvider([(ConversationDecision, {
        "intent": intent, "standalone_query": original, "retrieval_query": expansion,
    })])
    result = await ConversationRouter(provider).route(original)
    assert result.standalone_query == original
    assert result.retrieval_query == (expansion if expected else None)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("current,original,rewrite,history", [
    ("Còn xe máy?", "Xe máy vượt đèn đỏ phạt bao nhiêu tiền?",
     "Xe máy không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị phạt bao nhiêu tiền?",
     [{"role": "user", "content": "Ô tô vượt đèn đỏ phạt bao nhiêu tiền?"}]),
    ("Vậy vi phạm thì bị phạt bao nhiêu", "Người say rượu lái xe máy bị phạt bao nhiêu?",
     "Mức phạt tiền đối với người điều khiển xe mô tô, xe gắn máy có nồng độ cồn",
     [{"role": "user", "content": "Người say rượu có được lái xe máy không?"},
      {"role": "assistant", "content": "Không được điều khiển phương tiện khi có nồng độ cồn."}]),
])
async def test_expanded_chat_keeps_followup_facts_for_generation_and_verification(current, original, rewrite, history):
    from ai.agent.answer_generator import AnswerGenerator, DraftAnswer, GeneratedAnswer
    from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
    from ai.agent.contextualizer import QueryContextualizer
    from backend.services.answer import AnswerService
    from backend.services.chat import ChatService
    from backend.services.lean_retrieval import LeanRetrievalService
    from tests.unit.test_grounded_answer import semantic

    provider = ScriptedProvider([
        (ConversationDecision, {"intent": "legal", "standalone_query": original, "retrieval_query": rewrite}),
        (GeneratedAnswer, {"claims": [{"text": "Quy tắc theo nguồn.", "chunk_ids": ["rule"], "support_state": "positive_support"}]}),
        (SemanticVerification, semantic(1)),
    ])

    class Retriever:
        async def search(self, query, top_k=5, *, retrieval_query=None):
            self.received = (query, retrieval_query, top_k)
            return [chunk("rule")]

    retriever = Retriever()
    legal = AnswerService(LeanRetrievalService(QueryContextualizer(provider), retriever),
                          AnswerGenerator(provider), CitationVerifier(provider))
    result = await ChatService(lambda: legal, lambda: ConversationRouter(provider)).answer(current, history)
    assert result.status == "answered"
    assert retriever.received == (original, rewrite, 10)
    assert result.retrieval.original_query == current
    assert result.retrieval.standalone_query == original
    assert result.retrieval.retrieval_queries == [original, rewrite]
    assert result.retrieval.retrieval_query == rewrite
    assert result.retrieval.retrieval_attempts == 1
    assert len(provider.calls) == 3
    for call in provider.calls[1:]:
        assert call["payload"]["question"] == original
        assert rewrite not in str(call["payload"])


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Hiện nay, vượt đèn đỏ phạt bao nhiêu tiền?",
    "Con tôi 15 tuổi vượt đèn đỏ phạt bao nhiêu tiền?",
])
async def test_original_and_rewrite_pools_share_one_rerank_budget(query):
    units = [u for u in load_bundle()["chunks"] if u["metadata"]["publication_eligible"]]
    original_pool, rewritten_pool = units[:20], [units[0], *units[20:39]]
    rewrite = query.replace("vượt đèn đỏ", "không chấp hành hiệu lệnh của đèn tín hiệu giao thông")
    calls = []

    def hybrid(**kwargs):
        calls.append(kwargs)
        return native_response(original_pool if kwargs["query"] == lexical_text(query) else rewritten_pool)

    class Ranker:
        def predict(self, pairs):
            self.pairs = pairs
            return list(range(len(pairs)))

    embedder, ranker = Embedder(), Ranker()
    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)), embedder, ranker)
    result = await retriever.search(query, top_k=5, retrieval_query=rewrite)
    assert len(calls) == 2 and len(ranker.pairs) == 20
    assert len({text for _, text in ranker.pairs}) == 20
    texts = {text for _, text in ranker.pairs}
    assert all(unit["embedding_text"] in texts for unit in original_pool[:10])
    assert rewritten_pool[1]["embedding_text"] in texts
    assert embedder.queries[0] == query and rewrite in embedder.queries[1]
    from ai.retrieval.structured import age_penalty_focus
    focus = age_penalty_focus(query)
    assert all(q == (focus or rewrite) for q, _ in ranker.pairs)
    assert all(c.metadata["rerank_query_view"] == ("age_penalty" if focus else "query_expansion") for c in result)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_invalid_expansion_does_not_search_invented_locator():
    calls = []
    units = [u for u in load_bundle()["chunks"] if u["metadata"]["publication_eligible"]]

    def hybrid(**kwargs):
        calls.append(kwargs)
        return native_response([])

    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)), Embedder(), None)
    assert await retriever.search("Mức phạt vượt đèn đỏ?", retrieval_query="Điều 6 Nghị định 168/2024") == []
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_explicit_frozen_backend_also_bounds_and_deduplicates_expansion():
    from ai.retrieval.current_law import CurrentLawRetriever
    from unittest.mock import Mock

    original = [{"id": str(i), "enriched_text": str(i)} for i in range(20)]
    additional = [original[0], *[{"id": str(i), "enriched_text": str(i)} for i in range(20, 40)]]
    ranker = Mock()
    ranker.predict.side_effect = lambda pairs: [1.0] * len(pairs)
    retriever = CurrentLawRetriever([], None, None, None, ranker)
    retriever._candidates = Mock(side_effect=[[(c, .5) for c in original], [(c, .5) for c in additional]])
    # Mapping is unrelated to candidate selection; inspect the rerank boundary.
    import unittest.mock
    with unittest.mock.patch("ai.retrieval.current_law.map_chunk", side_effect=lambda c, score: c):
        results = await retriever.search("Câu hỏi gốc", top_k=5, retrieval_query="Diễn đạt tìm nguồn")
    pairs = ranker.predict.call_args.args[0]
    assert len(pairs) == 20 and len({text for _, text in pairs}) == 20
    assert len(results) == 5 and retriever._candidates.call_count == 2
    assert all(q == "Diễn đạt tìm nguồn" for q, _ in pairs)


def test_existing_question_focus_is_not_displaced_by_a_generic_rewrite():
    from evaluation.core_runner import questions_for
    query = next(q.current_query for q in questions_for("legacy")[0] if q.id == "current_law_049")
    rewrite = "Quy định về tuân thủ tốc độ tối đa cho phép khi vượt xe container trên quốc lộ"
    assert checked_expansion(query, rewrite) == (None, "existing_question_focus")
