"""Scoped source ingestion must preserve review, temporal and provenance boundaries."""

import copy
import json
from pathlib import Path
import shutil

import pytest

from ai.agent.evidence import evidence_payload
from ai.retrieval.structured import map_unit
from ingestion import legal_dependency as dependency
from ingestion.legal_registry import file_digest, read_json
from ingestion.structured_corpus import load_bundle


def test_bundle_keeps_four_dependency_units_and_ten_blocked_sources():
    current = load_bundle()['chunks']
    assert sum(u['metadata']['document_id'] == '90-vbhn-vpqh-2026' for u in current) == 4
    assert sum(not u['metadata']['publication_eligible'] for u in current) == 10
    assert len({u['id'] for u in current}) == len(current) == 1759


def test_partial_dependency_keeps_precise_citations_context_and_scope():
    units = [u for u in load_bundle()['chunks'] if u['metadata']['document_id'] == '90-vbhn-vpqh-2026']
    assert {(u['metadata']['article_no'], u['metadata']['granularity']) for u in units} == {
        ('5', 'point'), ('11', 'clause'), ('22', 'article'), ('134', 'clause')}
    exclusion = next(u for u in units if u['metadata']['article_no'] == '11')
    target = next(u for u in units if u['metadata']['article_no'] == '5')
    assert target['id'] in {i for ref in exclusion['metadata']['references'] for i in ref['chunk_ids']}
    assert 'Không xử phạt vi phạm hành chính đối với' in exclusion['embedding_text']
    assert target['text'].startswith('a) Người') and 'a) a)' not in target['text']
    minor = next(u for u in units if u['metadata']['article_no'] == '134')
    assert any(not r['resolved'] and r['article_no'] == '126' for r in minor['metadata']['references'])
    for item in evidence_payload([map_unit(u) for u in units]):
        assert item['metadata']['scope_complete'] is False
        assert item['metadata']['publication_scope']
        assert item['metadata']['scope_limitations']


def test_explicit_new_document_locator_does_not_select_other_article_fives():
    from ai.retrieval.structured import StructuredRetriever
    retriever = StructuredRetriever(load_bundle()['chunks'], None, None, None)
    found = retriever._exact_candidates('Điểm a khoản 1 Điều 5 90/VBHN-VPQH quy định gì?')
    assert len(found) == 1
    assert found[0]['metadata']['document_id'] == '90-vbhn-vpqh-2026'


@pytest.fixture
def local_dependency(tmp_path, monkeypatch):
    registry = read_json(dependency.DEFAULT_DEPENDENCY / 'registry.json')
    paths = [dependency.DEFAULT_DEPENDENCY / name for name in ('registry.json', 'review.json')]
    paths += [dependency.PROJECT_ROOT / path for path in (
        registry['base_registry_path'], registry['document']['source']['raw_path'],
        registry['document']['extraction']['path'])]
    for source in paths:
        dest = tmp_path / source.relative_to(dependency.PROJECT_ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    relative = dependency.DEFAULT_DEPENDENCY.relative_to(dependency.PROJECT_ROOT)
    monkeypatch.setattr(dependency, 'PROJECT_ROOT', tmp_path)
    return tmp_path / relative


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False))


def test_pending_scope_cannot_be_published(local_dependency):
    p = local_dependency / 'registry.json'
    registry = read_json(p)
    registry['scope_review']['status'] = 'pending'
    save(p, registry)
    with pytest.raises(ValueError, match='not been approved'):
        dependency.load_dependency(local_dependency)


@pytest.mark.parametrize('mutation', ['text', 'parent', 'future'])
def test_reviewed_units_cannot_silently_change_spans_or_effectivity(local_dependency, mutation):
    p = local_dependency / 'review.json'
    review = read_json(p)
    if mutation == 'text':
        review['units'][0]['text'] = 'changed law'
    elif mutation == 'parent':
        review['units'][0]['parent_context'] = 'changed parent'
    else:
        review['units'][0]['effective_from'] = '2027-01-01'
    save(p, review)
    with pytest.raises(ValueError, match='source span|parent context|active at cutoff'):
        dependency.load_dependency(local_dependency)


def test_modified_source_fails_checksum(local_dependency):
    registry = read_json(local_dependency / 'registry.json')
    p = dependency.PROJECT_ROOT / registry['document']['extraction']['path']
    p.write_text(p.read_text() + '\nchanged')
    with pytest.raises(ValueError, match='checksum mismatch'):
        dependency.load_dependency(local_dependency)
