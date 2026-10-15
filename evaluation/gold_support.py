"""Shared helpers for gold evidence: frozen-corpus context, references and facet coverage."""

from __future__ import annotations

import gzip
import hashlib
import json
from typing import Sequence

from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST, verify_frozen_snapshot
from evaluation.snapshot import digest
from ingestion.current_law_corpus import DEFAULT_OUTPUT
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json
from ingestion.shadow_index import (
    DEFAULT_OUTPUT_DIR, deterministic_uuid, verify_shadow_bundle, verify_shadow_records,
)

__all__ = ["DEFAULT_OUTPUT", "artifact_bytes", "evidence_reference", "load_snapshot_context", "missing_facets"]


def load_snapshot_context() -> tuple[dict, dict[str, dict]]:
    """Frozen snapshot plus its leaf chunks, after verifying sources and the shadow replay."""
    verify_frozen_snapshot()
    manifest = verify_shadow_bundle()
    snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
    for item in snapshot["processed_corpus"]["inputs"].values():
        if file_digest(PROJECT_ROOT / item["path"]) != item["sha256"]:
            raise ValueError("frozen source input changed")
    registry = read_json(PROJECT_ROOT / "data/legal_sources/registry.json")
    for document in registry["documents"]:
        if document["document_id"] not in {"49-vbhn-vpqh", "55-vbhn-vpqh", "168-2024-nd-cp", "238-2026-nd-cp"}:
            continue
        for artifact in (document["source"], document["extraction"]):
            path = artifact.get("raw_path", artifact.get("path"))
            if file_digest(PROJECT_ROOT / path) != artifact["sha256"]:
                raise ValueError("registered legal source artifact changed")
    corpus = read_json(DEFAULT_OUTPUT)
    with gzip.open(DEFAULT_OUTPUT_DIR / "indexed.json.gz", "rt", encoding="utf-8") as stream:
        records = json.load(stream)
    if not verify_shadow_records(corpus, records)["passed"]:
        raise ValueError("shadow replay membership does not match current-law corpus")
    fingerprint = {
        "objects_sha256": digest(sorted(records, key=lambda row: row["uuid"])),
        "schema_sha256": digest(read_json(DEFAULT_OUTPUT_DIR / "schema.json")),
    }
    if fingerprint != snapshot["shadow_resources"]["collection_fingerprint"]:
        raise ValueError("shadow replay fingerprint differs from frozen snapshot")
    if fingerprint != manifest["collection_fingerprint"]:
        raise ValueError("shadow manifest fingerprint differs from replay")
    return snapshot, {chunk["id"]: chunk for chunk in corpus["chunks"]}


def evidence_reference(chunk: dict, role: str) -> dict:
    # Runtime ID is the stable shadow chunk_id, not a legacy serving adapter hash.
    return {
        "processed_id": chunk["id"], "runtime_id": chunk["id"],
        "uuid": deterministic_uuid(chunk["id"]),
        "citation": chunk["display_citation"], "law": chunk["law"],
        "article": chunk["article_no"], "clause": chunk["clause_no"],
        "point": chunk["point"],
        "text_sha256": hashlib.sha256(chunk["text"].encode()).hexdigest(),
        "role": role,
    }


def artifact_bytes(value: object) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def missing_facets(case, pool: Sequence[str]) -> list[str]:
    """Required facets whose gold evidence groups are not covered by the given leaf IDs."""
    groups = {group.id: group for group in case.gold.evidence_groups}
    available = set(pool)
    missing = []
    for facet in case.gold.required_facets:
        if not facet.required:
            continue
        covered = False
        for identity in facet.evidence_group_ids:
            group = groups[identity]
            supports = [ref.processed_id for ref in group.references if ref.role == "support"]
            if len(supports) != len(group.references):
                continue
            matches = [identity in available for identity in supports]
            covered |= bool(matches) and (all(matches) if group.match == "all" else any(matches))
        if facet.support_state != "positive_support" or not covered:
            missing.append(facet.id)
    return missing
