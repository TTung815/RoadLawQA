"""Regressions for the new corpus, native hybrid, provenance and inspection UI API."""

from collections import Counter
from types import SimpleNamespace

import httpx
import pytest

from ai.agent.evidence import evidence_payload
from ai.retrieval.structured import StructuredRetriever, map_unit
from ingestion.current_law_corpus import DEFAULT_OUTPUT
from ingestion.legal_registry import read_json
from ingestion.structured_corpus import load_bundle, lexical_text, source_contexts, reference_targets
from ingestion.structured_index import properties


@pytest.fixture(scope="module")
def corpus():
    return load_bundle()["chunks"]


def test_every_reviewed_source_preserved_once_and_blocks_not_lifted(corpus):
    from ingestion.legal_dependency import load_dependency
    source = read_json(DEFAULT_OUTPUT)["chunks"] + load_dependency()[0]
    assert Counter(x for u in corpus for x in u["metadata"]["source_processed_ids"]) == Counter(r["id"] for r in source)
    by_id = {r["id"]: r for r in source}
    for u in corpus:
        for identity in u["metadata"]["source_processed_ids"]:
            assert by_id[identity]["text"] in u["embedding_text"]
            if not by_id[identity]["publication_eligible"]:
                assert not u["metadata"]["publication_eligible"]
                assert len(u["metadata"]["source_processed_ids"]) == 1
    assert len(corpus) < len(source)
    for unit in corpus:
        assert unit['metadata']['source_leaf_text_sha256'] == {
            identity: by_id[identity]['source_text_sha256']
            for identity in unit['metadata']['source_processed_ids']}


def test_grouped_references_keep_document_scope_and_parenthetical_conditions():
    text = ('khoản 1 Điều 56 (đối với xe ô tô), khoản 2 Điều 56 (đối với xe máy) '
            'của Luật Trật tự, an toàn giao thông đường bộ; khoản 7 Điều 20; '
            'điểm c khoản 6 Điều 21 của Nghị định này. khoản 3 Điều này.')
    assert reference_targets(text, 'nd168', '32') == [
        ('55-vbhn-vpqh', '56', '1'), ('55-vbhn-vpqh', '56', '2'),
        ('nd168', '20', '7'), ('nd168', '21', '6'), ('nd168', '32', '3')]
    assert reference_targets('Điều 2 Luật chưa biết và Điều 3 Luật Đường bộ', 'nd168', '32') == []


@pytest.mark.asyncio
async def test_owner_sanction_expands_cross_law_license_conditions(corpus):
    from ai.retrieval.neighborhood import LegalNeighborhoodExpander
    anchor = next(u for u in corpus if 'nd168-effective-as-of-2026-09-22-d32-k14-pi'
                  in u['metadata']['source_processed_ids'])
    retriever = StructuredRetriever(corpus, None, None, None)
    selection = await LegalNeighborhoodExpander(retriever.fetch_article).expand_references([map_unit(anchor)])
    included = {x for c in selection.chunks for x in c.metadata['source_processed_ids']}
    assert '55-vbhn-vpqh-d56-k1-pa' in included


@pytest.mark.asyncio
@pytest.mark.parametrize('anchors, points_leaf', [
    # Observed top 10 of reviewed 005 and 020: whole referenced clauses (khoản
    # 11, 7, 9) filled the lookup budget before the license-points leaf that
    # names the retrieved violation point.
    (['d6-k5-ph', 'd7-k4-pđ', 'd6-k12', 'd20-k5-pm', 'd18-k9-pb', 'd6-k10-pa',
      'd6-k2-pđ', 'd6-k3-pb', 'd6-k3-pk', 'd6-k8'], 'd6-k16-pb'),
    (['d6-k11-pđ', 'd6-k7-pc', 'd6-k5-pd', 'd20-k8', 'd6-k9-pd', 'd6-k6-pb',
      'd6-k5-pi', 'd6-k4-pe', 'd6-k5-pn', 'd21-k9'], 'd6-k16-pd'),
])
async def test_points_leaf_naming_a_retrieved_violation_precedes_referenced_clauses(corpus, anchors, points_leaf):
    from ai.retrieval.neighborhood import LegalNeighborhoodExpander
    prefix = 'nd168-effective-as-of-2026-09-22-'
    by_leaf = {u['metadata']['source_processed_ids'][0]: u for u in corpus}
    retriever = StructuredRetriever(corpus, None, None, None)
    selection = await LegalNeighborhoodExpander(retriever.fetch_article).expand_references(
        [map_unit(by_leaf[prefix + leaf]) for leaf in anchors])
    included = {x for c in selection.chunks for x in c.metadata['source_processed_ids']}
    assert prefix + points_leaf in included
    assert len(selection.chunks) <= 8 and selection.added_characters <= 12000


