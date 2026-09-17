"""Production lookup contract with fake Weaviate modules, without the real client."""

import sys
from types import SimpleNamespace

import pytest

from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter
from ai.retrieval.weaviate_lookup import WeaviateArticleLookup


class Filter:
    def __init__(self, name=None, clauses=()):
        self.name, self.clauses = name, clauses

    @classmethod
    def by_property(cls, name):
        return cls(name)

    def equal(self, value):
        return Filter(clauses=((self.name, value),))

    def __and__(self, other):
        return Filter(clauses=self.clauses + other.clauses)


@pytest.mark.asyncio
@pytest.mark.parametrize('fail', [False, True])
async def test_lookup_filters_paginates_reuses_chunk_identity_and_closes_client(monkeypatch, fail):
    props = {'law': 'Test regulation', 'article_no': '6', 'clause_no': '16', 'point': 'b',
             'text': 'Reference to khoản 6 Điều này.', 'enriched_text': 'Full test context',
             'display_citation': 'Test citation', 'law_code': 'TEST', 'source_file': 'test.txt'}
    obj = SimpleNamespace(properties=props, uuid='test-uuid')
    calls, closes = [], []

    def fetch_objects(**kwargs):
        calls.append(kwargs)
        if fail:
            raise RuntimeError('Weaviate unavailable')
        assert kwargs['filters'].clauses == (('law', 'Test regulation'), ('article_no', '6'))
        if kwargs['offset'] == 0:
            return SimpleNamespace(objects=[obj] * 100)
        return SimpleNamespace(objects=[SimpleNamespace(properties=dict(props, law='Wrong regulation'), uuid='wrong')])

    collection = SimpleNamespace(query=SimpleNamespace(fetch_objects=fetch_objects))
    client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: collection), close=lambda: closes.append(True))
    monkeypatch.setitem(sys.modules, 'weaviate', SimpleNamespace(connect_to_local=lambda **kwargs: client))
    monkeypatch.setitem(sys.modules, 'weaviate.classes.query', SimpleNamespace(Filter=Filter))
    lookup = WeaviateArticleLookup()
    if fail:
        with pytest.raises(RuntimeError, match='Weaviate unavailable'):
            await lookup.fetch_article('Test regulation', '6')
    else:
        chunks = await lookup.fetch_article('Test regulation', '6')
        assert len(chunks) == 100  # Selection, rather than DB mapping, owns deduplication.
        assert all(chunk.id == LegacyRetrieverAdapter.map_results([{'props': props}])[0].id for chunk in chunks)
        assert chunks[0].metadata['weaviate_uuid'] == 'test-uuid'
        assert chunks[0].metadata['law_code'] == 'TEST'
        assert [call['offset'] for call in calls] == [0, 100]
    assert closes == [True]
