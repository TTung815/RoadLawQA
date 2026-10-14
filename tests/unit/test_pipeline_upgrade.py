"""Regressions for observed pipeline failures, independent of network/models."""

import json
import pickle
from pathlib import Path

import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer, GeneratedAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from ai.agent.evidence import evidence_payload
from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from ai.diagnostics import PipelineError, TRACE
from ai.retrieval.current_law import CurrentLawRetriever, hybrid_candidates, map_chunk
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from backend.services.answer import AnswerService
from evaluation.legacy_probe import load_bm25
from tests.unit.test_agentic_retrieval import ScriptedProvider, chunk, make_service
from tests.unit.test_grounded_answer import COMPLETE, QUESTION, qa_service, semantic


@pytest.mark.asyncio
async def test_long_source_ids_round_trip_without_asking_model_to_copy_hashes():
    source = chunk('chunk_' + 'a' * 64)
    provider = ScriptedProvider([(GeneratedAnswer, {'claims': [
        {'text': 'Quy tắc trong nguồn.', 'chunk_ids': ['source_1'], 'support_state': 'positive_support'}]})])
    draft = await AnswerGenerator(provider).generate('Quy tắc là gì?', [source])
    assert provider.calls[0]['payload']['chunks'][0]['id'] == 'source_1'
    assert draft.claims[0].chunk_ids == [source.id]
    verifier = ScriptedProvider([(SemanticVerification, semantic(1))])
    result = await CitationVerifier(verifier).verify('Quy tắc là gì?', draft, [source])
    assert result.status == 'passed'
    assert verifier.calls[0]['payload']['claims'][0]['chunk_ids'][0] == 'source_1'


@pytest.mark.asyncio
async def test_unknown_short_source_is_not_fuzzy_repaired():
    source = chunk('chunk_' + 'a' * 64)
    provider = ScriptedProvider([(GeneratedAnswer, {'claims': [
        {'text': 'Quy tắc.', 'chunk_ids': ['source_99'], 'support_state': 'positive_support'}]})])
    draft = await AnswerGenerator(provider).generate('?', [source])
    verifier = ScriptedProvider([])
    result = await CitationVerifier(verifier).verify('?', draft, [source])
    assert result.status == 'failed'
    assert 'outside final evidence' in result.issues[0]
    assert not verifier.calls


@pytest.mark.asyncio
async def test_grader_short_range_ids_return_real_source_proof():
    source = chunk('chunk_' + 'b' * 64)
    source.text = source.enriched_text = 'Ô tô vượt tốc độ trên 20 đến 35 km/h.'
    source.metadata.update(article_no='6', article_title='Ô tô')
    provider = ScriptedProvider([(EvidenceGrade, {
        'sufficient': True, 'reason': 'Nguồn đúng phạm vi.', 'anchor_chunk_ids': ['source_1'],
        'coverage': [{'aspect': name, 'covered': True, 'support_state': 'positive_support'}
                     for name in ['subject_violation', 'threshold_range']],
        'range_coverage': {'question_quote': 'trên 20 đến 35 km/h', 'unit': 'km/h',
                           'leaves': [{'chunk_id': 'source_1', 'range_quote': 'trên 20 đến 35 km/h', 'compatible': True}]},
    })])
    result = await EvidenceGrader(provider).grade('Ô tô vượt tốc độ trên 20 đến 35 km/h?', [source])
    assert result.sufficient
    assert result.anchor_chunk_ids == [source.id]
    assert result.range_coverage.leaves[0].chunk_id == source.id


def test_payload_removes_duplicate_bodies_but_retains_legal_provenance():
    source = chunk('s')
    source.metadata.update(text=source.text, enriched_text=source.enriched_text,
                           source_spans=[{'line_start': 2}], publication_eligible=False)
    result = evidence_payload([source])[0]
    assert 'text' not in result['metadata'] and 'enriched_text' not in result['metadata']
    assert result['text'] == source.text
    assert result['metadata']['publication_eligible'] is False
    assert result['metadata']['source_spans'] == [{'line_start': 2}]


@pytest.mark.asyncio
async def test_clarification_is_verified_and_does_not_claim_a_complete_answer():
    retrieval, _, _, _ = make_service([(EvidenceGrade, COMPLETE)], [[chunk('money')]], max_attempts=1)
    draft = {'claims': [], 'response_kind': 'clarification',
             'limitations': ['Chưa rõ vị trí dừng xe.'], 'follow_up_questions': ['Xe dừng ở làn nào?']}
    verdict = {**semantic(0, complete=False), 'response_appropriate': True}
    provider = ScriptedProvider([(GeneratedAnswer, draft), (SemanticVerification, verdict)])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer('?')
    assert result.status == 'needs_clarification'
    assert result.follow_up_questions == ['Xe dừng ở làn nào?']
    assert not result.verification.answer_complete


