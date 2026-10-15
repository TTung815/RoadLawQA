# -*- coding: utf-8 -*-
"""
Unit Tests for FastAPI Health API Endpoint
"""
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest
from backend.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "VietLaw-Agent"
    assert payload["version"] == "2.0.0"


def test_health_import_isolated_from_resources_and_environment():
    script = '''
import asyncio
import importlib.abc
import os
import sys
blocked = ('backend.retriever_custom', 'backend.generator', 'torch',
           'sentence_transformers', 'weaviate', 'google.generativeai')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Unexpected resource import: ' + fullname)
sys.meta_path.insert(0, Guard())
before = dict(os.environ)
from backend.main import app
assert dict(os.environ) == before
import httpx
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url='http://test') as client:
        assert (await client.get('/api/v1/health')).status_code == 200
asyncio.run(check())
assert not any(name in sys.modules for name in blocked)
'''
    env = dict(
        os.environ, WEAVIATE_PORT="invalid", WEAVIATE_GRPC_PORT="invalid",
    )
    env.pop("GEMINI_API_KEY", None)
    subprocess.run(
        [sys.executable, "-B", "-c", script], env=env,
        cwd=Path(__file__).resolve().parents[2], check=True,
    )
