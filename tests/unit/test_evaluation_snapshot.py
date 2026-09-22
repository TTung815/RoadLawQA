"""Snapshot integrity behavior with deterministic lexical data and read-only fakes."""

import copy
import json
import os
from pathlib import Path
import pickle
from types import SimpleNamespace
import subprocess
import sys

import pytest

from evaluation import legacy_probe, snapshot


def props(text="Alpha Beta", clause="1"):
    return {"law": "Test law", "chapter": "Chapter", "section": "", "article_no": "1",
            "article_title": "Title", "clause_no": clause, "point": None, "clause_head": "Head",
            "text": text, "enriched_text": "Context " + text, "display_citation": "Test citation " + clause}


@pytest.fixture(autouse=True)
def lexical_fake(monkeypatch):
    # BM25 math is real; production PyVi and embedding/reranker models are not loaded.
    monkeypatch.setattr(legacy_probe, "tokenized_corpus", lambda rows: [
        " ".join(row.get(key) for key in legacy_probe.BM25_FIELDS if row.get(key)).split() for row in rows])


def processed(rows):
    return [{"processed_id": str(i), "file": "data/processed/test.json", "properties": row}
            for i, row in enumerate(rows)]


def records(rows):
    return [{"uuid": f"uuid-{i}", "properties": dict(row), "vectors": {"default": [0.1] * 768}}
            for i, row in enumerate(rows)]


class FakeCollection:
    def __init__(self, rows, change_vectors=False):
        self.rows = records(rows)
        self.calls = []
        self.schema = {"class": "LawChunks", "properties": []}
        self.config = SimpleNamespace(get=lambda: SimpleNamespace(to_dict=lambda: self.schema))
        self.aggregate = SimpleNamespace(over_all=lambda **kwargs: SimpleNamespace(total_count=len(self.rows)))
        self.query = SimpleNamespace(fetch_objects=self.fetch)
        self.change_vectors = change_vectors

    def fetch(self, **kwargs):
        self.calls.append(kwargs)
        if "return_properties" in kwargs:
            result = [SimpleNamespace(properties=row["properties"], uuid=row["uuid"]) for row in self.rows]
            if self.change_vectors:
                self.rows[0]["vectors"]["default"][0] = 0.2
            return SimpleNamespace(objects=result[:10000])
        start = 0
        if "after" in kwargs:
            start = next(i + 1 for i, row in enumerate(self.rows) if row["uuid"] == kwargs["after"])
        return SimpleNamespace(objects=[SimpleNamespace(properties=copy.deepcopy(row["properties"]),
                                                       uuid=row["uuid"], vector=copy.deepcopy(row["vectors"]))
                                        for row in self.rows[start:start + kwargs["limit"]]])


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    (root / "data/processed").mkdir(parents=True)
    (root / "ai").mkdir()
    (root / "ai/test.py").write_text("# source\n")
    rows = [props(), props("Gamma Delta", "2")]
    snapshot.write_json(root / "data/processed/test.json", [dict(row, id=str(i)) for i, row in enumerate(rows)])
    with (root / "bm25_index.pkl").open("wb") as stream:
        pickle.dump(legacy_probe.build_bm25(rows), stream)

    def context(_):
        return {"source_files": snapshot.source_fingerprints(root), "data_files": snapshot.data_fingerprints(root),
                "legacy": {"resources": {"host": "localhost", "port": 8080,
                                         "grpc_port": 50051, "collection": "LawChunks"}},
                "resource_configuration_matches": True, "packages": {}, "llm": {},
                "models": [], "structural_resources": {}, "tokenizer_files": {}}
    monkeypatch.setattr(snapshot, "baseline_context", context)
    monkeypatch.setattr(snapshot, "_read_live", lambda _: snapshot.capture_live(FakeCollection(rows)))
    return root, rows


def test_probe_checks_actual_legacy_fields_without_importing_models():
    contract = legacy_probe.legacy_contract(snapshot.PROJECT_ROOT)
    assert tuple(contract["search_fields"]) == legacy_probe.SEARCH_FIELDS
    assert contract["resources"]["collection"] == "LawChunks"


def test_tokenization_preserves_case_and_field_order(monkeypatch):
    import types
    fake = types.ModuleType("pyvi")
    seen = []
    fake.ViTokenizer = SimpleNamespace(tokenize=lambda text: seen.append(text) or text)
    monkeypatch.setitem(sys.modules, "pyvi", fake)
    # Recover the real function instead of the autouse fixture's lexical fake.
    import ast
    tree = ast.parse(Path(legacy_probe.__file__).read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "tokenized_corpus")
    namespace = dict(legacy_probe.__dict__)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<tokenization>", "exec"), namespace)
    assert namespace["tokenized_corpus"]([props()]) == [["1", "Title", "1", "Head", "Alpha", "Beta"]]
    assert seen == ["1 Title 1 Head Alpha Beta"]


