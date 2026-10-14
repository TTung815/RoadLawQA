"""Complete exposed development drafts and a compact owner-review packet.

Only dataset/provenance checks run here. No serving changes, LLM calls, benchmark
execution, approval, freeze, held-out authoring or index mutations.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Literal, Sequence

from pydantic import Field, model_validator

from evaluation import current_law_dataset as draft
from evaluation import phase3_design as design
from evaluation import reviewed_current_law_dataset as reviewed
from evaluation.dataset_schema import GoldLabels, LabelModel, Message, SHA256, Text
from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json


DATASET_ID = "current_law_20260922_development_draft_v1"
DEFAULT_DIR = PROJECT_ROOT / "evaluation/datasets" / DATASET_ID
PROTOCOL = PROJECT_ROOT / "docs/BENCHMARK_DEVELOPMENT_DRAFT_V1.md"
AUTHOR = "Codex — source/technical draft, independent content review pending"
DRAFTED_ON = date(2026, 10, 11)


class NumericLabel(LabelModel):
    id: Text
    excess_kmh: int = Field(gt=0)
    chunk_id: Text
    money_min: int = Field(gt=0)
    money_max: int = Field(gt=0)
    query: Text
    reference_answer: Text
    interval_description: Text


class Probe(design.StageProbe):
    mode: Literal["end_to_end", "fixed_evidence", "rewrite_probe", "publication_guard_probe"]


class DevelopmentDraftCase(LabelModel):
    schema_version: Literal[1] = 1
    id: Text
    split: Literal["legacy", "regression"]
    exposure: Literal["historically_used", "known_regression"]
    suite: Literal["development"] = "development"
    family_id: Text
    query_type: Literal["factual", "penalty", "scenario"]
    query: Text
    chat_history: list[Message] = Field(default_factory=list)
    snapshot_id: Literal[draft.CORPUS_ID] = draft.CORPUS_ID
    legal_as_of: Literal[draft.LEGAL_AS_OF] = draft.LEGAL_AS_OF
    origin_kind: Literal["phase3_design", "reviewed_numeric_derivative", "snapshot_guard"]
    origin_id: Text
    origin_sha256: SHA256
    authored_by: Literal[AUTHOR] = AUTHOR
    authored_on: date = DRAFTED_ON
    gold: GoldLabels
    temporal_provenance: reviewed.TemporalReview | None = None
    boundary_date: date | None = None
    boundary_offset_days: Literal[-1, 0, 1] | None = None
    stage_probe: Probe
    review_group_id: Text

    @model_validator(mode="after")
    def draft_safety(self):
        review = self.gold.review
        if review.status != "needs_review" or review.reviewer or review.reviewed_on:
            raise ValueError("new development gold is not independently approved")
        expected = ("regression", "known_regression") if self.origin_kind == "snapshot_guard" else ("legacy", "historically_used")
        if (self.split, self.exposure) != expected:
            raise ValueError("development exposure cannot be relabeled unseen")
        if (self.boundary_date is None) != (self.boundary_offset_days is None):
            raise ValueError("boundary needs an anchor and an offset together")
        if any(len(batch) != len(set(batch)) for batch in self.stage_probe.evidence_batches):
            raise ValueError("duplicate evidence in a batch")
        if self.origin_kind == "snapshot_guard":
            if self.stage_probe.mode != "publication_guard_probe":
                raise ValueError("blocked locator needs a guard probe, not positive replay")
            if self.gold.publication.disposition != "abstain" or self.gold.expected_coverage != "insufficient":
                raise ValueError("guard cannot publish an unsupported legal conclusion")
            if any(f.support_state != "unknown" for f in self.gold.required_facets):
                raise ValueError("guard has no positive/negative legal support")
            if any(ref.role != "context" for group in self.gold.evidence_groups for ref in group.references):
                raise ValueError("blocked locator is context only")
            if self.temporal_provenance is not None:
                raise ValueError("guard cannot inherit an unrelated continuity proof")
        elif self.stage_probe.mode == "publication_guard_probe" or self.boundary_date is not None:
            raise ValueError("unexpected guard/boundary metadata")
        if self.stage_probe.mode in {"end_to_end", "rewrite_probe"} and (
            self.stage_probe.evidence_batches or self.stage_probe.expected_pool_coverage is not None
            or self.stage_probe.missing_facet_ids
        ):
            raise ValueError("end-to-end/rewrite does not prescribe an evidence pool")
        return self


def fresh_review() -> dict:
    return {"status": "needs_review", "reviewer": None, "reviewed_on": None,
            "notes": ["Source/technical audit is not independent gold approval."]}


def from_design(parent: design.DevelopmentCase) -> DevelopmentDraftCase:
    group = {"dev_009": "B1", "dev_010": "B2"}.get(parent.id, "C1")
    return DevelopmentDraftCase.model_validate({
        "id": parent.id, "split": parent.split, "exposure": parent.exposure,
        "family_id": parent.family_id, "query_type": parent.query_type, "query": parent.query,
        "chat_history": [message.model_dump() for message in parent.chat_history],
        "origin_kind": "phase3_design", "origin_id": parent.id,
        "origin_sha256": digest(parent.model_dump(mode="json")),
        "gold": parent.gold.model_dump(mode="json"),
        "temporal_provenance": parent.temporal_provenance.model_dump(mode="json") if parent.temporal_provenance else None,
        "stage_probe": parent.stage_probe.model_dump(), "review_group_id": group,
    })


def validate_numeric(label: NumericLabel, chunk: dict) -> None:
    if not chunk["publication_eligible"] or chunk["active_at_cutoff"] is not True:
        raise ValueError("numeric source is not active/publishable")
    pattern = r"Điều khiển xe chạy quá tốc độ quy định (từ|trên) (\d+) km/h đến (dưới )?(\d+) km/h;"
    match = re.fullmatch(pattern, chunk["text"])
    if not match or chunk["article_no"] != "6":
        raise ValueError("numeric source is not the scoped car-speed rule")
    lower, upper = int(match[2]), int(match[4])
    lower_ok = label.excess_kmh >= lower if match[1] == "từ" else label.excess_kmh > lower
    upper_ok = label.excess_kmh < upper if match[3] else label.excess_kmh <= upper
    if not lower_ok or not upper_ok:
        raise ValueError("numeric query does not belong to evidence interval")
    money = re.findall(r"\d{1,3}(?:\.\d{3})+", chunk["clause_head"])
    if len(money) != 2 or [int(value.replace(".", "")) for value in money] != [label.money_min, label.money_max]:
        raise ValueError("numeric amount differs from clause head")
    query_number = re.search(r"quá tốc độ quy định (?:đúng )?(\d+) km/h", label.query)
    if not query_number or int(query_number[1]) != label.excess_kmh:
        raise ValueError("numeric label and query disagree")
    if any(value not in label.reference_answer for value in money) or chunk["display_citation"] not in label.reference_answer:
        raise ValueError("numeric answer lacks source amount or citation")


def numeric_case(label: NumericLabel, parent: reviewed.ReviewedCase, chunks: dict[str, dict], number: int) -> DevelopmentDraftCase:
    chunk = chunks[label.chunk_id]
    validate_numeric(label, chunk)
    return DevelopmentDraftCase.model_validate({
        "id": label.id, "split": "legacy", "exposure": "historically_used",
        "family_id": parent.family_id, "query_type": "penalty", "query": label.query,
        "origin_kind": "reviewed_numeric_derivative", "origin_id": parent.id,
        "origin_sha256": digest(parent.model_dump(mode="json")), "review_group_id": f"A{number}",
        "gold": {"review": fresh_review(), "reference_answer": label.reference_answer,
                 "temporal_basis": "frozen_corpus", "as_of_date": None,
                 "evidence_groups": [{"id": "g1", "description": "Leaf xác định khoảng tốc độ; clause head cung cấp tiền.",
                                      "match": "all", "references": [draft.evidence_reference(chunk, "support")]}],
                 "required_facets": [
                     {"id": "f1", "kind": "condition", "description": label.interval_description,
                      "support_state": "positive_support", "evidence_group_ids": ["g1"]},
                     {"id": "f2", "kind": "money", "description": f"Mức tiền {label.money_min:,}–{label.money_max:,} đồng, đúng chủ thể/hành vi đã nêu.",
                      "support_state": "positive_support", "evidence_group_ids": ["g1"]},
                 ], "expected_coverage": "sufficient",
                 "publication": {"disposition": "publish", "allowed_statuses": ["answered"],
                                 "rationale": "Có dữ kiện cho nhánh tiền, positive evidence tại cutoff; chưa review độc lập."},
                 "external_evidence_needed": [],
                 "failure_categories": ["answer_incorrect", "citation_unsupported", "unnecessary_abstention"]},
        "stage_probe": {"mode": "end_to_end", "assertion": "Chấm đúng biên và tiền; query chỉ hỏi tiền, không suy mức điểm hoặc kết luận âm về điểm."},
    })


def future_boundaries(chunk: dict) -> list[date]:
    cutoff = date.fromisoformat(draft.LEGAL_AS_OF)
    return sorted({date.fromisoformat(rule["effective_from"]) for rule in chunk["temporal_rules"]
                   if rule.get("effective_from") and date.fromisoformat(rule["effective_from"]) > cutoff})


def guard_reason(chunk: dict) -> str:
    return {
        "mixed_effective_date": "Đoạn chứa các phạm vi có mốc hiệu lực khác nhau và đang bị chặn dùng làm căn cứ kết luận chắc chắn; không được coi toàn đoạn là chưa hiệu lực hoặc đã áp dụng.",
        "future": "Đoạn được snapshot đánh dấu chưa hiệu lực tại cutoff và bị chặn publication. Ngày hỏi tới/sau mốc ghi trong đoạn không tự làm nguồn frozen thành căn cứ đã duyệt cho ngày đó.",
        "repealed": "Đoạn chỉ còn placeholder bãi bỏ, được giữ để truy nguyên; không có nội dung quy tắc đang áp dụng hoặc nội dung cũ đầy đủ để kết luận từ đây.",
    }[chunk["temporal_status"]]


def guard_case(chunk: dict, number: int, event_date: date, anchor: date | None = None,
               offset: int | None = None) -> DevelopmentDraftCase:
    if chunk["publication_eligible"]:
        raise ValueError("guard requires a blocked locator")
    suffix = "cutoff" if anchor is None else f"{anchor.isoformat()}_{ {-1: 'before', 0: 'on', 1: 'after'}[offset]}"
    query = (f"Tại ngày {event_date.strftime('%d/%m/%Y')}, có thể chỉ dùng đoạn {chunk['display_citation']} "
             "được cung cấp để kết luận chắc chắn nghĩa vụ hoặc chế tài tương ứng không? Chỉ xét bộ căn cứ đang có, không tự bổ sung nguồn.")
    reason = guard_reason(chunk)
    return DevelopmentDraftCase.model_validate({
        "id": f"guard_{number:02d}_{suffix}", "split": "regression", "exposure": "known_regression",
        "family_id": f"publication_guard:{chunk['id']}", "query_type": "scenario", "query": query,
        "origin_kind": "snapshot_guard", "origin_id": chunk["id"], "origin_sha256": digest(chunk),
        "boundary_date": anchor, "boundary_offset_days": offset, "review_group_id": "C1",
        "gold": {"review": fresh_review(),
                 "reference_answer": "Với đúng bộ căn cứ được cung cấp, chưa đủ cơ sở để kết luận chắc chắn. " + reason +
                     " Cần căn cứ được duyệt cho đúng phạm vi và ngày hỏi; không suy rằng không bị phạt, không có nghĩa vụ hoặc quy định cũ tiếp tục áp dụng.",
                 "temporal_basis": "frozen_corpus" if anchor is None else "explicit_date",
                 "as_of_date": None if anchor is None else event_date,
                 "evidence_groups": [{"id": "g1", "description": "Chỉ context/provenance; không chứng minh kết luận pháp lý.",
                                      "match": "all", "references": [draft.evidence_reference(chunk, "context")]}],
                 "required_facets": [{"id": "f1", "kind": "uncertainty", "description": reason,
                                      "support_state": "unknown", "evidence_group_ids": ["g1"]},
                                     {"id": "f2", "kind": "temporal", "description": "Nêu giới hạn nguồn/ngày; không tự gỡ block hoặc suy kết luận không áp dụng.",
                                      "support_state": "unknown", "evidence_group_ids": ["g1"]}],
                 "expected_coverage": "insufficient",
                 "publication": {"disposition": "abstain", "allowed_statuses": ["insufficient_evidence", "verification_failed"],
                                 "rationale": "Policy expectation cho context-only frozen pool, không phải kết luận luật tương lai."},
                 "external_evidence_needed": ["Căn cứ/provenance đã duyệt cho đúng phạm vi và ngày hỏi."],
                 "failure_categories": ["unsafe_publication", "expected_abstention"]},
        "stage_probe": {"mode": "publication_guard_probe", "evidence_batches": [[chunk["id"]]],
                        "expected_pool_coverage": "insufficient", "missing_facet_ids": ["f1", "f2"],
                        "assertion": "Locator bị block chỉ là context; không dùng ngày query, source confidence hoặc approval chung để gỡ publication block."},
    })


def validate_case(case: DevelopmentDraftCase, chunks: dict[str, dict]) -> None:
    # Re-parse to validate callers that have mutated a model in place.
    case = DevelopmentDraftCase.model_validate(case.model_dump())
    groups = {group.id: group for group in case.gold.evidence_groups}
    for group in groups.values():
        for ref in group.references:
            chunk = chunks[ref.processed_id]
            if ref.model_dump() != draft.evidence_reference(chunk, ref.role):
                raise ValueError("source reference changed")
            if ref.role == "support" and (not chunk["publication_eligible"] or chunk["active_at_cutoff"] is not True):
                raise ValueError("blocked/inactive source cannot support publication")
    pool = design.ordered_pool(case.stage_probe.evidence_batches)
    if case.origin_kind == "snapshot_guard":
        chunk = chunks[case.origin_id]
        if chunk["publication_eligible"] or case.origin_sha256 != digest(chunk) or pool != [chunk["id"]]:
            raise ValueError("guard differs from the blocked frozen source")
        refs = [ref.processed_id for group in groups.values() for ref in group.references]
        if refs != [chunk["id"]] or case.stage_probe.expected_pool_coverage != "insufficient":
            raise ValueError("guard needs matching context and insufficient pool expectation")
        if case.stage_probe.missing_facet_ids != [facet.id for facet in case.gold.required_facets if facet.required]:
            raise ValueError("guard required facets remain unsupported")
        if case.boundary_date is not None:
            if case.boundary_date not in future_boundaries(chunk):
                raise ValueError("guard boundary absent from frozen temporal rules")
            if case.gold.as_of_date != case.boundary_date + timedelta(days=case.boundary_offset_days):
                raise ValueError("guard query date is not the registered boundary offset")
        elif case.gold.temporal_basis != "frozen_corpus" or case.gold.as_of_date is not None:
            raise ValueError("cutoff guard cannot claim an unregistered query date")
    elif case.stage_probe.mode == "fixed_evidence":
        if not pool or any(not chunks[identity]["publication_eligible"] for identity in pool):
            raise ValueError("positive replay contains empty/blocked evidence")
        missing = design.missing_facets(case, pool)
        expected = "insufficient" if missing else "sufficient"
        if case.stage_probe.expected_pool_coverage != expected or case.stage_probe.missing_facet_ids != missing:
            raise ValueError("replay expectation differs from available evidence")
    if case.gold.publication.disposition == "publish":
        if case.gold.expected_coverage != "sufficient" or case.gold.external_evidence_needed:
            raise ValueError("publish needs complete source scope")
        if any(f.required and f.support_state != "positive_support" for f in case.gold.required_facets):
            raise ValueError("publish requires positive supported facets")
        if design.missing_facets(case, design.support_ids(case)):
            raise ValueError("publish lacks a required support group")


def render_evidence(used: list[str], chunks: dict[str, dict]) -> str:
    lines = ["# Căn cứ đầy đủ — development draft v1", "",
             "Source/context của snapshot đã freeze; blocked chỉ context, không là gold publishable.", ""]
    for identity in used:
        chunk = chunks[identity]
        lines.extend([f"## {identity}", "", chunk["display_citation"], "",
                      f"Publication eligible: {chunk['publication_eligible']}; temporal: {chunk['temporal_status']}.", "",
                      "```text", chunk["enriched_text"], "```", "", "Source spans:", ""])
        for span in chunk["source_spans"]:
            path = span["path"]
            lines.append(f"- [{path}:{span['line_start']}–{span['line_end']}](../../../{path})")
        if chunk["temporal_rules"]:
            lines.extend(["", "Temporal rules (metadata frozen; không tự gỡ block):", ""])
            lines.extend(f"- {rule.get('effective_from')}: {rule['scope']} — {rule['source_locator']}" for rule in chunk["temporal_rules"])
        lines.extend(["", f"Context SHA256: `{reviewed.context_hash(chunk)}`", ""])
    return "\n".join(lines) + "\n"


def review_groups(cases: Sequence[DevelopmentDraftCase]) -> list[dict]:
    groups = []
    for identity in ("A1", "A2", "A3", "A4", "B1", "B2", "C1"):
        selected = [case for case in cases if case.review_group_id == identity]
        if not selected:
            raise ValueError("review group has no cases")
        groups.append({"id": identity, "status": "needs_review", "case_ids": [case.id for case in selected],
                       "content_sha256": digest([case.model_dump(mode="json") for case in selected]),
                       "reviewer": None, "reviewed_on": None})
    members = [identity for group in groups for identity in group["case_ids"]]
    if len(members) != len(set(members)) or set(members) != {case.id for case in cases}:
        raise ValueError("review groups must cover every case once")
    return groups


def render_review(cases: Sequence[DevelopmentDraftCase], chunks: dict[str, dict], groups: list[dict]) -> str:
    lines = ["# Bản review nội dung — chỉ 7 mục cần chốt", "",
             "Tôi đã tự kiểm tra kỹ thuật và căn cứ. Bạn không cần đọc code, facet IDs, batch hoặc hash.",
             "**Chưa mục nào được tự duyệt.** Đây không phải kết quả chạy hệ thống.", "",
             "Bạn kiểm tra: tình huống có rõ không, trả lời có đúng/đủ không, và lý do giữ giới hạn có hợp lý không.",
             "Có thể phản hồi `A1–A4: Duyệt; B1–B2: Duyệt; C1: Duyệt` hoặc ghi sửa từng mục.",
             "Không cần duyệt lại 50 câu cũ. Full context tùy chọn tại [EVIDENCE.md](EVIDENCE.md).", ""]
    for case in [case for case in cases if case.review_group_id.startswith("A")]:
        lines.extend([f"## {case.review_group_id} — {case.id}", "", "**Câu hỏi:** " + case.query, "",
                      "**Đáp án dự kiến:** " + (case.gold.reference_answer or ""), "",
                      "Điểm cần kiểm: " + case.gold.required_facets[0].description, ""])
    lines.extend(["## Căn cứ chung cho A1–A4", "",
                  "Các câu chỉ hỏi tiền; không yêu cầu hoặc kết luận số điểm GPLX.", ""])
    numeric_ids = sorted({ref.processed_id for case in cases if case.review_group_id.startswith("A")
                          for group in case.gold.evidence_groups for ref in group.references})
    for identity in numeric_ids:
        chunk = chunks[identity]
        lines.extend([f"- **{chunk['display_citation']}**: {chunk['clause_head']} {chunk['text']}"])
    lines.extend(["", "Nguồn đối chiếu bổ sung: [toàn văn NĐ 168 trên Cổng Chính phủ](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-168-2024-nd-cp-quy-dinh-xu-phat-vi-pham-hanh-chinh-ve-trat-tu-atgt-duong-bo-119241231164556785.htm).",
                  "Căn cứ chấm vẫn là snapshot 22/09/2026, không nhập thêm nguồn web vào index.", ""])
    for case in [case for case in cases if case.review_group_id.startswith("B")]:
        lines.extend([f"## {case.review_group_id} — Theo dõi tình huống qua hội thoại", "",
                      "**Người dùng đã nói trước đó:**", ""])
        lines.extend(f"- {message.content}" for message in case.chat_history)
        lines.extend(["", "**Câu hỏi tiếp:** " + case.query, "", "**Đáp án dự kiến:** " + (case.gold.reference_answer or ""), "",
                      "Điểm cần kiểm: câu hỏi tiếp vẫn chỉ đúng tình huống vừa nói; không mang loại xe/hành vi của câu cũ sang.",
                      f"Đáp án/căn cứ giữ nguyên từ bài design {case.origin_id}, có lineage tới gold 50; nguồn xem EVIDENCE.md.", ""])
    lines.extend(["## C1 — Dùng lại đáp án đã duyệt và giữ chính sách an toàn", "",
                  "Đây là một quyết định về phạm vi sử dụng, không yêu cầu bạn kiểm 48 fixture kỹ thuật:", "",
                  "- 14 bài còn lại từ design giữ nguyên câu hỏi/đáp án/căn cứ đã review: thử thiếu/đủ evidence, rewrite, thiếu dữ kiện/dependency, ngày lịch sử và amendment. Không sửa kết luận pháp lý cũ; case mới vẫn cần được chấp thuận sử dụng.",
                  "- 34 guard probes chỉ kiểm tra chặn dùng 10 đoạn bị khóa, tại cutoff và trước/đúng/sau mốc tương lai đã ghi trong nguồn. Không coi chúng là 34 câu hỏi luật độc lập.",
                  "- Đoạn trộn ngày, tương lai hoặc placeholder bãi bỏ chỉ làm context. Không kết luận chắc chắn nghĩa vụ/mức phạt, không suy 'không phạt' hay luật cũ tiếp tục áp dụng. Ngày query qua mốc không tự mở block.",
                  "- Các guard/replay không cộng vào điểm end-to-end. Không tự approve gold, không mở C0–C4, không thay production hoặc tạo held-out giả unseen.", "",
                  "**Bạn cần chốt:** có đồng ý dùng lại nội dung đã duyệt và giữ các giới hạn này cho bộ development không?",
                  "Nếu muốn thay đáp án ở mục này, ghi rõ case và nội dung; sẽ tạo version mới, không sửa gold đã freeze.", "",
                  "Danh sách 10 đoạn và mốc được kiểm tra:", "",
                  "| Đoạn nguồn | Trạng thái tại cutoff | Mốc tương lai (kiểm trước/đúng/sau) |",
                  "| --- | --- | --- |"])
    blocked = sorted({case.origin_id for case in cases if case.origin_kind == "snapshot_guard"})
    for identity in blocked:
        chunk = chunks[identity]
        boundaries = ", ".join(str(value) for value in future_boundaries(chunk)) or "chỉ tại cutoff"
        status = {"mixed_effective_date": "trộn nhiều mốc, bị block", "future": "tương lai tại cutoff, bị block", "repealed": "placeholder bãi bỏ"}[chunk["temporal_status"]]
        lines.append(f"| {chunk['display_citation']} | {status} | {boundaries} |")
    lines.extend(["", "## Phạm vi của từng quyết định", "",
                  "Mỗi approval sau này sẽ gắn đúng IDs và checksum; bảng dưới là đề nghị, chưa có approval.", "",
                  "| Mục | Số đơn vị | IDs |", "| --- | --- | --- |"])
    for group in groups:
        ids = ", ".join(group["case_ids"]) if group["id"] != "C1" else "14 design fixtures còn lại + 34 guard probes (full list trong review_groups.json)"
        lines.append(f"| {group['id']} | {len(group['case_ids'])} | {ids} |")
    lines.extend(["", "Held-out chưa được tạo hoặc giữ kín. Bộ này chỉ development exposed, chưa freeze/scoring.", ""])
    return "\n".join(lines) + "\n"


def make_artifacts(directory: Path = DEFAULT_DIR) -> dict:
    design.verify_bundle()
    original_design = [design.DevelopmentCase.model_validate_json(line) for line in
                       (design.DEFAULT_DIR / "development_cases.jsonl").read_text().splitlines()]
    reviewed_cases = [reviewed.ReviewedCase.model_validate_json(line) for line in
                      (reviewed.DEFAULT_DIR / "cases.jsonl").read_text().splitlines()]
    parent = next(case for case in reviewed_cases if case.id == "current_law_036")
    chunks = {chunk["id"]: chunk for chunk in read_json(draft.DEFAULT_OUTPUT)["chunks"]}
    labels = [NumericLabel.model_validate(value) for value in read_json(directory / "numeric_labels.json")]
    if len(labels) != 4 or {label.excess_kmh for label in labels} != {9, 10, 20, 21}:
        raise ValueError("numeric suite must cover the four registered boundary inputs")
    cases = [from_design(case) for case in original_design]
    cases.extend(numeric_case(label, parent, chunks, number) for number, label in enumerate(labels, 1))
    cutoff = date.fromisoformat(draft.LEGAL_AS_OF)
    blocked = sorted((chunk for chunk in chunks.values() if not chunk["publication_eligible"]), key=lambda c: c["id"])
    for number, chunk in enumerate(blocked, 1):
        cases.append(guard_case(chunk, number, cutoff))
        for anchor in future_boundaries(chunk):
            for offset in (-1, 0, 1):
                cases.append(guard_case(chunk, number, anchor + timedelta(days=offset), anchor, offset))
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("duplicate development IDs")
    for case in cases:
        validate_case(case, chunks)
    groups = review_groups(cases)
    used = sorted({ref.processed_id for case in cases for group in case.gold.evidence_groups for ref in group.references}
                  | {identity for case in cases for identity in design.ordered_pool(case.stage_probe.evidence_batches)})
    guard_count = sum(case.origin_kind == "snapshot_guard" for case in cases)
    report = {
        "dataset_id": DATASET_ID, "technical_integrity_passed": True,
        "authored_case_count": len(cases), "numeric_count": len(labels), "guard_count": guard_count,
        "blocked_locator_count": len(blocked), "future_boundary_count": sum(len(future_boundaries(c)) for c in blocked),
        "modes": dict(Counter(case.stage_probe.mode for case in cases)),
        "review_groups": len(groups), "gold_review_status": {"needs_review": len(cases)},
        "technical_auditor": AUTHOR, "audited_on": str(DRAFTED_ON),
        "checks": ["frozen source/snapshot/gold/design integrity", "typed draft-only schema and provenance",
                   "numeric source interval/query/clause-head money", "stable evidence reference and full context hashes",
                   "blocked context-only guard and registered temporal offsets", "replay pool/facet consistency",
                   "review group exact membership/hash"],
        "scoring_ready": False, "benchmark_c0_c4_ready": False, "held_out_authored": 0,
        "model_runs": 0, "production_writes": 0, "system_stage_results": None,
    }
    technical = ["# Technical/source audit — development draft v1", "",
                 "Các check dưới đây do Codex thực hiện; **không là review pháp lý độc lập hoặc model pass**.", "",
                 f"{len(cases)} đơn vị: 16 design, 4 numeric, {guard_count} guard; tất cả needs_review.",
                 f"Modes: {report['modes']}; guard {len(blocked)} locator, {report['future_boundary_count']} mốc tương lai.", ""]
    technical.extend(f"- PASS (dataset/provenance): {check}" for check in report["checks"])
    technical.extend(["", "0 model runs, 0 production writes; chưa runner/C0–C4, chưa held-out.",
                      "Xem REVIEW.md cho 7 quyết định nội dung; owner không phải audit pool/code.", ""])
    catalog = {"snapshot_id": draft.CORPUS_ID, "chunks": [chunks[identity] for identity in used],
               "context_hashes": {identity: reviewed.context_hash(chunks[identity]) for identity in used}}
    prior_inventory = read_json(design.DEFAULT_DIR / "coverage.json")["exclusion_inventory"]
    exposure = {"families": sorted(set(prior_inventory["families"]) | {case.family_id for case in cases}),
                "articles": sorted(set(prior_inventory["articles"]) | {design.article_key(chunks[identity]) for identity in used}),
                "evidence_ids": sorted(set(prior_inventory["evidence_ids"]) | set(used)),
                "scope": "Exposed legacy/development/guard inventory; independent semantic test/prompt/output audit still required for held-out."}
    artifacts = {"cases.jsonl": "".join(case.model_dump_json() + "\n" for case in cases),
                 "case.schema.json": DevelopmentDraftCase.model_json_schema(), "evidence_catalog.json": catalog,
                 "EVIDENCE.md": render_evidence(used, chunks), "REVIEW.md": render_review(cases, chunks, groups),
                 "review_groups.json": groups, "exposure_inventory.json": exposure,
                 "technical_audit.json": report, "TECHNICAL.md": "\n".join(technical) + "\n"}
    artifacts["manifest.json"] = {
        "dataset_id": DATASET_ID, "status": "technical_draft_needs_review", "legal_as_of": draft.LEGAL_AS_OF,
        "parent_design_manifest_sha256": file_digest(design.DEFAULT_DIR / "manifest.json"),
        "parent_reviewed_manifest_sha256": file_digest(reviewed.DEFAULT_DIR / "manifest.json"),
        "snapshot_receipt_sha256": file_digest(draft.DEFAULT_RECEIPT),
        "numeric_labels_sha256": file_digest(directory / "numeric_labels.json"),
        "protocol_sha256": file_digest(PROTOCOL), "builder_sha256": file_digest(Path(__file__)),
        "artifacts": {name: hashlib.sha256(draft.artifact_bytes(value)).hexdigest() for name, value in artifacts.items()},
        "scoring_ready": False, "benchmark_c0_c4_ready": False, "held_out_authored": 0,
    }
    return artifacts


def build_bundle(directory: Path = DEFAULT_DIR) -> dict:
    artifacts = make_artifacts(directory)
    if any((directory / name).exists() for name in artifacts):
        raise FileExistsError("development artifacts exist; verify or create a new version")
    for name, value in artifacts.items():
        with (directory / name).open("xb") as stream:
            stream.write(draft.artifact_bytes(value))
    return artifacts["technical_audit.json"]


def verify_bundle(directory: Path = DEFAULT_DIR) -> dict:
    expected = make_artifacts(directory)
    for name, value in expected.items():
        path = directory / name
        if not path.is_file() or path.read_bytes() != draft.artifact_bytes(value):
            raise ValueError(f"development artifact changed: {name}")
    return expected["technical_audit.json"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "verify"])
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    report = {"build": build_bundle, "verify": verify_bundle}[args.action](args.directory)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
