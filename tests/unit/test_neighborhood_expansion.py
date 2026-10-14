"""Structural selection and agent routing with deterministic providers, no resources."""

import pytest

from ai.agent.contextualizer import QueryContextualizer
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.agent.query_rewriter import QueryRewriter, RewrittenQuery
from ai.retrieval.base import RetrievedChunk
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from backend.services.agentic_retrieval import AgenticRetrievalService
from tests.unit.test_agentic_retrieval import ScriptedProvider, ScriptedRetriever

QUESTION = 'Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?'


def legal(identifier, clause='6', point='a', text='Test monetary evidence for the requested car range.',
          head='Phạt tiền đối với người điều khiển xe', law='Test regulation', article='6'):
    return RetrievedChunk(id=identifier, text=text, enriched_text=text,
                          citation=f'{law}: Điều {article}, khoản {clause}, điểm {point}', score=0.8,
                          metadata={'law': law, 'article_no': article, 'clause_no': clause,
                                    'point': point, 'clause_head': head})


def consequence(identifier='points', clause='16', point='b', reference='khoản 6', **kwargs):
    return legal(identifier, clause, point,
                 text=f'Thực hiện hành vi quy định tại {reference} Điều này bị trừ điểm giấy phép lái xe.',
                 head='Ngoài hình thức xử phạt còn bị trừ điểm giấy phép lái xe', **kwargs)


def assessment(sufficient, anchors=('fine',), aspect='license_points', **coverage):
    values = {'monetary_penalty': True, 'subject_violation': True, 'threshold_range': True,
              aspect: sufficient, **coverage}
    return {'sufficient': sufficient, 'reason': 'Complete coverage.' if sufficient else 'Missing consequence evidence.',
            'coverage': [{'aspect': key, 'covered': value, 'support_state': 'positive_support' if value else 'unknown'} for key, value in values.items()],
            'anchor_chunk_ids': list(anchors)}


class Lookup:
    def __init__(self, chunks):
        self.chunks, self.calls = chunks, []

    async def fetch(self, law, article):
        self.calls.append((law, article))
        if isinstance(self.chunks, Exception):
            raise self.chunks
        return self.chunks


def service(script, batches, lookup, **budgets):
    provider = ScriptedProvider(script)
    retriever = ScriptedRetriever(batches)
    agent = AgenticRetrievalService(QueryContextualizer(provider), retriever,
                                   EvidenceGrader(provider), QueryRewriter(provider), max_attempts=1,
                                   structural_expander=LegalNeighborhoodExpander(lookup.fetch, **budgets))
    return agent, provider, retriever


@pytest.mark.asyncio
async def test_sufficient_evidence_does_not_expand():
    lookup = Lookup(AssertionError('Must not look up siblings'))
    agent, _, _ = service([(EvidenceGrade, assessment(True))], [[legal('fine')]], lookup)
    result = await agent.retrieve(QUESTION)
    assert result.structural_expansions == []
    assert lookup.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize('aspect', ['license_points', 'additional_sanction'])
async def test_gap_expands_and_grades_complementary_evidence(aspect):
    sibling = consequence()
    if aspect == 'additional_sanction':
        sibling = legal('points', '15', 'b', 'Hành vi tại khoản 6 Điều này bị tước quyền sử dụng GPLX.',
                        head='Các hình thức xử phạt bổ sung')
    lookup = Lookup([sibling])
    fine = legal('fine')
    agent, provider, retriever = service([
        (EvidenceGrade, assessment(False, aspect=aspect)),
        (EvidenceGrade, assessment(True, aspect=aspect)),
    ], [[fine]], lookup)
    result = await agent.retrieve(QUESTION)
    assert lookup.calls == [('Test regulation', '6')]
    assert result.chunks == [fine, sibling]
    assert result.grade.sufficient is True
    assert result.rewritten_query is None
    assert len(retriever.calls) == 1
    assert [c['payload']['question'] for c in provider.calls] == [QUESTION, QUESTION]
    assert [c['id'] for c in provider.calls[1]['payload']['chunks']] == ['fine', 'points']
    trace = result.structural_expansions[0]
    assert trace.triggered is True
    assert trace.missing_aspects == [aspect]
    assert trace.scopes[0].anchor_chunk_ids == ['fine']
    assert trace.scopes[0].candidate_count == 1
    assert trace.grade_before.sufficient is False
    assert trace.grade_after.sufficient is True
    assert trace.chunk_ids == ['points']
    assert trace.citations == [sibling.citation]
    assert trace.evidence_chunk_ids == ['fine', 'points']