@pytest.mark.parametrize("change", ["order", "text", "length", "idf", "avgdl", "parameter", "tokenizer"])
def test_bm25_same_count_does_not_authorize_mismatched_resources(change):
    rows = [props(), props("Gamma Delta", "2")]
    wanted = legacy_probe.build_bm25(rows)
    actual = copy.deepcopy(wanted)
    if change == "order":
        actual.doc_freqs.reverse()
        actual.doc_len.reverse()
    elif change == "text":
        actual.doc_freqs[0] = {"unrelated": actual.doc_len[0]}
    elif change == "length":
        actual.doc_len[0] += 1
    elif change == "idf":
        actual.idf[next(iter(actual.idf))] += 1
    elif change == "avgdl":
        actual.avgdl += 1
    elif change == "parameter":
        actual.k1 = 2.0
    else:
        actual.tokenizer = "unknown tokenizer"
    result = legacy_probe.audit_bm25(actual, wanted)
    assert not result["passed"]
    assert result["checks"]["count_matches"]
    if change == "order":
        assert result["frequency_multiset_matches"]
        assert result["mismatched_position_count"] == 2


@pytest.mark.parametrize("change", ["missing", "unexpected", "duplicate", "metadata", "runtime_partial", "structural_id"])
def test_corpus_gate_rejects_divergence(change):
    rows = [props(), props("Gamma Delta", "2")]
    indexed = records(rows)
    runtime = copy.deepcopy(rows)
    if change == "missing":
        indexed.pop()
    elif change == "unexpected":
        indexed[0]["properties"]["text"] = "Changed"
    elif change == "duplicate":
        indexed[1] = copy.deepcopy(indexed[0])
    elif change == "metadata":
        indexed[0]["properties"]["display_citation"] = ""
    elif change == "runtime_partial":
        runtime.pop()
    else:
        indexed[0]["properties"]["id"] = "persisted-id-not-returned-by-search"
    assert not snapshot.compare_corpora(processed(rows), indexed, runtime)["passed"]


def test_same_citation_distinct_content_retains_distinct_runtime_identity():
    rows = [props(), props("Gamma Delta")]
    result = snapshot.compare_corpora(processed(rows), records(rows), rows)
    assert result["passed"]
    assert len({row["runtime_id"] for row in result["id_mapping"]}) == 2
    assert len({row["citation"] for row in result["id_mapping"]}) == 1


def test_export_cursor_pagination_and_exact_legacy_order():
    collection = FakeCollection([props(str(i), str(i)) for i in range(201)])
    result = snapshot.capture_live(collection)
    assert len(result["records"]) == 201
    assert result["vectors_valid"]
    assert collection.calls[1]["after"] == "uuid-199"
    legacy = [call for call in collection.calls if "return_properties" in call]
    assert legacy == [{"limit": 10000, "return_properties": list(legacy_probe.SEARCH_FIELDS)}]


def test_capture_rejects_vector_change_even_when_text_and_count_match():
    with pytest.raises(snapshot.IntegrityError, match="changed"):
        snapshot.capture_live(FakeCollection([props()], change_vectors=True))


@pytest.mark.parametrize("vector", [[], [0.1] * 767, [float("nan")] * 768, [True] * 768])
def test_invalid_vectors_cannot_authorize_dense_evaluation(vector):
    indexed = records([props()])
    indexed[0]["vectors"]["default"] = vector
    assert not snapshot.vectors_valid(indexed)


def test_offline_diagnostic_never_authorizes_scores(project, tmp_path):
    root, _ = project
    output = tmp_path / "offline"
    manifest = snapshot.create_snapshot(root, output)
    assert manifest["baseline_kind"] == "unverified"
    assert snapshot.read_json(output / "integrity.json")["bm25"]["passed"]
    with pytest.raises(snapshot.IntegrityError, match="blocked"):
        snapshot.require_trusted_snapshot(output, root)


def test_live_matching_cache_snapshot_is_trusted_and_production_untouched(project, tmp_path):
    root, _ = project
    before = snapshot.file_digest(root / "bm25_index.pkl")
    output = tmp_path / "live"
    manifest = snapshot.create_snapshot(root, output, live=True)
    assert manifest["baseline_kind"] == "as_is_verified"
    assert snapshot.require_trusted_snapshot(output, root)["gate_passed"]
    assert snapshot.file_digest(root / "bm25_index.pkl") == before
    assert snapshot.verify_live_snapshot(output, root)["passed"]
    with pytest.raises(FileExistsError):
        snapshot.create_snapshot(root, output, live=True)


