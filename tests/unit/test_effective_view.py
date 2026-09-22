"""Kiểm tra effective view kỹ thuật của Nghị định 168 + 238."""

import hashlib
import json

from ingestion.effective_view import (
    SOURCE_LINES,
    build_effective_view,
    clean_quoted_payload,
    parse_fragment,
    phrase_specs,
)
from ingestion.legal_registry import PROJECT_ROOT


def record_map(view: dict) -> dict[tuple, dict]:
    return {
        (record["article"], record["clause"], record["point"]): record
        for record in view["records"]
    }


def test_effective_view_applies_all_leaf_operations_deterministically():
    first, first_manifest = build_effective_view()
    second, second_manifest = build_effective_view()
    assert first == second
    assert first_manifest == second_manifest
    assert len(first["patch_ledger"]) == 102
    assert len({item["operation_id"] for item in first["patch_ledger"]}) == 102
    assert all(item["status"] == "applied" for item in first["patch_ledger"])
    assert all(item["source_lines"] for item in first["patch_ledger"])
    assert all(
        item["state_before_sha256"] != item["state_after_sha256"]
        for item in first["patch_ledger"]
    )
    assert first_manifest["summary"]["failed_operation_count"] == 0
    assert first_manifest["summary"]["effective_locator_count"] == 1308
    assert first_manifest["freeze_eligible"]


def test_effective_view_contains_known_repairs_repeals_and_provenance():
    view, manifest = build_effective_view()
    records = record_map(view)

    point_d = records[(20, "6", "d")]
    assert ", xe vận tải nội bộ" in point_d["text"]
    assert point_d["operation_ids"] == ["a19-p06-nd168-d20-k6-d"]

    point_a = records[(50, "3", "a")]
    assert "Chủ tịch Ủy ban nhân dân cấp xã" in point_a["text"]
    assert "Chủ tịch Ủy ban nhân dân cấp huyện" not in point_a["text"]

    article_55 = records[(55, None, None)]
    assert "trực thuộc trung ương" not in article_55["text"].casefold()
    assert article_55["operation_ids"] == ["a19-p16-nd168-d55"]

    assert all((32, "17", point) not in records for point in ("d", "đ", "e", "g"))
    assert "được sửa đổi, bổ sung" in point_d["citation"]
    assert "được sửa đổi, bổ sung" not in records[(1, "1", "a")]["citation"]
    assert manifest["summary"]["future_locator_count"] == 3
    assert manifest["summary"]["mixed_effective_date_locator_count"] == 3
    assert manifest["summary"]["future_or_mixed_locator_count"] == 6
    assert sum(record["active_at_cutoff"] is False for record in view["records"]) == 3
    assert sum(record["active_at_cutoff"] is None for record in view["records"]) == 3


def test_partial_2028_deferral_is_not_applied_to_entire_locator():
    view, _ = build_effective_view()
    records = record_map(view)

    for locator in ((20, "5", "l"), (21, "3", "b"), (32, "9a", "b")):
        record = records[locator]
        assert record["effective_from"] is None
        assert record["active_at_cutoff"] is None
        assert not record["publication_eligible"]
        assert record["temporal_status"] == "mixed_effective_date"
        assert [rule["effective_from"] for rule in record["temporal_rules"]] == [
            "2026-08-15",
            "2028-01-01",
        ]

    for locator in ((20, "5", "n"), (26, "7", "k"), (26, "7", "l")):
        record = records[locator]
        assert record["effective_from"] == "2029-01-01"
        assert record["active_at_cutoff"] is False
        assert not record["publication_eligible"]
        assert record["temporal_status"] == "future"


def test_manual_review_checks_source_payload_and_all_phrase_results():
    view, _ = build_effective_view()
    records = record_map(view)
    source_lines = (
        PROJECT_ROOT / "data/raw/legal/238-2026-nd-cp/supporting-text.txt"
    ).read_text(encoding="utf-8").splitlines()
    amendment_map = json.loads(
        (PROJECT_ROOT / "data/legal_sources/amendments_238_2026.json").read_text(
            encoding="utf-8"
        )
    )

    for operation in amendment_map["operations"]:
        operation_id = operation["operation_id"]
        target = (
            operation["target_article"],
            operation["target_clause"],
            operation["target_point"],
        )
        if operation["amendment_article"] <= 18:
            start, end = SOURCE_LINES[operation_id]
            payload = clean_quoted_payload(source_lines[start - 1 : end])
            if operation_id == "a17-nd168-d50-k3-a-doan2":
                assert payload in records[target]["text"]
                continue
            expected = parse_fragment(payload, target)
            for locator, expected_text in expected.items():
                assert records[locator]["text"] == expected_text
                assert operation_id in records[locator]["operation_ids"]
            continue

        if operation["operation"] == "repeal":
            assert target not in records
            continue

        result = records[target]["text"]
        for mode, anchor, value in phrase_specs(operation_id):
            if mode in {"replace", "replace_all", "remove"}:
                assert anchor.casefold() not in result.casefold()
            if value:
                assert value.casefold() in result.casefold()
        assert operation_id in records[target]["operation_ids"]


def test_all_modified_records_have_traceable_citation_and_provenance():
    view, _ = build_effective_view()
    ledger_ids = {item["operation_id"] for item in view["patch_ledger"]}
    represented_ids = {
        operation_id
        for record in view["records"]
        for operation_id in record["operation_ids"]
    }
    repealed_ids = {
        item["operation_id"]
        for item in view["patch_ledger"]
        if item["operation"] == "repeal"
    }
    assert represented_ids | repealed_ids == ledger_ids

    for record in view["records"]:
        assert hashlib.sha256(record["text"].encode("utf-8")).hexdigest() == record[
            "text_sha256"
        ]
        if record["operation_ids"]:
            assert record["source_document_ids"] == [
                "168-2024-nd-cp",
                "238-2026-nd-cp",
            ]
            assert "được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP" in record[
                "citation"
            ]
            assert record["source_amendment_articles"]
        else:
            assert record["source_document_ids"] == ["168-2024-nd-cp"]


def test_written_effective_view_matches_manifest_checksum():
    manifest = json.loads(
        (PROJECT_ROOT / "data/legal_sources/nd168_effective_view_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    output = PROJECT_ROOT / manifest["output"]["path"]
    assert output.is_file()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == manifest["output"]["sha256"]
    assert manifest["status"] == "approved_for_snapshot_freeze"

    review = json.loads(
        (PROJECT_ROOT / "data/legal_sources/nd168_effective_view_review.json").read_text(
            encoding="utf-8"
        )
    )
    reviewed = review["reviewed_artifact"]
    assert reviewed["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    manifest_path = PROJECT_ROOT / reviewed["manifest_path"]
    assert reviewed["manifest_sha256"] == hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
