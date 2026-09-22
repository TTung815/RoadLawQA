"""Phase 0: read-only baseline capture and fail-closed evaluation preflight.

Run with python -m evaluation.snapshot. Importing this module loads no models,
database clients, tokenizer, credentials or legacy retrieval implementation.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
from typing import Any, Mapping, Sequence

from evaluation.legacy_probe import (
    SEARCH_FIELDS, audit_bm25, build_bm25, legacy_contract, load_bm25,
    runtime_id, search_properties,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORMAT_VERSION = 1


class IntegrityError(ValueError):
    """The recorded baseline cannot authorize official evaluation scores."""


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, Path)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False, default=_json_default).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                               allow_nan=False, default=_json_default) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_json(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def source_fingerprints(root: Path) -> dict[str, str]:
    paths = []
    for directory in ("ai", "backend", "configs"):
        paths.extend((root / directory).rglob("*.py"))
    paths.extend((root / "docker").glob("*.yml"))
    paths.extend(root / name for name in ("requirements.txt", "pytest.ini", "AGENTS.md"))
    return {str(path.relative_to(root)): file_digest(path)
            for path in sorted(set(paths)) if path.is_file()}


def evaluator_fingerprints(root: Path) -> dict[str, str]:
    paths = sorted((root / "evaluation").rglob("*.py")) + sorted((root / "tests").rglob("*.py"))
    return {str(path.relative_to(root)): file_digest(path) for path in paths}


def data_fingerprints(root: Path) -> dict[str, str]:
    paths = sorted((root / "data/raw").glob("*.txt")) + sorted((root / "data/processed").glob("*.json"))
    return {str(path.relative_to(root)): file_digest(path) for path in paths}


def load_processed(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted((root / "data/processed").glob("*.json")):
        for row in read_json(path):
            result.append({"processed_id": row.get("id"), "file": str(path.relative_to(root)),
                           "properties": row})
    if not result:
        raise IntegrityError("Processed corpus is empty")
    return result


def compare_corpora(processed: Sequence[Mapping[str, Any]], indexed: Sequence[Mapping[str, Any]],
                    runtime_order: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare exact search content, identities, and complete baseline membership."""
    expected = Counter(digest(search_properties(row["properties"])) for row in processed)
    actual = Counter(digest(search_properties(row["properties"])) for row in indexed)
    runtime = Counter(digest(search_properties(row)) for row in runtime_order)
    uuids = [row["uuid"] for row in indexed]
    runtime_ids = [runtime_id(row["properties"]) for row in indexed]
    missing = list((expected - actual).elements())
    unexpected = list((actual - expected).elements())
    duplicate_ids = [key for key, count in Counter(runtime_ids).items() if count > 1]
    duplicate_processed_ids = [key for key, count in Counter(row["processed_id"] for row in processed).items()
                               if not key or count > 1]
    mismatched_structural_ids = [row["uuid"] for row in indexed
                                if row["properties"].get("id") and
                                str(row["properties"]["id"]) != runtime_id(row["properties"])]
    metadata_missing = [row["uuid"] for row in indexed if any(
        not str(row["properties"].get(key) or "").strip()
        for key in ("law", "article_no", "text", "enriched_text", "display_citation"))]
    checks = {
        "processed_matches_indexed": expected == actual,
        "runtime_covers_full_index": runtime == actual,
        "unique_uuids": len(uuids) == len(set(uuids)),
        "unique_runtime_ids": not duplicate_ids,
        "unique_processed_ids": not duplicate_processed_ids,
        "required_metadata_present": not metadata_missing,
        "structural_search_ids_match": not mismatched_structural_ids,
    }
    by_content = {digest(search_properties(row["properties"])): row for row in processed}
    mapping = []
    for row in indexed:
        match = by_content.get(digest(search_properties(row["properties"])))
        mapping.append({"uuid": row["uuid"], "runtime_id": runtime_id(row["properties"]),
                        "processed_id": match["processed_id"] if match else None,
                        "processed_file": match["file"] if match else None,
                        "citation": row["properties"].get("display_citation")})
    return {"passed": all(checks.values()), "checks": checks,
            "processed_count": len(processed), "indexed_count": len(indexed),
            "runtime_count": len(runtime_order), "missing_content_hashes": missing,
            "unexpected_content_hashes": unexpected, "duplicate_runtime_ids": duplicate_ids,
            "duplicate_processed_ids": duplicate_processed_ids, "missing_metadata_uuids": metadata_missing,
            "structural_identity_mismatch_uuids": mismatched_structural_ids, "id_mapping": mapping}


