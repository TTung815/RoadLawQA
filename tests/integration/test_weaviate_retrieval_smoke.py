"""Read-only smoke against the current-law resources used by the API."""

import math
import socket

import pytest
from ai.retrieval.current_law import LazyCurrentLawRetriever
from configs.settings import Settings


@pytest.fixture(scope="module")
def live_retriever():
    settings = Settings()
    try:
        with socket.create_connection((settings.weaviate_host, settings.weaviate_port), timeout=1):
            pass
    except OSError:
        pytest.skip("Start the existing Weaviate container to run this smoke test")
    retriever = LazyCurrentLawRetriever()
    try:
        yield retriever
    finally:
        retriever.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_weaviate_retrieval_smoke(live_retriever):
    results = await live_retriever.search("vượt đèn đỏ", top_k=3)
    from ai.retrieval.devices import resolve_device
    settings = Settings()
    assert live_retriever.runtime_devices["reranker"].split(":")[0] == resolve_device(settings.reranker_device)
    assert live_retriever.runtime_devices["embedding"].split(":")[0] == resolve_device(settings.embedding_device)
    assert results
    for chunk in results:
        assert chunk.id and chunk.citation and chunk.text
        assert chunk.metadata["legal_as_of"] == "2026-09-22"
        assert chunk.metadata["publication_eligible"] is True
        assert math.isfinite(chunk.score)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("case_id, required", [
    (
        "current_law_023",
        {"nd168-effective-as-of-2026-09-22-d6-k9-pb", "nd168-effective-as-of-2026-09-22-d6-k5-ph"},
    ),
    (
        "current_law_049",
        {"55-vbhn-vpqh-d12-k1", "49-vbhn-vpqh-d26-k2-pa"},
    ),
])
async def test_observed_multi_topic_sources_survive_top_five(live_retriever, case_id, required):
    # Reuse query-only inputs. Duplicating the literal queries in test code
    # changes the historical overlap inventory bound by frozen dataset audits.
    from evaluation.core_runner import questions_for
    questions, _, _ = questions_for("reviewed")
    question = next(q for q in questions if q.id == case_id)
    results = await live_retriever.search(question.current_query, top_k=5)
    included = {source for chunk in results for source in chunk.metadata["source_processed_ids"]}
    assert required <= included
    assert len(results) == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_age_dependency_support_and_explicit_exclusion_are_retrievable(live_retriever):
    from evaluation.core_runner import questions_for
    from ai.retrieval.neighborhood import LegalNeighborhoodExpander
    questions, _, _ = questions_for('reviewed')
    question = next(q for q in questions if q.id == 'current_law_043')
    # Serving default top 10: the age facet now shares slots with the question
    # facet (observed 019), so five slots cannot hold both age sources.
    results = await live_retriever.search(question.current_query, top_k=10)
    expanded = await LegalNeighborhoodExpander(live_retriever.fetch_article).expand_references(results)
    included = {source for chunk in [*results, *expanded.chunks]
                for source in chunk.metadata['source_processed_ids']}
    assert {'90-vbhn-vpqh-2026-d5-k1-pa', '90-vbhn-vpqh-2026-d11-k5'} <= included


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["Hiện nay, vượt đèn đỏ phạt bao nhiêu tiền?",
                                   "Xe máy vượt đèn đỏ phạt bao nhiêu tiền?"])
async def test_colloquial_signal_violation_recovers_sanctions(live_retriever, query):
    # This endpoint-level search has no LLM. Supply a router-style paraphrase;
    # live routing is checked separately in the versioned chat diagnostic.
    rewrite = ("Xe máy " if query.startswith("Xe máy") else "") + "không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị phạt bao nhiêu tiền?"
    results = await live_retriever.search(query, top_k=5, retrieval_query=rewrite)
    included = {source for chunk in results for source in chunk.metadata['source_processed_ids']}
    assert {'nd168-effective-as-of-2026-09-22-d6-k9-pb',
            'nd168-effective-as-of-2026-09-22-d7-k7-pc'} <= included


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("case_id,rewrite,required", [
    ("current_law_023",
     "Cách xác định tổng tiền phạt và điểm giấy phép lái xe khi người điều khiển ô tô đồng thời không chấp hành hiệu lệnh đèn tín hiệu giao thông và cầm, sử dụng điện thoại khi xe đang di chuyển, không gây tai nạn, không có hiệu lệnh khác cho phép đi, và hai hành vi bị xử phạt trong cùng một lần.",
     {"nd168-effective-as-of-2026-09-22-d6-k9-pb", "nd168-effective-as-of-2026-09-22-d6-k5-ph"}),
    ("current_law_049",
     "Quy định về tuân thủ tốc độ tối đa cho phép khi vượt xe container trên quốc lộ, kể cả khi vượt trong thời gian ngắn",
     {"55-vbhn-vpqh-d12-k1", "49-vbhn-vpqh-d26-k2-pa"}),
    ("current_law_043",
     "Người 13 tuổi điều khiển xe máy 110cc bị công an giữ lại thì có bị xử phạt tiền không, mức phạt bao nhiêu?",
     {"90-vbhn-vpqh-2026-d5-k1-pa", "90-vbhn-vpqh-2026-d11-k5"}),
])
async def test_observed_router_rewrites_preserve_multi_topic_and_age_sources(live_retriever, case_id, rewrite, required):
    from evaluation.core_runner import questions_for
    from ai.retrieval.neighborhood import LegalNeighborhoodExpander
    query = next(q.current_query for q in questions_for("reviewed")[0] if q.id == case_id)
    results = await live_retriever.search(query, retrieval_query=rewrite)
    expansion = await LegalNeighborhoodExpander(live_retriever.fetch_article).expand_references(results)
    included = {source for chunk in [*results, *expansion.chunks]
                for source in chunk.metadata['source_processed_ids']}
    assert required <= included