@pytest.mark.asyncio
async def test_unsupported_advice_cannot_hide_in_partial_answer_limitations():
    draft = {'claims': [{'text': 'Một quy tắc.', 'chunk_ids': ['money'], 'support_state': 'positive_support'}],
             'response_kind': 'partial', 'limitations': ['Bạn chắc chắn không bị xử phạt.']}
    service, _, _, _ = qa_service(draft, {**semantic(1, complete=False), 'response_appropriate': False})
    result = await service.answer(QUESTION)
    assert result.status == 'verification_failed'
    assert result.answer is None and result.limitations == []


@pytest.mark.asyncio
async def test_temporally_blocked_source_cannot_be_published_despite_positive_label():
    source = chunk('s');source.metadata['publication_eligible'] = False
    draft = DraftAnswer(claims=[{'text': 'Quy tắc.', 'chunk_ids': ['s'], 'support_state': 'positive_support'}])
    provider = ScriptedProvider([])
    result = await CitationVerifier(provider).verify('?', draft, [source])
    assert result.status == 'failed' and not provider.calls


@pytest.mark.asyncio
async def test_error_stage_and_private_draft_are_available_without_secret_exception_text():
    service, provider, _, _ = qa_service()
    provider.script[1] = (SemanticVerification, ValueError('private-secret-marker'))
    trace = []; token = TRACE.set(trace)
    try:
        with pytest.raises(PipelineError) as caught:
            await service.answer(QUESTION)
    finally:
        TRACE.reset(token)
    assert caught.value.stage == 'verification'
    assert caught.value.error_type == 'ValueError'
    assert any(event.get('event') == 'draft' for event in trace)
    assert 'private-secret-marker' not in json.dumps(trace)
    assert 'private-secret-marker' not in str(caught.value)


def corpus():
    return json.loads(Path('data/processed/current-law/current-law-chunks-2026-09-22.json').read_text())['chunks']


@pytest.mark.asyncio
async def test_case_29_missing_priority_conditions_are_found_in_same_article():
    rows = corpus()
    retriever = CurrentLawRetriever(rows, None, None, None, None)
    anchor = map_chunk(next(c for c in rows if c['id'] == '55-vbhn-vpqh-d27-k1'))
    selection = await LegalNeighborhoodExpander(retriever.fetch_article).expand(
        [anchor], ['condition_exception'], [anchor])
    ids = {c.metadata['processed_id'] for c in selection.chunks}
    assert '55-vbhn-vpqh-d27-k4' in ids
    assert '55-vbhn-vpqh-d27-k2-pđ' in ids
    assert len(selection.chunks) <= 8
    assert all(c.metadata['publication_eligible'] for c in selection.chunks)


@pytest.mark.asyncio
async def test_case_27_explicit_cross_document_reference_finds_driver_licence_rule():
    rows = corpus()
    retriever = CurrentLawRetriever(rows, None, None, None, None)
    anchor = map_chunk(next(c for c in rows if c['id'] == 'nd168-effective-as-of-2026-09-22-d32-k14-pi'))
    selection = await LegalNeighborhoodExpander(retriever.fetch_article).expand(
        [anchor], ['monetary_penalty', 'condition_exception'], [anchor])
    assert '55-vbhn-vpqh-d56-k1-pb' in {c.metadata['processed_id'] for c in selection.chunks}


@pytest.mark.asyncio
async def test_unresolved_subject_can_fetch_the_reference_needed_to_establish_applicability():
    rows = corpus()
    source = map_chunk(next(c for c in rows if c['id'] == 'nd168-effective-as-of-2026-09-22-d32-k14-pi'))
    missing = {'sufficient': False, 'reason': 'Thiếu nội dung điều kiện được dẫn chiếu.',
               'anchor_chunk_ids': ['source_1'], 'coverage': [
                   {'aspect': 'subject_violation', 'covered': False, 'support_state': 'unknown'}]}
    found = {'sufficient': True, 'reason': 'Nguồn đã xác định điều kiện.', 'coverage': [
        {'aspect': 'subject_violation', 'covered': True, 'support_state': 'positive_support'}]}
    retrieval, provider, _, _ = make_service([(EvidenceGrade, missing), (EvidenceGrade, found)],
                                             [[source]], max_attempts=1)
    retrieval._structural_expander = LegalNeighborhoodExpander(
        CurrentLawRetriever(rows, None, None, None, None).fetch_article)
    result = await retrieval.retrieve('Chủ xe giao ô tô cho người không có giấy phép bị phạt bao nhiêu?')
    assert result.grade.sufficient
    assert '55-vbhn-vpqh-d56-k1-pb' in {c.metadata['processed_id'] for c in result.chunks}
    assert len(provider.calls) == 2  # Fresh evidence must be graded before publishing.


