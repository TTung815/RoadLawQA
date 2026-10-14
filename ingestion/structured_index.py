"""Build a new native-hybrid collection, without altering either existing collection."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import uuid

from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json
from ingestion.structured_corpus import BASE_BUNDLE, DEFAULT_BUNDLE, VERSION, load_bundle

COLLECTION = "LawStructured20260922V2"
DEFAULT_INDEX = PROJECT_ROOT / "outputs/structured-law-v2"
BASE_INDEX = PROJECT_ROOT / "outputs/structured-law-v1"


def object_id(identity: str, version: str = VERSION) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"roadlawqa:{version}:{identity}"))


def properties(unit: dict) -> dict:
    m = unit["metadata"]
    return {"chunk_id": unit["id"], "corpus_version": m["corpus_id"],
            "embedding_text": unit["embedding_text"], "lexical_text": unit["lexical_text"],
            "body": unit["text"], "document_id": m["document_id"], "article_no": m["article_no"],
            "clause_no": m["clause_no"] or "", "point": m["point"] or "",
            "publication_eligible": m["publication_eligible"], "active_at_cutoff": m["active_at_cutoff"],
            "legal_as_of": m["legal_as_of"], "metadata_json": json.dumps(m, ensure_ascii=False, sort_keys=True)}


def create_collection(client):
    from weaviate.classes.config import Configure, DataType, Property, Tokenization, VectorDistances, StopwordsPreset
    sample = properties(load_bundle()["chunks"][0])
    fields = [Property(name=name, data_type=DataType.BOOL if isinstance(value, bool) else DataType.TEXT,
                       index_searchable=name == "lexical_text", index_filterable=True,
                       **({"tokenization": Tokenization.WHITESPACE if name == "lexical_text" else Tokenization.FIELD}
                          if isinstance(value, str) else {}), skip_vectorization=True)
              for name, value in sample.items()]
    return client.collections.create(
        name=COLLECTION, properties=fields, vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE),
        inverted_index_config=Configure.inverted_index(bm25_k1=1.5, bm25_b=0.75,
                                                       stopwords_preset=StopwordsPreset.NONE))


def fingerprint(collection, units: list[dict]) -> dict:
    from ingestion.shadow_index import export_collection
    records, schema = export_collection(collection)
    expected = {object_id(u["id"], u["metadata"]["corpus_id"]): properties(u) for u in units}
    actual = {r["uuid"]: r["properties"] for r in records}
    if len(records) != len(units) or actual != expected:
        raise ValueError("structured index membership/properties mismatch")
    for row in records:
        vector = row["vectors"].get("default")
        if not vector or len(vector) != 768 or not all(math.isfinite(x) for x in vector):
            raise ValueError("invalid structured index vector")
    return {"objects_sha256": digest(sorted(records, key=lambda r: r["uuid"])), "schema_sha256": digest(schema)}


def verify_index(collection, directory: Path = DEFAULT_INDEX, bundle_dir: Path = DEFAULT_BUNDLE) -> dict:
    corpus = load_bundle(bundle_dir)
    receipt = read_json(directory / "index.json")
    if (receipt["collection"] != collection.name or receipt["version"] != corpus["version"]
            or receipt["corpus_sha256"] != file_digest(bundle_dir / "chunks.json")):
        raise ValueError("structured index is bound to a different corpus")
    if receipt["fingerprint"] != fingerprint(collection, corpus["chunks"]):
        raise ValueError("structured index changed after build")
    return receipt


def reusable_vectors(client, units: list[dict], embedding: dict) -> dict[str, list[float]]:
    """Reuse only vectors from a verified immutable index with identical model/text."""
    from ingestion.shadow_index import export_collection
    base_receipt = read_json(BASE_INDEX / "index.json")
    base = client.collections.get(base_receipt["collection"])
    verify_index(base, BASE_INDEX, BASE_BUNDLE)
    if base_receipt["embedding"] != embedding:
        raise ValueError("base embedding configuration differs; cannot reuse vectors")
    records, _ = export_collection(base)
    by_id = {r["properties"]["chunk_id"]: r for r in records}
    return {u["id"]: by_id[u["id"]]["vectors"]["default"] for u in units
            if u["id"] in by_id and by_id[u["id"]]["properties"]["embedding_text"] == u["embedding_text"]}


def build_index(host: str = "localhost", port: int = 8080, grpc_port: int = 50051) -> dict:
    from ingestion.shadow_index import connect_local, load_embedder, model_provenance, production_state
    from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST
    from weaviate.classes.data import DataObject
    corpus = load_bundle()
    manifest = read_json(DEFAULT_BUNDLE / "manifest.json")
    client = connect_local(host, port, grpc_port)
    try:
        old_state = production_state(client)
        snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
        if old_state != snapshot["production"]["state"]:
            raise ValueError("original collection differs from recorded state")
        # No delete/rebuild API: an existing new collection must have a valid receipt.
        if client.collections.exists(COLLECTION):
            return verify_index(client.collections.get(COLLECTION))
        if DEFAULT_INDEX.exists():
            raise FileExistsError("index output exists without the collection")
        embedder = load_embedder()
        provenance = model_provenance(embedder)
        if provenance["revision"] != manifest["embedding_revision"] or provenance["dimensions"] != 768:
            raise ValueError("embedding model does not match corpus tokenizer")
        units = corpus["chunks"]
        vectors_by_id = reusable_vectors(client, units, provenance)
        reused_count = len(vectors_by_id)
        missing = [u for u in units if u["id"] not in vectors_by_id]
        # Encode before creating the collection: model failures leave no partial index.
        for start in range(0, len(missing), 16):
            batch = missing[start:start + 16]
            vectors = embedder.encode([u["embedding_text"] for u in batch], normalize_embeddings=True,
                                      batch_size=4, show_progress_bar=False)
            vectors_by_id.update({u["id"]: v.tolist() for u, v in zip(batch, vectors, strict=True)})
        collection = create_collection(client)
        for start in range(0, len(units), 16):
            batch = units[start:start + 16]
            result = collection.data.insert_many([
                DataObject(uuid=object_id(u["id"], u["metadata"]["corpus_id"]), properties=properties(u),
                           vector=vectors_by_id[u["id"]]) for u in batch])
            if result.has_errors:
                raise ValueError("structured index insert failed; incomplete collection is not usable")
            print(f"Indexed {min(start + 16, len(units))}/{len(units)}", flush=True)
        receipt = {"version": VERSION, "collection": COLLECTION,
                   "corpus_sha256": file_digest(DEFAULT_BUNDLE / "chunks.json"), "embedding": provenance,
                   "fingerprint": fingerprint(collection, units), "chunks": len(units),
                   "reused_vectors": reused_count, "new_vectors": len(missing),
                   "base_index_sha256": file_digest(BASE_INDEX / "index.json"),
                   "original_collection_unchanged": production_state(client) == old_state}
        if not receipt["original_collection_unchanged"]:
            raise ValueError("original collection changed during build")
        DEFAULT_INDEX.mkdir(parents=True)
        (DEFAULT_INDEX / "index.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        return receipt
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--grpc-port", type=int, default=50051)
    args = parser.parse_args()
    print(json.dumps(build_index(args.host, args.port, args.grpc_port), indent=2))
