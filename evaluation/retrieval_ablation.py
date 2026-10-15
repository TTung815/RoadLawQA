"""Retrieval ablation on the reviewed 50: BM25, dense and hybrid, before/after rerank.

No LLM is called. Each alpha runs the serving search path (same query views,
candidate budget and reranker); the native candidate order is the "no rerank"
ranking and the reranked order is the "+ rerank" ranking of the same pool.
Final evidence adds the bounded reference lookup used by the chatbot.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import subprocess
import time
from pathlib import Path
from statistics import mean

from ai.diagnostics import TRACE
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from evaluation import revised_current_law_dataset as revised
from evaluation.core_runner import write_new
from evaluation.core_scoring import quantile
from evaluation.module_scoring import facet_coverage, gold_units, rank_metrics
from ingestion.legal_registry import file_digest
from ingestion.structured_corpus import DEFAULT_BUNDLE, load_bundle
from ingestion.structured_index import DEFAULT_INDEX

KS = (1, 5, 10)
TOP_K = 10
LABELS = {0.0: "BM25 (sparse)", 1.0: "Dense (vector)"}


def label(alpha: float) -> str:
    return LABELS.get(alpha, f"Hybrid α={alpha:g}")


def summarize(values: list[float]) -> dict:
    return {"mean": mean(values), "p50": quantile(values, .5), "p95": quantile(values, .95)} if values else {}


async def evaluate(base, alphas: list[float]) -> dict:
    units = {u["id"]: u for u in load_bundle()["chunks"]}
    mapping = {leaf: u["id"] for u in units.values() for leaf in u["metadata"]["source_processed_ids"]}
    cases = revised.load_cases()
    configs = []
    for alpha in alphas:
        retriever = copy.copy(base)
        retriever.alpha = alpha
        expander = LegalNeighborhoodExpander(retriever.fetch_article,
                                             combination_lookup=retriever.fetch_combination_rules)
        rows = []
        for case in cases:
            relevant = gold_units(case.gold, mapping)
            trace = []
            token = TRACE.set(trace)
            started = time.perf_counter()
            try:
                top = await retriever.search(case.query, top_k=TOP_K)
            finally:
                TRACE.reset(token)
            search_ms = (time.perf_counter() - started) * 1000
            ranking, = [e for e in trace if e["stage"] == "retrieval_ranking"]
            orders = {"no_rerank": ranking["candidate_ids"],
                      "rerank": [item["chunk_id"] for item in ranking["reranked"]]}
            selection = await expander.expand_references(top, question=case.query)
            final = list(dict.fromkeys([c.id for c in top] + [c.id for c in selection.chunks]))
            timing = {e["stage"]: e["duration_ms"] for e in trace if e.get("event") == "timing"}
            rows.append({
                "id": case.id, "gold_units": sorted(relevant),
                "candidate_recall": len(set(orders["rerank"]) & relevant) / len(relevant),
                **{stage: {str(k): rank_metrics(order, relevant, k) for k in KS} for stage, order in orders.items()},
                "top10_facet_coverage": {stage: facet_coverage(case.gold, order[:TOP_K], units)
                                         for stage, order in orders.items()},
                "final_evidence": {"count": len(final), "facet_coverage": facet_coverage(case.gold, final, units),
                                   "gold_precision": len(set(final) & relevant) / len(final)},
                "latency_ms": {"search": search_ms, "rerank": timing.get("rerank"),
                               "native_hybrid": timing.get("native_hybrid")},
            })
        aggregate = {}
        for stage in ("no_rerank", "rerank"):
            aggregate[stage] = {str(k): {m: mean(r[stage][str(k)][m] for r in rows)
                                         for m in ("hit", "recall", "rr", "ndcg")} for k in KS}
            aggregate[stage]["top10_facet_coverage"] = mean(r["top10_facet_coverage"][stage] for r in rows)
        configs.append({
            "alpha": alpha, "label": label(alpha), "cases": len(rows), "metrics": aggregate,
            "candidate_recall": mean(r["candidate_recall"] for r in rows),
            "final_evidence": {key: mean(r["final_evidence"][key] for r in rows)
                               for key in ("count", "facet_coverage", "gold_precision")},
            "latency_ms": {key: summarize([r["latency_ms"][key] for r in rows if r["latency_ms"][key] is not None])
                           for key in ("search", "rerank", "native_hybrid")},
            "per_case": rows,
        })
    return {"dataset_version": revised.DATASET_ID,
            "dataset_manifest_sha256": file_digest(revised.DEFAULT_DIR / "manifest.json"),
            "corpus_sha256": file_digest(DEFAULT_BUNDLE / "chunks.json"),
            "index_sha256": file_digest(DEFAULT_INDEX / "index.json"),
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "git_dirty": bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                             capture_output=True, text=True).stdout.strip()),
            "top_k": TOP_K, "candidate_limits": [base.candidate_limit, base.compound_candidate_limit],
            "runtime_devices": base.runtime_devices, "configs": configs,
            "limitations": [
                "Binary relevance: union of required positive gold sources, mapped to structured units; other valid sources may exist.",
                "No rerank = native candidate order of the same search; latency still includes the rerank pass.",
                "Final evidence includes bounded reference lookup; it is not Recall@10.",
            ]}


def render(report: dict) -> str:
    lines = ["# Retrieval ablation — reviewed 50", "",
             f"Commit `{report['git_commit'][:7]}`{' (dirty)' if report['git_dirty'] else ''}, top {report['top_k']}, "
             f"candidates {report['candidate_limits']}, devices {report['runtime_devices']}. No LLM calls.", "",
             "| Retrieval | Rerank | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | Facet cov. top10 |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for config in report["configs"]:
        for stage, name in (("no_rerank", "—"), ("rerank", "bge-reranker-v2-m3")):
            m = config["metrics"][stage]
            lines.append(f"| {config['label']} | {name} | {m['5']['recall']:.4f} | {m['10']['recall']:.4f} | "
                         f"{m['10']['rr']:.4f} | {m['10']['ndcg']:.4f} | {m['top10_facet_coverage']:.4f} |")
    lines += ["", "| Retrieval | Candidate recall | Final evidence facet cov. | Final evidence size | Search p50 (ms) |",
              "|---|---:|---:|---:|---:|"]
    for config in report["configs"]:
        fe = config["final_evidence"]
        lines.append(f"| {config['label']} | {config['candidate_recall']:.4f} | {fe['facet_coverage']:.4f} | "
                     f"{fe['count']:.1f} | {config['latency_ms']['search'].get('p50', 0):.0f} |")
    lines += ["", "## Limitations", *[f"- {item}" for item in report["limitations"]]]
    return "\n".join(lines) + "\n"


def main() -> None:
    from ai.retrieval.runtime import LazyRetriever
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--alphas", default="0,0.25,0.5,0.75,1")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("choose a new ablation directory")
    alphas = [float(value) for value in args.alphas.split(",")]
    if any(not 0 <= alpha <= 1 for alpha in alphas):
        raise ValueError("alpha must be within [0, 1]")
    lazy = LazyRetriever()
    try:
        base = lazy._load()
        report = asyncio.run(evaluate(base, alphas))
    finally:
        lazy.close()
    write_new(args.output / "metrics.json", report)
    write_new(args.output / "REPORT.md", render(report))
    print(render(report))


if __name__ == "__main__":
    main()
