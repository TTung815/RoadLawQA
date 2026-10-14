"""Create-only Phase 3 coverage/design packets; no model, scoring or index writes.

New development drafts have their own provenance contract. A reviewed parent is
not an approval of a new conversation or a deliberately incomplete replay pool.
Held-out content is intentionally not authored in the tuning workspace.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
from pathlib import Path
from typing import Literal, Sequence
import json

from pydantic import Field, model_validator

from evaluation import current_law_dataset as draft
from evaluation import reviewed_current_law_dataset as reviewed
from evaluation.dataset_schema import (
    FAILURE_CATEGORIES, GoldLabels, LabelModel, Message, SHA256, Text,
)
from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json


PLAN_ID = "current_law_20260922_phase3_design_v1"
DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets" / PLAN_ID
PROTOCOL = PROJECT_ROOT / "docs/BENCHMARK_PHASE3_DESIGN.md"


class Recipe(LabelModel):
    id: Text
    parent: int = Field(ge=1, le=50)
    kind: Literal[
        "money_only", "complete_pool", "wrong_citation", "equipment_distractor",
        "accumulation", "rewrite_probe", "multi_turn", "distractor_history", "end_to_end",
    ]
    purpose: Text
    failures: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def known_failures(self):
        if not set(self.failures) <= set(FAILURE_CATEGORIES):
            raise ValueError("unknown failure category")
        return self


class PendingSuite(LabelModel):
    id: Text
    parent: int | None = Field(default=None, ge=1, le=50)
    authoring_spec: Text


class HeldOutCell(LabelModel):
    id: Text
    target_families: int = Field(ge=1)
    query_type: Literal["factual", "penalty", "scenario"]
    goal: Text


class DesignPlan(LabelModel):
    plan_id: Literal[PLAN_ID]
    status: Literal["design_draft"]
    legal_as_of: Literal[draft.LEGAL_AS_OF]
    held_out_status: Literal["not_authored"]
    custodian: None
    author: None
    reviewer: None
    development_recipes: list[Recipe] = Field(min_length=1)
    pending_suites: list[PendingSuite] = Field(min_length=1)
    held_out_cells: list[HeldOutCell] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_entries(self):
        for entries in (self.development_recipes, self.pending_suites, self.held_out_cells):
            ids = [item.id for item in entries]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate design entry")
        return self


class StageProbe(LabelModel):
    mode: Literal["end_to_end", "fixed_evidence", "rewrite_probe"]
    evidence_batches: list[list[Text]] = Field(default_factory=list)
    expected_pool_coverage: Literal["sufficient", "insufficient"] | None = None
    missing_facet_ids: list[Text] = Field(default_factory=list)
    assertion: Text


class DevelopmentCase(LabelModel):
    schema_version: Literal[1] = 1
    id: Text
    split: Literal["legacy"] = "legacy"
    exposure: Literal["historically_used"] = "historically_used"
    suite: Literal["development"] = "development"
    family_id: Text
    query_type: Literal["factual", "penalty", "scenario"]
    query: Text
    chat_history: list[Message] = Field(default_factory=list)
    snapshot_id: Literal[draft.CORPUS_ID] = draft.CORPUS_ID
    legal_as_of: Literal[draft.LEGAL_AS_OF] = draft.LEGAL_AS_OF
    parent_case_id: Text
    parent_case_sha256: SHA256
    parent_manifest_sha256: SHA256
    recipe: Recipe
    gold: GoldLabels
    temporal_provenance: reviewed.TemporalReview | None = None
    stage_probe: StageProbe
    open_review_items: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def draft_only(self):
        if self.gold.review.status != "needs_review" or self.gold.review.reviewer or self.gold.review.reviewed_on:
            raise ValueError("development draft cannot inherit approval")
        if any(len(batch) != len(set(batch)) for batch in self.stage_probe.evidence_batches):
            raise ValueError("duplicate evidence within a batch")
        if self.stage_probe.mode != "fixed_evidence" and (
            self.stage_probe.evidence_batches or self.stage_probe.expected_pool_coverage is not None
            or self.stage_probe.missing_facet_ids
        ):
            raise ValueError("only replay prescribes a pool")
        return self


def support_ids(case, kind: str | None = None) -> list[str]:
    groups = {group.id: group for group in case.gold.evidence_groups}
    refs = [ref.processed_id for facet in case.gold.required_facets
            if facet.required and (kind is None or facet.kind == kind)
            for identity in facet.evidence_group_ids for ref in groups[identity].references
            if ref.role == "support"]
    return list(dict.fromkeys(refs))


def missing_facets(case, pool: Sequence[str]) -> list[str]:
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


def ordered_pool(batches: Sequence[Sequence[str]]) -> list[str]:
    return list(dict.fromkeys(identity for batch in batches for identity in batch))


def article_key(chunk: dict) -> str:
    return f"{chunk['document_id']}:d{chunk['article_no']}"


def make_development(recipe: Recipe, parents: dict[int, reviewed.ReviewedCase],
                     chunks: dict[str, dict]) -> DevelopmentCase:
    parent = parents[recipe.parent]
    gold = parent.gold.model_dump(mode="json")
    gold["review"] = {"status": "needs_review", "reviewer": None, "reviewed_on": None,
                      "notes": ["Reference từ parent đã duyệt; bài thử mới chưa review độc lập."]}
    gold["technical_audit"] = None
    gold["failure_categories"] = recipe.failures
    query, history = parent.query, []
    batches = []
    mode = "end_to_end"
    assertion = "Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset."
    if recipe.kind in {"money_only", "complete_pool", "wrong_citation", "equipment_distractor", "accumulation"}:
        mode = "fixed_evidence"
        if recipe.kind == "money_only":
            batches = [support_ids(parent, "money")]
            assertion = "Pool chưa đủ mọi yêu cầu; không công bố câu trả lời đầy đủ như đã grounded."
        elif recipe.kind == "complete_pool":
            batches = [support_ids(parent)]
            assertion = "Control pool đủ positive support; đo false-insufficient/unnecessary abstention."
        elif recipe.kind == "wrong_citation":
            batches = [support_ids(parents[3])]
            assertion = "Locator hợp lệ của lỗi khác không chứng minh claim tiền/điểm bài này."
        elif recipe.kind == "equipment_distractor":
            batches = [["nd168-effective-as-of-2026-09-22-d9-k1-pi"]]
            assertion = "Điều 9 về sử dụng đèn không thay căn cứ thiếu trang bị tại Điều 15."
        else:
            money = support_ids(parent, "money")
            consequence = [identity for identity in support_ids(parent) if identity not in money]
            batches = [money, consequence]
            assertion = "Grade ordered union, không chỉ batch cuối; hai facet đều còn evidence."
        if not batches or any(not batch for batch in batches):
            raise ValueError("replay requires nonempty evidence batches")
    elif recipe.kind == "rewrite_probe":
        mode = "rewrite_probe"
        assertion = "Bảo toàn nguyên chủ thể, hành vi, khoảng số và ngày của parent; chưa có rewrite output."
    elif recipe.kind == "multi_turn":
        history = [{"role": "user", "content": parent.query}]
        query = "Vậy tiền phạt và số điểm bị trừ là bao nhiêu?"
    elif recipe.kind == "distractor_history":
        history = [{"role": "user", "content": parents[3].query},
                   {"role": "user", "content": parent.query}]
        query = "Vậy trường hợp vừa nói bị xử lý thế nào?"
    pool = ordered_pool(batches)
    for identity in pool:
        if identity not in chunks or not chunks[identity]["publication_eligible"]:
            raise ValueError("replay contains absent or blocked evidence")
    missing = missing_facets(parent, pool) if mode == "fixed_evidence" else []
    if mode == "fixed_evidence" and recipe.kind in {"money_only", "wrong_citation", "equipment_distractor"} and not missing:
        raise ValueError("incomplete replay unexpectedly covers all facets")
    if mode == "fixed_evidence" and recipe.kind in {"complete_pool", "accumulation"} and missing:
        raise ValueError("complete replay lacks a required facet")
    if recipe.kind == "accumulation" and not missing_facets(parent, batches[-1]):
        raise ValueError("last batch alone must be insufficient for accumulation probe")
    return DevelopmentCase.model_validate({
        "id": recipe.id, "family_id": parent.family_id, "query_type": parent.query_type,
        "query": query, "chat_history": history, "parent_case_id": parent.id,
        "parent_case_sha256": digest(parent.model_dump(mode="json")),
        "parent_manifest_sha256": file_digest(reviewed.DEFAULT_DIR / "manifest.json"),
        "recipe": recipe.model_dump(), "gold": gold,
        "temporal_provenance": parent.temporal_provenance.model_dump(mode="json") if parent.temporal_provenance else None,
        "stage_probe": {"mode": mode, "evidence_batches": batches,
                        "expected_pool_coverage": ("insufficient" if missing else "sufficient") if mode == "fixed_evidence" else None,
                        "missing_facet_ids": missing, "assertion": assertion},
        "open_review_items": [
            "Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.",
            "Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.",
            "Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.",
        ],
    })


def coverage_report(parents: Sequence[reviewed.ReviewedCase], cases: Sequence[DevelopmentCase],
                    chunks: dict[str, dict]) -> dict:
    references = {ref.processed_id for case in parents for group in case.gold.evidence_groups for ref in group.references}
    exposed = references | {identity for case in cases for identity in ordered_pool(case.stage_probe.evidence_batches)}
    support_counts = Counter(len(support_ids(case)) for case in parents)
    sources = Counter()
    for case in parents:
        for document in {chunks[identity]["document_id"] for identity in support_ids(case)}:
            sources[document] += 1
    blocked = [chunk for chunk in chunks.values() if not chunk["publication_eligible"]]
    return {
        "legacy": {**draft.coverage_report(parents),
                   "multi_turn_cases": sum(bool(case.chat_history) for case in parents),
                   "support_locator_count_histogram": dict(sorted(support_counts.items())),
                   "source_case_counts": dict(sorted(sources.items())),
                   "operation_linked_support_cases": sum(any(chunks[identity]["operation_ids"] for identity in support_ids(case)) for case in parents),
                   "facet_case_counts": dict(sorted(Counter(kind for case in parents for kind in {facet.kind for facet in case.gold.required_facets}).items())),
                   "all_group_count": sum(group.match == "all" for case in parents for group in case.gold.evidence_groups),
                   "any_group_count": sum(group.match == "any" for case in parents for group in case.gold.evidence_groups)},
        "development": {"count": len(cases), "approved": 0,
                        "families": len({case.family_id for case in cases}),
                        "modes": dict(Counter(case.stage_probe.mode for case in cases)),
                        "multi_turn_cases": sum(bool(case.chat_history) for case in cases)},
        "held_out": {"authored": 0, "approved": 0, "sealed": False},
        "exclusion_inventory": {"families": sorted({case.family_id for case in parents} | {case.family_id for case in cases}),
                                "articles": sorted({article_key(chunks[identity]) for identity in exposed}),
                                "evidence_ids": sorted(exposed),
                                "scope": "Gold/context/replay references only; independent test/prompt/output semantic exposure audit still required."},
        "blocked_context_inventory": [{"id": c["id"], "article": article_key(c),
                                       "temporal_status": c["temporal_status"], "support_allowed": False} for c in blocked],
        "system_results": None,
        "coverage_limit": "Counts describe cases, not measured errors, representativeness or complete legal-domain coverage.",
    }


class HeldOutProposal(LabelModel):
    """Metadata screen only; does not read sealed questions or authorize scoring."""
    id: Text
    family_id: Text
    article_keys: list[Text] = Field(min_length=1)
    parent_case_ids: list[Text] = Field(default_factory=list)
    content_sha256: SHA256
    author: Text
    reviewer: Text
    custodian: Text
    reviewed_on: date
    semantic_overlap_reviewed: bool
    exposure_inventory_reviewed: bool
    tuning_exposed: bool
    used_for_selection: bool


def screen_held_out(proposal: HeldOutProposal, inventory: dict, tuner: str) -> None:
    """Reject detectable leakage; a passing metadata screen is NOT a freeze gate."""
    if not tuner.strip():
        raise ValueError("held-out screen needs a tuner identity")
    if proposal.parent_case_ids or proposal.family_id in inventory["families"]:
        raise ValueError("held-out family is exposed")
    if set(proposal.article_keys) & set(inventory["articles"]):
        raise ValueError("held-out article is exposed")
    if proposal.author == proposal.reviewer or tuner in {proposal.author, proposal.reviewer, proposal.custodian}:
        raise ValueError("held-out roles lack separation")
    if not proposal.semantic_overlap_reviewed or not proposal.exposure_inventory_reviewed:
        raise ValueError("held-out overlap review is incomplete")
    if proposal.tuning_exposed or proposal.used_for_selection:
        raise ValueError("held-out content was used for tuning/selection")


def render_development(cases: Sequence[DevelopmentCase], chunks: dict[str, dict]) -> str:
    lines = ["# Development regression/challenge — draft cần review", "",
             "16 bài dẫn xuất từ gold đã freeze; **0 bài mới approved**. Chưa chạy model.",
             "Không phải held-out; các biến thể giữ family exposed của parent.",
             "Replay thiếu evidence không đổi full-corpus gold thành abstain.", ""]
    for case in cases:
        probe = case.stage_probe
        lines.extend([f"## {case.id} — {case.recipe.purpose}", "",
                      f"Parent: `{case.parent_case_id}`; family: `{case.family_id}`; mode: `{probe.mode}`.", ""])
        if case.chat_history:
            lines.extend(["History (dữ kiện người dùng, không bịa câu trả lời assistant):", ""])
            lines.extend(f"- {message.role}: {message.content}" for message in case.chat_history)
            lines.append("")
        lines.extend([f"**Câu hỏi hiện tại:** {case.query}", "", "**Đáp án tham chiếu toàn corpus — draft:**", "",
                      case.gold.reference_answer or "", "", f"- Full-corpus expectation: {case.gold.publication.disposition}",
                      f"- Bài thử: {probe.assertion}"])
        if probe.mode == "fixed_evidence":
            lines.append(f"- Expectation pool được đưa: {probe.expected_pool_coverage}; không dùng nhãn này thay full-corpus gold.")
            for i, batch in enumerate(probe.evidence_batches, 1):
                lines.append(f"- Batch {i}: {', '.join(f'`{identity}`' for identity in batch)}")
            descriptions = [facet.description for facet in case.gold.required_facets if facet.id in probe.missing_facet_ids]
            lines.append("- Ý chưa đủ căn cứ trong tổng các batch: " + ("; ".join(descriptions) or "không có"))
        lines.extend(["", "Ý bắt buộc (căn cứ không thay đổi từ parent):", ""])
        lines.extend(f"- {facet.description}" for facet in case.gold.required_facets)
        refs = {ref.processed_id: ref for group in case.gold.evidence_groups for ref in group.references}
        lines.extend(["", "Căn cứ đầy đủ trong evidence_catalog.json:", ""])
        for identity, ref in refs.items():
            spans = "; ".join(f"{s['path']}:{s['line_start']}–{s['line_end']}" for s in chunks[identity]["source_spans"])
            lines.append(f"- {ref.citation} ({ref.role}); `{identity}`; {spans}")
        lines.extend(["", "Reviewer cần chốt:", "", *[f"- {note}" for note in case.open_review_items], ""])
    return "\n".join(lines) + "\n"


def render_coverage(report: dict, plan: DesignPlan) -> str:
    legacy = report["legacy"]
    lines = ["# Coverage và kế hoạch bổ sung Pha 3", "",
             "Counts dưới đây được tính từ frozen gold, **không phải điểm chạy hệ thống**.", "",
             f"Legacy: {legacy['count']} case; {len(legacy['families'])} family; nhãn {legacy['publication']}.",
             f"Multi-turn legacy: {legacy['multi_turn_cases']}; support có operation overlay cụ thể: {legacy['operation_linked_support_cases']}.", "",
             "| Tag trong legacy | Số case |", "| --- | --- |"]
    lines.extend(f"| {tag} | {count} |" for tag, count in legacy["tags"].items())
    lines.extend(["", "## Khoảng trống và hành động", "",
                  "| Khoảng trống/rủi ro | Bài development | Còn cần làm |", "| --- | --- | --- |",
                  "| Tiền/điểm, tiền/chế tài bị thiếu evidence | dev_001–004 controls | Review pool rồi triển khai replay runner |",
                  "| Citation tồn tại nhưng không support; đổi hành vi | dev_005–006 | Rubric claim-to-source, không chỉ kiểm locator |",
                  "| Mất evidence trước; rewrite đổi chủ thể/biên | dev_007–008 | Runner lưu từng stage, chấm intent preservation |",
                  "| Legacy không có multi-turn | dev_009–010 | Review history/current query/full context |",
                  "| Thiếu facts/dependency/negative provenance | dev_011–013 | Đo unsafe publication riêng, giữ safety gates |",
                  "| Từ chối khi đủ nguồn; date proof/amendment | dev_014–016 | Review derivative, không tự mở proof/gate |",
                  "| Chưa có suite sát biên số và temporal blocks | pending_suites | Author gold từng nhánh, review riêng |",
                  "| Chưa có unseen held-out | 6 cell, 12 family mục tiêu | Chỉ định custodian/author/reviewer, author ngoài tuning workspace |",
                  "", "## Suite chưa author", ""])
    lines.extend(f"- {suite.id}: {suite.authoring_spec}" for suite in plan.pending_suites)
    lines.extend(["", "## Blueprint held-out (không có query/gold)", "",
                  "| Cell | Target families | Mục tiêu |", "| --- | --- | --- |"])
    lines.extend(f"| {cell.id} | {cell.target_families} | {cell.goal} |" for cell in plan.held_out_cells)
    lines.extend(["", "Số dự kiến là budget tối thiểu thử protocol, không là bằng chứng representative.",
                  "Exclusion inventory machine-readable ở coverage.json; còn cần independent semantic exposure audit.",
                  "Không có custodian hoặc sealed content ở thời điểm này. C0–C4 vẫn bị chặn.", ""])
    return "\n".join(lines) + "\n"


def make_artifacts(directory: Path = DEFAULT_DIR) -> dict:
    reviewed.verify_bundle()
    plan = DesignPlan.model_validate(read_json(directory / "plan.json"))
    parents = {int(case.source.historical_id): case for case in (
        reviewed.ReviewedCase.model_validate_json(line)
        for line in (reviewed.DEFAULT_DIR / "cases.jsonl").read_text().splitlines())}
    chunks = {chunk["id"]: chunk for chunk in read_json(draft.DEFAULT_OUTPUT)["chunks"]}
    cases = [make_development(recipe, parents, chunks) for recipe in plan.development_recipes]
    coverage = coverage_report(list(parents.values()), cases, chunks)
    used = sorted({ref.processed_id for case in cases for group in case.gold.evidence_groups for ref in group.references}
                  | {identity for case in cases for identity in ordered_pool(case.stage_probe.evidence_batches)})
    catalog = {"snapshot_id": draft.CORPUS_ID, "chunks": [chunks[identity] for identity in used],
               "context_hashes": {identity: reviewed.context_hash(chunks[identity]) for identity in used}}
    artifacts = {"development_cases.jsonl": "".join(case.model_dump_json() + "\n" for case in cases),
                 "evidence_catalog.json": catalog, "development.schema.json": DevelopmentCase.model_json_schema(),
                 "coverage.json": coverage, "COVERAGE.md": render_coverage(coverage, plan),
                 "DEVELOPMENT.md": render_development(cases, chunks)}
    artifacts["manifest.json"] = {
        "plan_id": PLAN_ID, "status": "design_draft", "legal_as_of": draft.LEGAL_AS_OF,
        "parent_manifest_sha256": file_digest(reviewed.DEFAULT_DIR / "manifest.json"),
        "parent_receipt_sha256": file_digest(reviewed.DEFAULT_DIR / reviewed.RECEIPT),
        "snapshot_receipt_sha256": file_digest(draft.DEFAULT_RECEIPT),
        "plan_sha256": file_digest(directory / "plan.json"), "protocol_sha256": file_digest(PROTOCOL),
        "builder_sha256": file_digest(Path(__file__)),
        "artifacts": {name: hashlib.sha256(draft.artifact_bytes(value)).hexdigest() for name, value in artifacts.items()},
        "development_approved": 0, "held_out_authored": 0, "scoring_ready": False,
        "benchmark_c0_c4_ready": False, "model_runs": 0, "production_writes": 0,
    }
    return artifacts


def build_bundle(directory: Path = DEFAULT_DIR) -> dict:
    artifacts = make_artifacts(directory)
    if any((directory / name).exists() for name in artifacts):
        raise FileExistsError("design artifacts exist; verify or use a new version")
    for name, value in artifacts.items():
        with (directory / name).open("xb") as stream:
            stream.write(draft.artifact_bytes(value))
    return artifacts["manifest.json"]


def verify_bundle(directory: Path = DEFAULT_DIR) -> dict:
    artifacts = make_artifacts(directory)
    for name, value in artifacts.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != draft.artifact_bytes(value):
            raise ValueError(f"design artifact changed: {name}")
    return artifacts["manifest.json"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    report = {"build": build_bundle, "verify": verify_bundle}[args.action](args.directory)
    print(json.dumps({key: report[key] for key in (
        "plan_id", "status", "development_approved", "held_out_authored", "scoring_ready", "benchmark_c0_c4_ready",
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
