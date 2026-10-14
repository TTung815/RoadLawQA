"""Regressions for the default pipeline without coverage grading or query rewrite."""

import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from ai.agent.contextualizer import ContextualizedQuery, QueryContextualizer
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from backend.services.answer import AnswerService
from backend.services.lean_retrieval import LeanRetrievalService
from evaluation.core_runtime import CoreRuntime
from evaluation.core_schema import Question
from tests.unit.test_agentic_retrieval import ScriptedProvider, ScriptedRetriever, chunk
from tests.unit.test_core_evaluation import settings
from tests.unit.test_grounded_answer import semantic
from tests.unit.test_neighborhood_expansion import legal, consequence, Lookup


def draft(text='Quy tắc đúng theo nguồn.'):
    return {'claims': [{'text': text, 'chunk_ids': ['rule'], 'support_state': 'positive_support'}]}


@pytest.mark.asyncio
@pytest.mark.parametrize('history', [[], [{'role': 'user', 'content': 'Xe ô tô.'}]])
async def test_default_runtime_calls_only_context_when_needed_generation_and_verification(history):
    script = [(ContextualizedQuery, {'standalone_query': 'Câu hỏi đủ ngữ cảnh.'})] if history else []
    script += [(DraftAnswer, draft()), (SemanticVerification, semantic(1))]
    provider = ScriptedProvider(script)
    retriever = ScriptedRetriever([[chunk('rule')]])
    runtime = CoreRuntime(provider, [], settings(max_attempts=1, expansion=False), retriever)
    result = await runtime.execute(Question(id='fixture', current_query='Quy tắc là gì?', chat_history=history))
    assert result['status'] == 'answered'
    assert result['retrieval']['grade'] is None
    assert result['retrieval']['attempts'][0]['grade'] is None
    assert result['retrieval']['timings']['grading_ms'] == 0
    assert result['retrieval']['timings']['rewrite_ms'] == 0
    assert len(retriever.calls) == 1
    assert provider.script == []
    assert all(e['stage'] not in {'coverage_grading', 'query_rewrite'} for e in runtime.last_trace)


@pytest.mark.asyncio
async def test_blocked_and_duplicate_sources_are_removed_before_generation():
    blocked = chunk('future')
    blocked.metadata['active_at_cutoff'] = False
    retriever = ScriptedRetriever([[blocked, chunk('rule'), chunk('rule')]])
    result = await LeanRetrievalService(QueryContextualizer(ScriptedProvider([])), retriever).retrieve('?')
    assert [c.id for c in result.chunks] == ['rule']


@pytest.mark.asyncio
async def test_no_evidence_returns_without_any_llm_calls():
    provider = ScriptedProvider([])
    retrieval = LeanRetrievalService(QueryContextualizer(provider), ScriptedRetriever([[]]))
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer('?')
    assert result.status == 'insufficient_evidence'
    assert result.verification.status == 'not_run'
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize('supported', [True, False])
async def test_inline_reference_is_judged_by_evidence_not_blanket_regex(supported):
    provider = ScriptedProvider([(SemanticVerification, semantic(1, supported=supported))])
    result = await CitationVerifier(provider).verify('?', DraftAnswer(**draft('Theo khoản 2 Điều 27, quy tắc này có phạm vi riêng.')), [chunk('rule')])
    assert result.status == ('passed' if supported else 'failed')
    assert result.provenance_valid is True
    payload = provider.calls[0]['payload']
    assert payload['claims'][0]['chunk_ids'] == ['rule']
    assert 'cited_chunks' not in payload['claims'][0]
    assert len(payload['final_evidence']) == 1


