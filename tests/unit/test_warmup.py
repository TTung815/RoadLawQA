"""Startup warm-up loads retrieval in the background; readiness never loads it."""

import time

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import retrieval as dependencies
from backend.main import create_app


class FakeRetriever:
    def __init__(self, fail=False):
        self.fail, self.searches, self.closed = fail, [], False
        self._loaded = False

    async def search(self, query, top_k=10, **kwargs):
        self.searches.append((query, top_k))
        if self.fail:
            raise ConnectionError("weaviate down: secret detail")
        self._loaded = True
        return []

    @property
    def loaded(self):
        return self._loaded

    runtime_devices = {"reranker": "fake"}

    def close(self):
        self.closed = True


@pytest.fixture
def fake(monkeypatch):
    holder = {}

    def factory():
        holder["retriever"] = FakeRetriever(fail=holder.get("fail", False))
        return holder["retriever"]

    monkeypatch.setattr(dependencies, "LazyCurrentLawRetriever", factory)
    dependencies.get_current_retriever.cache_clear()
    yield holder
    dependencies.get_current_retriever.cache_clear()


def ready(client):
    for _ in range(100):
        state = client.get("/api/v1/ready").json()
        if state["warmup"] not in {"not_started", "running"}:
            return state
        time.sleep(0.01)
    raise AssertionError("warm-up did not finish")


def test_startup_warmup_loads_once_before_the_first_question(fake, monkeypatch):
    monkeypatch.setenv("WARMUP_ON_STARTUP", "true")
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert ready(client) == {"retrieval_loaded": True, "warmup": "done"}
    retriever = fake["retriever"]
    assert len(retriever.searches) == 1 and retriever.searches[0][1] == 1
    assert retriever.closed


def test_failed_warmup_keeps_serving_and_logs_no_exception_text(fake, monkeypatch, caplog):
    monkeypatch.setenv("WARMUP_ON_STARTUP", "true")
    fake["fail"] = True
    with TestClient(create_app()) as client:
        assert ready(client) == {"retrieval_loaded": False, "warmup": "failed"}
        assert client.get("/api/v1/health").status_code == 200
    assert "ConnectionError" in caplog.text and "secret detail" not in caplog.text


def test_disabled_warmup_and_readiness_do_not_load_resources(fake, monkeypatch):
    monkeypatch.setenv("WARMUP_ON_STARTUP", "false")
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/ready").json() == {"retrieval_loaded": False, "warmup": "disabled"}
    # Readiness only reads state: the lazy retriever was never constructed.
    assert "retriever" not in fake