@pytest.mark.asyncio
async def test_same_law_article_and_local_reference_scope_is_enforced():
    fine = legal('fine')
    good = consequence()
    bad = [consequence('other-law', law='Another regulation'),
           consequence('other-article', article='7'),
           consequence('other-clause', reference='khoản 7'),
           legal('external-reference', '16', text='Hành vi tại khoản 6 Điều 7 bị trừ điểm.', head='Trừ điểm')]
    selection = await LegalNeighborhoodExpander(Lookup(bad + [good]).fetch).expand(
        [fine], ['license_points'], [fine])
    assert selection.chunks == [good]
    assert selection.scopes[0].candidate_count == 5


@pytest.mark.asyncio
async def test_lookup_finds_nothing_preserves_evidence_and_insufficient_grade():
    fine = legal('fine')
    agent, provider, _ = service([(EvidenceGrade, assessment(False))], [[fine]], Lookup([]))
    result = await agent.retrieve(QUESTION)
    assert result.chunks == [fine]
    assert result.grade.sufficient is False
    assert len(provider.calls) == 1
    assert result.structural_expansions[0].chunk_ids == []


@pytest.mark.asyncio
async def test_duplicate_structural_evidence_is_not_added_twice():
    fine, points = legal('fine'), consequence()
    lookup = Lookup([points, points])
    agent, _, _ = service([(EvidenceGrade, assessment(False)), (EvidenceGrade, assessment(True))], [[fine]], lookup)
    result = await agent.retrieve(QUESTION)
    assert [chunk.id for chunk in result.chunks] == ['fine', 'points']
    selection = await LegalNeighborhoodExpander(lookup.fetch).expand([fine], ['license_points'], [fine, points])
    assert selection.chunks == []


@pytest.mark.asyncio
@pytest.mark.parametrize('question,anchor_clause,anchor_point,expected,range_quote', [
    ('Ô tô vượt quá tốc độ đúng 20 km/h bị xử phạt thế nào?', '5', 'đ', 'exact-20', 'đúng 20 km/h'),
    ('Ô tô vượt quá tốc độ trên 20 đến 35 km/h bị xử phạt thế nào?', '6', 'a', 'over-20', 'trên 20 đến 35 km/h'),
])
async def test_exact_20_and_over_20_use_distinct_anchor_references(question, anchor_clause, anchor_point, expected, range_quote):
    fine = legal('fine', anchor_clause, anchor_point, text=question)
    exact = consequence('exact-20', point='a', reference='điểm a, điểm đ khoản 5')
    over = consequence('over-20', point='b', reference='khoản 6')
    proof = {'question_quote': range_quote, 'unit': 'km/h',
             'leaves': [{'chunk_id': 'fine', 'range_quote': range_quote, 'compatible': True}]}
    agent, provider, _ = service([(EvidenceGrade, {**assessment(False), 'range_coverage': proof}),
                                 (EvidenceGrade, {**assessment(True), 'range_coverage': proof})],
                                 [[fine]], Lookup([exact, over]))
    result = await agent.retrieve(question)
    assert [chunk.id for chunk in result.chunks] == ['fine', expected]
    assert all(call['payload']['question'] == question for call in provider.calls)