@pytest.mark.asyncio
async def test_complete_claims_with_imagined_limitations_are_blocked():
    provider = ScriptedProvider([(SemanticVerification, {**semantic(1), 'response_appropriate': False})])
    answer = DraftAnswer(**draft(), limitations=['Có thể có ngoại lệ chưa biết.'])
    result = await CitationVerifier(provider).verify('?', answer, [chunk('rule')])
    assert result.status == 'failed'
    assert result.answer_complete is True
    assert 'Unsupported limitations' in result.issues[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('repair_appropriate', [True, False])
async def test_unnecessary_clarification_is_repaired_on_same_facts_and_evidence(repair_appropriate):
    # Replay the observed unnecessary seating-layout question, without claiming
    # that a scripted verifier tests the LLM's interpretation of the new prompt.
    import json
    from pathlib import Path
    cases = [json.loads(line) for line in Path(
        'evaluation/datasets/current_law_20260922_reviewed_v1/cases.jsonl'
    ).read_text().splitlines()]
    question = next(c['query'] for c in cases if c['id'] == 'current_law_007')
    first = {**draft('Nếu xe có nhiều hàng ghế thì trẻ không ngồi cùng hàng ghế người lái.'),
             'response_kind': 'partial',
             'limitations': ['Chưa rõ xe chỉ có một hàng ghế hay nhiều hàng ghế.'],
             'follow_up_questions': ['Xe chỉ có một hàng ghế hay nhiều hàng ghế?']}
    repaired = draft('Với tình huống đã nêu, trẻ không được ngồi cùng hàng ghế người lái và phải dùng thiết bị an toàn phù hợp.')
    provider = ScriptedProvider([
        (DraftAnswer, first),
        (SemanticVerification, {**semantic(1, complete=False), 'response_appropriate': False}),
        (DraftAnswer, repaired),
        (SemanticVerification, {**semantic(1), 'response_appropriate': repair_appropriate}),
    ])
    retriever = ScriptedRetriever([[chunk('rule')]])
    retrieval = LeanRetrievalService(QueryContextualizer(provider), retriever)
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(question)
    assert result.status == ('answered' if repair_appropriate else 'verification_failed')
    assert result.repair_attempts == 1
    assert len(retriever.calls) == 1
    assert len(provider.calls) == 4
    original, verification, repair, final = [c['payload'] for c in provider.calls]
    assert original['question'] == verification['question'] == repair['question'] == final['question'] == question
    assert original['chunks'] == repair['chunks']
    assert repair['previous_draft']['follow_up_questions'] == first['follow_up_questions']
    assert repair['verification_feedback']
    assert result.follow_up_questions == []
    if repair_appropriate:
        assert result.answer is not None
    else:
        assert result.answer is None and result.limitations == []


@pytest.mark.asyncio
async def test_genuinely_missing_scenario_fact_still_allows_clarification_without_repair():
    response = {**draft('Nghĩa vụ áp dụng tùy theo điều kiện sử dụng xe trong nguồn.'),
                'response_kind': 'clarification',
                'limitations': ['Chưa rõ mục đích sử dụng xe.'],
                'follow_up_questions': ['Xe có kinh doanh vận tải hành khách không?']}
    provider = ScriptedProvider([(DraftAnswer, response),
                                (SemanticVerification, semantic(1, complete=False))])
    retrieval = LeanRetrievalService(QueryContextualizer(provider), ScriptedRetriever([[chunk('rule')]]))
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(
        'Tôi chở trẻ em trên ô tô, cần thiết bị an toàn gì?')
    assert result.status == 'needs_clarification'
    assert result.follow_up_questions == response['follow_up_questions']
    assert result.limitations == response['limitations']
    assert result.repair_attempts == 0
    assert len(provider.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('appropriate', [True, False])
async def test_abstention_requires_semantic_check_and_never_publishes_a_draft(appropriate):
    refusal = {'claims': [], 'response_kind': 'abstain', 'limitations': ['Thiếu quy tắc về tuổi chịu xử phạt.']}
    provider = ScriptedProvider([(DraftAnswer, refusal), (SemanticVerification, {
        **semantic(0, complete=False), 'response_appropriate': appropriate})])
    retrieval = LeanRetrievalService(QueryContextualizer(provider), ScriptedRetriever([[chunk('rule')]]))
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider), max_answer_attempts=1).answer('?')
    assert result.status == ('insufficient_evidence' if appropriate else 'verification_failed')
    assert result.answer is None
    assert result.limitations == (refusal['limitations'] if appropriate else [])


