"""Evaluation-only inspection and resource binding; never import legacy eagerly."""

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SEARCH_FIELDS = (
    "law", "chapter", "section", "article_no", "article_title", "clause_no",
    "point", "clause_head", "text", "enriched_text", "display_citation",
)
BM25_FIELDS = ("article_no", "article_title", "clause_no", "point", "clause_head", "text")
BM25_PARAMETERS = {"k1": 1.5, "b": 0.75, "epsilon": 0.25}


def legacy_contract(root: Path) -> dict[str, Any]:
    """Check the assumptions of the probe against source without executing it."""
    tree = ast.parse((root / "backend/retriever_custom.py").read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    fields = []
    for name in ("load_chunks_from_weaviate", "retrieve_dense"):
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.keyword) and node.arg == "return_properties":
                fields.append(tuple(ast.literal_eval(node.value)))
    # The lexical list contains c.get calls; extract their field arguments instead.
    if fields != [SEARCH_FIELDS, SEARCH_FIELDS]:
        raise ValueError("Legacy search fields changed; update and validate the evaluation probe")
    return _contract_details(tree, functions)


def _contract_details(tree: ast.Module, functions: Mapping[str, ast.FunctionDef]) -> dict[str, Any]:
    assignment = next(node for node in ast.walk(functions["build_bm25_index"])
                      if isinstance(node, ast.Assign) and any(
                          isinstance(target, ast.Name) and target.id == "fields" for target in node.targets))
    lexical = tuple(element.args[0].value for element in assignment.value.elts)
    if lexical != BM25_FIELDS:
        raise ValueError("Legacy BM25 fields changed; evaluation cannot assume compatibility")
    bm25_call = next(node for node in ast.walk(functions["build_bm25_index"])
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "BM25Okapi")
    if bm25_call.keywords or len(bm25_call.args) != 1:
        raise ValueError("Legacy BM25 parameters changed")
    model_calls = {node.func.id: node.args[0].value for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in ("SentenceTransformer", "CrossEncoder")}
    connect = next(node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "client" for target in node.targets))
    if ast.unparse(connect.value) != "weaviate.connect_to_local(skip_init_checks=True)":
        raise ValueError("Legacy connection changed; inspect its actual resource configuration")
    collection = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "weaviate_collection"
                              for target in node.targets))
    multiplier = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "CANDIDATE_MULTIPLIER"
                              for target in node.targets))
    return {
        "search_fields": list(SEARCH_FIELDS), "bm25_fields": list(BM25_FIELDS),
        "bm25_parameters": BM25_PARAMETERS, "candidate_multiplier": multiplier,
        "embedding_model": model_calls["SentenceTransformer"],
        "reranker_model": model_calls["CrossEncoder"],
        "resources": {"host": "localhost", "port": 8080, "grpc_port": 50051,
                      "collection": collection.args[0].value},
        "device_policy": "cuda if available, otherwise cpu; legacy disables MPS and sets Torch threads to 1",
    }


def search_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    """Project exactly the fields requested by baseline search, including nulls."""
    return {key: properties.get(key) for key in SEARCH_FIELDS}


def runtime_id(properties: Mapping[str, Any]) -> str:
    from ai.retrieval.legacy_adapter import LegacyRetrieverAdapter

    return LegacyRetrieverAdapter.map_results([{"props": search_properties(properties)}])[0].id


