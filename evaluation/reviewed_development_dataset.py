"""Create a separate owner-reviewed development version without altering drafts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import model_validator

from evaluation import current_law_dataset as corpus
from evaluation import development_dataset as draft
from evaluation.dataset_schema import GoldLabels, LabelModel, SHA256, Text
from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json


DATASET_ID = "current_law_20260922_development_reviewed_v1"
DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets" / DATASET_ID
GROUPS = {"A1", "A2", "A3", "A4", "B1", "B2", "C1"}
PROTOCOL = PROJECT_ROOT / "docs/BENCHMARK_CORE_EVALUATION.md"


class OwnerReview(LabelModel):
    dataset_id: Literal[DATASET_ID]
    parent_manifest_sha256: SHA256
    reviewer: Text
    reviewed_on: date
    recorded_on: date
    approved_groups: list[Text]
    authorization: Text
    scope: Text

    @model_validator(mode="after")
    def exact_scope(self):
        if set(self.approved_groups) != GROUPS or len(self.approved_groups) != 7:
            raise ValueError("owner approval must cover the seven actual review groups")
        if self.recorded_on < self.reviewed_on:
            raise ValueError("review cannot be recorded before approval")
        return self


class ReviewedDevelopmentCase(LabelModel):
    id: Text
    parent_case: draft.DevelopmentDraftCase
    parent_case_sha256: SHA256
    review_group_sha256: SHA256
    gold: GoldLabels

    @model_validator(mode="after")
    def approval_only(self):
        if self.id != self.parent_case.id or self.parent_case_sha256 != digest(self.parent_case.model_dump(mode="json")):
            raise ValueError("reviewed development parent changed")
        if self.gold.review.status != "approved":
            raise ValueError("reviewed development requires actual owner approval")
        if self.gold.model_dump(exclude={"review"}) != self.parent_case.gold.model_dump(exclude={"review"}):
            raise ValueError("this version only records approval, not new legal content")
        return self


def make_artifacts(directory: Path = DEFAULT_DIR) -> dict:
    draft.verify_bundle()
    review = OwnerReview.model_validate(read_json(directory / "owner_review.json"))
    if review.parent_manifest_sha256 != file_digest(draft.DEFAULT_DIR / "manifest.json"):
        raise ValueError("owner review targets a different draft")
    groups = {item["id"]: item for item in read_json(draft.DEFAULT_DIR / "review_groups.json")}
    chunks = {c["id"]: c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"]}
    parents = [draft.DevelopmentDraftCase.model_validate_json(line) for line in
               (draft.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]
    cases = []
    for parent in parents:
        draft.validate_case(parent, chunks)
        group = groups[parent.review_group_id]
        if parent.id not in group["case_ids"]:
            raise ValueError("case is outside its owner-approved group")
        gold = parent.gold.model_dump(mode="json")
        gold["review"] = {
            "status": "approved", "reviewer": review.reviewer,
            "reviewed_on": str(review.reviewed_on),
            "notes": [review.scope, "Owner grouped content/scope approval, not professional legal certification.",
                      "Author/technical annotations in the immutable draft describe its earlier state."],
        }
        cases.append(ReviewedDevelopmentCase(
            id=parent.id, parent_case=parent, parent_case_sha256=digest(parent.model_dump(mode="json")),
            review_group_sha256=group["content_sha256"], gold=GoldLabels.model_validate(gold),
        ))
    report = {
        "dataset_id": DATASET_ID, "case_count": len(cases), "approved": len(cases),
        "modes": dict(Counter(c.parent_case.stage_probe.mode for c in cases)),
        "review_groups": 7, "development_gold_ready": True,
        "benchmark_c0_c4_ready": False, "model_runs": 0, "production_writes": 0,
    }
    lines = ["# Development reviewed v1", "", f"Owner approved all 7 groups on {review.reviewed_on}; recorded {review.recorded_on}.",
             "54 units: 12 end-to-end, 7 fixed-evidence, 1 rewrite, 34 publication guards.",
             "Not 54 independent legal questions; report modes separately. Draft content remains unchanged.", "",
             "Owner internal review only, not professional legal certification. No model evaluation has run.", ""]
    for c in cases:
        lines.extend([f"## {c.id} ({c.parent_case.review_group_id})", "", c.parent_case.query, "",
                      c.gold.reference_answer or "", ""])
    artifacts = {
        "cases.jsonl": "".join(c.model_dump_json() + "\n" for c in cases),
        "case.schema.json": ReviewedDevelopmentCase.model_json_schema(),
        "review_groups.json": [{**groups[key], "status": "approved", "reviewer": review.reviewer,
                                "reviewed_on": str(review.reviewed_on)} for key in sorted(GROUPS)],
        "audit.json": report, "REVIEWED.md": "\n".join(lines),
    }
    artifacts["manifest.json"] = {
        "dataset_id": DATASET_ID, "legal_as_of": corpus.LEGAL_AS_OF,
        "parent_manifest_sha256": review.parent_manifest_sha256,
        "owner_review_sha256": file_digest(directory / "owner_review.json"),
        "snapshot_receipt_sha256": file_digest(corpus.DEFAULT_RECEIPT),
        "protocol_sha256": file_digest(PROTOCOL), "builder_sha256": file_digest(Path(__file__)),
        "artifacts": {name: hashlib.sha256(corpus.artifact_bytes(value)).hexdigest() for name, value in artifacts.items()},
        "development_gold_ready": True, "benchmark_c0_c4_ready": False,
    }
    return artifacts


def receipt_for(directory: Path) -> dict:
    review = OwnerReview.model_validate(read_json(directory / "owner_review.json"))
    return {"dataset_id": DATASET_ID, "frozen": True, "frozen_on": str(review.recorded_on),
            "manifest_sha256": file_digest(directory / "manifest.json"),
            "owner_review_sha256": file_digest(directory / "owner_review.json"),
            "development_gold_ready": True, "benchmark_c0_c4_ready": False}


def verify_bundle(directory: Path = DEFAULT_DIR, *, require_frozen: bool = True) -> dict:
    artifacts = make_artifacts(directory)
    for name, value in artifacts.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != corpus.artifact_bytes(value):
            raise ValueError(f"reviewed development artifact changed: {name}")
    if require_frozen:
        path = directory / "freeze_receipt.json"
        if not path.is_file() or path.read_bytes() != corpus.artifact_bytes(receipt_for(directory)):
            raise ValueError("reviewed development is not frozen or receipt changed")
    return artifacts["audit.json"]


def build_bundle(directory: Path = DEFAULT_DIR) -> dict:
    artifacts = make_artifacts(directory)
    if any((directory / name).exists() for name in artifacts):
        raise FileExistsError("version exists; verify or create a new version")
    for name, value in artifacts.items():
        with (directory / name).open("xb") as stream:
            stream.write(corpus.artifact_bytes(value))
    return artifacts["audit.json"]


def freeze_bundle(directory: Path = DEFAULT_DIR) -> dict:
    report = verify_bundle(directory, require_frozen=False)
    with (directory / "freeze_receipt.json").open("xb") as stream:
        stream.write(corpus.artifact_bytes(receipt_for(directory)))
    return report


def load_cases(directory: Path = DEFAULT_DIR) -> list[ReviewedDevelopmentCase]:
    verify_bundle(directory)
    return [ReviewedDevelopmentCase.model_validate_json(line) for line in
            (directory / "cases.jsonl").read_text().splitlines()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "freeze", "verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    print(json.dumps({"build": build_bundle, "freeze": freeze_bundle, "verify": verify_bundle}[args.action](args.directory)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