@pytest.mark.asyncio
async def test_reference_expansion_keeps_whole_clause_and_honors_budgets():
    anchor = legal('anchor', clause='4', text='Quy tắc áp dụng cho xe tại khoản 2 Điều này.')
    a, b = legal('a', clause='2'), legal('b', clause='2', point='b')
    blocked = legal('blocked', clause='2'); blocked.metadata['publication_eligible'] = False
    lookup = Lookup([a, b, blocked, legal('unrelated', clause='1')])
    result = await LegalNeighborhoodExpander(lookup.fetch).expand_references([anchor])
    assert [c.id for c in result.chunks] == ['a', 'b']
    bounded = await LegalNeighborhoodExpander(lookup.fetch, max_chunks=1).expand_references([anchor])
    assert bounded.chunks == []
    assert result.missing_aspects == []


@pytest.mark.asyncio
async def test_consequence_expansion_does_not_copy_every_sibling():
    anchor = legal('fine')
    lookup = Lookup([anchor, consequence(), legal('unrelated', clause='1')])
    result = await LegalNeighborhoodExpander(lookup.fetch).expand_references([anchor])
    assert [c.id for c in result.chunks] == ['points']


@pytest.mark.asyncio
async def test_reverse_scope_reference_brings_rule_and_complete_referenced_clause():
    anchor = legal('listed', clause='2', point='c')
    rule = legal('scope', clause='4', point='', text='Các xe tại các điểm a, b, c và d khoản 2 Điều này được áp dụng quyền này.', head='')
    members = [legal('other', clause='2', point='a'), legal('excluded', clause='2', point='đ')]
    lookup = Lookup([anchor, rule, *members, legal('unrelated', clause='1')])
    result = await LegalNeighborhoodExpander(lookup.fetch).expand_references([anchor])
    assert {c.id for c in result.chunks} == {'scope', 'other', 'excluded'}
    assert result.added_characters <= 12000


@pytest.mark.asyncio
async def test_combination_lookup_is_conditional_and_uses_shared_budget():
    calls = []
    async def lookup(laws):
        calls.append(laws)
        return [legal('combine-money', article='98'), legal('combine-points', article='99')]
    expander = LegalNeighborhoodExpander(Lookup([]).fetch, combination_lookup=lookup)
    await expander.expand_references([legal('fine')], question='Mức phạt của hành vi này?')
    assert calls == []
    result = await expander.expand_references([legal('fine')], question='Tổng tiền và điểm bị trừ trong cùng một lần?')
    assert calls == [['Test regulation']]
    assert [c.id for c in result.chunks] == ['combine-money', 'combine-points']
    bounded = LegalNeighborhoodExpander(Lookup([]).fetch, combination_lookup=lookup, max_chunks=1)
    assert (await bounded.expand_references([legal('fine')], question='Tổng tiền?')).chunks == []


