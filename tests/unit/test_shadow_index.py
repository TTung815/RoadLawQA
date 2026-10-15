"""Offline checks for shadow-index identity, metadata and ordering gates."""

import copy

from ingestion.current_law_corpus import build_current_law_corpus
from ingestion.shadow_index import (
    PRODUCTION_COLLECTION,
    SHADOW_COLLECTION,
    VECTOR_DIMENSIONS,
    deterministic_uuid,
    index_properties,
    verify_shadow_records,
)


def indexed_record(chunk: dict) -> dict:
    return {
        "uuid": deterministic_uuid(chunk["id"]),
        "properties": index_properties(chunk),
        "vectors": {"default": [0.01] * VECTOR_DIMENSIONS},
    }


def test_shadow_name_and_uuid_are_isolated_and_stable():
    assert SHADOW_COLLECTION == "LawChunksCurrentLaw20260922"
    assert SHADOW_COLLECTION != PRODUCTION_COLLECTION
    assert deterministic_uuid("chunk-a") == deterministic_uuid("chunk-a")
    assert deterministic_uuid("chunk-a") != deterministic_uuid("chunk-b")


def test_index_projection_preserves_legal_and_temporal_metadata():
    corpus, _ = build_current_law_corpus()
    chunk = next(item for item in corpus["chunks"] if not item["publication_eligible"])
    properties = index_properties(chunk)
    assert properties["chunk_id"] == chunk["id"]
    assert properties["legal_as_of"] == "2026-09-22"
    assert properties["publication_eligible"] is False
    assert properties["temporal_status"] in {
        "future",
        "mixed_effective_date",
        "repealed",
    }
    assert properties["source_document_ids"] == chunk["source_document_ids"]
    assert "effective_from" in properties["temporal_rules_json"]
    assert "document_id" in properties["source_spans_json"]


def test_shadow_verification_requires_exact_membership_properties_vectors_and_order():
    corpus, _ = build_current_law_corpus()
    subset = copy.deepcopy(corpus)
    subset["chunks"] = copy.deepcopy(corpus["chunks"][:3])
    for ordinal, chunk in enumerate(subset["chunks"]):
        chunk["ordinal"] = ordinal
    records = [indexed_record(chunk) for chunk in subset["chunks"]]
    result = verify_shadow_records(subset, list(reversed(records)))
    assert result["passed"]
    assert [
        record["properties"]["ordinal"] for record in result["ordered_records"]
    ] == [0, 1, 2]

    changed = copy.deepcopy(records)
    changed[0]["properties"]["text"] = "changed"
    assert not verify_shadow_records(subset, changed)["passed"]

    missing = copy.deepcopy(records[:-1])
    assert not verify_shadow_records(subset, missing)["passed"]

    invalid_vector = copy.deepcopy(records)
    invalid_vector[0]["vectors"]["default"] = [0.1]
    assert not verify_shadow_records(subset, invalid_vector)["passed"]

    wrong_uuid = copy.deepcopy(records)
    wrong_uuid[0]["uuid"] = deterministic_uuid("another-id")
    assert not verify_shadow_records(subset, wrong_uuid)["passed"]