@pytest.mark.asyncio
async def test_closed_range_can_use_two_distinct_monetary_anchors():
    exact_anchor, over_anchor = legal('exact', '5', 'đ'), legal('over', '6', 'a')
    exact = consequence('exact-20', point='a', reference='điểm đ khoản 5')
    over = consequence('over-20', reference='khoản 6')
    selection = await LegalNeighborhoodExpander(Lookup([over, exact]).fetch).expand(
        [exact_anchor, over_anchor], ['license_points'], [exact_anchor, over_anchor])
    assert [chunk.id for chunk in selection.chunks] == ['exact-20', 'over-20']


@pytest.mark.asyncio
async def test_lookup_failure_propagates_as_error():
    agent, _, _ = service([(EvidenceGrade, assessment(False))], [[legal('fine')]], Lookup(RuntimeError('lookup unavailable')))
    with pytest.raises(RuntimeError, match='lookup unavailable'):
        await agent.retrieve(QUESTION)


@pytest.mark.asyncio
@pytest.mark.parametrize('coverage', [{'subject_violation': False}, {'threshold_range': False}])
async def test_unresolved_applicability_can_lookup_but_does_not_authorize_publication(coverage):
    lookup = Lookup([])
    agent, _, _ = service([(EvidenceGrade, assessment(False, **coverage))], [[legal('fine')]], lookup)
    result = await agent.retrieve(QUESTION)
    assert lookup.calls == [('Test regulation', '6')]
    assert result.structural_expansions[0].triggered is True
    assert result.grade.sufficient is False


@pytest.mark.asyncio
async def test_grader_cannot_invent_anchor_ids():
    provider = ScriptedProvider([(EvidenceGrade, assessment(False, anchors=('invented',)))])
    with pytest.raises(ValueError, match='outside supplied evidence'):
        await EvidenceGrader(provider).grade(QUESTION, [legal('fine')])


@pytest.mark.asyncio
async def test_budget_never_partially_includes_an_exhaustive_additional_clause():
    fine = legal('fine')
    group = [legal(f'extra-{p}', '15', p, f'Hành vi tại khoản {n} Điều này.',
                   head='Các hình thức xử phạt bổ sung') for p, n in [('a', 11), ('b', 12)]]
    lookup = Lookup(group + [consequence()])
    selection = await LegalNeighborhoodExpander(lookup.fetch, max_chunks=2).expand(
        [fine], ['license_points', 'additional_sanction'], [fine])
    assert [chunk.id for chunk in selection.chunks] == ['points']
    selection = await LegalNeighborhoodExpander(lookup.fetch, max_characters=1).expand(
        [fine], ['license_points', 'additional_sanction'], [fine])
    assert selection.chunks == []


@pytest.mark.asyncio
async def test_no_anchor_or_unsupported_gap_performs_no_lookup():
    lookup = Lookup(AssertionError('No lookup expected'))
    expander = LegalNeighborhoodExpander(lookup.fetch)
    assert not (await expander.expand([], ['license_points'], [])).triggered
    assert not (await expander.expand([legal('fine')], ['threshold_range'], [])).triggered
    assert lookup.calls == []


@pytest.mark.asyncio
async def test_expansion_runs_once_and_rewrite_uses_remaining_gap():
    fine, points = legal('fine'), consequence()
    lookup = Lookup([points])
    provider = ScriptedProvider([
        (EvidenceGrade, assessment(False)),
        (EvidenceGrade, assessment(False, aspect='additional_sanction')),
        (RewrittenQuery, {'rewritten_query': QUESTION}),
    ])
    retriever = ScriptedRetriever([[fine], [fine]])
    agent = AgenticRetrievalService(QueryContextualizer(provider), retriever, EvidenceGrader(provider),
                                   QueryRewriter(provider), structural_expander=LegalNeighborhoodExpander(lookup.fetch))
    result = await agent.retrieve(QUESTION)
    assert len(lookup.calls) == 1
    assert result.retrieval_attempts == 2
    assert result.chunks == [fine, points]
    assert provider.calls[2]['payload']['missing_aspects'] == ['additional_sanction']


