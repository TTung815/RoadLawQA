"""Load a scoped, reviewed dependency without changing the frozen core registry."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from ingestion.legal_registry import PROJECT_ROOT, LegalDocument, Review, file_digest, read_json

DEFAULT_DEPENDENCY = PROJECT_ROOT / "data/legal_sources/administrative-age-v1"


def load_dependency(directory: Path = DEFAULT_DEPENDENCY) -> tuple[list[dict], dict, dict[str, str]]:
    registry_path, review_path = directory / "registry.json", directory / "review.json"
    registry, review = read_json(registry_path), read_json(review_path)
    document = LegalDocument.model_validate(registry["document"])
    scope = Review.model_validate(registry["scope_review"])
    if (scope.status != "approved" or document.metadata_review.status != "approved"
            or document.scope.decision != "ingest" or document.extraction.review.status != "approved"
            or review["status"] != "approved" or not review.get("reviewer")
            or not registry.get("owner_authorization")):
        raise ValueError("dependency scope/extraction has not been approved")
    if review["registry_sha256"] != file_digest(registry_path):
        raise ValueError("dependency registry changed since review")
    inputs = {str(p.relative_to(PROJECT_ROOT)): file_digest(p) for p in (registry_path, review_path)}
    artifacts = {
        registry["base_registry_path"]: registry["base_registry_sha256"],
        document.source.raw_path: document.source.sha256,
        document.extraction.path: document.extraction.sha256,
    }
    for path, expected in artifacts.items():
        if file_digest(PROJECT_ROOT / path) != expected:
            raise ValueError("dependency source checksum mismatch")
        inputs[path] = expected
    if (review["source_pdf_sha256"] != document.source.sha256
            or review["extracted_text_sha256"] != document.extraction.sha256):
        raise ValueError("dependency review refers to different source artifacts")
    if (not review["units"] or len({u["id"] for u in review["units"]}) != len(review["units"])
            or sorted(u["display_citation"] for u in review["units"]) != sorted(document.scope.included_sections)):
        raise ValueError("dependency units differ from approved scope")
    lines = (PROJECT_ROOT / document.extraction.path).read_text().splitlines()
    rows, nodes = [], {}
    cutoff = date.fromisoformat(registry["legal_as_of"])
    for unit in review["units"]:
        start, end = unit["line_start"], unit["line_end"]
        text = unit["text"]
        if (not 1 <= start <= end <= len(lines) or "\n".join(lines[start - 1:end]) != text
                or hashlib.sha256(text.encode()).hexdigest() != unit["source_text_sha256"]):
            raise ValueError("dependency unit differs from reviewed source span")
        if (date.fromisoformat(unit["effective_from"]) > cutoff or
                (unit["effective_to"] and cutoff >= date.fromisoformat(unit["effective_to"]))):
            raise ValueError("dependency provision is not active at cutoff")
        context = unit["parent_context"].splitlines()
        if context and lines[start - 1 - len(context):start - 1] != context:
            raise ValueError("dependency parent context differs from source")
        article_id = f"{document.document_id}:article:{unit['article_no']}"
        for identity, value in [(article_id, context[0] if context else text)]:
            nodes[identity] = {"id": identity, "text": value, "source_path": document.extraction.path,
                               "publication_eligible": True, "active_at_cutoff": True}
        if unit["point"]:
            if not text.startswith(unit["point"] + ") ") or len(context) != 2:
                raise ValueError("dependency point lacks complete parent context")
            clause_id = f"{article_id}:clause:{unit['clause_no']}"
            nodes[clause_id] = {**nodes[article_id], "id": clause_id, "text": context[1]}
            text = text[len(unit["point"]) + 2:]
        elif context:
            nodes[article_id]["text"] = "\n".join(context)
        rows.append({
            "id": unit["id"], "document_id": document.document_id, "law": document.title,
            "law_code": document.symbol, "article_no": unit["article_no"],
            "clause_no": unit["clause_no"], "point": unit["point"], "text": text,
            "display_citation": unit["display_citation"], "source_path": document.extraction.path,
            "source_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "source_document_ids": [document.document_id, *unit["lineage_document_ids"]],
            "lineage_document_ids": unit["lineage_document_ids"],
            "amending_document_ids": unit["amending_document_ids"],
            "source_footnote_ids": unit["source_footnote_ids"],
            "source_spans": [{"document_id": document.document_id, "path": document.extraction.path,
                              "line_start": start, "line_end": end, "pdf_path": document.source.raw_path,
                              "pdf_page": unit["pdf_page"]}],
            "legal_as_of": registry["legal_as_of"], "effective_from": unit["effective_from"],
            "effective_to": unit["effective_to"], "temporal_status": "active", "temporal_rules": [],
            "publication_eligible": True, "active_at_cutoff": True,
            "artifact_kind": "official_consolidation", "is_official_consolidated_document": True,
            "scope_complete": False, "publication_scope": review["publication_scope"],
            "scope_limitations": review["scope_limitations"], "dependency_review_path": str(review_path.relative_to(PROJECT_ROOT)),
        })
    return rows, nodes, inputs
