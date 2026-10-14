"""Device selection must be lazy, visible and stable in an execution plan."""

import sys
from types import SimpleNamespace

import pytest

from ai.retrieval.devices import resolve_device


def hardware(monkeypatch, *, mps=False, cuda=False):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)),
    ))


@pytest.mark.parametrize("mps,cuda,expected", [(True, False, "mps"), (False, True, "cuda"),
                                               (False, False, "cpu")])
def test_auto_uses_available_hardware(monkeypatch, mps, cuda, expected):
    hardware(monkeypatch, mps=mps, cuda=cuda)
    assert resolve_device("auto") == expected


@pytest.mark.parametrize("device", ["mps", "cuda"])
def test_explicit_gpu_never_silently_runs_on_cpu(monkeypatch, device):
    hardware(monkeypatch)
    with pytest.raises(RuntimeError, match="unavailable"):
        resolve_device(device)


def test_cpu_selection_and_device_inspection_do_not_load_resources(monkeypatch):
    from ai.retrieval.current_law import LazyCurrentLawRetriever
    monkeypatch.setitem(sys.modules, "torch", None)
    assert resolve_device("cpu") == "cpu"
    retriever = LazyCurrentLawRetriever()
    assert retriever.runtime_devices == {}
    assert retriever._retriever is None
    retriever._retriever = SimpleNamespace(runtime_devices={"embedding": "mps:0", "reranker": "mps:0"})
    devices = retriever.runtime_devices
    devices["embedding"] = "cpu"
    assert retriever.runtime_devices["embedding"] == "mps:0"


def test_plan_locks_resolved_device_not_auto(monkeypatch):
    from evaluation.core_runner import default_settings
    from evaluation.core_schema import RunSettings
    hardware(monkeypatch, mps=True)
    monkeypatch.setenv("EMBEDDING_DEVICE", "auto")
    monkeypatch.setenv("RERANKER_DEVICE", "auto")
    settings = default_settings()
    assert settings.embedding_device == settings.reranker_device == "mps"
    with pytest.raises(ValueError):
        RunSettings.model_validate({**settings.model_dump(), "reranker_device": "auto"})
    # Old receipts retain their actual CPU-only interpretation.
    historical = settings.model_dump(exclude={"embedding_device", "reranker_device"})
    assert RunSettings.model_validate(historical).reranker_device == "cpu"


def test_settings_reject_unsupported_device(monkeypatch):
    from configs.settings import Settings
    monkeypatch.setenv("RERANKER_DEVICE", "metal")
    with pytest.raises(ValueError):
        Settings()