def vectors_valid(records: Sequence[Mapping[str, Any]]) -> bool:
    for record in records:
        vectors = record.get("vectors")
        if not isinstance(vectors, dict) or not vectors:
            return False
        for vector in vectors.values():
            if not isinstance(vector, list) or len(vector) != 768 or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in vector):
                return False
    return bool(records)


def collection_fingerprint(records: Sequence[Mapping[str, Any]], schema: Mapping[str, Any]) -> dict[str, str]:
    return {"objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])),
            "schema_sha256": digest(schema)}


def redact_schema(value: Any):
    """Preserve schema settings but never export embedded credentials."""
    if isinstance(value, dict):
        return {key: "<redacted>" if key.replace("_", "").lower() in (
            "apikey", "authorization", "password", "secret", "accesstoken", "token")
                else redact_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_schema(item) for item in value]
    return value


def export_collection(collection: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read all objects with cursor pagination; no insert/update/delete methods."""
    before = collection.aggregate.over_all(total_count=True).total_count
    schema = redact_schema(collection.config.get().to_dict())
    records, after, seen = [], None, set()
    while True:
        kwargs = {"limit": 200, "include_vector": True}
        if after is not None:
            kwargs["after"] = after
        objects = collection.query.fetch_objects(**kwargs).objects
        for obj in objects:
            identity = str(obj.uuid)
            if identity in seen:
                raise IntegrityError("Pagination returned a repeated UUID")
            seen.add(identity)
            records.append({"uuid": identity, "properties": obj.properties, "vectors": obj.vector})
        if len(objects) < 200:
            break
        after = objects[-1].uuid
    count = collection.aggregate.over_all(total_count=True).total_count
    if before != count or len(records) != count:
        raise IntegrityError("Collection count changed or export omitted objects")
    return records, schema


def capture_live(collection: Any) -> dict[str, Any]:
    """Capture the actual legacy fetch order, bracketed by complete exports."""
    records, schema = export_collection(collection)
    runtime = collection.query.fetch_objects(limit=10000, return_properties=list(SEARCH_FIELDS)).objects
    runtime_order = [obj.properties for obj in runtime]
    final_records, final_schema = export_collection(collection)
    fingerprint = collection_fingerprint(records, schema)
    if fingerprint != collection_fingerprint(final_records, final_schema):
        raise IntegrityError("Collection/schema/vectors changed during capture")
    return {"records": records, "schema": schema, "runtime_order": runtime_order,
            "fingerprint": fingerprint, "vectors_valid": vectors_valid(records)}


def _read_live(resources: Mapping[str, Any]) -> dict[str, Any]:
    import weaviate

    client = weaviate.connect_to_local(host=resources["host"], port=resources["port"],
                                      grpc_port=resources["grpc_port"], skip_init_checks=True)
    try:
        return capture_live(client.collections.get(resources["collection"]))
    finally:
        client.close()


def resources_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    loopback = {"localhost", "127.0.0.1", "::1"}
    def normal(value):
        return dict(value, host="loopback" if value["host"] in loopback else value["host"])
    return normal(left) == normal(right)


def model_provenance(model_name: str, cache_root: Path) -> dict[str, Any]:
    """Hash cached files only; never download or instantiate an embedding model."""
    directory = cache_root / ("models--" + model_name.replace("/", "--"))
    ref = directory / "refs/main"
    revision = ref.read_text().strip() if ref.is_file() else None
    if revision is None or not revision.isalnum():
        return {"model": model_name, "status": "not_cached", "revision": None}
    snapshot = directory / "snapshots" / revision
    files = {str(path.relative_to(snapshot)): file_digest(path)
             for path in sorted(snapshot.rglob("*")) if path.is_file()}
    weights = any(key.endswith((".bin", ".safetensors")) for key in files)
    return {"model": model_name, "status": "cached_candidate" if weights else "weights_missing",
            "revision": revision, "files": files, "files_sha256": digest(files),
            "loaded": False}


def baseline_context(root: Path) -> dict[str, Any]:
    from configs.settings import Settings

    contract = legacy_contract(root)
    settings = Settings()
    structural = {"host": settings.weaviate_host, "port": settings.weaviate_port,
                  "grpc_port": settings.weaviate_grpc_port, "collection": settings.weaviate_collection}
    packages = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()
                if dist.metadata["Name"]}
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    cache_root = Path(os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE") or
                      (Path(os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub"))
    models = [model_provenance(contract[key], cache_root) for key in ("embedding_model", "reranker_model")]
    from pyvi import ViTokenizer
    import pyvi
    tokenizer_root = Path(pyvi.__file__).parent
    tokenizer_files = {name: file_digest(tokenizer_root / name)
                       for name in ("ViTokenizer.py", "models/words.txt", ViTokenizer.ViTokenizer.model_file)}
    return {"git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--short"),
            "source_files": source_fingerprints(root), "evaluator_files": evaluator_fingerprints(root),
            "data_files": data_fingerprints(root),
            "python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "logical_cpus": os.cpu_count(),
            "packages": dict(sorted(packages.items())), "legacy": contract,
            "structural_resources": structural,
            "resource_configuration_matches": not settings.structural_expansion_enabled or
                resources_match(contract["resources"], structural),
            "llm": {"model_name": settings.gemini_model_name,
                    "max_retrieval_attempts": settings.max_retrieval_attempts,
                    "structural_expansion_enabled": settings.structural_expansion_enabled},
            "models": models, "tokenizer_files": tokenizer_files,
            "local_models_loaded": False,
            "remote_model_revision": "not available from configured Gemini model name"}


def create_snapshot(root: Path, output: Path, live: bool = False) -> dict[str, Any]:
    """Always persist an honest diagnostic; a failed live gate never becomes trusted."""
    import pickle

    output.mkdir(parents=True, exist_ok=False)
    baseline = baseline_context(root)
    processed = load_processed(root)
    write_json(output / "processed.json", processed)
    report: dict[str, Any] = {"live_status": "not_requested", "gate_passed": False}
    live_data = None
    if live:
        try:
            live_data = _read_live(baseline["legacy"]["resources"])
            report["live_status"] = "captured"
        except Exception as exc:
            # Network exception strings can contain URLs/credentials; retain only the class.
            report["live_status"] = "failed"
            report["live_error_type"] = type(exc).__name__
    rows = ([search_properties(row["properties"]) for row in processed] if live_data is None
            else live_data["runtime_order"])
    write_json(output / "runtime_order.json", rows)
    expected = build_bm25(rows)
    cache = root / "bm25_index.pkl"
    cache_hash = file_digest(cache) if cache.is_file() else None
    cache_audit = {"passed": False, "status": "missing"}
    if cache_hash is not None:
        try:
            cache_audit = dict(audit_bm25(load_bm25(cache), expected), status="checked")
        except Exception as exc:
            cache_audit = {"passed": False, "status": "unreadable", "error_type": type(exc).__name__}
    report["bm25"] = cache_audit
    report["bm25_order_basis"] = "live_legacy_fetch" if live_data else "processed_diagnostic_only"
    with (output / "evaluation_bm25.pkl").open("wb") as stream:
        pickle.dump(expected, stream)
    fingerprint = None
    if live_data is not None:
        with gzip.open(output / "indexed.json.gz", "wb") as stream:
            stream.write(canonical_bytes(live_data["records"]))
        write_json(output / "schema.json", live_data["schema"])
        corpus = compare_corpora(processed, live_data["records"], rows)
        write_json(output / "id_mapping.json", corpus.pop("id_mapping"))
        report["corpus"] = corpus
        report["vectors_valid"] = live_data["vectors_valid"]
        fingerprint = live_data["fingerprint"]
        report["gate_passed"] = bool(corpus["passed"] and live_data["vectors_valid"] and
                                      baseline["resource_configuration_matches"])
    report["resource_configuration_matches"] = baseline["resource_configuration_matches"]
    report["production_bm25_unchanged"] = cache_hash == (file_digest(cache) if cache.is_file() else None)
    report["source_unchanged_during_capture"] = baseline["source_files"] == source_fingerprints(root)
    report["data_unchanged_during_capture"] = baseline["data_files"] == data_fingerprints(root)
    report["gate_passed"] = bool(report["gate_passed"] and all(report[key] for key in (
        "production_bm25_unchanged", "source_unchanged_during_capture", "data_unchanged_during_capture")))
    kind = "unverified" if not report["gate_passed"] else (
        "as_is_verified" if cache_audit["passed"] else "snapshot_bound")
    write_json(output / "integrity.json", report)
    write_json(output / "baseline.json", baseline)
    (output / "README.md").write_text(
        "# Evaluation snapshot\n\n"
        f"- Baseline kind: `{kind}`\n- Integrity gate: `{report['gate_passed']}`\n"
        f"- Live capture: `{report['live_status']}`\n- BM25 order: `{report['bm25_order_basis']}`\n\n"
        "No production cache, models, chunks or index were changed.\n"
        "A processed-only diagnostic cannot authorize official retrieval scores.\n"
        "Cached model fingerprints are candidates, not proof of the revisions loaded by a future worker.\n"
        "Check live schema/objects/vectors again before and after each evaluation run.\n"
        "See integrity.json for ordered BM25 checks and baseline.json for resource configuration.\n",
        encoding="utf-8")
    artifacts = {path.name: file_digest(path) for path in sorted(output.iterdir()) if path.is_file()}
    manifest = {"format_version": FORMAT_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
                "creator_pid": os.getpid(), "baseline_kind": kind, "gate_passed": report["gate_passed"],
                "collection_fingerprint": fingerprint, "production_bm25_sha256": cache_hash,
                "runtime_order_sha256": digest(rows), "baseline": baseline, "artifacts": artifacts}
    write_json(output / "manifest.json", manifest)
    return manifest


def require_trusted_snapshot(snapshot_dir: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    manifest = read_json(snapshot_dir / "manifest.json")
    if manifest.get("format_version") != FORMAT_VERSION or manifest.get("gate_passed") is not True:
        raise IntegrityError("Snapshot is unverified; official evaluation is blocked")
    if manifest.get("baseline_kind") not in ("as_is_verified", "snapshot_bound"):
        raise IntegrityError("Unknown baseline kind")
    required = {"indexed.json.gz", "schema.json", "runtime_order.json", "evaluation_bm25.pkl",
                "id_mapping.json", "processed.json", "integrity.json", "baseline.json", "README.md"}
    if set(manifest.get("artifacts", {})) != required:
        raise IntegrityError("Incomplete snapshot artifact inventory")
    for name, checksum in manifest["artifacts"].items():
        path = snapshot_dir / name
        if not path.is_file() or file_digest(path) != checksum:
            raise IntegrityError(f"Snapshot artifact changed: {name}")
    baseline = manifest["baseline"]
    if baseline["source_files"] != source_fingerprints(root):
        raise IntegrityError("Source changed since baseline capture; take a new snapshot")
    if baseline["data_files"] != data_fingerprints(root):
        raise IntegrityError("Raw/processed corpus changed since baseline capture")
    current = baseline_context(root)
    for key in ("packages", "llm", "structural_resources", "models", "tokenizer_files"):
        if baseline[key] != current[key]:
            raise IntegrityError(f"Baseline environment changed: {key}")
    return manifest


def verify_live_snapshot(snapshot_dir: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    manifest = require_trusted_snapshot(snapshot_dir, root)
    current = _read_live(manifest["baseline"]["legacy"]["resources"])
    if current["fingerprint"] != manifest["collection_fingerprint"]:
        raise IntegrityError("Live schema/objects/vectors changed since capture")
    return {"passed": True, "fingerprint": current["fingerprint"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New snapshot directory (never overwrite)")
    parser.add_argument("--live", action="store_true", help="Read the actual legacy Weaviate resources")
    parser.add_argument("--verify-live", type=Path, help="Recheck an existing snapshot; no artifact writes")
    args = parser.parse_args(argv)
    if args.verify_live:
        try:
            result = verify_live_snapshot(args.verify_live)
        except Exception as exc:
            print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
            return 2
        print(json.dumps(result))
        return 0
    output = args.output or PROJECT_ROOT / "outputs/evaluation" / (
        "snapshot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    try:
        manifest = create_snapshot(PROJECT_ROOT, output, live=args.live)
    except Exception as exc:
        print(json.dumps({"snapshot": str(output), "gate_passed": False,
                          "error_type": type(exc).__name__}))
        return 2
    print(json.dumps({"snapshot": str(output), "baseline_kind": manifest["baseline_kind"],
                      "gate_passed": manifest["gate_passed"]}, ensure_ascii=False))
    return 0 if manifest["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
