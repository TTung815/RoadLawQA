"""Build and verify isolated Weaviate/BM25 resources for the current-law corpus.

The only collection this module may create is ``LawChunksCurrentLaw20260922``.
It never deletes or updates a collection and never writes ``bm25_index.pkl`` in
the repository root.  An existing shadow collection is accepted only when its
complete membership, properties, vectors and schema pass the same verification.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import math
import pickle
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from ingestion.current_law_corpus import (
    CORPUS_ID,
    DEFAULT_MANIFEST as DEFAULT_CORPUS_MANIFEST,
    DEFAULT_OUTPUT as DEFAULT_CORPUS,
    LEGAL_AS_OF,
    validate_corpus,
)
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json, write_json
from evaluation.legacy_probe import SEARCH_FIELDS, audit_bm25, build_bm25, load_bm25
from evaluation.snapshot import canonical_bytes, digest, redact_schema


SHADOW_COLLECTION = "LawChunksCurrentLaw20260922"
PRODUCTION_COLLECTION = "LawChunks"
EMBEDDING_MODEL = "Alibaba-NLP/gte-multilingual-base"
VECTOR_DIMENSIONS = 768
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs/current-law-shadow-2026-09-22"
PROPERTY_TYPES = {
    "chunk_id": "text",
    "ordinal": "int",
    "corpus_id": "text",
    "granularity": "text",
    "law": "text",
    "law_code": "text",
    "chapter": "text",
    "section": "text",
    "article_no": "text",
    "article_title": "text",
    "clause_no": "text",
    "point": "text",
    "bullet_idx": "int",
    "header": "text",
    "display_citation": "text",
    "path_text": "text",
    "clause_head": "text",
    "text": "text",
    "enriched_text": "text",
    "source_file": "text",
    "source_path": "text",
    "document_id": "text",
    "artifact_kind": "text",
    "is_official_consolidated_document": "boolean",
    "legal_as_of": "text",
    "effective_from": "text",
    "effective_to": "text",
    "active_at_cutoff": "boolean",
    "temporal_status": "text",
    "publication_eligible": "boolean",
    "temporal_rules_json": "text",
    "source_locator": "text",
    "source_document_ids": "text[]",
    "lineage_document_ids": "text[]",
    "amending_document_ids": "text[]",
    "operation_ids": "text[]",
    "source_amendment_articles": "int[]",
    "source_footnote_ids": "int[]",
    "source_spans_json": "text",
    "source_text_sha256": "text",
    "content_sha256": "text",
}


class ShadowIntegrityError(ValueError):
    """The shadow resource cannot authorize a frozen current-law snapshot."""


def deterministic_uuid(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"roadlawqa:{CORPUS_ID}:{chunk_id}"))


def index_properties(chunk: Mapping[str, Any]) -> dict[str, Any]:
    properties = {
        key: chunk.get(key)
        for key in PROPERTY_TYPES
        if key not in {"chunk_id", "temporal_rules_json", "source_spans_json"}
    }
    properties["chunk_id"] = chunk["id"]
    properties["temporal_rules_json"] = json.dumps(
        chunk["temporal_rules"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    properties["source_spans_json"] = json.dumps(
        chunk["source_spans"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return properties


def load_validated_corpus(
    corpus_path: Path = DEFAULT_CORPUS,
    manifest_path: Path = DEFAULT_CORPUS_MANIFEST,
) -> tuple[dict, dict]:
    corpus = read_json(corpus_path)
    manifest = read_json(manifest_path)
    if corpus.get("corpus_id") != CORPUS_ID or corpus.get("legal_as_of") != LEGAL_AS_OF:
        raise ShadowIntegrityError("processed corpus identity/cutoff mismatch")
    validation = validate_corpus(corpus)
    if not validation["passed"] or corpus.get("validation") != validation:
        raise ShadowIntegrityError("processed corpus validation is stale or failed")
    if manifest.get("frozen") is not False or manifest.get("status") != "processed_corpus_validated_shadow_index_pending":
        raise ShadowIntegrityError("processed manifest has an invalid pre-freeze state")
    if manifest["output"]["path"] != str(corpus_path.relative_to(PROJECT_ROOT)):
        raise ShadowIntegrityError("processed manifest points to another corpus")
    if manifest["output"]["sha256"] != file_digest(corpus_path):
        raise ShadowIntegrityError("processed corpus checksum mismatch")
    return corpus, manifest


def collection_schema_properties():
    from weaviate.classes.config import DataType, Property

    data_types = {
        "text": DataType.TEXT,
        "int": DataType.INT,
        "boolean": DataType.BOOL,
        "text[]": DataType.TEXT_ARRAY,
        "int[]": DataType.INT_ARRAY,
    }
    non_searchable = {
        "chunk_id",
        "corpus_id",
        "granularity",
        "law_code",
        "chapter",
        "section",
        "bullet_idx",
        "header",
        "display_citation",
        "path_text",
        "enriched_text",
        "source_file",
        "source_path",
        "document_id",
        "artifact_kind",
        "is_official_consolidated_document",
        "legal_as_of",
        "effective_from",
        "effective_to",
        "active_at_cutoff",
        "temporal_status",
        "publication_eligible",
        "temporal_rules_json",
        "source_locator",
        "source_document_ids",
        "lineage_document_ids",
        "amending_document_ids",
        "operation_ids",
        "source_amendment_articles",
        "source_footnote_ids",
        "source_spans_json",
        "source_text_sha256",
        "content_sha256",
        "ordinal",
    }
    return [
        Property(
            name=name,
            data_type=data_types[data_type],
            skip_vectorization=True,
            index_searchable=(
                False if data_type == "text" and name in non_searchable else None
            ),
        )
        for name, data_type in PROPERTY_TYPES.items()
    ]


def create_shadow_collection(client: Any):
    from weaviate.classes.config import Configure, VectorDistances

    if SHADOW_COLLECTION == PRODUCTION_COLLECTION:
        raise ShadowIntegrityError("shadow and production collection names collide")
    if client.collections.exists(SHADOW_COLLECTION):
        return client.collections.get(SHADOW_COLLECTION), False
    client.collections.create(
        name=SHADOW_COLLECTION,
        description=(
            "RoadLawQA isolated current-law shadow collection as of 2026-09-22; "
            "not authorized for production."
        ),
        vectorizer_config=Configure.Vectorizer.none(),
        properties=collection_schema_properties(),
        vector_index_config=Configure.VectorIndex.hnsw(
            distance_metric=VectorDistances.COSINE,
            ef_construction=128,
            max_connections=64,
        ),
    )
    return client.collections.get(SHADOW_COLLECTION), True


def production_state(client: Any) -> dict:
    """Read a small immutable membership fingerprint; never fetch production vectors."""
    if not client.collections.exists(PRODUCTION_COLLECTION):
        return {"exists": False, "collection": PRODUCTION_COLLECTION}
    collection = client.collections.get(PRODUCTION_COLLECTION)
    before = collection.aggregate.over_all(total_count=True).total_count
    uuids = []
    after = None
    while True:
        kwargs = {"limit": 200, "return_properties": []}
        if after is not None:
            kwargs["after"] = after
        objects = collection.query.fetch_objects(**kwargs).objects
        uuids.extend(str(item.uuid) for item in objects)
        if len(objects) < 200:
            break
        after = objects[-1].uuid
    final = collection.aggregate.over_all(total_count=True).total_count
    if before != final or len(uuids) != final:
        raise ShadowIntegrityError("production membership changed while fingerprinting")
    schema = redact_schema(collection.config.get().to_dict())
    return {
        "exists": True,
        "collection": PRODUCTION_COLLECTION,
        "count": final,
        "uuid_membership_sha256": digest(sorted(uuids)),
        "schema_sha256": digest(schema),
    }


def export_collection(collection: Any) -> tuple[list[dict], dict]:
    before = collection.aggregate.over_all(total_count=True).total_count
    schema = redact_schema(collection.config.get().to_dict())
    records = []
    seen = set()
    after = None
    while True:
        kwargs = {"limit": 200, "include_vector": True}
        if after is not None:
            kwargs["after"] = after
        objects = collection.query.fetch_objects(**kwargs).objects
        for item in objects:
            item_uuid = str(item.uuid)
            if item_uuid in seen:
                raise ShadowIntegrityError("shadow pagination returned duplicate UUID")
            seen.add(item_uuid)
            records.append(
                {
                    "uuid": item_uuid,
                    "properties": item.properties,
                    "vectors": item.vector,
                }
            )
        if len(objects) < 200:
            break
        after = objects[-1].uuid
    count = collection.aggregate.over_all(total_count=True).total_count
    if before != count or len(records) != count:
        raise ShadowIntegrityError("shadow collection changed or export omitted objects")
    return records, schema


def vector_values(record: Mapping[str, Any]) -> list[float] | None:
    vectors = record.get("vectors")
    if isinstance(vectors, list):
        return vectors
    if isinstance(vectors, dict) and vectors:
        value = next(iter(vectors.values()))
        return value if isinstance(value, list) else None
    return None


def verify_shadow_records(corpus: dict, records: Sequence[Mapping[str, Any]]) -> dict:
    chunks = corpus["chunks"]
    expected_by_id = {chunk["id"]: index_properties(chunk) for chunk in chunks}
    actual_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_ids = []
    invalid_vectors = []
    invalid_uuids = []
    for record in records:
        properties = record["properties"]
        chunk_id = properties.get("chunk_id")
        if chunk_id in actual_by_id:
            duplicate_ids.append(chunk_id)
        actual_by_id[chunk_id] = properties
        if chunk_id and record["uuid"] != deterministic_uuid(chunk_id):
            invalid_uuids.append(record["uuid"])
        vector = vector_values(record)
        if (
            vector is None
            or len(vector) != VECTOR_DIMENSIONS
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in vector
            )
        ):
            invalid_vectors.append(record["uuid"])
    missing = sorted(set(expected_by_id) - set(actual_by_id))
    unexpected = sorted(set(actual_by_id) - set(expected_by_id))
    property_mismatches = sorted(
        chunk_id
        for chunk_id in set(expected_by_id) & set(actual_by_id)
        if digest(expected_by_id[chunk_id]) != digest(actual_by_id[chunk_id])
    )
    ordered = sorted(records, key=lambda record: record["properties"].get("ordinal", -1))
    ordinals = [record["properties"].get("ordinal") for record in ordered]
    checks = {
        "count_matches": len(records) == len(chunks),
        "membership_matches": not missing and not unexpected,
        "properties_match": not property_mismatches,
        "deterministic_uuids": not invalid_uuids,
        "vectors_valid": not invalid_vectors and bool(records),
        "unique_ids": not duplicate_ids and None not in actual_by_id,
        "ordinal_order_complete": ordinals == list(range(len(chunks))),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "processed_count": len(chunks),
        "indexed_count": len(records),
        "missing_ids": missing[:50],
        "unexpected_ids": unexpected[:50],
        "property_mismatch_ids": property_mismatches[:50],
        "duplicate_ids": duplicate_ids[:50],
        "invalid_uuid_count": len(invalid_uuids),
        "invalid_vector_count": len(invalid_vectors),
        "ordered_records": ordered,
    }


def insert_chunks(collection: Any, chunks: Sequence[Mapping[str, Any]], embedder: Any) -> None:
    from weaviate.classes.data import DataObject

    batch_size = 32
    for start in range(0, len(chunks), batch_size):
        batch_chunks = chunks[start : start + batch_size]
        texts = [chunk["enriched_text"] for chunk in batch_chunks]
        vectors = embedder.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        objects = [
            DataObject(
                uuid=deterministic_uuid(chunk["id"]),
                properties=index_properties(chunk),
                vector=vector.astype("float32").tolist(),
            )
            for chunk, vector in zip(batch_chunks, vectors, strict=True)
        ]
        result = collection.data.insert_many(objects)
        if getattr(result, "has_errors", False):
            raise ShadowIntegrityError("Weaviate reported errors while inserting shadow chunks")


def load_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        EMBEDDING_MODEL,
        device="cpu",
        trust_remote_code=True,
        local_files_only=True,
    )


def model_provenance(embedder: Any) -> dict:
    model = embedder[0].auto_model
    revision = getattr(model.config, "_commit_hash", None)
    return {
        "model": EMBEDDING_MODEL,
        "revision": revision,
        "dimensions": int(embedder.get_sentence_embedding_dimension()),
        "normalize_embeddings": True,
        "device": str(embedder.device),
        "loaded": True,
    }


def connect_local(host: str, port: int, grpc_port: int):
    import weaviate

    return weaviate.connect_to_local(
        host=host,
        port=port,
        grpc_port=grpc_port,
        skip_init_checks=False,
    )


def build_shadow_resources(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    host: str = "localhost",
    port: int = 8080,
    grpc_port: int = 50051,
    client: Any | None = None,
    embedder: Any | None = None,
) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"shadow output already exists: {output_dir}")
    corpus, corpus_manifest = load_validated_corpus()
    production_bm25 = PROJECT_ROOT / "bm25_index.pkl"
    production_bm25_before = file_digest(production_bm25) if production_bm25.is_file() else None
    own_client = client is None
    if client is None:
        client = connect_local(host, port, grpc_port)
    created = False
    loaded_embedder = embedder
    try:
        production_before = production_state(client)
        collection, created = create_shadow_collection(client)
        existing_count = collection.aggregate.over_all(total_count=True).total_count
        if created:
            if existing_count:
                raise ShadowIntegrityError("new shadow collection is unexpectedly non-empty")
            loaded_embedder = loaded_embedder or load_embedder()
            provenance = model_provenance(loaded_embedder)
            if provenance["dimensions"] != VECTOR_DIMENSIONS or not provenance["revision"]:
                raise ShadowIntegrityError("embedding model dimensions/revision are not pinned")
            insert_chunks(collection, corpus["chunks"], loaded_embedder)
        else:
            loaded_embedder = loaded_embedder or load_embedder()
            provenance = model_provenance(loaded_embedder)
            if provenance["dimensions"] != VECTOR_DIMENSIONS or not provenance["revision"]:
                raise ShadowIntegrityError("embedding model dimensions/revision are not pinned")
        records, schema = export_collection(collection)
        verification = verify_shadow_records(corpus, records)
        if not verification["passed"]:
            raise ShadowIntegrityError(
                f"shadow verification failed: {verification['checks']}"
            )
        ordered = verification.pop("ordered_records")
        runtime_order = [
            {key: record["properties"].get(key) for key in SEARCH_FIELDS}
            for record in ordered
        ]
        bm25 = build_bm25(runtime_order)
        bm25_audit = audit_bm25(bm25, build_bm25(runtime_order))
        production_after = production_state(client)
        production_bm25_after = (
            file_digest(production_bm25) if production_bm25.is_file() else None
        )
        production_unchanged = production_before == production_after
        production_bm25_unchanged = production_bm25_before == production_bm25_after
        gate_passed = bool(
            verification["passed"]
            and bm25_audit["passed"]
            and production_unchanged
            and production_bm25_unchanged
        )

        if not gate_passed:
            raise ShadowIntegrityError("shadow integrity gate did not pass")
        output_dir.mkdir(parents=True, exist_ok=False)
        bm25_path = output_dir / "bm25_index.pkl"
        with bm25_path.open("wb") as stream:
            pickle.dump(bm25, stream)

        with gzip.open(output_dir / "indexed.json.gz", "wb") as stream:
            stream.write(canonical_bytes(records))
        write_json(output_dir / "schema.json", schema)
        write_json(output_dir / "runtime_order.json", runtime_order)
        write_json(output_dir / "processed_manifest.json", corpus_manifest)
        integrity = {
            "gate_passed": gate_passed,
            "collection_created": created,
            "collection": SHADOW_COLLECTION,
            "resource": {"host": host, "port": port, "grpc_port": grpc_port},
            "verification": verification,
            "bm25": bm25_audit,
            "bm25_order_basis": "explicit_processed_ordinal_verified_against_shadow_membership",
            "production_collection_unchanged": production_unchanged,
            "production_bm25_unchanged": production_bm25_unchanged,
            "production_bm25_sha256": production_bm25_after,
            "production_state_before": production_before,
            "production_state_after": production_after,
        }
        write_json(output_dir / "integrity.json", integrity)
        artifacts = {
            path.name: file_digest(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "manifest.json"
        }
        manifest = {
            "format_version": 1,
            "snapshot_id": CORPUS_ID,
            "legal_as_of": LEGAL_AS_OF,
            "gate_passed": gate_passed,
            "frozen": False,
            "collection": SHADOW_COLLECTION,
            "collection_created": created,
            "collection_fingerprint": {
                "objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])),
                "schema_sha256": digest(schema),
            },
            "runtime_order_sha256": digest(runtime_order),
            "bm25_sha256": file_digest(bm25_path),
            "corpus_sha256": file_digest(DEFAULT_CORPUS),
            "corpus_manifest_sha256": file_digest(DEFAULT_CORPUS_MANIFEST),
            "embedding": provenance,
            "builder": {
                "path": str(Path(__file__).resolve().relative_to(PROJECT_ROOT)),
                "sha256": file_digest(Path(__file__).resolve()),
            },
            "packages": {
                name: importlib.metadata.version(name)
                for name in (
                    "weaviate-client",
                    "sentence-transformers",
                    "torch",
                    "transformers",
                    "pyvi",
                    "rank-bm25",
                    "numpy",
                )
            },
            "production_collection": PRODUCTION_COLLECTION,
            "production_collection_unchanged": production_unchanged,
            "production_bm25_unchanged": production_bm25_unchanged,
            "artifacts": artifacts,
        }
        write_json(output_dir / "manifest.json", manifest)
        return manifest
    finally:
        if own_client:
            client.close()


def verify_shadow_bundle(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    manifest = read_json(output_dir / "manifest.json")
    if manifest.get("gate_passed") is not True or manifest.get("collection") != SHADOW_COLLECTION:
        raise ShadowIntegrityError("shadow bundle is not trusted")
    required = {
        "bm25_index.pkl",
        "indexed.json.gz",
        "integrity.json",
        "processed_manifest.json",
        "runtime_order.json",
        "schema.json",
    }
    if set(manifest.get("artifacts", {})) != required:
        raise ShadowIntegrityError("shadow bundle artifact inventory is incomplete")
    for name, expected in manifest["artifacts"].items():
        path = output_dir / name
        if not path.is_file() or file_digest(path) != expected:
            raise ShadowIntegrityError(f"shadow artifact changed: {name}")
    if manifest["corpus_sha256"] != file_digest(DEFAULT_CORPUS):
        raise ShadowIntegrityError("processed corpus changed after shadow build")
    if manifest["corpus_manifest_sha256"] != file_digest(DEFAULT_CORPUS_MANIFEST):
        raise ShadowIntegrityError("processed manifest changed after shadow build")
    rows = read_json(output_dir / "runtime_order.json")
    if digest(rows) != manifest["runtime_order_sha256"]:
        raise ShadowIntegrityError("runtime order checksum mismatch")
    if not audit_bm25(load_bm25(output_dir / "bm25_index.pkl"), build_bm25(rows))["passed"]:
        raise ShadowIntegrityError("BM25 no longer matches frozen runtime order")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--grpc-port", type=int, default=50051)
    parser.add_argument("--verify-bundle", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = (
            verify_shadow_bundle(args.output_dir)
            if args.verify_bundle
            else build_shadow_resources(
                args.output_dir,
                host=args.host,
                port=args.port,
                grpc_port=args.grpc_port,
            )
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "gate_passed": False,
                    "collection": SHADOW_COLLECTION,
                    "error_type": type(exc).__name__,
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "gate_passed": manifest["gate_passed"],
                "collection": manifest["collection"],
                "frozen": manifest["frozen"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
