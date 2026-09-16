# -*- coding: utf-8 -*-
"""
Integration Smoke Test for LegacyRetrieverAdapter with Live Weaviate Instance
Requires running Weaviate service (via Docker on localhost:8080).
Does not assume score > 0 (Cross-Encoder scores can be negative); verifies math.isfinite(score).
"""
import math
import socket
import pytest
from ai.retrieval.base import RetrievedChunk
from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter


def is_weaviate_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_weaviate_retrieval_smoke():
    # backend.retriever_custom uses connect_to_local() with default ports;
    # V2 Settings do not configure the legacy implementation.
    if not all(is_weaviate_reachable("localhost", port) for port in (8080, 50051)):
        pytest.skip(
            "Legacy Weaviate prerequisite is unavailable on localhost:8080/50051. "
            f"Start with: docker compose -f docker/docker-compose.yml up -d"
        )

    adapter = LegacyRetrieverAdapter()
    query = "vượt đèn đỏ"

    results = await adapter.search(query, top_k=3)

    assert len(results) > 0, "Expected at least one result from legacy retrieval"
    for chunk in results:
        assert isinstance(chunk, RetrievedChunk)
        assert chunk.id is not None
        assert isinstance(chunk.citation, str)
        assert len(chunk.citation.strip()) > 0
        assert isinstance(chunk.text, str)

        # Correction 1: Verify score is a valid finite numeric value, do NOT assume > 0
        assert isinstance(chunk.score, (int, float))
        assert math.isfinite(chunk.score), f"Expected finite score, got: {chunk.score}"
