"""Build the deterministic processed corpus for the 2026-09-22 legal snapshot.

This module deliberately does not import the legacy chunker or index builder:
both execute filesystem/database work at import time.  It preserves the legacy
leaf/window search fields while adding explicit legal, temporal and provenance
metadata required by the current-law snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ingestion.corpus_refresh import EXPECTED_ARTICLES, extract_document_sections
from ingestion.legal_registry import (
    DEFAULT_REGISTRY,
    PROJECT_ROOT,
    LegalDocument,
    Registry,
    file_digest,
    read_json,
    write_json,
)


LEGAL_AS_OF = "2026-09-22"
CORPUS_ID = "roadlawqa-current-law-2026-09-22"
EFFECTIVE_DOCUMENT_ID = "nd168-effective-as-of-2026-09-22"
CHUNKING_CONTRACT = "legacy-leaf-window-v1+legal-provenance-v1"
DEFAULT_EFFECTIVE_VIEW = (
    PROJECT_ROOT / "data/processed/current-law/nd168-effective-2026-09-22.json"
)
DEFAULT_EFFECTIVE_MANIFEST = (
    PROJECT_ROOT / "data/legal_sources/nd168_effective_view_manifest.json"
)
DEFAULT_EFFECTIVE_REVIEW = (
    PROJECT_ROOT / "data/legal_sources/nd168_effective_view_review.json"
)
DEFAULT_SOURCE_REVIEW = PROJECT_ROOT / "data/legal_sources/source_extraction_review.json"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data/processed/current-law/current-law-chunks-2026-09-22.json"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "data/processed/current-law/current-law-corpus-manifest-2026-09-22.json"
)

MAX_TOKENS_LEAF = 1500
WINDOW_TOKENS = 900
WINDOW_OVERLAP_TOKENS = 300
MAX_HEAD_CHARS = 400

ARTICLE_RE = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$")
CLAUSE_RE = re.compile(r"^(\d+[a-z]?)\.\s", re.IGNORECASE)
POINT_RE = re.compile(r"^([a-zđ]\d?)\)\s", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^(Chương\s+[IVXLC]+)\.?\s*(.*)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^(Mục\s+\d+)\.?\s*(.*)$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-•]\s+", re.MULTILINE)
VIETNAMESE_DATE_RE = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE,
)
REPEALED_LAW_LOCATORS = {
    ("49-vbhn-vpqh", 10, "4", None),
    ("49-vbhn-vpqh", 83, None, None),
    ("55-vbhn-vpqh", 62, "7", None),
}


class CorpusModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemporalRule(CorpusModel):
    effective_from: date
    scope: str
    source_locator: str


class SourceSpan(CorpusModel):
    document_id: str
    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered_lines(self):
        if self.line_end < self.line_start:
            raise ValueError("source span has reversed lines")
        return self


class CurrentLawChunk(CorpusModel):
    id: str
    ordinal: int = Field(ge=0)
    corpus_id: Literal[CORPUS_ID]
    granularity: Literal["leaf", "leaf_window"]
    law: str
    law_code: str
    chapter: str
    section: str
    article_no: str
    article_title: str
    clause_no: str | None = None
    point: str | None = None
    bullet_idx: int | None = Field(default=None, ge=1)
    header: str
    display_citation: str
    path: str
    path_text: str
    clause_head: str
    text: str
    enriched_text: str
    source_file: str
    source_path: str
    document_id: str
    artifact_kind: Literal["official_consolidation", "technical_effective_view"]
    is_official_consolidated_document: bool
    legal_as_of: Literal[LEGAL_AS_OF]
    effective_from: date | None = None
    effective_to: date | None = None
    active_at_cutoff: bool | None = None
    temporal_status: Literal["active", "future", "mixed_effective_date", "repealed"]
    publication_eligible: bool
    temporal_rules: list[TemporalRule] = Field(default_factory=list)
    source_locator: str
    source_document_ids: list[str]
    lineage_document_ids: list[str] = Field(default_factory=list)
    amending_document_ids: list[str] = Field(default_factory=list)
    operation_ids: list[str] = Field(default_factory=list)
    source_amendment_articles: list[int] = Field(default_factory=list)
    source_footnote_ids: list[int] = Field(default_factory=list)
    source_spans: list[SourceSpan]
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def legal_contract(self):
        if not self.text.strip() or not self.enriched_text.strip():
            raise ValueError("chunk text must not be empty")
        if not self.display_citation.strip() or not self.source_locator.strip():
            raise ValueError("chunk citation must not be empty")
        if not self.source_document_ids or not self.source_spans:
            raise ValueError("chunk provenance must not be empty")
        if self.publication_eligible and self.active_at_cutoff is not True:
            raise ValueError("only active chunks can be publication eligible")
        if self.temporal_status == "mixed_effective_date":
            if self.active_at_cutoff is not None or self.publication_eligible:
                raise ValueError("mixed-date chunks must fail closed")
            if len(self.temporal_rules) < 2:
                raise ValueError("mixed-date chunks require scoped temporal rules")
        if self.temporal_status == "repealed" and (
            self.active_at_cutoff is not False or self.publication_eligible
        ):
            raise ValueError("repealed chunks must not be active or publishable")
        return self


@dataclass(frozen=True)
class LocatorNode:
    article: int
    clause: str | None
    point: str | None
    text: str
    line_start: int
    line_end: int
    chapter: str
    section: str
    article_title: str

    @property
    def locator(self) -> tuple[int, str | None, str | None]:
        return self.article, self.clause, self.point


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def strip_structural_tail(value: str) -> str:
    """Remove chapter/section headings captured before the next article anchor."""
    result = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if CHAPTER_RE.match(line) or SECTION_RE.match(line):
            break
        result.append(raw_line)
    return "\n".join(result).strip()


def normalized_match(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip().casefold()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_count(value: str) -> int:
    return len(re.findall(r"\S+", value or ""))


def sliding_windows_by_tokens(
    value: str,
    window_tokens: int = WINDOW_TOKENS,
    overlap_tokens: int = WINDOW_OVERLAP_TOKENS,
) -> list[str]:
    tokens = re.findall(r"\S+|\s+", value)
    words = [index for index, token in enumerate(tokens) if not token.isspace()]
    if not words:
        return [value.strip()] if value.strip() else []
    result: list[str] = []
    step = max(1, window_tokens - overlap_tokens)
    position = 0
    while position < len(words):
        end = min(position + window_tokens, len(words))
        window = "".join(tokens[words[position] : words[end - 1] + 1]).strip()
        if window:
            result.append(window)
        if end == len(words):
            break
        position += step
    return result


def truncate(value: str, max_chars: int = MAX_HEAD_CHARS) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value if len(value) <= max_chars else value[:max_chars].rstrip() + "…"


def parse_document_nodes(
    text: str,
    expected_last: int,
) -> tuple[dict[tuple[int, str | None, str | None], LocatorNode], dict[int, dict[str, str]]]:
    """Parse structural nodes and their exact source line spans."""
    source_text = unicodedata.normalize(
        "NFC", text.replace("\r\n", "\n").replace("\r", "\n")
    )
    lines = source_text.splitlines()
    article_context: dict[int, dict[str, str]] = {}
    chapter = ""
    section = ""
    expected = 1
    for raw_line in lines:
        line = re.sub(r"[ \t\f\v]+", " ", raw_line).strip()
        chapter_match = CHAPTER_RE.match(line)
        section_match = SECTION_RE.match(line)
        article_match = ARTICLE_RE.match(line)
        if chapter_match:
            chapter = chapter_match.group(1) + (
                ". " + chapter_match.group(2) if chapter_match.group(2) else ""
            )
            section = ""
        elif section_match:
            section = section_match.group(1) + (
                ". " + section_match.group(2) if section_match.group(2) else ""
            )
        elif article_match and int(article_match.group(1)) == expected:
            article_context[expected] = {"chapter": chapter, "section": section}
            expected += 1
            if expected > expected_last:
                break
    if expected != expected_last + 1:
        raise ValueError(f"Only found document articles 1-{expected - 1}; expected 1-{expected_last}")

    sections = extract_document_sections(source_text, expected_last)
    nodes: dict[tuple[int, str | None, str | None], LocatorNode] = {}
    for article_section in sections:
        article = article_section["article"]
        title = article_section["title"]
        context = article_context[article]
        section_lines = article_section["text"].strip().splitlines()
        section_start = article_section["source_line_start"]
        current = (article, None, None)
        buffers: dict[tuple[int, str | None, str | None], list[str]] = {
            current: [section_lines[0].strip()]
        }
        starts = {current: section_start}
        ends = {current: section_start}
        for offset, raw_line in enumerate(section_lines[1:], start=1):
            line = re.sub(r"[ \t\f\v]+", " ", raw_line).strip()
            if not line:
                continue
            line_number = section_start + offset
            clause_match = CLAUSE_RE.match(line)
            point_match = POINT_RE.match(line)
            if CHAPTER_RE.match(line) or SECTION_RE.match(line):
                break
            if clause_match:
                current = (article, clause_match.group(1).lower(), None)
                buffers[current] = [line]
                starts[current] = line_number
            elif point_match and current[1] is not None:
                current = (article, current[1], point_match.group(1).lower())
                buffers[current] = [line]
                starts[current] = line_number
            else:
                buffers[current].append(line)
            ends[current] = line_number
        for locator, parts in buffers.items():
            nodes[locator] = LocatorNode(
                article=locator[0],
                clause=locator[1],
                point=locator[2],
                text="\n".join(parts),
                line_start=starts[locator],
                line_end=ends[locator],
                chapter=context["chapter"],
                section=context["section"],
                article_title=title,
            )
    return nodes, article_context


def locate_footnote_references(
    text: str,
    footnotes: dict,
    nodes: dict[tuple[int, str | None, str | None], LocatorNode],
) -> tuple[dict[tuple[int, str | None, str | None], list[dict]], dict]:
    """Map ordered DOCX footnote references back to the deepest structural node."""
    references: dict[tuple[int, str | None, str | None], list[dict]] = {}
    cursor = 0
    matched = 0
    heading_only = 0
    unmatched: list[int] = []
    for note in footnotes["notes"]:
        for context in note["reference_contexts"]:
            position = text.find(context, cursor)
            if position < 0:
                position = text.find(context)
            if position < 0:
                unmatched.append(note["footnote_id"])
                continue
            cursor = position + len(context)
            line = text.count("\n", 0, position) + 1
            candidates = [
                node
                for node in nodes.values()
                if node.line_start <= line <= node.line_end
            ]
            if not candidates:
                # Chapter/section heading footnotes document consolidation metadata,
                # not a body rule. They remain covered in the footnote artifact.
                heading_only += 1
                matched += 1
                continue
            node = max(
                candidates,
                key=lambda item: (
                    item.point is not None,
                    item.clause is not None,
                    -item.line_end + item.line_start,
                ),
            )
            references.setdefault(node.locator, []).append(note)
            matched += 1
    total = sum(len(note["reference_contexts"]) for note in footnotes["notes"])
    report = {
        "footnote_count": footnotes["footnote_count"],
        "reference_count": total,
        "matched_reference_count": matched,
        "heading_only_reference_count": heading_only,
        "unmatched_footnote_ids": sorted(set(unmatched)),
        "passed": matched == total and not unmatched,
    }
    return references, report


def is_ancestor(
    ancestor: tuple[int, str | None, str | None],
    locator: tuple[int, str | None, str | None],
) -> bool:
    if ancestor[0] != locator[0]:
        return False
    if ancestor[1] is not None and ancestor[1] != locator[1]:
        return False
    if ancestor[2] is not None and ancestor[2] != locator[2]:
        return False
    return True


def effective_date_from_note(note: dict) -> str | None:
    dates = []
    for match in VIETNAMESE_DATE_RE.finditer(note["text"]):
        day, month, year = map(int, match.groups())
        dates.append(date(year, month, day).isoformat())
    return max(dates) if dates else None


def article_body(node: LocatorNode) -> str:
    lines = node.text.splitlines()
    return "\n".join(lines[1:]).strip()


def clause_head(node: LocatorNode | None) -> str:
    if node is None:
        return ""
    return truncate(CLAUSE_RE.sub("", node.text, count=1))


def point_body(value: str) -> str:
    return POINT_RE.sub("", value, count=1).strip()


def split_bullets(value: str) -> list[str]:
    matches = list(BULLET_RE.finditer(value or ""))
    result: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        result.append(BULLET_RE.sub("", value[match.start() : end], count=1).strip())
    return [item for item in result if item]


def build_path(
    chapter: str,
    section: str,
    article: int,
    clause: str | None,
    point: str | None,
    bullet: int | None,
) -> str:
    parts = [item for item in (chapter, section) if item]
    parts.append(f"Điều {article}")
    if clause is not None:
        parts.append(f"Khoản {clause}")
    if point is not None:
        parts.append(f"Điểm {point}")
    if bullet is not None:
        parts.append(f"Gạch {bullet}")
    return " > ".join(parts)


def header_of(
    article: int,
    clause: str | None,
    point: str | None,
    bullet: int | None,
) -> str:
    parts = []
    if bullet is not None:
        parts.append(f"Gạch {bullet}")
    if point is not None:
        parts.append(f"Điểm {point}")
    if clause is not None:
        parts.append(f"Khoản {clause}")
    parts.append(f"Điều {article}")
    return " ".join(parts)


def citation_of(
    symbol: str,
    article: int,
    clause: str | None,
    point: str | None,
    bullet: int | None,
) -> str:
    parts = []
    if bullet is not None:
        parts.append(f"gạch {bullet}")
    if point is not None:
        parts.append(f"điểm {point}")
    if clause is not None:
        parts.append(f"khoản {clause}")
    parts.append(f"Điều {article} {symbol}")
    return " ".join(parts)


def enriched_text(
    *,
    chapter: str,
    article: int,
    article_title: str,
    clause: str | None,
    clause_heading: str,
    point: str | None,
    point_text: str | None,
    text: str,
    bullet: int | None,
) -> str:
    parts = []
    if chapter:
        parts.append(f"[CHAPTER] {chapter}")
    parts.append(f"[ARTICLE] Điều {article}. {article_title}".rstrip())
    if clause is not None:
        parts.append(
            f"[CLAUSE] Khoản {clause}. {clause_heading}"
            if clause_heading
            else f"[CLAUSE] Khoản {clause}"
        )
    if point is not None:
        parts.append(
            f"[POINT] Điểm {point}) {point_text}"
            if point_text
            else f"[POINT] Điểm {point})"
        )
    if text and (bullet is not None or point is None):
        parts.append(text)
    return "\n".join(parts).strip()


def stable_chunk_id(
    document_id: str,
    article: int,
    clause: str | None,
    point: str | None,
    bullet: int | None,
) -> str:
    value = f"{document_id}-d{article}"
    if clause is not None:
        value += f"-k{clause}"
    if point is not None:
        value += f"-p{point}"
    if bullet is not None:
        value += f"-b{bullet}"
    return value


def terminal_locators(
    nodes: dict[tuple[int, str | None, str | None], Any],
) -> list[tuple[int, str | None, str | None]]:
    locators = set(nodes)
    result = []
    for locator in sorted(
        locators,
        key=lambda value: (value[0], value[1] or "", value[2] or ""),
    ):
        article, clause, point = locator
        if point is not None:
            result.append(locator)
        elif clause is not None and not any(
            candidate[0] == article
            and candidate[1] == clause
            and candidate[2] is not None
            for candidate in locators
        ):
            result.append(locator)
        elif clause is None and not any(
            candidate[0] == article and candidate[1] is not None for candidate in locators
        ):
            result.append(locator)
    return result


def indexable_law_locators(
    document_id: str,
    nodes: dict[tuple[int, str | None, str | None], LocatorNode],
) -> list[tuple[int, str | None, str | None]]:
    """Legacy leaves plus article preambles that precede numbered clauses."""
    result = {
        locator
        for locator in terminal_locators(nodes)
        if locator[1] is not None or article_body(nodes[locator])
    }
    result.update(
        locator
        for locator, node in nodes.items()
        if locator[1] is None and article_body(node)
    )
    result.update(
        (article, clause, point)
        for repealed_document_id, article, clause, point in REPEALED_LAW_LOCATORS
        if repealed_document_id == document_id
        if (article, clause, point) in nodes
    )
    return sorted(result, key=effective_locator_sort_key)


def emit_chunks(base: dict, output: list[dict]) -> None:
    value = base["enriched_text"]
    windows = (
        sliding_windows_by_tokens(value)
        if token_count(value) > MAX_TOKENS_LEAF
        else [value]
    )
    base_id = base["id"]
    for number, window in enumerate(windows, start=1):
        record = dict(base)
        if len(windows) > 1:
            record["id"] = f"{base_id}-w{number}"
            record["granularity"] = "leaf_window"
            record["enriched_text"] = window
        record["content_sha256"] = sha256_text(record["enriched_text"])
        output.append(record)


def law_default_effective_from(document_id: str, locator: tuple[int, str | None, str | None]) -> str:
    article, clause, point = locator
    if document_id == "49-vbhn-vpqh":
        early = (
            (article == 42 and clause == "2" and point in {"a", "b"})
            or article in {43, 50}
            or (article == 84 and clause == "1")
        )
        return "2024-10-01" if early else "2025-01-01"
    if document_id == "55-vbhn-vpqh" and article == 10 and clause == "3":
        return "2026-07-01"
    return "2025-01-01"


def law_temporal_metadata(
    document_id: str,
    locator: tuple[int, str | None, str | None],
    notes: Sequence[dict],
) -> dict:
    if (document_id, *locator) in REPEALED_LAW_LOCATORS:
        repeal_dates = [
            value for note in notes if (value := effective_date_from_note(note))
        ]
        if not repeal_dates:
            raise ValueError(f"repealed locator lacks dated footnote provenance: {locator}")
        repeal_date = max(repeal_dates)
        return {
            "effective_from": law_default_effective_from(document_id, locator),
            "effective_to": (
                date.fromisoformat(repeal_date) - timedelta(days=1)
            ).isoformat(),
            "active_at_cutoff": False,
            "temporal_status": "repealed",
            "publication_eligible": False,
            "temporal_rules": [
                {
                    "effective_from": repeal_date,
                    "scope": "Locator bị bãi bỏ toàn bộ theo footnote của văn bản hợp nhất.",
                    "source_locator": f"footnote VBHN tại {document_id}",
                }
            ],
        }
    if document_id == "55-vbhn-vpqh" and locator == (35, "2", None):
        return {
            "effective_from": None,
            "effective_to": None,
            "active_at_cutoff": None,
            "temporal_status": "mixed_effective_date",
            "publication_eligible": False,
            "temporal_rules": [
                {
                    "effective_from": "2026-07-01",
                    "scope": (
                        "Các nghĩa vụ tại khoản 2 Điều 35 không thuộc hai phạm vi "
                        "được khoản 2a Điều 88 hoãn riêng."
                    ),
                    "source_locator": "khoản 2 và khoản 2a Điều 88 55/VBHN-VPQH",
                },
                {
                    "effective_from": "2028-01-01",
                    "scope": (
                        "Thiết bị ghi nhận hình ảnh người lái xe đối với xe kinh doanh "
                        "vận tải hành khách dưới 08 chỗ, xe kinh doanh vận tải hàng hóa "
                        "trừ xe đầu kéo và xe vận tải nội bộ."
                    ),
                    "source_locator": "khoản 2a Điều 88 55/VBHN-VPQH",
                },
                {
                    "effective_from": "2029-01-01",
                    "scope": (
                        "Thiết bị ghi nhận hình ảnh khoang chở khách đối với xe kinh "
                        "doanh vận tải hành khách từ 08 chỗ trở lên."
                    ),
                    "source_locator": "khoản 2a Điều 88 55/VBHN-VPQH",
                },
            ],
        }
    candidates = [law_default_effective_from(document_id, locator)]
    candidates.extend(value for note in notes if (value := effective_date_from_note(note)))
    effective_from = max(candidates)
    active = effective_from <= LEGAL_AS_OF
    return {
        "effective_from": effective_from,
        "effective_to": None,
        "active_at_cutoff": active,
        "temporal_status": "active" if active else "future",
        "publication_eligible": active,
        "temporal_rules": [],
    }


def build_law_chunks(
    project_root: Path,
    document: LegalDocument,
) -> tuple[list[dict], dict]:
    if not document.extraction:
        raise ValueError(f"{document.document_id}: missing extraction")
    source_path = project_root / document.extraction.path
    source_text = source_path.read_text(encoding="utf-8", errors="strict")
    nodes, _ = parse_document_nodes(
        source_text, EXPECTED_ARTICLES[document.document_id]
    )
    footnote_path = source_path.parent / "footnotes.json"
    footnotes = read_json(footnote_path)
    footnote_refs, footnote_report = locate_footnote_references(
        source_text, footnotes, nodes
    )
    if not footnote_report["passed"]:
        raise ValueError(f"{document.document_id}: unresolved footnote references")

    lineage = [relation.target_document_id for relation in document.relations]
    base_lineage = next(
        item
        for item in lineage
        if item in {"35-2024-qh15", "36-2024-qh15"}
    )
    chunks: list[dict] = []
    indexable = indexable_law_locators(document.document_id, nodes)
    covered_locators = set()
    for locator in indexable:
        node = nodes[locator]
        article, clause, point = locator
        if point is not None:
            body = point_body(node.text)
        elif clause is not None:
            body = node.text.strip()
        else:
            body = article_body(node)
            if not body and (document.document_id, *locator) in REPEALED_LAW_LOCATORS:
                body = node.article_title
            if not body:
                continue

        inherited_notes = [
            note
            for annotated_locator, notes in footnote_refs.items()
            if is_ancestor(annotated_locator, locator)
            for note in notes
        ]
        temporal = law_temporal_metadata(document.document_id, locator, inherited_notes)
        amending_ids = ["118-2025-qh15"] if inherited_notes else []
        source_document_ids = list(
            dict.fromkeys([document.document_id, base_lineage, *amending_ids])
        )
        clause_node = nodes.get((article, clause, None)) if clause else None
        bullets = split_bullets(body) if point is not None else []
        leaves = list(enumerate(bullets, start=1)) if bullets else [(None, body)]
        for bullet, leaf_text in leaves:
            citation = citation_of(document.symbol, article, clause, point, bullet)
            point_text = leaf_text if point is not None and bullet is None else None
            enriched = enriched_text(
                chapter=node.chapter,
                article=article,
                article_title=node.article_title,
                clause=clause,
                clause_heading=clause_head(clause_node),
                point=point,
                point_text=point_text,
                text=leaf_text,
                bullet=bullet,
            )
            path = build_path(node.chapter, node.section, article, clause, point, bullet)
            base = {
                "id": stable_chunk_id(document.document_id, article, clause, point, bullet),
                "ordinal": 0,
                "corpus_id": CORPUS_ID,
                "granularity": "leaf",
                "law": f"{document.title} ({document.symbol})",
                "law_code": document.document_id.upper(),
                "chapter": node.chapter,
                "section": node.section,
                "article_no": str(article),
                "article_title": node.article_title,
                "clause_no": clause,
                "point": point,
                "bullet_idx": bullet,
                "header": header_of(article, clause, point, bullet),
                "display_citation": citation,
                "path": path,
                "path_text": path,
                "clause_head": clause_head(clause_node),
                "text": leaf_text,
                "enriched_text": enriched,
                "source_file": source_path.name,
                "source_path": str(source_path.relative_to(project_root)),
                "document_id": document.document_id,
                "artifact_kind": "official_consolidation",
                "is_official_consolidated_document": True,
                "legal_as_of": LEGAL_AS_OF,
                "source_locator": citation,
                "source_document_ids": source_document_ids,
                "lineage_document_ids": lineage,
                "amending_document_ids": amending_ids,
                "operation_ids": [],
                "source_amendment_articles": [],
                "source_footnote_ids": sorted(
                    {note["footnote_id"] for note in inherited_notes}
                ),
                "source_spans": [
                    {
                        "document_id": document.document_id,
                        "path": str(source_path.relative_to(project_root)),
                        "line_start": node.line_start,
                        "line_end": node.line_end,
                    }
                ],
                "source_text_sha256": sha256_text(node.text),
                **temporal,
            }
            emit_chunks(base, chunks)
            covered_locators.add(locator)

    return chunks, {
        "document_id": document.document_id,
        "symbol": document.symbol,
        "article_count": EXPECTED_ARTICLES[document.document_id],
        "article_coverage_passed": {
            node.article for node in nodes.values()
        } == set(range(1, EXPECTED_ARTICLES[document.document_id] + 1)),
        "indexable_locator_count": len(indexable),
        "covered_locator_count": len(covered_locators),
        "locator_coverage_passed": covered_locators == set(indexable),
        "chunk_count": len(chunks),
        "source_sha256": file_digest(source_path),
        "footnotes_sha256": file_digest(footnote_path),
        "footnote_mapping": footnote_report,
    }


def effective_locator_sort_key(locator: tuple[int, str | None, str | None]) -> tuple:
    article, clause, point = locator
    clause_match = re.fullmatch(r"(\d+)([a-z]?)", clause or "0")
    clause_key = (
        int(clause_match.group(1)),
        clause_match.group(2),
    ) if clause_match else (0, clause or "")
    point_order = {
        value: index
        for index, value in enumerate(
            ["a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "k1", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "x", "y"]
        )
    }
    return article, *clause_key, -1 if point is None else point_order.get(point, 999)


def build_effective_chunks(
    project_root: Path,
    registry: Registry,
    view_path: Path = DEFAULT_EFFECTIVE_VIEW,
) -> tuple[list[dict], dict]:
    view = read_json(view_path)
    if view["legal_as_of"] != LEGAL_AS_OF or view["is_official_consolidated_document"]:
        raise ValueError("effective view identity/official status is invalid")
    documents = {document.document_id: document for document in registry.documents}
    base_document = documents[view["base_document_id"]]
    if not base_document.extraction:
        raise ValueError("base decree extraction is missing")
    base_path = project_root / base_document.extraction.path
    base_nodes, _ = parse_document_nodes(
        base_path.read_text(encoding="utf-8"), EXPECTED_ARTICLES[base_document.document_id]
    )
    records = {
        (record["article"], record["clause"], record["point"]): record
        for record in view["records"]
    }
    ledger = {item["operation_id"]: item for item in view["patch_ledger"]}
    chunks: list[dict] = []
    indexable = sorted(terminal_locators(records), key=effective_locator_sort_key)
    covered_locators = set()
    for locator in indexable:
        record = records[locator]
        article, clause, point = locator
        raw_text = strip_structural_tail(record["text"])
        if point is not None:
            body = point_body(raw_text)
        elif clause is not None:
            body = raw_text.strip()
        else:
            body = "\n".join(raw_text.splitlines()[1:]).strip()
            if not body:
                continue
        context = base_nodes.get(locator) or base_nodes.get((article, None, None))
        if context is None:
            raise ValueError(f"No base structural context for effective locator {locator}")
        article_record = records[(article, None, None)]
        article_title_match = ARTICLE_RE.match(article_record["text"].splitlines()[0])
        article_title = article_title_match.group(2).strip() if article_title_match else ""
        clause_record = records.get((article, clause, None)) if clause else None
        clause_node = (
            LocatorNode(
                article=article,
                clause=clause,
                point=None,
                text=strip_structural_tail(clause_record["text"]),
                line_start=context.line_start,
                line_end=context.line_end,
                chapter=context.chapter,
                section=context.section,
                article_title=article_title,
            )
            if clause_record
            else None
        )
        source_spans = []
        if locator in base_nodes:
            source_spans.append(
                {
                    "document_id": base_document.document_id,
                    "path": str(base_path.relative_to(project_root)),
                    "line_start": base_nodes[locator].line_start,
                    "line_end": base_nodes[locator].line_end,
                }
            )
        amendment_path = documents[view["amending_document_id"]].extraction.path
        for operation_id in record["operation_ids"]:
            item = ledger[operation_id]
            source_spans.append(
                {
                    "document_id": view["amending_document_id"],
                    "path": amendment_path,
                    "line_start": item["source_lines"][0],
                    "line_end": item["source_lines"][1],
                }
            )
        if not source_spans:
            raise ValueError(f"Effective locator has no source span: {locator}")

        bullets = split_bullets(body) if point is not None else []
        leaves = list(enumerate(bullets, start=1)) if bullets else [(None, body)]
        for bullet, leaf_text in leaves:
            citation = record["citation"]
            if bullet is not None:
                citation = f"gạch {bullet} {citation}"
            point_text = leaf_text if point is not None and bullet is None else None
            enriched = enriched_text(
                chapter=context.chapter,
                article=article,
                article_title=article_title,
                clause=clause,
                clause_heading=clause_head(clause_node),
                point=point,
                point_text=point_text,
                text=leaf_text,
                bullet=bullet,
            )
            path = build_path(context.chapter, context.section, article, clause, point, bullet)
            base = {
                "id": stable_chunk_id(view["view_id"], article, clause, point, bullet),
                "ordinal": 0,
                "corpus_id": CORPUS_ID,
                "granularity": "leaf",
                "law": "Nghị định 168/2024/NĐ-CP",
                "law_code": "ND168-2024-EFFECTIVE-20260922",
                "chapter": context.chapter,
                "section": context.section,
                "article_no": str(article),
                "article_title": article_title,
                "clause_no": clause,
                "point": point,
                "bullet_idx": bullet,
                "header": header_of(article, clause, point, bullet),
                "display_citation": citation,
                "path": path,
                "path_text": path,
                "clause_head": clause_head(clause_node),
                "text": leaf_text,
                "enriched_text": enriched,
                "source_file": view_path.name,
                "source_path": str(view_path.relative_to(project_root)),
                "document_id": view["view_id"],
                "artifact_kind": "technical_effective_view",
                "is_official_consolidated_document": False,
                "legal_as_of": LEGAL_AS_OF,
                "effective_from": record["effective_from"],
                "effective_to": None,
                "active_at_cutoff": record["active_at_cutoff"],
                "temporal_status": record["temporal_status"],
                "publication_eligible": record["publication_eligible"],
                "temporal_rules": record["temporal_rules"],
                "source_locator": record["citation"],
                "source_document_ids": record["source_document_ids"],
                "lineage_document_ids": [],
                "amending_document_ids": (
                    [view["amending_document_id"]] if record["operation_ids"] else []
                ),
                "operation_ids": record["operation_ids"],
                "source_amendment_articles": record["source_amendment_articles"],
                "source_footnote_ids": [],
                "source_spans": source_spans,
                "source_text_sha256": record["text_sha256"],
            }
            emit_chunks(base, chunks)
            covered_locators.add(locator)

    return chunks, {
        "document_id": view["view_id"],
        "symbol": "168/2024/NĐ-CP + overlay 238/2026/NĐ-CP",
        "article_count": EXPECTED_ARTICLES[base_document.document_id],
        "article_coverage_passed": {
            locator[0] for locator in records
        } == set(range(1, EXPECTED_ARTICLES[base_document.document_id] + 1)),
        "effective_locator_count": len(view["records"]),
        "indexable_locator_count": len(indexable),
        "covered_locator_count": len(covered_locators),
        "locator_coverage_passed": covered_locators == set(indexable),
        "chunk_count": len(chunks),
        "source_sha256": file_digest(view_path),
        "blocked_locator_count": sum(
            not record["publication_eligible"] for record in view["records"]
        ),
    }


def validate_corpus(corpus: dict) -> dict:
    chunks = corpus["chunks"]
    ids = [chunk["id"] for chunk in chunks]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("duplicate_chunk_id")
    if [chunk["ordinal"] for chunk in chunks] != list(range(len(chunks))):
        errors.append("ordinal_sequence")
    if any(chunk["legal_as_of"] != LEGAL_AS_OF for chunk in chunks):
        errors.append("legal_as_of")
    if any(not chunk["display_citation"].strip() for chunk in chunks):
        errors.append("citation")
    if any(not chunk["source_spans"] for chunk in chunks):
        errors.append("source_spans")
    if any(
        any(
            CHAPTER_RE.match(line.strip()) or SECTION_RE.match(line.strip())
            for line in chunk["text"].splitlines()
        )
        for chunk in chunks
    ):
        errors.append("structural_heading_leak")
    if any(
        not report.get("article_coverage_passed", True)
        or not report.get("locator_coverage_passed", True)
        for report in corpus["documents"]
    ):
        errors.append("article_or_locator_coverage")

    blocked_nd168 = {
        ("20", "5", "l"),
        ("20", "5", "n"),
        ("21", "3", "b"),
        ("26", "7", "k"),
        ("26", "7", "l"),
        ("32", "9a", "b"),
    }
    actual_blocked_nd168 = {
        (chunk["article_no"], chunk["clause_no"], chunk["point"])
        for chunk in chunks
        if chunk["document_id"] == EFFECTIVE_DOCUMENT_ID
        and not chunk["publication_eligible"]
    }
    if actual_blocked_nd168 != blocked_nd168:
        errors.append("nd168_publication_blocks")
    law_55_mixed = [
        chunk
        for chunk in chunks
        if chunk["document_id"] == "55-vbhn-vpqh"
        and (chunk["article_no"], chunk["clause_no"], chunk["point"])
        == ("35", "2", None)
    ]
    if len(law_55_mixed) != 1 or law_55_mixed[0]["temporal_status"] != "mixed_effective_date" or law_55_mixed[0]["publication_eligible"]:
        errors.append("law_55_article_35_temporal_block")

    expected_documents = {
        "49-vbhn-vpqh",
        "55-vbhn-vpqh",
        EFFECTIVE_DOCUMENT_ID,
    }
    if {chunk["document_id"] for chunk in chunks} != expected_documents:
        errors.append("document_membership")
    return {
        "passed": not errors,
        "errors": errors,
        "chunk_count": len(chunks),
        "unique_id_count": len(set(ids)),
        "publication_eligible_count": sum(
            chunk["publication_eligible"] for chunk in chunks
        ),
        "publication_blocked_count": sum(
            not chunk["publication_eligible"] for chunk in chunks
        ),
        "temporal_status_counts": {
            status: sum(chunk["temporal_status"] == status for chunk in chunks)
            for status in ("active", "future", "mixed_effective_date", "repealed")
        },
    }


def build_current_law_corpus(
    project_root: Path = PROJECT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    effective_view_path: Path = DEFAULT_EFFECTIVE_VIEW,
) -> tuple[dict, dict]:
    registry = Registry.model_validate(read_json(registry_path))
    if registry.legal_as_of.isoformat() != LEGAL_AS_OF:
        raise ValueError("registry cutoff does not match the current-law contract")
    documents = {document.document_id: document for document in registry.documents}
    chunks: list[dict] = []
    document_reports = []
    for document_id in ("49-vbhn-vpqh", "55-vbhn-vpqh"):
        document_chunks, report = build_law_chunks(project_root, documents[document_id])
        chunks.extend(document_chunks)
        document_reports.append(report)
    decree_chunks, decree_report = build_effective_chunks(
        project_root, registry, effective_view_path
    )
    chunks.extend(decree_chunks)
    document_reports.append(decree_report)

    for ordinal, chunk in enumerate(chunks):
        chunk["ordinal"] = ordinal
        CurrentLawChunk.model_validate(chunk)
    corpus = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "legal_as_of": LEGAL_AS_OF,
        "chunking_contract": CHUNKING_CONTRACT,
        "is_official_consolidated_document": False,
        "effective_view_disclaimer": (
            "The 168+238 effective view is a technical artifact, not an official "
            "consolidated legal document."
        ),
        "documents": document_reports,
        "chunks": chunks,
    }
    validation = validate_corpus(corpus)
    if not validation["passed"]:
        raise ValueError(f"current-law corpus validation failed: {validation['errors']}")
    corpus["validation"] = validation

    input_paths = {
        "registry": registry_path,
        "source_review": DEFAULT_SOURCE_REVIEW,
        "effective_view": effective_view_path,
        "effective_view_manifest": DEFAULT_EFFECTIVE_MANIFEST,
        "effective_view_review": DEFAULT_EFFECTIVE_REVIEW,
        "law_49_text": project_root / documents["49-vbhn-vpqh"].extraction.path,
        "law_49_footnotes": (
            project_root / documents["49-vbhn-vpqh"].extraction.path
        ).parent
        / "footnotes.json",
        "law_55_text": project_root / documents["55-vbhn-vpqh"].extraction.path,
        "law_55_footnotes": (
            project_root / documents["55-vbhn-vpqh"].extraction.path
        ).parent
        / "footnotes.json",
    }
    manifest = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "legal_as_of": LEGAL_AS_OF,
        "status": "processed_corpus_validated_shadow_index_pending",
        "frozen": False,
        "chunking_contract": CHUNKING_CONTRACT,
        "builder": {
            "path": str(Path(__file__).resolve().relative_to(project_root)),
            "sha256": file_digest(Path(__file__).resolve()),
        },
        "inputs": {
            name: {
                "path": str(path.relative_to(project_root)),
                "sha256": file_digest(path),
            }
            for name, path in input_paths.items()
        },
        "output": {
            "path": str(DEFAULT_OUTPUT.relative_to(project_root)),
            "sha256": sha256_text(
                json.dumps(corpus, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ),
        },
        "summary": validation,
        "shadow_collection": "LawChunksCurrentLaw20260922",
        "production_collection_touched": False,
        "production_bm25_touched": False,
    }
    return corpus, manifest


def write_current_law_corpus(
    output_path: Path = DEFAULT_OUTPUT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> tuple[dict, dict]:
    corpus, manifest = build_current_law_corpus()
    if output_path.resolve() == DEFAULT_EFFECTIVE_VIEW.resolve():
        raise ValueError("processed corpus must not overwrite the effective view")
    manifest["output"]["path"] = str(output_path.relative_to(PROJECT_ROOT))
    write_json(output_path, corpus)
    actual = file_digest(output_path)
    if actual != manifest["output"]["sha256"]:
        raise ValueError("written corpus checksum differs from deterministic payload")
    write_json(manifest_path, manifest)
    return corpus, manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true", help="Validate without writing")
    args = parser.parse_args(argv)
    try:
        if args.check:
            corpus, manifest = build_current_law_corpus()
        else:
            corpus, manifest = write_current_law_corpus(args.output, args.manifest)
    except Exception as exc:
        print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
        return 2
    print(
        json.dumps(
            {
                "passed": True,
                "chunk_count": len(corpus["chunks"]),
                "corpus_sha256": manifest["output"]["sha256"],
                "frozen": manifest["frozen"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