def tokenized_corpus(rows: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    from pyvi import ViTokenizer

    # Deliberately use the original join/tokenization, without lowercasing or normalization.
    return [ViTokenizer.tokenize(" ".join(row.get(key) for key in BM25_FIELDS if row.get(key))).split()
            for row in rows]


def build_bm25(rows: Sequence[Mapping[str, Any]]):
    from rank_bm25 import BM25Okapi

    if not rows:
        raise ValueError("An empty corpus cannot authorize retrieval evaluation")
    return BM25Okapi(tokenized_corpus(rows), **BM25_PARAMETERS)


def load_bm25(path: Path):
    """Read only local BM25/NumPy cache data; reject arbitrary pickle globals."""
    import pickle

    class CacheUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            allowed = {
                ("rank_bm25", "BM25Okapi"), ("numpy", "dtype"), ("numpy", "ndarray"),
                ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
                ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"),
            }
            if (module, name) not in allowed:
                raise ValueError("Unsupported BM25 cache format")
            return super().find_class(module, name)

    with path.open("rb") as stream:
        return CacheUnpickler(stream).load()


def audit_bm25(cache: Any, expected: Any) -> dict[str, Any]:
    import math
    from collections import Counter

    def signature(frequencies):
        return hashlib.sha256(json.dumps(frequencies, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    actual = getattr(cache, "doc_freqs", [])
    wanted = expected.doc_freqs
    mismatches = [number for number, (left, right) in enumerate(zip(actual, wanted)) if left != right]
    idf = getattr(cache, "idf", {})
    idf_matches = set(idf) == set(expected.idf) and all(
        math.isclose(idf[key], value, rel_tol=1e-12, abs_tol=1e-12) for key, value in expected.idf.items())
    checks = {
        "class_matches": type(cache) is type(expected),
        "parameters_match": all(getattr(cache, key, None) == value for key, value in BM25_PARAMETERS.items()),
        "count_matches": getattr(cache, "corpus_size", None) == expected.corpus_size,
        "ordered_frequencies_match": actual == wanted,
        "document_lengths_match": getattr(cache, "doc_len", None) == expected.doc_len,
        "average_length_matches": math.isclose(getattr(cache, "avgdl", -1), expected.avgdl,
                                               rel_tol=1e-12, abs_tol=1e-12),
        "idf_matches": idf_matches,
        "average_idf_matches": math.isclose(getattr(cache, "average_idf", -1), expected.average_idf,
                                            rel_tol=1e-12, abs_tol=1e-12),
        "tokenizer_matches": getattr(cache, "tokenizer", None) is None,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "frequency_multiset_matches": Counter(map(signature, actual)) == Counter(map(signature, wanted)),
            "mismatched_positions": mismatches[:50], "mismatched_position_count": len(mismatches),
            "cache_count": getattr(cache, "corpus_size", None), "expected_count": expected.corpus_size}


def bind_legacy_resources(module: Any, snapshot_dir: Path, root: Path) -> str:
    """Bind verified files only in a dedicated worker, before any search.

    Caller owns the worker's legacy import. This function never imports legacy,
    changes production files, or changes ranking functions/models. Recheck the
    live fingerprint with verify_live_snapshot before and after a future run.
    """
    import os
    from evaluation.snapshot import require_trusted_snapshot, read_json, read_gzip_json

    manifest = require_trusted_snapshot(snapshot_dir, root)
    if os.environ.get("ROADLAWQA_EVALUATION_WORKER") != "1" or manifest["creator_pid"] == os.getpid():
        raise ValueError("Resource binding requires a separate evaluation worker process")
    expected_resources = manifest["baseline"]["legacy"]["resources"]
    if getattr(module.weaviate_collection, "name", None) != expected_resources["collection"]:
        raise ValueError("Worker collection differs from the recorded legacy collection")
    rows = read_json(snapshot_dir / "runtime_order.json")
    bm25 = load_bm25(snapshot_dir / "evaluation_bm25.pkl")
    if not audit_bm25(bm25, build_bm25(rows))["passed"]:
        raise ValueError("Snapshot BM25 does not match the frozen runtime order")
    indexed = read_gzip_json(snapshot_dir / "indexed.json.gz")
    expected = sorted(runtime_id(record["properties"]) for record in indexed)
    actual = sorted(runtime_id(row) for row in module.chunks_cache)
    if actual != expected:
        raise ValueError("Worker loaded a different corpus; evaluation cannot bind it")
    from evaluation.snapshot import digest
    kind = manifest["baseline_kind"]
    if digest(module.chunks_cache) != manifest["runtime_order_sha256"]:
        kind = "snapshot_bound"
    module.chunks_cache = rows
    module.bm25_index = bm25
    return kind


def main() -> int:
    """Optional offline-model worker smoke: initialization/binding, no LLM or search."""
    import argparse
    import importlib
    import os
    import shutil
    import tempfile
    from evaluation.snapshot import PROJECT_ROOT, require_trusted_snapshot, verify_live_snapshot, write_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New probe result file outside frozen snapshot")
    args = parser.parse_args()
    snapshot = args.snapshot.resolve()
    output = args.output.resolve()
    if output.exists() or snapshot in output.parents:
        parser.error("Probe output must be a new file outside the frozen snapshot")
    result = {"passed": False, "llm_calls": 0, "search_calls": 0}
    module = None
    cwd = Path.cwd()
    try:
        manifest = require_trusted_snapshot(snapshot, PROJECT_ROOT)
        verify_live_snapshot(snapshot, PROJECT_ROOT)
        os.environ["ROADLAWQA_EVALUATION_WORKER"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        with tempfile.TemporaryDirectory(prefix="roadlawqa-probe-", dir=output.parent) as directory:
            shutil.copyfile(snapshot / "evaluation_bm25.pkl", Path(directory) / "bm25_index.pkl")
            os.chdir(directory)
            module = importlib.import_module("backend.retriever_custom")
            kind = bind_legacy_resources(module, snapshot, PROJECT_ROOT)
            models = (module.emb_model[0].auto_model, module.reranker.model)
            revisions = [getattr(model.config, "_commit_hash", None) for model in models]
            candidates = [model["revision"] for model in manifest["baseline"]["models"]]
            result.update({"baseline_kind": kind, "device": module.DEVICE,
                           "model_revisions": revisions, "model_revisions_match": revisions == candidates,
                           "bound_chunks": len(module.chunks_cache)})
            os.chdir(cwd)
            verify_live_snapshot(snapshot, PROJECT_ROOT)
            result["passed"] = all(revisions) and revisions == candidates
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    finally:
        os.chdir(cwd)
        if module is not None:
            module.cleanup()
    write_json(output, result)
    print(json.dumps(result))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
