"""Compatibility import for frozen builders: shared ID/BM25 helpers only.

The V1 execution, AST inspection and resource-rebinding tools have been retired.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SEARCH_FIELDS = (
    "law", "chapter", "section", "article_no", "article_title", "clause_no",
    "point", "clause_head", "text", "enriched_text", "display_citation",
)
BM25_FIELDS = ("article_no", "article_title", "clause_no", "point", "clause_head", "text")
BM25_PARAMETERS = {"k1": 1.5, "b": 0.75, "epsilon": 0.25}


def search_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    """Project exactly the fields requested by baseline search, including nulls."""
    return {key: properties.get(key) for key in SEARCH_FIELDS}

def runtime_id(properties: Mapping[str, Any]) -> str:
    identity = {key: str(properties.get(key) or "").strip() for key in SEARCH_FIELDS}
    # This stable identity is retained for existing source references and results.
    payload = json.dumps(identity, sort_keys=True, ensure_ascii=False)
    return "chunk_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

def tokenized_corpus(rows: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    from pyvi import ViTokenizer

    # Deliberately use the original join/tokenization, without lowercasing or normalization.
    return [ViTokenizer.tokenize(" ".join(row.get(key) for key in BM25_FIELDS if row.get(key))).split()
            for row in rows]

def build_bm25(rows: Sequence[Mapping[str, Any]]):
    from rank_bm25 import BM25Okapi

    if not rows:
        raise ValueError("An empty corpus cannot authorize retrieval evaluation")
    return BM25Okapi(tokenized_corpus(rows), **BM25_PARAMETERS)

def load_bm25(path: Path):
    """Read only local BM25/NumPy cache data; reject arbitrary pickle globals."""
    import pickle

    class CacheUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            allowed = {
                ("rank_bm25", "BM25Okapi"), ("numpy", "dtype"), ("numpy", "ndarray"),
                ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
                ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"),
            }
            if (module, name) not in allowed:
                raise ValueError("Unsupported BM25 cache format")
            return super().find_class(module, name)

    with path.open("rb") as stream:
        return CacheUnpickler(stream).load()

def audit_bm25(cache: Any, expected: Any) -> dict[str, Any]:
    import math
    from collections import Counter

    def signature(frequencies):
        return hashlib.sha256(json.dumps(frequencies, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    actual = getattr(cache, "doc_freqs", [])
    wanted = expected.doc_freqs
    mismatches = [number for number, (left, right) in enumerate(zip(actual, wanted)) if left != right]
    idf = getattr(cache, "idf", {})
    idf_matches = set(idf) == set(expected.idf) and all(
        math.isclose(idf[key], value, rel_tol=1e-12, abs_tol=1e-12) for key, value in expected.idf.items())
    checks = {
        "class_matches": type(cache) is type(expected),
        "parameters_match": all(getattr(cache, key, None) == value for key, value in BM25_PARAMETERS.items()),
        "count_matches": getattr(cache, "corpus_size", None) == expected.corpus_size,
        "ordered_frequencies_match": actual == wanted,
        "document_lengths_match": getattr(cache, "doc_len", None) == expected.doc_len,
        "average_length_matches": math.isclose(getattr(cache, "avgdl", -1), expected.avgdl,
                                               rel_tol=1e-12, abs_tol=1e-12),
        "idf_matches": idf_matches,
        "average_idf_matches": math.isclose(getattr(cache, "average_idf", -1), expected.average_idf,
                                            rel_tol=1e-12, abs_tol=1e-12),
        "tokenizer_matches": getattr(cache, "tokenizer", None) is None,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "frequency_multiset_matches": Counter(map(signature, actual)) == Counter(map(signature, wanted)),
            "mismatched_positions": mismatches[:50], "mismatched_position_count": len(mismatches),
            "cache_count": getattr(cache, "corpus_size", None), "expected_count": expected.corpus_size}