def test_reordered_cache_uses_private_snapshot_bound_baseline(project, tmp_path):
    root, rows = project
    with (root / "bm25_index.pkl").open("wb") as stream:
        pickle.dump(legacy_probe.build_bm25(list(reversed(rows))), stream)
    before = snapshot.file_digest(root / "bm25_index.pkl")
    output = tmp_path / "bound"
    manifest = snapshot.create_snapshot(root, output, live=True)
    assert manifest["baseline_kind"] == "snapshot_bound"
    assert snapshot.require_trusted_snapshot(output, root)["gate_passed"]
    assert snapshot.read_json(output / "integrity.json")["bm25"]["frequency_multiset_matches"]
    assert legacy_probe.audit_bm25(legacy_probe.load_bm25(output / "evaluation_bm25.pkl"),
                                  legacy_probe.build_bm25(rows))["passed"]
    assert snapshot.file_digest(root / "bm25_index.pkl") == before


def test_live_failure_persists_diagnostic_without_secrets(project, tmp_path, monkeypatch):
    root, _ = project
    def fail(_):
        raise RuntimeError("secret credential in exception")
    monkeypatch.setattr(snapshot, "_read_live", fail)
    output = tmp_path / "unavailable"
    manifest = snapshot.create_snapshot(root, output, live=True)
    assert not manifest["gate_passed"]
    for path in output.glob("*.json"):
        assert "secret credential" not in path.read_text()
    assert snapshot.read_json(output / "integrity.json")["live_error_type"] == "RuntimeError"


@pytest.mark.parametrize("change", ["artifact", "source", "processed", "inventory"])
def test_preflight_rejects_changes_after_freeze(project, tmp_path, change):
    root, _ = project
    output = tmp_path / "frozen"
    snapshot.create_snapshot(root, output, live=True)
    if change == "artifact":
        snapshot.write_json(output / "runtime_order.json", [props("Changed")])
    elif change == "source":
        (root / "ai/test.py").write_text("# changed\n")
    elif change == "processed":
        snapshot.write_json(root / "data/processed/test.json", [dict(props(), id="new")])
    else:
        manifest = snapshot.read_json(output / "manifest.json")
        manifest["artifacts"].pop("runtime_order.json")
        snapshot.write_json(output / "manifest.json", manifest)
    with pytest.raises(snapshot.IntegrityError):
        snapshot.require_trusted_snapshot(output, root)


def test_preflight_rejects_changed_live_vectors(project, tmp_path, monkeypatch):
    root, rows = project
    output = tmp_path / "frozen"
    snapshot.create_snapshot(root, output, live=True)
    different = FakeCollection(rows)
    different.rows[0]["vectors"]["default"][0] = 0.5
    monkeypatch.setattr(snapshot, "_read_live", lambda _: snapshot.capture_live(different))
    with pytest.raises(snapshot.IntegrityError, match="changed"):
        snapshot.verify_live_snapshot(output, root)


def test_future_evaluator_additions_do_not_change_frozen_production_baseline(project, tmp_path):
    root, _ = project
    output = tmp_path / "frozen"
    snapshot.create_snapshot(root, output, live=True)
    (root / "evaluation").mkdir()
    (root / "evaluation/next_phase.py").write_text("# new evaluator, same production\n")
    assert snapshot.require_trusted_snapshot(output, root)["gate_passed"]


def test_baseline_context_supports_pyvi_module_exports(project, tmp_path, monkeypatch):
    import types
    root, _ = project
    fake = types.ModuleType("pyvi")
    fake.__file__ = str(tmp_path / "pyvi/__init__.py")
    directory = Path(fake.__file__).parent
    (directory / "models").mkdir(parents=True)
    for name in ("ViTokenizer.py", "models/words.txt", "models/pyvi3.pkl"):
        (directory / name).write_text("tokenizer resource")
    fake.ViTokenizer = SimpleNamespace(ViTokenizer=SimpleNamespace(model_file="models/pyvi3.pkl"))
    monkeypatch.setitem(sys.modules, "pyvi", fake)
    monkeypatch.setattr(snapshot, "legacy_contract", lambda _: {
        "embedding_model": "vendor/embed", "reranker_model": "vendor/rerank",
        "resources": {"host": "localhost", "port": 8080, "grpc_port": 50051, "collection": "LawChunks"}})
    monkeypatch.setattr(snapshot.subprocess, "check_output", lambda *a, **k: "test commit")
    monkeypatch.setattr(snapshot.platform, "platform", lambda: "test platform")
    monkeypatch.setattr(snapshot, "model_provenance", lambda name, cache: {"model": name})
    # The fixture replaces baseline_context; retrieve its actual function for this compatibility test.
    import ast
    tree = ast.parse(Path(snapshot.__file__).read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "baseline_context")
    namespace = dict(snapshot.__dict__)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<baseline-context>", "exec"), namespace)
    result = namespace["baseline_context"](root)
    assert set(result["tokenizer_files"]) == {"ViTokenizer.py", "models/words.txt", "models/pyvi3.pkl"}
    assert "gemini_api_key" not in result["llm"]


