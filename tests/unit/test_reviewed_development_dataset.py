"""Owner group approval preserves exposed draft provenance and immutable versions."""

import shutil

import pytest
from pydantic import ValidationError

from evaluation import development_dataset as draft
from evaluation import reviewed_development_dataset as reviewed
from ingestion.legal_registry import read_json


@pytest.fixture(scope="module")
def cases():
    return [reviewed.ReviewedDevelopmentCase.model_validate_json(line) for line in
            (reviewed.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]


def test_owner_packet_targets_all_seven_groups_and_exact_draft():
    packet = reviewed.OwnerReview.model_validate(read_json(reviewed.DEFAULT_DIR / "owner_review.json"))
    assert set(packet.approved_groups) == reviewed.GROUPS
    assert packet.parent_manifest_sha256 == reviewed.file_digest(draft.DEFAULT_DIR / "manifest.json")
    for groups in (["A1"], ["A1"] * 7, list(reviewed.GROUPS) + ["extra"]):
        data = packet.model_dump()
        data["approved_groups"] = groups
        with pytest.raises(ValidationError):
            reviewed.OwnerReview.model_validate(data)


def test_reviewed_case_changes_approval_only(cases):
    assert len(cases) == 54
    for case in cases:
        assert case.gold.review.status == "approved"
        assert case.parent_case.gold.review.status == "needs_review"
        assert case.gold.model_dump(exclude={"review"}) == case.parent_case.gold.model_dump(exclude={"review"})
        assert case.parent_case.exposure != "unseen"
    assert sum(c.parent_case.stage_probe.mode == "end_to_end" for c in cases) == 12


@pytest.mark.parametrize("mutation", ["answer", "parent", "hash", "approval"])
def test_cannot_change_reviewed_content_under_same_approval(cases, mutation):
    data = cases[0].model_dump(mode="json")
    if mutation == "answer":
        data["gold"]["reference_answer"] = "changed answer"
    elif mutation == "parent":
        data["parent_case"]["query"] = "changed query"
    elif mutation == "hash":
        data["parent_case_sha256"] = "0" * 64
    else:
        data["gold"]["review"]["status"] = "needs_review"
    with pytest.raises(ValidationError):
        reviewed.ReviewedDevelopmentCase.model_validate(data)


def test_guards_still_abstain_and_context_only(cases):
    guards = [c for c in cases if c.parent_case.origin_kind == "snapshot_guard"]
    assert len(guards) == 34
    for case in guards:
        assert case.gold.publication.disposition == "abstain"
        assert all(ref.role == "context" for group in case.gold.evidence_groups for ref in group.references)
        assert all(f.support_state == "unknown" for f in case.gold.required_facets)


def test_bundle_freeze_verify_and_tamper_detection(tmp_path):
    directory = tmp_path / "reviewed"
    shutil.copytree(reviewed.DEFAULT_DIR, directory, ignore=shutil.ignore_patterns("freeze_receipt.json"))
    report = reviewed.freeze_bundle(directory)
    assert report["approved"] == 54
    assert reviewed.verify_bundle(directory)["development_gold_ready"] is True
    with pytest.raises(FileExistsError):
        reviewed.freeze_bundle(directory)
    with pytest.raises(FileExistsError):
        reviewed.build_bundle(directory)
    (directory / "cases.jsonl").write_text("changed")
    with pytest.raises(ValueError):
        reviewed.verify_bundle(directory)
