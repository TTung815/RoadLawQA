"""Load owner-approved v2 labels without changing the frozen v1 contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal, Sequence

from pydantic import Field, model_validator

from evaluation import current_law_dataset as corpus
from evaluation import reviewed_current_law_dataset as parent
from evaluation.dataset_schema import GoldLabels, LabelModel, Message, SHA256, Text
from evaluation.snapshot import digest
from ingestion.legal_dependency import load_dependency
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json
from ingestion.structured_corpus import load_bundle


DATASET_ID = "current_law_20260922_reviewed_v2"
DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets" / DATASET_ID
ARTIFACTS = {"cases.jsonl", "REVIEWED.md", "review_decisions.json", "case.schema.json", "README.md"}
ResponseStatus = Literal["answered", "partial_answer", "needs_clarification", "insufficient_evidence"]


class Publication(LabelModel):
    disposition: Literal["publish", "conditional", "abstain"]
    allowed_statuses: list[ResponseStatus] = Field(min_length=1)
    rationale: Text
    status_criteria: dict[ResponseStatus, Text]

    @model_validator(mode="after")
    def criteria_match(self):
        if set(self.status_criteria) != set(self.allowed_statuses):
            raise ValueError("each allowed response status needs explicit semantic criteria")
        return self


class RevisedGold(GoldLabels):
    publication: Publication


class RevisedCase(LabelModel):
    id: Text
    query: Text
    query_type: Literal["factual", "penalty", "scenario"]
    chat_history: list[Message] = Field(default_factory=list)
    parent_case_sha256: SHA256
    gold: RevisedGold


def source_chunks() -> dict[str, dict]:
    """Canonical leaf text for citation checks, including the reviewed age scope."""
    chunks = {c["id"]: c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"]}
    rows, nodes, _ = load_dependency()
    for row in rows:
        article = f"{row['document_id']}:article:{row['article_no']}"
        contexts = [nodes[article]["text"]]
        clause = f"{article}:clause:{row['clause_no']}"
        if clause in nodes:
            contexts.append(nodes[clause]["text"])
        body = f"{row['point']}) {row['text']}" if row["point"] else row["text"]
        chunks[row["id"]] = {**row, "enriched_text": "\n".join([row["law"], *contexts, body])}
    return chunks


def load_cases(directory: Path = DEFAULT_DIR) -> list[RevisedCase]:
    manifest = read_json(directory / "manifest.json")
    if (manifest["dataset_id"] != DATASET_ID or manifest["status"] != "owner_approved"
            or manifest["approval"]["status"] != "approved"
            or not manifest["approval"]["authorization"]):
        raise ValueError("v2 labels need the recorded owner approval")
    if set(manifest["artifacts"]) != ARTIFACTS:
        raise ValueError("incomplete v2 artifact manifest")
    for name, expected in manifest["artifacts"].items():
        if file_digest(directory / name) != expected:
            raise ValueError(f"v2 artifact changed: {name}")
    for name, expected in manifest["inputs"].items():
        if file_digest(PROJECT_ROOT / name) != expected:
            raise ValueError(f"v2 source binding changed: {name}")
    parents = {c.id: c for c in parent.require_reviewed_scoring()}
    cases = [RevisedCase.model_validate_json(line) for line in (directory / "cases.jsonl").read_text().splitlines()]
    if len(cases) != 50 or {c.id for c in cases} != set(parents):
        raise ValueError("v2 must preserve the 50 parent case IDs exactly once")
    decisions = read_json(directory / "review_decisions.json")
    if len(decisions) != 50 or {d["case_id"] for d in decisions} != set(parents):
        raise ValueError("v2 needs one review decision per case")
    decisions = {d["case_id"]: d for d in decisions}
    chunks = source_chunks()
    unit_leaves = {pid for u in load_bundle()["chunks"]
                   if u["metadata"]["publication_eligible"] and u["metadata"]["active_at_cutoff"]
                   for pid in u["metadata"]["source_processed_ids"]}
    for case in cases:
        original = parents[case.id]
        decision = decisions[case.id]
        if case.parent_case_sha256 != digest(original.model_dump(mode="json")):
            raise ValueError("v2 parent case binding changed")
        if decision["case_sha256"] != digest(case.model_dump(mode="json")):
            raise ValueError("v2 case differs from approved decision")
        if case.query_type != original.query_type or case.chat_history != original.chat_history:
            raise ValueError("v2 review cannot change question type or history")
        if (case.gold.temporal_basis, case.gold.as_of_date) != (original.gold.temporal_basis, original.gold.as_of_date):
            raise ValueError("v2 review cannot change temporal provenance")
        if case.gold.review.status != "approved":
            raise ValueError("unapproved v2 case")
        for group in case.gold.evidence_groups:
            for ref in group.references:
                chunk = chunks.get(ref.processed_id)
                if chunk is None or ref.model_dump() != corpus.evidence_reference(chunk, ref.role):
                    raise ValueError("v2 citation does not match canonical source")
                if ref.role == "support" and ref.processed_id not in unit_leaves:
                    raise ValueError("v2 support is blocked or missing from serving corpus")
    return cases


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    cases = load_cases(args.directory)
    print(json.dumps({"dataset_id": DATASET_ID, "cases": len(cases), "verified": True,
                      "publication": {s: sum(c.gold.publication.disposition == s for c in cases)
                                      for s in ["publish", "conditional", "abstain"]}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
