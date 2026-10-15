"""Regressions for observed pipeline failures, independent of network/models."""

import json
import pickle
from pathlib import Path

import pytest

from ai.agent.answer_generator import AnswerGenerator, DraftAnswer, GeneratedAnswer
from ai.agent.citation_verifier import CitationVerifier, SemanticVerification
from ai.agent.evidence import evidence_payload
from ai.diagnostics import PipelineError, TRACE
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from backend.services.answer import AnswerService
from evaluation.legacy_probe import load_bm25
from tests.unit.fakes import ScriptedProvider, chunk, semantic
from tests.unit.test_grounded_answer import QUESTION, qa_service


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
async def test_unsupported_advice_cannot_hide_in_partial_answer_limitations():
    draft = {'claims': [{'text': 'Một quy tắc.', 'chunk_ids': ['money'], 'support_state': 'positive_support'}],
             'response_kind': 'partial', 'limitations': ['Bạn chắc chắn không bị xử phạt.']}
    service, _, _ = qa_service(draft, {**semantic(1, complete=False), 'response_appropriate': False})
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
    service, provider, _ = qa_service()
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


def test_bm25_cache_rejects_executable_pickle_globals(tmp_path):
    path = tmp_path/'bad.pkl';path.write_bytes(pickle.dumps(eval))
    with pytest.raises(ValueError, match='Unsupported BM25 cache'):
        load_bm25(path)


def test_new_plan_hashes_do_not_require_deleted_v1_scripts():
    from evaluation.core_runner import code_hashes
    files = code_hashes()
    assert 'ai/retrieval/current_law.py' in files
    assert 'ai/diagnostics.py' in files
    assert 'backend/retriever_custom.py' not in files