def test_parent_introductions_are_not_clipped_and_not_duplicated(corpus):
    source = read_json(DEFAULT_OUTPUT)["chunks"]
    nodes, _ = source_contexts(source)
    long_parents = [s for u in corpus for s in u["metadata"]["context_sections"]
                    if ':clause:' in s['id'] and len(s['text']) > 400]
    assert long_parents
    for section in long_parents:
        assert section["text"] == nodes[section["id"]]["text"]
    simple = next(u for u in corpus if u['metadata']['source_processed_ids'] == ['55-vbhn-vpqh-d9-k2'])
    assert simple['embedding_text'].count(simple['text']) == 1


def test_independent_sanctions_not_merged_and_references_have_targets(corpus):
    point = next(u for u in corpus if 'nd168-effective-as-of-2026-09-22-d6-k9-pb' in u['metadata']['source_processed_ids'])
    assert point['metadata']['granularity'] == 'point'
    assert len(point['metadata']['source_processed_ids']) == 1
    ids={u['id'] for u in corpus}
    assert any(r['document_id'] == '55-vbhn-vpqh' for u in corpus if u['metadata']['document_id'].startswith('nd168')
               for r in u['metadata']['references'])
    assert all(set(r['chunk_ids']) <= ids for u in corpus for r in u['metadata']['references'])


def test_parent_context_sent_once_with_each_source_still_citable(corpus):
    units=[u for u in corpus if u['metadata']['article_no']=='6' and u['metadata']['clause_no']=='9'
           and u['metadata']['document_id'].startswith('nd168')][:2]
    assert len(units)==2
    payload=evidence_payload([map_unit(u) for u in units])
    contexts=[c['context_id'] for item in payload for c in item['shared_context']]
    assert len(contexts)==len(set(contexts))
    assert payload[0]['context_ids']==payload[1]['context_ids']
    assert payload[1]['shared_context']==[]
    assert all('enriched_text' not in p and 'source_spans' not in p['metadata'] for p in payload)
    conflicting=map_unit(units[1]).model_copy(deep=True)
    conflicting.metadata['context_sections'][0]['text']='changed parent'
    with pytest.raises(ValueError, match='conflicting'):
        evidence_payload([map_unit(units[0]),conflicting])


class Embedder:
    def encode(self, queries, **kwargs):
        self.queries=queries
        return [SimpleNamespace(tolist=lambda:[0.5]*768) for _ in queries]


class Reranker:
    def predict(self, pairs):
        self.pairs=pairs
        return list(range(len(pairs)))


@pytest.mark.asyncio
async def test_native_query_receives_separate_text_vector_and_filters(corpus):
    units=[u for u in corpus if u['metadata']['publication_eligible']][:3]
    calls=[]
    def hybrid(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(objects=[SimpleNamespace(properties=properties(u),
            metadata=SimpleNamespace(score=.6,explain_score='hybrid')) for u in units])
    embedder=Embedder()
    retriever=StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)),embedder,Reranker())
    query='Nồng Độ Cồn, bị phạt thế nào?'
    result=await retriever.search(query,2)
    assert embedder.queries==[query]
    assert calls[0]['query']==lexical_text(query)==lexical_text(query.lower())
    assert calls[0]['vector']==[.5]*768
    assert calls[0]['query_properties']==['lexical_text']
    assert calls[0]['filters'] is not None
    assert calls[0]['alpha']==.5
    assert [c.id for c in result]==[units[2]['id'],units[1]['id']]