def test_hybrid_keeps_distinct_sources_with_the_same_display_citation():
    rows = [{'id': 'a', 'display_citation': 'same'}, {'id': 'b', 'display_citation': 'same'}]
    result = hybrid_candidates(rows, [(0, 1)], [(rows[1], 1)], .5, 5)
    assert {row['id'] for row, _ in result} == {'a', 'b'}


def test_bm25_cache_rejects_executable_pickle_globals(tmp_path):
    path = tmp_path/'bad.pkl';path.write_bytes(pickle.dumps(eval))
    with pytest.raises(ValueError, match='Unsupported BM25 cache'):
        load_bm25(path)


@pytest.mark.asyncio
async def test_range_decisions_use_server_owned_quotes_and_reject_omissions():
    source = chunk('chunk_' + 'b' * 64)
    source.text = source.enriched_text = 'Xe tải chở hàng trên 30% đến 50%.'
    source.metadata.update(article_no='21', article_title='Xe tải')
    grade = {'sufficient': True, 'reason': 'Cùng đối tượng và khoảng.',
             'coverage': [{'aspect': 'subject_violation', 'covered': True, 'support_state': 'positive_support'}],
             'range_decisions': [{'candidate_index': 0, 'compatible': True}]}
    provider = ScriptedProvider([(EvidenceGrade, grade)])
    result = await EvidenceGrader(provider).grade('Xe tải chở hàng trên 30% đến 50%?', [source])
    assert result.range_coverage.leaves[0].range_quote == 'trên 30% đến 50%'
    assert result.range_coverage.leaves[0].chunk_id == source.id
    assert result.sufficient
    grade['range_decisions'] = [{'candidate_index': 8, 'compatible': True}]
    with pytest.raises(ValueError, match='exactly once'):
        await EvidenceGrader(ScriptedProvider([(EvidenceGrade, grade)])).grade(
            'Xe tải chở hàng trên 30% đến 50%?', [source])


def test_new_plan_hashes_do_not_require_deleted_v1_scripts():
    from evaluation.core_runner import code_hashes
    files = code_hashes()
    assert 'ai/retrieval/current_law.py' in files
    assert 'ai/diagnostics.py' in files
    assert 'backend/retriever_custom.py' not in files


@pytest.mark.asyncio
@pytest.mark.parametrize('fixed', [True, False])
async def test_verification_feedback_allows_only_one_repair_and_never_publishes_failed_draft(fixed):
    from tests.unit.test_grounded_answer import DRAFT
    retrieval, _, _, _ = make_service([(EvidenceGrade, COMPLETE)],
                                      [[chunk('money'), chunk('points')]], max_attempts=1)
    broken = {'claims': [{'text': 'Kết luận có nguồn bịa.', 'chunk_ids': ['invented'],
                          'support_state': 'positive_support'}]}
    script = [(GeneratedAnswer, broken), (GeneratedAnswer, DRAFT if fixed else broken)]
    if fixed:
        script.append((SemanticVerification, semantic(2)))
    provider = ScriptedProvider(script)
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer(QUESTION)
    assert result.repair_attempts == 1
    assert result.status == ('answered' if fixed else 'verification_failed')
    assert (result.answer is not None) is fixed
    assert provider.calls[1]['payload']['previous_draft']['claims'][0]['text'] == broken['claims'][0]['text']
    assert 'outside final evidence' in provider.calls[1]['payload']['verification_feedback'][0]
    assert provider.script == []
    if result.answer:
        assert '999' not in result.answer.text


@pytest.mark.asyncio
async def test_uncertain_applicability_with_relevant_anchor_can_request_missing_fact():
    grade = {'sufficient': False, 'reason': 'Chưa rõ xe có đang làm nhiệm vụ cấp cứu hay không.',
             'anchor_chunk_ids': ['rule'], 'coverage': [
                 {'aspect': 'subject_violation', 'covered': False, 'support_state': 'unknown'}]}
    retrieval, _, _, _ = make_service([(EvidenceGrade, grade)], [[chunk('rule')]], max_attempts=1)
    draft = {'claims': [], 'response_kind': 'clarification',
             'limitations': ['Chưa xác định nhiệm vụ của xe.'], 'follow_up_questions': ['Xe đang làm nhiệm vụ gì?']}
    provider = ScriptedProvider([(GeneratedAnswer, draft), (SemanticVerification, {
        **semantic(0, complete=False), 'response_appropriate': True})])
    result = await AnswerService(retrieval, AnswerGenerator(provider), CitationVerifier(provider)).answer('?')
    assert result.status == 'needs_clarification'
    assert not result.retrieval.grade.sufficient
    assert provider.calls[0]['payload']['coverage_reason'] == grade['reason']
