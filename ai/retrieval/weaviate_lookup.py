"""Lazy read-only Weaviate article lookup; no legacy imports or model loading."""

import asyncio
from typing import List

from ai.retrieval.base import RetrievedChunk
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter


class WeaviateArticleLookup:
    def __init__(self, host: str = 'localhost', port: int = 8080,
                 grpc_port: int = 50051, collection: str = 'LawChunks'):
        self.host, self.port, self.grpc_port = host, port, grpc_port
        self.collection = collection

    async def fetch_article(self, law: str, article_no: str) -> List[RetrievedChunk]:
        return await asyncio.to_thread(self._fetch_article, law, article_no)

    def _fetch_article(self, law: str, article_no: str) -> List[RetrievedChunk]:
        import weaviate
        from weaviate.classes.query import Filter

        client = weaviate.connect_to_local(host=self.host, port=self.port,
                                          grpc_port=self.grpc_port, skip_init_checks=True)
        try:
            collection = client.collections.get(self.collection)
            filters = Filter.by_property('law').equal(law) & Filter.by_property('article_no').equal(article_no)
            chunks = []
            offset = 0
            while True:
                objects = collection.query.fetch_objects(filters=filters, limit=100, offset=offset).objects
                for obj in objects:
                    props = obj.properties
                    # WORD-tokenized filters do not replace exact identity checks.
                    if props.get('law') != law or str(props.get('article_no') or '') != article_no:
                        continue
                    chunk = LegacyRetrieverAdapter.map_results([{'props': props}])[0]
                    chunk.metadata.update({key: props[key] for key in ('law_code', 'source_file') if key in props})
                    chunk.metadata['weaviate_uuid'] = str(obj.uuid)
                    chunks.append(chunk)
                if len(objects) < 100:
                    break
                offset += len(objects)
            return chunks
        finally:
            client.close()