@pytest.mark.asyncio
@pytest.mark.parametrize("expansion", [None, "Quy định về mũ bảo hiểm"])
async def test_ranking_trace_preserves_candidate_pool_and_native_views(corpus, expansion):
    from ai.diagnostics import TRACE
    units = [u for u in corpus if u['metadata']['publication_eligible']][:4]
    pools = [units[:3], [units[2], units[3], units[0]]]
    calls = []
    def hybrid(**kwargs):
        pool = pools[len(calls)]
        calls.append(kwargs)
        return SimpleNamespace(objects=[SimpleNamespace(properties=properties(u),
            metadata=SimpleNamespace(score=.6, explain_score='hybrid')) for u in pool])
    retriever = StructuredRetriever(units, SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)),
                                    Embedder(), Reranker())
    trace = []
    token = TRACE.set(trace)
    try:
        result = await retriever.search('Quy tắc đội mũ bảo hiểm', 2, retrieval_query=expansion)
    finally:
        TRACE.reset(token)
    ranking, = [event for event in trace if event['stage'] == 'retrieval_ranking']
    indices = [0, 2, 1, 3] if expansion else [0, 1, 2]
    candidates = [units[i]['id'] for i in indices]
    assert ranking['candidate_ids'] == candidates
    assert ranking['native_views'] == [
        {'view': 'original' if i == 0 else 'query_expansion', 'chunk_ids': [u['id'] for u in pool]}
        for i, pool in enumerate(pools[:2 if expansion else 1])]
    assert ranking['reranked'] == [
        {'chunk_id': identity, 'score': float(i)} for i, identity in reversed(list(enumerate(candidates)))]
    assert ranking['selected_ids'] == [c.id for c in result] == list(reversed(candidates))[:2]
    assert ranking['exact_lookup_ids'] == []
    assert len(ranking['reranked']) > len(result)


@pytest.mark.asyncio
async def test_native_rejects_changed_or_blocked_result(corpus):
    u=next(u for u in corpus if not u['metadata']['publication_eligible'])
    def hybrid(**kwargs):
        return SimpleNamespace(objects=[SimpleNamespace(properties=properties(u))])
    retriever=StructuredRetriever([u],SimpleNamespace(query=SimpleNamespace(hybrid=hybrid)),Embedder(),Reranker())
    with pytest.raises(ValueError,match='changed or blocked'):
        await retriever.search('quy định giao thông')


@pytest.mark.asyncio
async def test_inspection_endpoint_needs_no_provider_and_sanitizes_errors(corpus):
    from backend.main import app
    from backend.dependencies.retrieval import get_current_retriever
    chunk=map_unit(next(u for u in corpus if u['metadata']['publication_eligible']))
    class Fake:
        runtime_devices = {"embedding": "mps:0", "reranker": "mps:0", "hybrid_search": "cpu"}
        async def search(self,q,top_k):
            if q=='fail': raise RuntimeError('secret provider token')
            return [chunk]
        async def fetch_article(self,*args): return []
        async def fetch_combination_rules(self,*args): return []
    app.dependency_overrides[get_current_retriever]=lambda:Fake()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/api/v1/retrieve/inspect',json={'current_query':'quy định'})
            assert response.status_code==200
            assert response.json()['llm_calls']==0
            assert response.json()['devices'] == Fake.runtime_devices
            assert response.json()['context_preview']
            error=await client.post('/api/v1/retrieve/inspect',json={'current_query':'fail'})
            assert error.status_code==502
            assert 'secret' not in error.text
            history=await client.post('/api/v1/retrieve/inspect',json={'current_query':'quy định',
                'chat_history':[{'role':'user','content':'trước đó'}]})
            assert history.status_code==422
    finally:
        app.dependency_overrides.pop(get_current_retriever,None)


def test_scorer_maps_merged_unit_to_frozen_gold_only_for_canonical_content(corpus):
    from evaluation.core_scoring import deterministic_checks, gold_view
    from evaluation.revised_current_law_dataset import load_cases
    case = next(c for c in load_cases() if c.id == 'current_law_015')
    unit = next(u for u in corpus if u['metadata']['document_id'] == '49-vbhn-vpqh'
                and u['metadata']['article_no'] == '8' and u['metadata']['clause_no'] == '1')
    chunk = map_unit(unit).model_dump(mode='json')
    canonical = {unit['id']: {**unit['metadata'], 'text': unit['text'], 'enriched_text': unit['embedding_text']}}
    record = {'mode': 'end_to_end', 'error': None, 'output': {
        'retrieval': {'chunks': [chunk]}, 'answer': {'claims': [{'citations': [{
            'chunk_id': unit['id'], 'citation': chunk['citation']}]}]}}}
    checks = deterministic_checks(record, gold_view(case.gold), canonical, {})
    assert checks['evidence_completeness']['value'] == 1
    assert checks['citation_validity']['value'] == 1
    chunk['text'] = 'Tampered source with the same ID'
    checks = deterministic_checks(record, gold_view(case.gold), canonical, {})
    assert checks['evidence_completeness']['value'] == 0
    assert checks['citation_validity']['value'] == 0