@pytest.mark.asyncio
async def test_api_exposes_structural_path_and_before_after_grades():
    import httpx
    from backend.main import create_app
    from backend.dependencies.retrieval import get_agentic_retrieval_service

    agent, _, _ = service([(EvidenceGrade, assessment(False)), (EvidenceGrade, assessment(True))],
                           [[legal('fine')]], Lookup([consequence()]))
    app = create_app()
    app.dependency_overrides[get_agentic_retrieval_service] = lambda: agent
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/v1/retrieve/agentic', json={'current_query': QUESTION})
    assert response.status_code == 200
    payload = response.json()
    assert payload['structural_expansion_enabled'] is True
    trace = payload['structural_expansions'][0]
    assert trace['scopes'] == [{'law': 'Test regulation', 'article_no': '6',
                              'anchor_chunk_ids': ['fine'], 'candidate_count': 1}]
    assert trace['grade_before']['sufficient'] is False
    assert trace['grade_after']['sufficient'] is True
    assert trace['evidence_chunk_ids'] == ['fine', 'points']


def test_expansion_workflow_imports_no_models_sdk_or_database_and_uses_no_network():
    import os
    from pathlib import Path
    import subprocess
    import sys

    script = '''
import asyncio, importlib.abc, socket, sys
blocked = ('backend.retriever_custom', 'backend.generator', 'torch', 'sentence_transformers',
           'weaviate', 'google.generativeai', 'google.genai')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == n or fullname.startswith(n + '.') for n in blocked):
            raise AssertionError('Unexpected resource import: ' + fullname)
sys.meta_path.insert(0, Guard())
def fail(*args, **kwargs):
    raise AssertionError('Unexpected network access')
socket.create_connection = socket.socket.connect = socket.socket.connect_ex = fail
from tests.unit.test_neighborhood_expansion import service, legal, consequence, assessment, Lookup, QUESTION
from ai.agent.evidence_grader import EvidenceGrade
agent, provider, retriever = service([
    (EvidenceGrade, assessment(False)), (EvidenceGrade, assessment(True)),
], [[legal('fine')]], Lookup([consequence()]))
result = asyncio.run(agent.retrieve(QUESTION))
assert result.grade.sufficient is True
assert result.structural_expansions[0].triggered is True
assert len(result.chunks) == 2
assert not any(n in sys.modules for n in blocked)
'''
    env = dict(os.environ)
    env.pop('GEMINI_API_KEY', None)
    subprocess.run([sys.executable, '-B', '-c', script], env=env,
                   cwd=Path(__file__).resolve().parents[2], check=True)


@pytest.mark.asyncio
async def test_complete_clause_provenance_lists_all_supplied_members_without_mutating_source():
    fine = legal('fine')
    group = [legal(f'extra-{p}', '15', p, f'Hành vi tại khoản {n} Điều này.',
                   head='Các hình thức xử phạt bổ sung') for p, n in [('a', 11), ('b', 12)]]
    selection = await LegalNeighborhoodExpander(Lookup(group).fetch).expand(
        [fine], ['additional_sanction'], [fine])
    assert [chunk.id for chunk in selection.chunks] == ['extra-a', 'extra-b']
    for chunk in selection.chunks:
        assert chunk.metadata['structural_context']['complete_clause_chunk_ids'] == ['extra-a', 'extra-b']
    assert all('structural_context' not in chunk.metadata for chunk in group)
    unknown_member = legal('extra-c', '15', 'c', 'Other clause member.', head='')
    incomplete = await LegalNeighborhoodExpander(Lookup(group + [unknown_member]).fetch).expand(
        [fine], ['additional_sanction'], [fine])
    assert incomplete.chunks == []
