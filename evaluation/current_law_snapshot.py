"""Freeze a verified current-law corpus and its isolated shadow resources.

Freezing is fail closed: it re-reads the live shadow collection, verifies the
full object/vector/schema fingerprint and checks that production membership and
the root BM25 cache still match the state bracketed by the shadow build.  It
does not run retrieval, an LLM, or any benchmark case.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from evaluation.snapshot import digest
from ingestion.current_law_corpus import (
    CORPUS_ID,
    DEFAULT_MANIFEST as DEFAULT_CORPUS_MANIFEST,
    DEFAULT_OUTPUT as DEFAULT_CORPUS,
    LEGAL_AS_OF,
)
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json, write_json
from ingestion.shadow_index import (
    DEFAULT_OUTPUT_DIR as DEFAULT_SHADOW_DIR,
    PRODUCTION_COLLECTION,
    SHADOW_COLLECTION,
    ShadowIntegrityError,
    connect_local,
    export_collection,
    load_validated_corpus,
    production_state,
    verify_shadow_bundle,
    verify_shadow_records,
)


DEFAULT_SNAPSHOT_MANIFEST = (
    PROJECT_ROOT
    / "data/processed/current-law/current-law-snapshot-manifest-2026-09-22.json"
)
DEFAULT_RECEIPT = PROJECT_ROOT / "evaluation/manifests/current-law-2026-09-22.json"


def display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        str(resolved.relative_to(PROJECT_ROOT))
        if resolved.is_relative_to(PROJECT_ROOT)
        else str(resolved)
    )


def make_snapshot_documents(
    shadow_dir: Path,
    shadow_manifest: dict,
    shadow_integrity: dict,
    live_fingerprint: dict,
    production_live_state: dict,
) -> tuple[dict, dict]:
    corpus_manifest = read_json(DEFAULT_CORPUS_MANIFEST)
    blocked = {
        "nd168_mixed_2028": [
            "điểm l khoản 5 Điều 20",
            "điểm b khoản 3 Điều 21",
            "điểm b khoản 9a Điều 32",
        ],
        "nd168_future_2029": [
            "điểm n khoản 5 Điều 20",
            "điểm k khoản 7 Điều 26",
            "điểm l khoản 7 Điều 26",
        ],
        "law_55_mixed_article_35": ["khoản 2 Điều 35 55/VBHN-VPQH"],
        "consolidated_repealed_placeholders": [
            "khoản 4 Điều 10 49/VBHN-VPQH",
            "Điều 83 49/VBHN-VPQH",
            "khoản 7 Điều 62 55/VBHN-VPQH",
        ],
    }
    snapshot_manifest = {
        "schema_version": 1,
        "snapshot_id": CORPUS_ID,
        "legal_as_of": LEGAL_AS_OF,
        "status": "frozen",
        "frozen": True,
        "frozen_on": LEGAL_AS_OF,
        "freezer": {
            "path": str(Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            "sha256": file_digest(Path(__file__).resolve()),
        },
        "processed_corpus": {
            "path": str(DEFAULT_CORPUS.relative_to(PROJECT_ROOT)),
            "sha256": file_digest(DEFAULT_CORPUS),
            "manifest_path": str(DEFAULT_CORPUS_MANIFEST.relative_to(PROJECT_ROOT)),
            "manifest_sha256": file_digest(DEFAULT_CORPUS_MANIFEST),
            "chunk_count": corpus_manifest["summary"]["chunk_count"],
            "inputs": corpus_manifest["inputs"],
            "builder": corpus_manifest["builder"],
        },
        "shadow_resources": {
            "collection": SHADOW_COLLECTION,
            "collection_fingerprint": live_fingerprint,
            "runtime_order_sha256": shadow_manifest["runtime_order_sha256"],
            "bm25_sha256": shadow_manifest["bm25_sha256"],
            "bm25_order_basis": shadow_integrity["bm25_order_basis"],
            "embedding": shadow_manifest["embedding"],
            "builder": shadow_manifest["builder"],
            "packages": shadow_manifest["packages"],
        },
        "publication_blocks": blocked,
        "gates": {
            "processed_corpus_validated": True,
            "processed_matches_shadow": True,
            "shadow_vectors_valid": True,
            "shadow_schema_and_membership_stable": True,
            "runtime_order_matches_bm25": True,
            "production_collection_unchanged": True,
            "production_bm25_unchanged": True,
        },
        "production": {
            "collection": PRODUCTION_COLLECTION,
            "state": production_live_state,
            "touched": False,
            "root_bm25_touched": False,
            "root_bm25_sha256": shadow_integrity["production_bm25_sha256"],
        },
        "limitations": [
            "Effective view 168+238 is a technical artifact, not an official consolidated document.",
            "The ten listed mixed/future/repealed chunks remain blocked from automatic publication.",
            "The snapshot does not establish negative-support completeness.",
            "The snapshot does not ingest the Law on Handling Administrative Violations dependency.",
            "Production retrieval is not switched to the shadow resources by this freeze.",
        ],
    }
    receipt = {
        "receipt_version": 1,
        "snapshot_id": CORPUS_ID,
        "legal_as_of": LEGAL_AS_OF,
        "status": "frozen",
        "frozen": True,
        "gate_passed": True,
        "snapshot_manifest": {
            "path": str(DEFAULT_SNAPSHOT_MANIFEST.relative_to(PROJECT_ROOT)),
            "sha256": None,
        },
        "shadow_bundle": {
            "path": display_path(shadow_dir),
            "manifest_sha256": file_digest(shadow_dir / "manifest.json"),
            "tracked_in_git": False,
            "required_for_full_replay": True,
        },
        "production_index_changed": False,
        "benchmark_audit_or_c0_c4_run": False,
        "next_authorized_phase": "audit historical candidates and rebuild current-law gold",
    }
    return snapshot_manifest, receipt


def freeze_current_law_snapshot(
    shadow_dir: Path = DEFAULT_SHADOW_DIR,
    snapshot_manifest_path: Path = DEFAULT_SNAPSHOT_MANIFEST,
    receipt_path: Path = DEFAULT_RECEIPT,
    *,
    host: str = "localhost",
    port: int = 8080,
    grpc_port: int = 50051,
    client: Any | None = None,
) -> tuple[dict, dict]:
    if snapshot_manifest_path.exists() or receipt_path.exists():
        raise FileExistsError("frozen snapshot artifacts already exist")
    corpus, _ = load_validated_corpus()
    shadow_manifest = verify_shadow_bundle(shadow_dir)
    shadow_integrity = read_json(shadow_dir / "integrity.json")
    if shadow_manifest.get("frozen") is not False:
        raise ShadowIntegrityError("shadow preflight must be unfrozen before receipt creation")

    own_client = client is None
    if client is None:
        client = connect_local(host, port, grpc_port)
    try:
        if not client.collections.exists(SHADOW_COLLECTION):
            raise ShadowIntegrityError("live shadow collection is missing")
        records, schema = export_collection(client.collections.get(SHADOW_COLLECTION))
        verification = verify_shadow_records(corpus, records)
        verification.pop("ordered_records")
        if not verification["passed"]:
            raise ShadowIntegrityError("live shadow no longer matches the processed corpus")
        live_fingerprint = {
            "objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])),
            "schema_sha256": digest(schema),
        }
        if live_fingerprint != shadow_manifest["collection_fingerprint"]:
            raise ShadowIntegrityError("live shadow fingerprint changed after preflight")
        production_live = production_state(client)
        if production_live != shadow_integrity["production_state_after"]:
            raise ShadowIntegrityError("production membership changed after shadow preflight")
        production_bm25 = PROJECT_ROOT / "bm25_index.pkl"
        current_bm25 = file_digest(production_bm25) if production_bm25.is_file() else None
        if shadow_integrity["production_bm25_unchanged"] is not True:
            raise ShadowIntegrityError("shadow preflight did not preserve production BM25")
        # The build recorded equality before/after. Rechecking its exact value here
        # catches any change between preflight and freeze.
        before_path = shadow_integrity.get("production_bm25_sha256")
        if before_path is not None and current_bm25 != before_path:
            raise ShadowIntegrityError("production BM25 changed after shadow preflight")
    finally:
        if own_client:
            client.close()

    snapshot_manifest, receipt = make_snapshot_documents(
        shadow_dir,
        shadow_manifest,
        shadow_integrity,
        live_fingerprint,
        production_live,
    )
    write_json(snapshot_manifest_path, snapshot_manifest)
    receipt["snapshot_manifest"]["path"] = str(
        display_path(snapshot_manifest_path)
    )
    receipt["snapshot_manifest"]["sha256"] = file_digest(snapshot_manifest_path)
    write_json(receipt_path, receipt)
    return snapshot_manifest, receipt


def verify_frozen_snapshot(
    snapshot_manifest_path: Path = DEFAULT_SNAPSHOT_MANIFEST,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> dict:
    snapshot = read_json(snapshot_manifest_path)
    receipt = read_json(receipt_path)
    if snapshot.get("frozen") is not True or receipt.get("gate_passed") is not True:
        raise ShadowIntegrityError("current-law snapshot is not frozen")
    if receipt["snapshot_manifest"]["sha256"] != file_digest(snapshot_manifest_path):
        raise ShadowIntegrityError("frozen snapshot manifest changed")
    if snapshot["processed_corpus"]["sha256"] != file_digest(DEFAULT_CORPUS):
        raise ShadowIntegrityError("processed corpus changed after freeze")
    if snapshot["processed_corpus"]["manifest_sha256"] != file_digest(DEFAULT_CORPUS_MANIFEST):
        raise ShadowIntegrityError("processed corpus manifest changed after freeze")
    if snapshot["freezer"]["sha256"] != file_digest(Path(__file__).resolve()):
        raise ShadowIntegrityError("snapshot freezer code changed after freeze")
    processed_builder = PROJECT_ROOT / snapshot["processed_corpus"]["builder"]["path"]
    if snapshot["processed_corpus"]["builder"]["sha256"] != file_digest(processed_builder):
        raise ShadowIntegrityError("processed corpus builder changed after freeze")
    shadow_builder = PROJECT_ROOT / snapshot["shadow_resources"]["builder"]["path"]
    if snapshot["shadow_resources"]["builder"]["sha256"] != file_digest(shadow_builder):
        raise ShadowIntegrityError("shadow index builder changed after freeze")
    production_bm25 = PROJECT_ROOT / "bm25_index.pkl"
    current_production_bm25 = (
        file_digest(production_bm25) if production_bm25.is_file() else None
    )
    if snapshot["production"]["root_bm25_sha256"] != current_production_bm25:
        raise ShadowIntegrityError("production BM25 changed after freeze")
    shadow_manifest = Path(receipt["shadow_bundle"]["path"])
    if not shadow_manifest.is_absolute():
        shadow_manifest = PROJECT_ROOT / shadow_manifest
    shadow_manifest = shadow_manifest / "manifest.json"
    if (
        not shadow_manifest.is_file()
        or receipt["shadow_bundle"]["manifest_sha256"] != file_digest(shadow_manifest)
    ):
        raise ShadowIntegrityError("shadow replay bundle is missing or changed")
    if receipt.get("benchmark_audit_or_c0_c4_run") is not False:
        raise ShadowIntegrityError("freeze receipt contains an invalid benchmark claim")
    if not all(snapshot["gates"].values()):
        raise ShadowIntegrityError("a frozen gate is not true")
    return {"passed": True, "snapshot_id": snapshot["snapshot_id"], "frozen": True}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-dir", type=Path, default=DEFAULT_SHADOW_DIR)
    parser.add_argument("--snapshot-manifest", type=Path, default=DEFAULT_SNAPSHOT_MANIFEST)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--grpc-port", type=int, default=50051)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            result = verify_frozen_snapshot(args.snapshot_manifest, args.receipt)
        else:
            snapshot, _ = freeze_current_law_snapshot(
                args.shadow_dir,
                args.snapshot_manifest,
                args.receipt,
                host=args.host,
                port=args.port,
                grpc_port=args.grpc_port,
            )
            result = {
                "passed": True,
                "snapshot_id": snapshot["snapshot_id"],
                "frozen": snapshot["frozen"],
            }
    except Exception as exc:
        print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