def test_preflight_rejects_changed_llm_configuration(project, tmp_path, monkeypatch):
    root, _ = project
    output = tmp_path / "frozen"
    snapshot.create_snapshot(root, output, live=True)
    original_context = snapshot.baseline_context
    def changed(root):
        context = original_context(root)
        context["llm"] = {"model_name": "changed model"}
        return context
    monkeypatch.setattr(snapshot, "baseline_context", changed)
    with pytest.raises(snapshot.IntegrityError, match="llm"):
        snapshot.require_trusted_snapshot(output, root)


def test_resource_split_is_blocked(project, tmp_path, monkeypatch):
    root, _ = project
    context = snapshot.baseline_context(root)
    context["resource_configuration_matches"] = False
    monkeypatch.setattr(snapshot, "baseline_context", lambda _: context)
    assert not snapshot.create_snapshot(root, tmp_path / "split", live=True)["gate_passed"]
    assert snapshot.resources_match({"host": "localhost", "port": 8080}, {"host": "127.0.0.1", "port": 8080})
    assert not snapshot.resources_match({"host": "localhost", "port": 8080}, {"host": "localhost", "port": 8081})


def test_private_binding_requires_separate_worker(project, tmp_path, monkeypatch):
    root, rows = project
    output = tmp_path / "frozen"
    snapshot.create_snapshot(root, output, live=True)
    module = SimpleNamespace(weaviate_collection=SimpleNamespace(name="LawChunks"), chunks_cache=rows,
                             bm25_index=None)
    monkeypatch.setenv("ROADLAWQA_EVALUATION_WORKER", "1")
    with pytest.raises(ValueError, match="separate"):
        legacy_probe.bind_legacy_resources(module, output, root)
    manifest = snapshot.read_json(output / "manifest.json")
    manifest["creator_pid"] = -1
    snapshot.write_json(output / "manifest.json", manifest)
    assert legacy_probe.bind_legacy_resources(module, output, root) == "as_is_verified"
    assert module.chunks_cache == rows
    assert module.bm25_index is not None


def test_cache_unpickler_rejects_executable_globals(tmp_path):
    class Unsafe:
        def __reduce__(self):
            return os.system, ("false",)
    path = tmp_path / "bad.pkl"
    with path.open("wb") as stream:
        pickle.dump(Unsafe(), stream)
    with pytest.raises(ValueError, match="Unsupported"):
        legacy_probe.load_bm25(path)


def test_cached_model_fingerprints_without_download(tmp_path):
    directory = tmp_path / "models--vendor--model"
    (directory / "refs").mkdir(parents=True)
    (directory / "refs/main").write_text("abc123")
    (directory / "snapshots/abc123").mkdir(parents=True)
    (directory / "snapshots/abc123/model.safetensors").write_bytes(b"cached weights")
    result = snapshot.model_provenance("vendor/model", tmp_path)
    assert result["status"] == "cached_candidate"
    assert result["revision"] == "abc123"
    assert result["loaded"] is False
    assert snapshot.model_provenance("missing/model", tmp_path)["status"] == "not_cached"


def test_schema_redaction_keeps_nonsecret_configuration():
    assert snapshot.redact_schema({"moduleConfig": {"apiKey": "secret"}, "tokenization": "word"}) == {
        "moduleConfig": {"apiKey": "<redacted>"}, "tokenization": "word"}


def test_import_snapshot_and_probe_does_not_initialize_models_or_network():
    script = '''
import importlib.abc, socket, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('torch', 'weaviate', 'pyvi', 'sentence_transformers', 'google') or fullname == 'backend.retriever_custom':
            raise AssertionError('Unexpected import: ' + fullname)
sys.meta_path.insert(0, Guard())
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
import evaluation.snapshot, evaluation.legacy_probe
'''
    subprocess.run([sys.executable, "-c", script], check=True, cwd=snapshot.PROJECT_ROOT)
