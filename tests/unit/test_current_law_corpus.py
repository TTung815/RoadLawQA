"""Regression tests for deterministic current-law processed chunks."""

from collections import Counter
from pathlib import Path

from ingestion.current_law_corpus import (
    CORPUS_ID,
    EFFECTIVE_DOCUMENT_ID,
    LEGAL_AS_OF,
    build_current_law_corpus,
)


def chunks_by_id(corpus: dict) -> dict[str, dict]:
    return {chunk["id"]: chunk for chunk in corpus["chunks"]}


def test_current_law_corpus_is_deterministic_and_complete():
    first, first_manifest = build_current_law_corpus()
    second, second_manifest = build_current_law_corpus()

    assert first == second
    assert first_manifest == second_manifest
    assert first["corpus_id"] == CORPUS_ID
    assert first["legal_as_of"] == LEGAL_AS_OF
    assert first["validation"]["passed"]
    assert len(first["chunks"]) == 2531
    assert [chunk["ordinal"] for chunk in first["chunks"]] == list(range(2531))
    assert len({chunk["id"] for chunk in first["chunks"]}) == 2531
    assert Counter(chunk["document_id"] for chunk in first["chunks"]) == {
        "49-vbhn-vpqh": 673,
        "55-vbhn-vpqh": 797,
        EFFECTIVE_DOCUMENT_ID: 1061,
    }
    assert first_manifest["frozen"] is False
    assert first_manifest["production_collection_touched"] is False
    assert first_manifest["production_bm25_touched"] is False
    assert all(
        report["article_coverage_passed"] and report["locator_coverage_passed"]
        for report in first["documents"]
    )
    assert not any(
        line.startswith(("Chương ", "Mục "))
        for chunk in first["chunks"]
        for line in chunk["text"].splitlines()
    )
    assert chunks_by_id(first)["49-vbhn-vpqh-d2"]["text"].startswith(
        "Trong Luật này"
    )


def test_temporal_publication_blocks_propagate_to_leaf_chunks():
    corpus, _ = build_current_law_corpus()
    blocked = [chunk for chunk in corpus["chunks"] if not chunk["publication_eligible"]]
    assert len(blocked) == 10
    assert Counter(chunk["temporal_status"] for chunk in blocked) == {
        "mixed_effective_date": 4,
        "future": 3,
        "repealed": 3,
    }

    decree = {
        (chunk["article_no"], chunk["clause_no"], chunk["point"]): chunk
        for chunk in blocked
        if chunk["document_id"] == EFFECTIVE_DOCUMENT_ID
    }
    assert set(decree) == {
        ("20", "5", "l"),
        ("20", "5", "n"),
        ("21", "3", "b"),
        ("26", "7", "k"),
        ("26", "7", "l"),
        ("32", "9a", "b"),
    }
    assert all(chunk["source_spans"] for chunk in decree.values())
    assert all(not chunk["is_official_consolidated_document"] for chunk in decree.values())

    law_55 = next(chunk for chunk in blocked if chunk["document_id"] == "55-vbhn-vpqh")
    assert (law_55["article_no"], law_55["clause_no"], law_55["point"]) == (
        "35",
        "2",
        None,
    )
    assert law_55["active_at_cutoff"] is None
    assert [rule["effective_from"] for rule in law_55["temporal_rules"]] == [
        "2026-07-01",
        "2028-01-01",
        "2029-01-01",
    ]
    repealed = [chunk for chunk in blocked if chunk["temporal_status"] == "repealed"]
    assert {
        (chunk["document_id"], chunk["article_no"], chunk["clause_no"])
        for chunk in repealed
    } == {
        ("49-vbhn-vpqh", "10", "4"),
        ("49-vbhn-vpqh", "83", None),
        ("55-vbhn-vpqh", "62", "7"),
    }
    assert all(chunk["active_at_cutoff"] is False for chunk in repealed)
    assert all(chunk["effective_to"] == "2026-06-30" for chunk in repealed)


def test_canonical_laws_keep_lineage_and_footnote_provenance_without_body_pollution():
    corpus, _ = build_current_law_corpus()
    chunks = corpus["chunks"]
    modified = next(
        chunk
        for chunk in chunks
        if chunk["document_id"] == "49-vbhn-vpqh"
        and chunk["article_no"] == "8"
    )
    assert modified["display_citation"].endswith("49/VBHN-VPQH")
    assert modified["source_document_ids"] == [
        "49-vbhn-vpqh",
        "35-2024-qh15",
        "118-2025-qh15",
    ]
    assert modified["lineage_document_ids"] == ["35-2024-qh15", "118-2025-qh15"]
    assert modified["amending_document_ids"] == ["118-2025-qh15"]
    assert modified["source_footnote_ids"]
    assert "Khoản này được sửa đổi" not in modified["text"]

    reports = {item["document_id"]: item for item in corpus["documents"]}
    assert reports["49-vbhn-vpqh"]["footnote_mapping"]["passed"]
    assert reports["55-vbhn-vpqh"]["footnote_mapping"]["passed"]
    assert reports["49-vbhn-vpqh"]["footnote_mapping"]["matched_reference_count"] == 41
    assert reports["55-vbhn-vpqh"]["footnote_mapping"]["matched_reference_count"] == 47


def test_effective_amendment_provenance_reaches_indexable_chunk():
    corpus, _ = build_current_law_corpus()
    chunk = chunks_by_id(corpus)[f"{EFFECTIVE_DOCUMENT_ID}-d20-k6-pd"]
    assert chunk["operation_ids"] == ["a19-p06-nd168-d20-k6-d"]
    assert chunk["source_document_ids"] == ["168-2024-nd-cp", "238-2026-nd-cp"]
    assert chunk["amending_document_ids"] == ["238-2026-nd-cp"]
    assert "được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP" in chunk[
        "display_citation"
    ]
    spans = {span["document_id"] for span in chunk["source_spans"]}
    assert spans == {"168-2024-nd-cp", "238-2026-nd-cp"}
    for span in chunk["source_spans"]:
        lines = Path(span["path"]).read_text(encoding="utf-8").splitlines()
        selected = "\n".join(lines[span["line_start"] - 1 : span["line_end"]])
        assert selected.strip()
    base_span = next(
        span for span in chunk["source_spans"] if span["document_id"] == "168-2024-nd-cp"
    )
    base_line = Path(base_span["path"]).read_text(encoding="utf-8").splitlines()[
        base_span["line_start"] - 1
    ]
    assert base_line.startswith("d)")
