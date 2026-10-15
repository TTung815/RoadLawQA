"""Compact evidence and request-local source references shared by LLM stages."""

from typing import Sequence

from ai.retrieval.base import RetrievedChunk


def publishable_chunk(chunk: RetrievedChunk) -> bool:
    metadata = chunk.metadata
    return (metadata.get("publication_eligible") is not False
            and metadata.get("active_at_cutoff") is not False)


def evidence_payload(chunks: Sequence[RetrievedChunk]) -> list[dict]:
    evidence = []
    shared_context = {}
    for chunk in chunks:
        if "context_sections" in chunk.metadata:
            contexts = []
            for section in chunk.metadata["context_sections"]:
                identity, text = section["id"], section["text"]
                if identity in shared_context and shared_context[identity] != text:
                    raise ValueError("conflicting parent context")
                if identity not in shared_context:
                    contexts.append({"context_id": identity, "text": text})
                    shared_context[identity] = text
            evidence.append({"id": chunk.id, "citation": chunk.citation, "text": chunk.text,
                             "context_ids": [s["id"] for s in chunk.metadata["context_sections"]],
                             "shared_context": contexts,
                             "metadata": {k: chunk.metadata[k] for k in (
                                 "law", "article_no", "clause_no", "point", "legal_as_of", "effective_from",
                                 "effective_to", "temporal_status", "temporal_rules", "publication_eligible",
                                 "active_at_cutoff", "artifact_kind", "scope_complete",
                                 "publication_scope", "scope_limitations") if k in chunk.metadata}})
            continue
        item = chunk.model_dump(mode="json", exclude={"score"})
        # Keep provenance and temporal metadata, not repeated copies of the body.
        item["metadata"] = {key: value for key, value in item["metadata"].items()
                            if key not in {"raw_score", "rerank_score", "text", "enriched_text", "id"}}
        evidence.append(item)
    return evidence


class SourceReferences:
    """Replace long hashes on the wire; never guess or fuzzy-match unknown IDs."""

    def __init__(self, chunks: Sequence[RetrievedChunk]):
        self.forward = {c.id: f"source_{i}" if len(c.id) > 24 else c.id
                        for i, c in enumerate(chunks, 1)}
        if len(set(self.forward.values())) != len(self.forward):
            self.forward = {c.id: f"source_{i}" for i, c in enumerate(chunks, 1)}
        self.reverse = {value: key for key, value in self.forward.items()}

    def translate(self, value, *, decode=False):
        mapping = self.reverse if decode else self.forward
        if isinstance(value, dict):
            return {key: self.translate(item, decode=decode) for key, item in value.items()}
        if isinstance(value, list):
            return [self.translate(item, decode=decode) for item in value]
        if isinstance(value, str):
            return mapping.get(value, value)
        return value
