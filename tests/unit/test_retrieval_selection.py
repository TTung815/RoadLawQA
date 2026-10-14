"""Observed losses before rerank, question intent and CPU score restoration."""

from types import SimpleNamespace

import pytest

from ai.retrieval.reranking import LengthBatchedReranker
from ai.retrieval.structured import StructuredRetriever, question_focus
from ingestion.structured_corpus import load_bundle, lexical_text
from ingestion.structured_index import properties


class Embedder:
    def encode(self, queries, **kwargs):
        self.queries = queries
        return [SimpleNamespace(tolist=lambda: [0.5] * 768) for _ in queries]


@pytest.fixture(scope="module")
def units():
    return [u for u in load_bundle()["chunks"] if u["metadata"]["publication_eligible"]]


def native_response(units):
    return SimpleNamespace(objects=[SimpleNamespace(
        properties=properties(u), metadata=SimpleNamespace(score=.5, explain_score="hybrid"))
        for u in units])


@pytest.mark.asyncio
async def test_second_simultaneous_action_survives_native_cutoff(units):
    # The actual red-light sanction was native rank 29, outside the former 20.
    target = next(u for u in units if "nd168-effective-as-of-2026-09-22-d6-k9-pb"
                  in u["metadata"]["source_processed_ids"])
    pool = [u for u in units if u != target][:28] + [target] + units[40:55]
    calls = []

    def hybrid(**kwargs):
        calls.append(kwargs)
        return native_response(pool[:kwargs["limit"]])

    class Reranker:
        def predict(self, pairs):
            self.pairs = pairs
            return [1.0 if text == target["embedding_text"] else .1 for _, text in pairs]

    ranker = Reranker()
    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)),
                                    Embedder(), ranker)
    result = await retriever.search("Tôi lái ô tô vượt đèn đỏ và đồng thời sử dụng điện thoại.")
    assert target["id"] in {c.id for c in result}
    assert len(ranker.pairs) <= 40
    assert len(calls) == 1
    await retriever.search("Tôi lái ô tô sử dụng điện thoại.")
    assert len(ranker.pairs) == 20


@pytest.mark.asyncio
async def test_question_focus_keeps_scenario_and_recovers_speed_obligation(units):
    target = next(u for u in units if "55-vbhn-vpqh-d12-k1" in u["metadata"]["source_processed_ids"])
    other = [u for u in units if u != target][:30]
    query = "Khi vượt xe container trên quốc lộ, tôi có phải tuân thủ tốc độ tối đa cho phép không?"
    focus = "tôi có phải tuân thủ tốc độ tối đa cho phép không?"
    calls = []

    def hybrid(**kwargs):
        calls.append(kwargs)
        pool = other[:18] + [target] + other[18:] if kwargs["query"] == lexical_text(query) else [target] + other
        return native_response(pool[:kwargs["limit"]])

    class Reranker:
        def predict(self, pairs):
            self.pairs = pairs
            # Mimics the observed original-vs-question ranking failure.
            return [1.0 if q == focus and text == target["embedding_text"] else .1 for q, text in pairs]

    embedder, ranker = Embedder(), Reranker()
    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)),
                                    embedder, ranker)
    result = await retriever.search(query)
    assert result[0].id == target["id"]
    assert embedder.queries == [query, focus]
    assert len(calls) == 2
    assert len(ranker.pairs) == 20
    assert result[0].metadata["rerank_query_view"] == "question_focus"


@pytest.mark.parametrize("query", [
    "Nếu đang làm nhiệm vụ khẩn cấp, tôi có phải tuân thủ tốc độ không?",
    "Trừ trường hợp được ưu tiên, tôi có phải chấp hành đèn không?",
    "Khi nào phải bật đèn chiếu sáng?",
    "Tôi lái xe, tôi có phải tuân thủ tốc độ không?",
])
def test_conditional_queries_are_not_reduced_to_a_question(query):
    assert question_focus(query) is None


