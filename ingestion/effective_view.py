"""Dựng effective view kỹ thuật của Nghị định 168 sau Nghị định 238.

Artifact giữ provenance cho từng locator và fail closed nếu target/anchor không
khớp. Đây không phải văn bản hợp nhất chính thức và chưa được phép index trước
legal review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ingestion.amendment_validator import (
    ARTICLE_19_ANCHORS,
    parse_base_locators,
)
from ingestion.legal_registry import (
    DEFAULT_AMENDMENTS,
    DEFAULT_REGISTRY,
    PROJECT_ROOT,
    AmendmentMap,
    Registry,
    file_digest,
    read_json,
    write_json,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/current-law/nd168-effective-2026-09-22.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "data/legal_sources/nd168_effective_view_manifest.json"
ARTICLE_RE = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$")
CLAUSE_RE = re.compile(r"^(\d+[a-z]?)\.\s")
POINT_RE = re.compile(r"^([a-zđ]\d?)\)\s", re.IGNORECASE)

# Dòng trong supporting-text 238 đã khóa bằng SHA-256 trong registry/manifest.
SOURCE_LINES = {
    "a01-nd168-d3-k3-i": (23, 23),
    "a01-nd168-d3-k3-l": (25, 25),
    "a02-nd168-d6-k1a": (28, 28),
    "a02-nd168-d6-k3-m": (30, 30),
    "a03-nd168-d13-k8-b": (32, 32),
    "a04-nd168-d14-k3-b": (34, 34),
    "a05-nd168-d17-k2-a": (36, 36),
    "a06-nd168-d18-k4-a": (38, 38),
    "a07-nd168-d20-k5-dd": (42, 42),
    "a07-nd168-d20-k5-g": (44, 44),
    "a07-nd168-d20-k5-l": (46, 46),
    "a07-nd168-d20-k5-m": (47, 47),
    "a07-nd168-d20-k5-n": (49, 49),
    "a07-nd168-d20-k6-d": (51, 51),
    "a07-nd168-d20-k8a": (53, 53),
    "a07-nd168-d20-k10-c": (55, 55),
    "a08-nd168-d21-k2-b": (58, 58),
    "a08-nd168-d21-k3-b": (60, 60),
    "a08-nd168-d21-k5-c": (62, 62),
    "a08-nd168-d21-k8-d": (65, 65),
    "a08-nd168-d21-k8-dd": (66, 66),
    "a08-nd168-d21-k8-e": (68, 68),
    "a09-nd168-d26-k7-e": (72, 72),
    "a09-nd168-d26-k7-k": (74, 74),
    "a09-nd168-d26-k7-l": (75, 75),
    "a09-nd168-d26-k8-d": (77, 77),
    "a09-nd168-d26-k13-c": (79, 79),
    "a09-nd168-d26-k13-d": (80, 80),
    "a10-nd168-d29-k3a": (83, 85),
    "a10-nd168-d29-k4": (87, 87),
    "a11-nd168-d32-k9a": (90, 92),
    "a11-nd168-d32-k11-e": (94, 94),
    "a11-nd168-d32-k13-e": (96, 96),
    "a11-nd168-d32-k19-l": (98, 98),
    "a11-nd168-d32-k21-c": (100, 100),
    "a12-nd168-d41-k2-d": (103, 103),
    "a12-nd168-d41-k4-k1": (105, 105),
    "a12-nd168-d41-k5": (107, 109),
    "a13-nd168-d42": (111, 123),
    "a14-nd168-d43": (125, 164),
    "a15-nd168-d44": (166, 181),
    "a16-nd168-d46-k2": (183, 183),
    "a17-nd168-d50-k1-d": (186, 186),
    "a17-nd168-d50-k3-a-doan2": (188, 188),
    "a18-nd168-d53-k3": (190, 190),
    "a18-nd168-d53-k4": (191, 191),
}

FULLY_DEFERRED_EFFECTIVE_FROM = {
    (20, "5", "n"): "2029-01-01",
    (26, "7", "k"): "2029-01-01",
    (26, "7", "l"): "2029-01-01",
}

# Khoản 3 Điều 53 chỉ hoãn chế tài đối với các nhóm xe được nêu trong khoản,
# không hoãn toàn bộ nội dung của ba locator dưới đây. Vì một locator chứa cả
# phần đã hiệu lực và phần được hoãn, view phải giữ trạng thái mixed và chặn
# publication cho tới khi lớp retrieval hỗ trợ điều kiện thời gian/chủ thể.
MIXED_EFFECTIVE_DATE_RULES = {
    (20, "5", "l"): {
        "active_scope": "Xe kinh doanh vận tải hành khách từ 08 chỗ trở lên (không kể chỗ của người lái xe).",
        "deferred_scope": "Xe kinh doanh vận tải hành khách dưới 08 chỗ (không kể chỗ của người lái xe) và xe vận tải nội bộ.",
    },
    (21, "3", "b"): {
        "active_scope": "Xe kinh doanh vận tải hành khách từ 08 chỗ trở lên (không kể chỗ của người lái xe) và xe ô tô đầu kéo.",
        "deferred_scope": "Xe kinh doanh vận tải hành khách dưới 08 chỗ (không kể chỗ của người lái xe), xe kinh doanh vận tải hàng hóa trừ xe ô tô đầu kéo và xe vận tải nội bộ.",
    },
    (32, "9a", "b"): {
        "active_scope": "Chủ xe ô tô đầu kéo.",
        "deferred_scope": "Chủ xe vận tải nội bộ.",
    },
}

ARTICLE_19_SOURCE_LINES = {
    "p01": 193,
    "p02": 194,
    "p03": 195,
    "p04": 196,
    "p05": 197,
    "p06": 198,
    "p07": 199,
    "p08": 200,
    "p09": 201,
    "p10": 202,
    "p11": 203,
    "p12a": 204,
    "p12b": 204,
    "p13": 205,
    "p14": 206,
    "p15": 207,
    "p16": 208,
    "p17": 209,
}

POINT_ORDER = ["a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "k1", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "x", "y"]
POINT_RANK = {point: index for index, point in enumerate(POINT_ORDER)}


def clean_quoted_payload(lines: list[str]) -> str:
    payload = "\n".join(lines).strip()
    if payload.startswith('"'):
        payload = payload[1:]
    if payload.endswith('".') or payload.endswith('";'):
        payload = payload[:-2]
    return payload.strip()


def parse_fragment(payload: str, target: tuple[int, str | None, str | None]) -> dict[tuple, str]:
    article, clause, point = target
    rows = [line.strip() for line in payload.splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"Payload rỗng cho {target}")
    first_article = ARTICLE_RE.match(rows[0])
    first_clause = CLAUSE_RE.match(rows[0])
    first_point = POINT_RE.match(rows[0])
    if first_article:
        if int(first_article.group(1)) != article:
            raise ValueError(f"Payload sai Điều cho {target}")
        current = (article, None, None)
    elif first_clause:
        if first_clause.group(1).lower() != clause:
            raise ValueError(f"Payload sai khoản cho {target}")
        current = (article, clause, None)
    elif first_point:
        if first_point.group(1).lower() != point or clause is None:
            raise ValueError(f"Payload sai điểm cho {target}")
        current = (article, clause, point)
    else:
        raise ValueError(f"Không nhận diện được payload cho {target}: {rows[0][:80]}")

    result: dict[tuple, list[str]] = {current: [rows[0]]}
    for line in rows[1:]:
        article_match = ARTICLE_RE.match(line)
        clause_match = CLAUSE_RE.match(line)
        point_match = POINT_RE.match(line)
        if article_match:
            raise ValueError("Fragment không được chứa Điều thứ hai")
        if clause_match:
            current = (article, clause_match.group(1).lower(), None)
            result[current] = [line]
        elif point_match:
            current_clause = current[1]
            if current_clause is None:
                raise ValueError(f"Điểm không có khoản trong payload {target}")
            current = (article, current_clause, point_match.group(1).lower())
            result[current] = [line]
        else:
            result[current].append(line)
    return {locator: "\n".join(parts) for locator, parts in result.items()}


def locator_sort_key(locator: tuple[int, str | None, str | None]) -> tuple:
    article, clause, point = locator
    if clause is None:
        return article, -1, "", -1
    match = re.fullmatch(r"(\d+)([a-z]?)", clause)
    if not match:
        raise ValueError(f"Khoản không hợp lệ: {clause}")
    clause_number = int(match.group(1))
    clause_suffix = match.group(2)
    point_rank = -1 if point is None else POINT_RANK.get(point, 1000)
    return article, clause_number, clause_suffix, point_rank


def locator_label(locator: tuple[int, str | None, str | None]) -> str:
    article, clause, point = locator
    parts = []
    if point is not None:
        parts.append(f"điểm {point}")
    if clause is not None:
        parts.append(f"khoản {clause}")
    parts.append(f"Điều {article}")
    return " ".join(parts)


def hash_records(records: dict[tuple, dict]) -> str:
    payload = [
        {"locator": list(locator), "text": records[locator]["text"]}
        for locator in sorted(records, key=locator_sort_key)
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def phrase_specs(operation_id: str) -> list[tuple[str, str, str]]:
    item = next((key for key in ARTICLE_19_ANCHORS if f"-{key}-" in operation_id), None)
    specs = {
        "p01": [("after", ARTICLE_19_ANCHORS["p01"][0], ", trừ hành vi vi phạm quy định tại điểm b khoản 3a Điều 29 của Nghị định này")],
        "p02": [("after", ARTICLE_19_ANCHORS["p02"][0], " hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên")],
        "p03": [("after", ARTICLE_19_ANCHORS["p03"][0], " hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang điều khiển")],
        "p04": [("after", ARTICLE_19_ANCHORS["p04"][0], " hoặc dải dừng xe khẩn cấp")],
        "p05": [("before", ARTICLE_19_ANCHORS["p05"][0], "khoản 1; điểm d, ")],
        "p06": [("after", ARTICLE_19_ANCHORS["p06"][0], ", xe vận tải nội bộ")],
        "p07": [("after", ARTICLE_19_ANCHORS["p07"][0], ", điểm l")],
        "p08": [
            ("before", "Điều 29", "Điều 20 (điểm l khoản 5, điểm đ khoản 6), Điều 21 (điểm b khoản 3, điểm c khoản 5), "),
            ("after", "điểm n khoản 7", "; khoản 9a"),
        ],
        "p09": [("after", ARTICLE_19_ANCHORS["p09"][0], ", khoản 3, khoản 4")],
        "p10": [("replace", ARTICLE_19_ANCHORS["p10"][0], "để người nằm, ngồi, đu bám bên ngoài xe khi xe đang chạy")],
        "p11": [("replace_all", ARTICLE_19_ANCHORS["p11"][0], "chứng nhận kiểm định")],
        "p12a": [("remove", ARTICLE_19_ANCHORS["p12a"][0], "")],
        "p12b": [("remove", ARTICLE_19_ANCHORS["p12b"][0], "")],
        "p13": [("remove", ARTICLE_19_ANCHORS["p13"][0], "")],
        "p14": [("remove", ARTICLE_19_ANCHORS["p14"][0], "")],
        "p15": [("remove", ARTICLE_19_ANCHORS["p15"][0], "")],
        "p16": [("remove", ARTICLE_19_ANCHORS["p16"][0], "")],
    }
    return specs.get(item, [])


def source_lines_for_operation(operation_id: str) -> list[int]:
    if operation_id in SOURCE_LINES:
        start, end = SOURCE_LINES[operation_id]
        return [start, end]
    match = re.search(r"-p(\d+[ab]?)-", operation_id)
    if not match:
        raise ValueError(f"Không xác định được source line cho {operation_id}")
    key = f"p{match.group(1)}"
    if key not in ARTICLE_19_SOURCE_LINES:
        raise ValueError(f"Thiếu source line Điều 19 cho {operation_id}")
    line = ARTICLE_19_SOURCE_LINES[key]
    return [line, line]


def apply_phrase(text: str, mode: str, anchor: str, value: str) -> str:
    matches = list(re.finditer(re.escape(anchor), text, flags=re.IGNORECASE))
    if mode == "replace_all":
        if not matches:
            raise ValueError(f"Anchor không tồn tại: {anchor!r}")
        return re.sub(re.escape(anchor), value, text, flags=re.IGNORECASE)
    if len(matches) != 1:
        raise ValueError(f"Anchor phải xuất hiện đúng một lần: {anchor!r}, thấy {len(matches)}")
    match = matches[0]
    if mode == "before":
        result = text[: match.start()] + value + text[match.start() :]
    elif mode == "after":
        result = text[: match.end()] + value + text[match.end() :]
    elif mode == "replace":
        result = text[: match.start()] + value + text[match.end() :]
    elif mode == "remove":
        result = text[: match.start()] + text[match.end() :]
    else:
        raise ValueError(f"Phrase mode không hỗ trợ: {mode}")
    return re.sub(r" {2,}", " ", result)


def build_effective_view(
    project_root: Path = PROJECT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    amendments_path: Path = DEFAULT_AMENDMENTS,
) -> tuple[dict, dict]:
    registry = Registry.model_validate(read_json(registry_path))
    amendments = AmendmentMap.model_validate(read_json(amendments_path))
    legal_review_approved = amendments.legal_review.status == "approved"
    view_status = (
        "approved_for_snapshot_freeze"
        if legal_review_approved
        else "technical_build_passed_legal_review_pending"
    )
    documents = {document.document_id: document for document in registry.documents}
    base_document = documents[amendments.base_document_id]
    amending_document = documents[amendments.amending_document_id]
    if not base_document.extraction or not amending_document.extraction:
        raise ValueError("Nguồn 168/238 thiếu extraction")
    base_path = project_root / base_document.extraction.path
    amendment_path = project_root / amending_document.extraction.path
    source_lines = amendment_path.read_text(encoding="utf-8").splitlines()
    base_locators = parse_base_locators(base_path.read_text(encoding="utf-8"))
    records = {
        locator: {
            "text": text,
            "operation_ids": [],
            "source_document_ids": [amendments.base_document_id],
            "source_amendment_articles": [],
        }
        for locator, text in base_locators.items()
    }
    ledger = []

    for operation in amendments.operations:
        target = (operation.target_article, operation.target_clause, operation.target_point)
        before_hash = hash_records(records)
        before_text = records[target]["text"] if target in records else None
        affected_before = []
        affected_after = []

        if operation.amendment_article <= 18:
            if operation.operation_id not in SOURCE_LINES:
                raise ValueError(f"Thiếu source lines cho {operation.operation_id}")
            start, end = SOURCE_LINES[operation.operation_id]
            payload = clean_quoted_payload(source_lines[start - 1 : end])
            if operation.operation_id == "a17-nd168-d50-k3-a-doan2":
                if target not in records:
                    raise ValueError(f"Thiếu target {target}")
                old_prefix = "Trường hợp Chủ tịch Ủy ban nhân dân cấp huyện"
                old_lines = records[target]["text"].splitlines()
                matches = [line for line in old_lines if line.startswith(old_prefix)]
                if len(matches) != 1:
                    raise ValueError("Không tìm được đúng đoạn thứ hai điểm a khoản 3 Điều 50")
                old_segment = matches[0]
                records[target]["text"] = records[target]["text"].replace(old_segment, payload, 1)
                records[target]["operation_ids"].append(operation.operation_id)
                records[target]["source_document_ids"] = [amendments.base_document_id, amendments.amending_document_id]
                records[target]["source_amendment_articles"].append(operation.amendment_article)
                affected_before = [locator_label(target)]
                affected_after = [locator_label(target)]
            else:
                fragment = parse_fragment(payload, target)
                if operation.target_clause is None:
                    affected = [locator for locator in records if locator[0] == operation.target_article]
                elif operation.target_point is None:
                    affected = [
                        locator
                        for locator in records
                        if locator[0] == operation.target_article
                        and locator[1] == operation.target_clause
                    ]
                else:
                    affected = [target] if target in records else []
                if operation.operation == "add" and affected:
                    raise ValueError(f"Add target đã tồn tại: {target}")
                if operation.operation == "replace" and not affected:
                    raise ValueError(f"Replace target không tồn tại: {target}")
                affected_before = [locator_label(locator) for locator in affected]
                for locator in affected:
                    del records[locator]
                for locator, text in fragment.items():
                    if locator in records:
                        raise ValueError(f"Patch tạo locator trùng: {locator}")
                    records[locator] = {
                        "text": text,
                        "operation_ids": [operation.operation_id],
                        "source_document_ids": [amendments.base_document_id, amendments.amending_document_id],
                        "source_amendment_articles": [operation.amendment_article],
                    }
                affected_after = [locator_label(locator) for locator in fragment]
        elif operation.operation == "repeal":
            if target not in records:
                raise ValueError(f"Repeal target không tồn tại: {target}")
            affected_before = [locator_label(target)]
            del records[target]
        else:
            if target not in records:
                raise ValueError(f"Phrase target không tồn tại: {target}")
            specs = phrase_specs(operation.operation_id)
            if not specs:
                raise ValueError(f"Thiếu phrase spec cho {operation.operation_id}")
            effective_text = records[target]["text"]
            for mode, anchor, value in specs:
                try:
                    effective_text = apply_phrase(effective_text, mode, anchor, value)
                except ValueError as exc:
                    raise ValueError(f"{operation.operation_id}: {exc}") from exc
            records[target]["text"] = effective_text
            records[target]["operation_ids"].append(operation.operation_id)
            records[target]["source_document_ids"] = [amendments.base_document_id, amendments.amending_document_id]
            records[target]["source_amendment_articles"].append(operation.amendment_article)
            affected_before = [locator_label(target)]
            affected_after = [locator_label(target)]

        after_hash = hash_records(records)
        after_text = records[target]["text"] if target in records else None
        if before_hash == after_hash:
            raise ValueError(f"Operation không làm thay đổi view: {operation.operation_id}")
        ledger.append(
            {
                "operation_id": operation.operation_id,
                "operation": operation.operation,
                "amendment_article": operation.amendment_article,
                "target": {"article": target[0], "clause": target[1], "point": target[2]},
                "source_pages": operation.source_pages,
                "source_lines": source_lines_for_operation(operation.operation_id),
                "affected_before": affected_before,
                "affected_after": affected_after,
                "before_text_sha256": hashlib.sha256(before_text.encode("utf-8")).hexdigest() if before_text else None,
                "after_text_sha256": hashlib.sha256(after_text.encode("utf-8")).hexdigest() if after_text else None,
                "state_before_sha256": before_hash,
                "state_after_sha256": after_hash,
                "status": "applied",
            }
        )

    operation_effective_from = {
        operation.operation_id: operation.effective_from.isoformat()
        for operation in amendments.operations
    }
    output_records = []
    for locator in sorted(records, key=locator_sort_key):
        article, clause, point = locator
        record = records[locator]
        operation_dates = {
            operation_effective_from[operation_id]
            for operation_id in record["operation_ids"]
        }
        if len(operation_dates) > 1:
            raise ValueError(f"Locator có nhiều mốc operation chưa được mô hình hóa: {locator}")
        general_effective_from = next(iter(operation_dates), base_document.effective_from.isoformat())
        temporal_rules = []
        if locator in MIXED_EFFECTIVE_DATE_RULES:
            mixed_rule = MIXED_EFFECTIVE_DATE_RULES[locator]
            effective_from = None
            active_at_cutoff = None
            publication_eligible = False
            temporal_status = "mixed_effective_date"
            temporal_rules = [
                {
                    "effective_from": general_effective_from,
                    "scope": mixed_rule["active_scope"],
                    "source_locator": "khoản 1 Điều 20 Nghị định 238/2026/NĐ-CP",
                },
                {
                    "effective_from": "2028-01-01",
                    "scope": mixed_rule["deferred_scope"],
                    "source_locator": "khoản 3 Điều 53 Nghị định 168/2024/NĐ-CP được bổ sung bởi Điều 18 Nghị định 238/2026/NĐ-CP",
                },
            ]
        else:
            effective_from = FULLY_DEFERRED_EFFECTIVE_FROM.get(locator, general_effective_from)
            active_at_cutoff = effective_from <= registry.legal_as_of.isoformat()
            publication_eligible = active_at_cutoff
            temporal_status = "active" if active_at_cutoff else "future"
            if locator in FULLY_DEFERRED_EFFECTIVE_FROM:
                temporal_rules = [
                    {
                        "effective_from": effective_from,
                        "scope": "Toàn bộ hành vi trong locator.",
                        "source_locator": "khoản 4 Điều 53 Nghị định 168/2024/NĐ-CP được bổ sung bởi Điều 18 Nghị định 238/2026/NĐ-CP",
                    }
                ]
        citation = locator_label(locator) + " Nghị định 168/2024/NĐ-CP"
        if record["operation_ids"]:
            citation += " được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP"
        output_records.append(
            {
                "id": "nd168-effective-" + "-".join(
                    [f"d{article}", *( [f"k{clause}"] if clause else []), *( [f"p{point}"] if point else [])]
                ),
                "article": article,
                "clause": clause,
                "point": point,
                "citation": citation,
                "text": record["text"],
                "text_sha256": hashlib.sha256(record["text"].encode("utf-8")).hexdigest(),
                "effective_from": effective_from,
                "active_at_cutoff": active_at_cutoff,
                "publication_eligible": publication_eligible,
                "temporal_status": temporal_status,
                "temporal_rules": temporal_rules,
                "operation_ids": record["operation_ids"],
                "source_document_ids": record["source_document_ids"],
                "source_amendment_articles": sorted(set(record["source_amendment_articles"])),
            }
        )

    view = {
        "schema_version": 1,
        "view_id": "nd168-effective-as-of-2026-09-22",
        "legal_as_of": registry.legal_as_of.isoformat(),
        "status": view_status,
        "is_official_consolidated_document": False,
        "base_document_id": amendments.base_document_id,
        "amending_document_id": amendments.amending_document_id,
        "records": output_records,
        "patch_ledger": ledger,
    }
    active_count = sum(record["active_at_cutoff"] is True for record in output_records)
    future_records = [
        {"id": record["id"], "citation": record["citation"], "effective_from": record["effective_from"]}
        for record in output_records
        if record["temporal_status"] == "future"
    ]
    mixed_records = [
        {
            "id": record["id"],
            "citation": record["citation"],
            "temporal_rules": record["temporal_rules"],
        }
        for record in output_records
        if record["temporal_status"] == "mixed_effective_date"
    ]
    manifest = {
        "schema_version": 1,
        "view_id": view["view_id"],
        "status": view["status"],
        "legal_review_status": amendments.legal_review.status,
        "freeze_eligible": legal_review_approved,
        "inputs": {
            "registry_sha256": file_digest(registry_path),
            "amendment_map_sha256": file_digest(amendments_path),
            "base_text_sha256": file_digest(base_path),
            "amendment_text_sha256": file_digest(amendment_path),
            "builder_sha256": file_digest(Path(__file__)),
        },
        "summary": {
            "base_locator_count": len(base_locators),
            "effective_locator_count": len(output_records),
            "active_at_cutoff_count": active_count,
            "future_locator_count": len(future_records),
            "mixed_effective_date_locator_count": len(mixed_records),
            "future_or_mixed_locator_count": len(future_records) + len(mixed_records),
            "operation_count": len(amendments.operations),
            "applied_operation_count": len(ledger),
            "failed_operation_count": 0,
            "future_records": future_records,
            "mixed_effective_date_records": mixed_records,
        },
        "limitations": [
            "Đây là artifact kỹ thuật, không phải văn bản hợp nhất chính thức.",
            "Ba locator có mốc 2029 chưa active tại cutoff.",
            "Ba locator có mốc 2028 chứa đồng thời phạm vi đã hiệu lực và phạm vi được hoãn; chúng được đánh dấu mixed_effective_date và chặn publication cho tới legal review.",
            "View không tự suy luận bản cũ tiếp tục áp dụng trong thời gian chờ mốc 2028/2029.",
            (
                "Được dùng để tạo snapshot/shadow index; việc thay production index là gate riêng."
                if legal_review_approved
                else "Chưa được chunk/index hoặc dùng làm gold trước legal review."
            ),
        ],
    }
    return view, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Dựng effective view NĐ168 + NĐ238")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--amendments", type=Path, default=DEFAULT_AMENDMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    view, manifest = build_effective_view(PROJECT_ROOT, args.registry, args.amendments)
    write_json(args.output, view)
    manifest["output"] = {
        "path": str(args.output.relative_to(PROJECT_ROOT)),
        "sha256": file_digest(args.output),
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
