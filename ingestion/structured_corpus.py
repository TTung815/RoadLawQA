"""Versioned search units over reviewed law; never rewrite the frozen leaf corpus.

Short, homogeneous provisions are grouped. Sanction lists remain point-sized.
Every unit retains exact source leaf membership for gold/provenance checks.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Callable
import unicodedata

from evaluation.snapshot import digest
from ingestion.current_law_corpus import (
    DEFAULT_OUTPUT, DEFAULT_EFFECTIVE_VIEW, EXPECTED_ARTICLES,
    parse_document_nodes, strip_structural_tail,
)
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json

VERSION = "structured-law-20260922-v2"
BASE_VERSION = "structured-law-20260922-v1"
BASE_BUNDLE = PROJECT_ROOT / "data/processed/structured-law-v1"
DEFAULT_BUNDLE = PROJECT_ROOT / "data/processed/structured-law-v2"
EMBEDDING_MODEL = "Alibaba-NLP/gte-multilingual-base"
EMBEDDING_REVISION = "9bbca17d9273fd0d03d5725c7a4b0f6b45142062"
MERGE_TOKENS = 480
MAX_TOKENS = 2048


def lexical_text(text: str) -> str:
    """Same normalization/segmentation on documents and queries; preserve accents."""
    from pyvi import ViTokenizer
    value = unicodedata.normalize("NFC", text).casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(ViTokenizer.tokenize(value).split())


def node_id(doc: str, article: str, clause: str | None = None) -> str:
    return f"{doc}:article:{article}" + (f":clause:{clause}" if clause else "")


def source_contexts(rows: list[dict]) -> tuple[dict, dict[str, str]]:
    """Recover complete introductions from reviewed text/effective view, not clipped headers."""
    nodes, inputs = {}, {}
    for doc in sorted({r["document_id"] for r in rows}):
        if doc.startswith("nd168-effective"):
            path = DEFAULT_EFFECTIVE_VIEW
            records = read_json(path)["records"]
        else:
            path = PROJECT_ROOT / next(r["source_path"] for r in rows if r["document_id"] == doc)
            parsed, _ = parse_document_nodes(path.read_text(), EXPECTED_ARTICLES[doc])
            records = [{"article": a, "clause": k, "point": p, "text": n.text,
                        "publication_eligible": True, "active_at_cutoff": True}
                       for (a, k, p), n in parsed.items()]
        inputs[str(path.relative_to(PROJECT_ROOT))] = file_digest(path)
        for record in records:
            if record["point"] is not None:
                continue
            identity = node_id(doc, str(record["article"]), record["clause"])
            nodes[identity] = {"id": identity, "text": strip_structural_tail(record["text"]).strip(),
                               "source_path": str(path.relative_to(PROJECT_ROOT)),
                               "publication_eligible": record["publication_eligible"],
                               "active_at_cutoff": record["active_at_cutoff"]}
    return nodes, inputs


def compatible(rows: list[dict]) -> bool:
    keys = ("active_at_cutoff", "publication_eligible", "effective_from", "effective_to",
            "temporal_status", "temporal_rules", "source_document_ids", "amending_document_ids")
    return all(r["publication_eligible"] and r["active_at_cutoff"] for r in rows) and len({
        digest({k: r.get(k) for k in keys}) for r in rows}) == 1


def union(rows: list[dict], key: str) -> list:
    values = {}
    for row in rows:
        for value in row.get(key, []):
            values.setdefault(digest(value), value)
    return list(values.values())


def make_unit(rows: list[dict], nodes: dict, level: str, count_tokens: Callable[[str], int]) -> dict:
    first = rows[0]
    article = node_id(first["document_id"], first["article_no"])
    clause = node_id(first["document_id"], first["article_no"], first["clause_no"]) if first["clause_no"] else None
    context_ids = [article] if level != "article" else []
    if level == "point" and clause:
        context_ids.append(clause)
    sections = [nodes[x] for x in context_ids if nodes[x]["text"]]
    if level == "article":
        parts = [nodes[article]["text"]]
        seen_clauses = set()
        for row in rows:
            if row["clause_no"]:
                key = node_id(row["document_id"], row["article_no"], row["clause_no"])
                if key not in seen_clauses:
                    parts.append(nodes[key]["text"])
                    seen_clauses.add(key)
                if row["point"]:
                    parts.append(f"{row['point']}) {row['text']}")
            # Article preamble is already in the article node.
        body = "\n".join(parts)
    elif level == "clause" and any(r["point"] for r in rows):
        body = "\n".join([nodes[clause]["text"], *[f"{r['point']}) {r['text']}" for r in rows]])
    else:
        body = (f"{first['point']}) " if first["point"] else "") + first["text"]
    title = first["law"]
    embedding = "\n".join([title, *[s["text"] for s in sections], body])
    if level == "article":
        citation = re.sub(r"^.*?(Điều\s+\d+)", r"\1", first["display_citation"], count=1)
    elif level == "clause":
        citation = re.sub(r"^điểm\s+\S+\s+", "", first["display_citation"])
    else:
        citation = first["display_citation"]
    metadata = {k: v for k, v in first.items() if k not in {
        "text", "enriched_text", "content_sha256", "source_text_sha256", "id", "ordinal", "header", "path", "path_text"}}
    metadata.update(corpus_id=VERSION, granularity=level,
                    point=first["point"] if level == "point" else None,
                    clause_no=first["clause_no"] if level != "article" else None,
                    display_citation=citation, source_locator=citation,
                    parent_id=clause if level == "point" else article if level == "clause" else first["document_id"],
                    article_id=article, clause_id=clause if level != "article" else None,
                    context_sections=sections, source_processed_ids=[r["id"] for r in rows],
                    source_leaf_text_sha256={r["id"]: r["source_text_sha256"] for r in rows},
                    clause_head=nodes[clause]["text"] if clause and level == "point" else "",
                    publication_eligible=all(r["publication_eligible"] for r in rows) and
                        all(s["publication_eligible"] for s in sections),
                    active_at_cutoff=all(r["active_at_cutoff"] for r in rows) and
                        all(s["active_at_cutoff"] for s in sections))
    for key in ("source_spans", "source_document_ids", "lineage_document_ids", "amending_document_ids",
                "operation_ids", "source_amendment_articles", "source_footnote_ids", "temporal_rules"):
        metadata[key] = union(rows, key)
    identity = f"sl1-{digest({'sources': metadata['source_processed_ids'], 'level': level})[:24]}"
    return {"id": identity, "text": body, "embedding_text": embedding,
            "lexical_text": lexical_text(embedding), "token_count": count_tokens(embedding),
            "metadata": metadata}


def build_units(rows: list[dict], nodes: dict, count_tokens: Callable[[str], int]) -> list[dict]:
    by_article = defaultdict(list)
    for row in rows:
        by_article[(row["document_id"], row["article_no"])].append(row)
    units = []
    # Preserve independent sanction branches even when their whole list happens to be short.
    sanctions = re.compile(r"phạt tiền|trừ điểm|tước quyền|xử phạt bổ sung|khắc phục hậu quả", re.I)
    for article_rows in by_article.values():
        candidate = make_unit(article_rows, nodes, "article", count_tokens)
        if compatible(article_rows) and candidate["token_count"] <= MERGE_TOKENS and not sanctions.search(candidate["text"]):
            units.append(candidate)
            continue
        by_clause = defaultdict(list)
        for row in article_rows:
            by_clause[row["clause_no"]].append(row)
        for clause, group in by_clause.items():
            if clause and len(group) > 1 and compatible(group):
                candidate = make_unit(group, nodes, "clause", count_tokens)
                if candidate["token_count"] <= MERGE_TOKENS and not sanctions.search(candidate["text"]):
                    units.append(candidate)
                    continue
            for row in group:
                level = "point" if row["point"] else "clause" if row["clause_no"] else "article"
                units.append(make_unit([row], nodes, level, count_tokens))
    # Do not silently truncate a long legal condition to fit a model.
    oversized = [u["id"] for u in units if u["token_count"] > MAX_TOKENS]
    if oversized:
        raise ValueError(f"Legal units exceed token budget; explicit splitting needed: {oversized}")
    membership = [i for u in units for i in u["metadata"]["source_processed_ids"]]
    if Counter(membership) != Counter(r["id"] for r in rows):
        raise ValueError("source membership was lost or duplicated")
    attach_references(units)
    return units


def reference_targets(text: str, document_id: str, article_no: str) -> list[tuple]:
    """Resolve explicit groups, including parenthetical vehicle qualifications.

    A named document closes a reference group. Unknown document names invalidate
    that group rather than silently assigning its article numbers to another law.
    These are lookup candidates, not a judgment of applicability.
    """
    plain = re.sub(r"\([^()]*\)", " ", text)
    targets = []
    suffix = r"Luật Trật tự,\s*an toàn giao thông đường bộ|Luật Đường bộ|Nghị định này|Luật này|(?<= )này\b"
    for sentence in re.split(r"[.\n]", plain):
        start = 0
        for match in re.finditer(suffix, sentence, re.I):
            segment = sentence[start:match.start()]
            start = match.end()
            if re.search(r"\b(?:Luật|Nghị định)\b", segment, re.I):
                continue
            name = match[0].casefold()
            doc = "55-vbhn-vpqh" if "trật tự" in name else "49-vbhn-vpqh" if "đường bộ" in name else document_id
            references = list(re.finditer(r"(?:khoản\s+(\d+[a-z]?)\s+)?Điều\s+(\d+)\b", segment, re.I))
            targets.extend((doc, r[2], r[1]) for r in references)
            if not references and re.search(r"\bĐiều\s*$", segment, re.I) and name == "này":
                targets.extend((document_id, article_no, clause) for clause in
                               re.findall(r"\bkhoản\s+(\d+[a-z]?)\b", segment, re.I))
    return list(dict.fromkeys(targets))


def attach_references(units: list[dict]) -> None:
    """Resolve unambiguous explicit references at build time; keep unresolved targets visible."""
    by_scope = defaultdict(list)
    for u in units:
        m = u["metadata"]
        by_scope[(m["document_id"], m["article_no"])].append(u)
    for unit in units:
        m = unit["metadata"]
        targets = reference_targets(unit["embedding_text"], m["document_id"], m["article_no"])
        references = []
        for doc, article, clause in dict.fromkeys(targets):
            found = [u["id"] for u in by_scope[(doc, article)] if clause is None or
                     u["metadata"]["clause_no"] == clause or u["metadata"]["granularity"] == "article"]
            references.append({"document_id": doc, "article_no": article, "clause_no": clause,
                               "law": by_scope[(doc, article)][0]["metadata"]["law"] if found else doc,
                               "chunk_ids": [x for x in found if x != unit["id"]], "resolved": bool(found)})
        m["references"] = references


def load_bundle(directory: Path = DEFAULT_BUNDLE) -> dict:
    manifest = read_json(directory / "manifest.json")
    if manifest["version"] not in {BASE_VERSION, VERSION} or file_digest(directory / "chunks.json") != manifest["corpus_sha256"]:
        raise ValueError("structured corpus checksum/version mismatch")
    for name, expected in manifest["inputs"].items():
        if file_digest(PROJECT_ROOT / name) != expected:
            raise ValueError("structured corpus source dependency changed")
    corpus = read_json(directory / "chunks.json")
    if corpus["version"] != manifest["version"] or any(
            u["metadata"]["corpus_id"] != corpus["version"] for u in corpus["chunks"]):
        raise ValueError("structured corpus unit version mismatch")
    return corpus


def build_bundle(directory: Path = DEFAULT_BUNDLE) -> dict:
    from evaluation.current_law_dataset import load_snapshot_context
    from transformers import AutoTokenizer
    _, source = load_snapshot_context()
    rows = sorted(source.values(), key=lambda r: r["ordinal"])
    nodes, inputs = source_contexts(rows)
    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL, revision=EMBEDDING_REVISION,
                                               local_files_only=True, trust_remote_code=True)
    units = build_units(rows, nodes, lambda text: len(tokenizer.encode(text, add_special_tokens=True)))
    # A partial dependency must never be merged into a falsely complete article.
    from ingestion.legal_dependency import load_dependency
    extra_rows, extra_nodes, extra_inputs = load_dependency()
    for row in extra_rows:
        level = "point" if row["point"] else "clause" if row["clause_no"] else "article"
        units.append(make_unit([row], extra_nodes, level,
                               lambda text: len(tokenizer.encode(text, add_special_tokens=True))))
    if any(u["token_count"] > MAX_TOKENS for u in units):
        raise ValueError("dependency unit exceeds token budget")
    attach_references(units)
    rows.extend(extra_rows)
    inputs.update(extra_inputs)
    inputs[str(DEFAULT_OUTPUT.relative_to(PROJECT_ROOT))] = file_digest(DEFAULT_OUTPUT)
    document = {"version": VERSION, "legal_as_of": "2026-09-22", "chunks": units}
    statistics = {"source_leaves": len(rows), "search_chunks": len(units),
                  "levels": dict(Counter(u["metadata"]["granularity"] for u in units)),
                  "blocked_chunks": sum(not u["metadata"]["publication_eligible"] for u in units),
                  "blocked_source_ids": [r["id"] for r in rows if not r["publication_eligible"]],
                  "max_tokens": max(u["token_count"] for u in units),
                  "merge_budget_tokens": MERGE_TOKENS, "hard_budget_tokens": MAX_TOKENS}
    if directory.exists():
        if load_bundle(directory) != document:
            raise FileExistsError("Different corpus already exists; choose a new version/directory")
        return read_json(directory / "manifest.json")
    directory.mkdir(parents=True)
    (directory / "chunks.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    manifest = {"version": VERSION, "corpus_sha256": file_digest(directory / "chunks.json"),
                "inputs": inputs, "builder_sha256": file_digest(Path(__file__)),
                "embedding_model": EMBEDDING_MODEL, "embedding_revision": EMBEDDING_REVISION,
                "lexical_pipeline": "NFC+casefold+punctuation-to-space+PyVi+whitespace", "statistics": statistics}
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args()
    print(json.dumps(build_bundle(args.output)["statistics"], ensure_ascii=False, indent=2))
