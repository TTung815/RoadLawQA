"""Checks for the committed current-law freeze receipt."""

import ast
import pytest

from evaluation import current_law_snapshot
from ingestion.legal_registry import PROJECT_ROOT, read_json, write_json
from ingestion.shadow_index import PRODUCTION_COLLECTION, SHADOW_COLLECTION, ShadowIntegrityError


def test_committed_current_law_receipt_is_frozen_and_verifiable():
    result = current_law_snapshot.verify_frozen_snapshot()
    assert result == {
        "passed": True,
        "snapshot_id": "roadlawqa-current-law-2026-09-22",
        "frozen": True,
    }
    snapshot = read_json(current_law_snapshot.DEFAULT_SNAPSHOT_MANIFEST)
    receipt = read_json(current_law_snapshot.DEFAULT_RECEIPT)
    assert snapshot["processed_corpus"]["chunk_count"] == 2531
    assert snapshot["shadow_resources"]["collection"] == SHADOW_COLLECTION
    assert snapshot["production"]["collection"] == PRODUCTION_COLLECTION
    assert snapshot["production"]["touched"] is False
    assert snapshot["production"]["root_bm25_touched"] is False
    assert len(snapshot["publication_blocks"]["nd168_mixed_2028"]) == 3
    assert len(snapshot["publication_blocks"]["nd168_future_2029"]) == 3
    assert receipt["benchmark_audit_or_c0_c4_run"] is False


def test_freeze_verification_rejects_changed_manifest(tmp_path):
    snapshot = read_json(current_law_snapshot.DEFAULT_SNAPSHOT_MANIFEST)
    receipt = read_json(current_law_snapshot.DEFAULT_RECEIPT)
    snapshot["gates"]["processed_matches_shadow"] = False
    snapshot_path = tmp_path / "snapshot.json"
    receipt_path = tmp_path / "receipt.json"
    write_json(snapshot_path, snapshot)
    write_json(receipt_path, receipt)
    with pytest.raises(ShadowIntegrityError, match="manifest changed"):
        current_law_snapshot.verify_frozen_snapshot(snapshot_path, receipt_path)


def test_shadow_builder_has_no_collection_delete_call():
    path = PROJECT_ROOT / "ingestion/shadow_index.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    delete_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "delete"
    ]
    assert delete_calls == []