@pytest.mark.asyncio
async def test_real_corpus_scope_and_combination_sources_are_reachable_without_grader():
    import json
    from pathlib import Path
    from ai.retrieval.current_law import CurrentLawRetriever, map_chunk
    rows = json.loads(Path('data/processed/current-law/current-law-chunks-2026-09-22.json').read_text())['chunks']
    retriever = CurrentLawRetriever(rows, None, None, None, None)
    expander = LegalNeighborhoodExpander(retriever.fetch_article,
                                        combination_lookup=retriever.fetch_combination_rules)
    anchors = [map_chunk(c) for c in rows if '55/VBHN' in c['law'] and str(c['article_no']) == '27'
               and str(c.get('clause_no')) == '2' and c.get('point') in {'c', 'd'}]
    assert anchors
    result = await expander.expand_references(anchors)
    assert any(str(c.metadata.get('clause_no')) == '4' for c in result.chunks)
    assert any(str(c.metadata.get('clause_no')) == '2' and c.metadata.get('point') == 'đ' for c in result.chunks)
    fine = next(map_chunk(c) for c in rows if '168/2024' in c['law'] and str(c['article_no']) == '6'
                and str(c.get('clause_no')) == '9' and c.get('point') == 'b')
    result = await expander.expand_references([fine], question='Tổng tiền và điểm khi bị xử phạt cùng một lần?')
    assert any(str(c.metadata.get('article_no')) == '5' and str(c.metadata.get('clause_no')) == '2' for c in result.chunks)
    assert any(str(c.metadata.get('article_no')) == '50' and c.metadata.get('point') == 'b' for c in result.chunks)


@pytest.mark.asyncio
async def test_cross_document_applicability_is_not_starved_by_sibling_sanctions():
    import json
    from pathlib import Path
    from ai.retrieval.current_law import CurrentLawRetriever, map_chunk
    rows = json.loads(Path('data/processed/current-law/current-law-chunks-2026-09-22.json').read_text())['chunks']
    retriever = CurrentLawRetriever(rows, None, None, None, None)
    anchors = [next(map_chunk(c) for c in rows if '168/2024' in c['law'] and str(c['article_no']) == '32'
                    and str(c.get('clause_no')) == clause and c.get('point') == point)
               for clause, point in [('13', 'e'), ('13', 'a'), ('14', 'i')]]
    result = await LegalNeighborhoodExpander(retriever.fetch_article).expand_references(anchors)
    assert any(str(c.metadata.get('article_no')) == '56' and str(c.metadata.get('clause_no')) == '1'
               for c in result.chunks)
    assert len(result.chunks) <= 8


@pytest.mark.asyncio
@pytest.mark.parametrize('asked_for_points', [False, True])
async def test_unrequested_points_gap_is_repaired_but_requested_gap_is_preserved(asked_for_points):
    # Replays the reported limitation through real orchestration. Scripted
    # judgments test repair/publication, not the LLM's interpretation of scope.
    limitation = 'Nguồn được cung cấp chưa xác định việc trừ điểm giấy phép lái xe.'
    first = {**draft('Quy tắc và hình thức xử lý theo nguồn.'),
             'response_kind': 'partial', 'limitations': [limitation]}
    question = ('Hành vi này bị xử lý thế nào và có bị trừ điểm không?' if asked_for_points
                else 'Tôi say rượu thì có nên lái ô tô không?')
    script = [
        (DraftAnswer, first),
        (SemanticVerification, {**semantic(1, complete=False),
                                'response_appropriate': asked_for_points,
                                'completeness_reason': 'Giới hạn phải gắn với ý được hỏi.'}),
    ]
    if not asked_for_points:
        script += [(DraftAnswer, draft('Quy tắc áp dụng trực tiếp theo nguồn.')),
                   (SemanticVerification, semantic(1))]
    provider = ScriptedProvider(script)
    retriever = ScriptedRetriever([[chunk('rule')]])
    retrieval = LeanRetrievalService(QueryContextualizer(provider), retriever)
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(question)
    assert len(retriever.calls) == 1
    assert result.status == ('partial_answer' if asked_for_points else 'answered')
    assert result.limitations == ([limitation] if asked_for_points else [])
    assert result.repair_attempts == (0 if asked_for_points else 1)
    if not asked_for_points:
        repair = provider.calls[2]['payload']
        assert repair['previous_draft']['limitations'] == [limitation]
        assert repair['verification_feedback']
        assert repair['question'] == question
        assert repair['chunks'] == provider.calls[0]['payload']['chunks']
