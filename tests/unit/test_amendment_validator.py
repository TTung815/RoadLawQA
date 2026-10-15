"""Kiểm tra audit locator của overlay Nghị định 168 + 238."""

import json

from ingestion.amendment_validator import audit_amendment_locators
from ingestion.legal_registry import DEFAULT_AMENDMENTS, read_json


def test_real_amendment_map_has_valid_leaf_locators_and_anchors():
    report = audit_amendment_locators()
    assert report["status"] == "passed"
    assert report["summary"]["operation_count"] == 102
    assert report["summary"]["passed_operations"] == 102
    assert report["summary"]["failed_operations"] == 0
    assert report["summary"]["target_article_count"] == 24
    assert report["summary"]["docx_extraction_reproducible"]
    assert report["summary"]["normalized_only_anchor_matches"] == [
        {
            "operation_id": "a19-p16-nd168-d55",
            "anchor": "trực thuộc trung ương",
        }
    ]
    assert report["freeze_allowed"]


def test_validator_catches_wrong_d_vs_dd_locator(tmp_path):
    payload = read_json(DEFAULT_AMENDMENTS)
    operation = next(
        item
        for item in payload["operations"]
        if item["operation_id"] == "a19-p06-nd168-d20-k6-d"
    )
    operation["target_point"] = "đ"
    broken = tmp_path / "amendments.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = audit_amendment_locators(amendments_path=broken)
    failure = next(
        item
        for item in report["failures"]
        if item["operation_id"] == "a19-p06-nd168-d20-k6-d"
    )
    assert report["status"] == "failed"
    assert failure["locator_check_passed"]
    assert not failure["anchors_passed"]