def test_length_batches_restore_scores_without_shortening_sources():
    pairs = [["query", "very long parent and source text"], ["query", "short"], ["query", "medium length"]]
    expected = {text: score for (_, text), score in zip(pairs, [.7, .1, .4])}

    class Model:
        max_length = None

        def tokenizer(self, queries, texts, **kwargs):
            assert texts == [p[1] for p in pairs]
            assert kwargs["max_length"] is None
            return {"length": [len(text) for text in texts]}

        def predict(self, sorted_pairs, **kwargs):
            self.received = sorted_pairs
            assert kwargs["batch_size"] == 2
            return [expected[text] for _, text in sorted_pairs]

    model = Model()
    ranker = LengthBatchedReranker(model, batch_size=2)
    assert ranker.predict(pairs) == [.7, .1, .4]
    assert model.received == [pairs[1], pairs[2], pairs[0]]
    assert ranker.predict([]) == []


def test_invalid_budgets_fail_before_loading_resources():
    from configs.settings import Settings
    from evaluation.core_schema import RunSettings

    with pytest.raises(ValueError):
        Settings(hybrid_candidate_limit=40, compound_candidate_limit=20)
    with pytest.raises(ValueError):
        RunSettings(model="fixture", embedding_revision="fixture", reranker_revision="fixture",
                    hybrid_candidate_limit=41)
    with pytest.raises(ValueError):
        LengthBatchedReranker(None, batch_size=0)


def test_new_plans_lock_the_serving_selection_and_batch_settings(monkeypatch):
    from evaluation.core_runner import default_settings
    monkeypatch.setenv("HYBRID_CANDIDATE_LIMIT", "24")
    monkeypatch.setenv("COMPOUND_CANDIDATE_LIMIT", "36")
    monkeypatch.setenv("RERANKER_BATCH_SIZE", "8")
    settings = default_settings()
    assert (settings.hybrid_candidate_limit, settings.compound_candidate_limit, settings.reranker_batch_size) == (24, 36, 8)


@pytest.mark.asyncio
async def test_age_condition_survives_vehicle_owner_distraction_within_budget(units):
    from evaluation.core_runner import questions_for
    from ai.retrieval.structured import age_penalty_focus
    query = next(q.current_query for q in questions_for('legacy')[0] if q.id == 'current_law_043')
    target = next(u for u in units if '90-vbhn-vpqh-2026-d11-k5' in u['metadata']['source_processed_ids'])
    unrelated = [u for u in units if u['metadata']['document_id'].startswith('nd168')][:30]
    focus = age_penalty_focus(query)
    calls = []

    def hybrid(**kwargs):
        calls.append(kwargs)
        return native_response((unrelated if kwargs['query'] == lexical_text(query)
                                else [target, *unrelated])[:kwargs['limit']])

    class Ranker:
        def predict(self, pairs):
            self.pairs = pairs
            return [1.0 if q == focus and text == target['embedding_text'] else .1 for q, text in pairs]

    embedder, ranker = Embedder(), Ranker()
    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)), embedder, ranker)
    results = await retriever.search(query)
    assert target['id'] in {c.id for c in results}
    assert embedder.queries[0] == query
    assert len(calls) == 2 and len(ranker.pairs) == 20
    assert results[0].metadata['rerank_query_view'] == 'age_penalty'


@pytest.mark.parametrize('query', [
    'Trẻ 9 tuổi ngồi ghế nào trên ô tô?',
    'Ô tô 10 năm tuổi phải đăng kiểm khi nào?',
    'Đi xe máy vượt đèn đỏ bị phạt bao nhiêu?',
])
def test_age_view_does_not_trigger_for_unrelated_age_or_penalty_questions(query):
    from ai.retrieval.structured import age_penalty_focus
    assert age_penalty_focus(query) is None


def test_child_penalty_without_age_searches_age_conditions_without_inventing_an_age():
    from ai.retrieval.structured import age_penalty_focus
    focus = age_penalty_focus('Con tôi vi phạm giao thông có bị phạt tiền hay chỉ cảnh cáo?')
    assert focus and 'độ tuổi' in focus
    assert not any(character.isdigit() for character in focus)


