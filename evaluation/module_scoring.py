"""Rank metrics on recorded candidate pools; no model calls or retrieval reruns."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean

from evaluation.core_runner import verify_run, write_new
from evaluation.core_scoring import load_gold, quantile
from evaluation.gold_support import missing_facets
from ingestion.legal_registry import file_digest
from ingestion.structured_corpus import DEFAULT_BUNDLE, load_bundle


KS = (1, 5, 10)


def rank_metrics(ranking: list[str], relevant: set[str], k: int) -> dict:
    if k < 1 or len(ranking) != len(set(ranking)):
        raise ValueError("positive k and unique ranked units required")
    if not relevant:
        return {name: None for name in ("hit", "recall", "rr", "ndcg")}
    positions = [i for i, identity in enumerate(ranking[:k], 1) if identity in relevant]
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return {"hit": int(bool(positions)), "recall": len(positions) / len(relevant),
            "rr": 1 / positions[0] if positions else 0,
            "ndcg": sum(1 / math.log2(i + 1) for i in positions) / ideal}


def gold_units(gold, leaf_to_unit: dict[str, str]) -> set[str]:
    groups = {g.id: g for g in gold.evidence_groups}
    leaves = {r.processed_id for f in gold.required_facets if f.required and f.support_state == "positive_support"
              for g in f.evidence_group_ids for r in groups[g].references if r.role == "support"}
    if not leaves <= leaf_to_unit.keys():
        raise ValueError("gold leaf is missing from the locked structured corpus")
    return {leaf_to_unit[identity] for identity in leaves}


def facet_coverage(gold, ids: list[str], units: dict) -> float | None:
    leaves = [leaf for identity in ids for leaf in units[identity]["metadata"]["source_processed_ids"]]
    required = [f for f in gold.required_facets if f.required and f.support_state == "positive_support"]
    if not required:
        return None
    proxy = type("Case", (), {"gold": gold})()
    missing = set(missing_facets(proxy, leaves))
    return sum(f.id not in missing for f in required) / len(required)


def score_ranking(trace: dict, gold, units: dict, top_k: int) -> dict:
    before = trace["candidate_ids"]
    after = [item["chunk_id"] for item in trace["reranked"]]
    if (len(before) != len(set(before)) or len(after) != len(set(after)) or set(before) != set(after)
            or not set(before) <= units.keys()):
        raise ValueError("reranker comparison requires the same unique known candidate pool")
    if trace["top_k"] != top_k or trace["selected_ids"] != after[:top_k]:
        raise ValueError("selected evidence differs from locked top-k ranking")
    if any(not units[i]["metadata"]["publication_eligible"] or
           not units[i]["metadata"]["active_at_cutoff"] for i in before):
        raise ValueError("ranking includes a blocked source")
    mapping = {leaf: u["id"] for u in units.values() for leaf in u["metadata"]["source_processed_ids"]}
    relevant = gold_units(gold, mapping)
    result = {"candidate_count": len(before), "gold_unit_count": len(relevant),
              "candidate_recall": len(set(before) & relevant) / len(relevant) if relevant else None,
              "candidate_ids": before, "reranked_ids": after, "gold_unit_ids": sorted(relevant),
              "before": {}, "after": {}}
    for label, ranking in (("before", before), ("after", after)):
        for k in KS:
            result[label][str(k)] = {**rank_metrics(ranking, relevant, k),
                                    "facet_coverage": facet_coverage(gold, ranking[:k], units)}
    return result


def distribution(values: list[float]) -> dict:
    return {"n": len(values), "mean": mean(values) if values else None,
            "p50": quantile(values, .5), "p95": quantile(values, .95)}


def score_modules(run_dir: Path) -> dict:
    plan, records = verify_run(run_dir)
    if plan.suite != "reviewed" or plan.settings.retrieval_backend != "structured":
        raise ValueError("module report currently requires reviewed v2 and structured retrieval")
    if any(r["execution_kind"] != "live" for r in records):
        raise ValueError("synthetic results cannot be reported as model quality")
    if file_digest(DEFAULT_BUNDLE / "chunks.json") != plan.settings.retrieval_corpus_sha256:
        raise ValueError("run corpus differs from scoring corpus")
    gold = load_gold(plan)
    units = {u["id"]: u for u in load_bundle()["chunks"]}
    cases, timings = [], {}
    verdicts = Counter()
    for record in records:
        output = record["output"] or {}
        events = record.get("diagnostics", [])
        rankings = [t for t in events if t["stage"] == "retrieval_ranking" and t.get("event") == "result"]
        if len(rankings) > 1:
            raise ValueError("multiple retrieval passes require a separate comparison protocol")
        case = {"id": record["id"], "status": output.get("status", "pipeline_error"),
                "error": record["error"], "ranking": None, "final_evidence_coverage": None,
                "repair_attempts": output.get("repair_attempts")}
        if rankings:
            case["ranking"] = score_ranking(rankings[0], gold[record["id"]]["gold"], units, plan.settings.top_k)
        retrieval = output.get("retrieval")
        if retrieval is None:
            retrieval = next((t["retrieval"] for t in events if t["stage"] == "retrieval" and t.get("event") == "result"), None)
        if retrieval is not None:
            ids = [c["id"] for c in retrieval["chunks"]]
            for chunk in retrieval["chunks"]:
                unit = units.get(chunk["id"])
                if unit is None or chunk["text"] != unit["text"] or chunk["enriched_text"] != unit["embedding_text"]:
                    raise ValueError("final evidence differs from the scoring corpus")
            case["final_evidence_coverage"] = facet_coverage(gold[record["id"]]["gold"], ids, units)
            case["final_evidence_count"] = len(ids)
        measures = {"end_to_end": record["elapsed_ms"]}
        measures.update({key: value for key, value in output.get("timings", {}).items()
                         if key in {"generation_ms", "verification_ms"}})
        measures.update({key: value for key, value in (retrieval or {}).get("timings", {}).items()
                         if key in {"contextualization_ms", "structural_lookup_ms", "retrieval_ms"}})
        for stage in ("query_embedding", "native_hybrid", "rerank"):
            values = [e["duration_ms"] for e in events if e["stage"] == stage and e.get("event") == "timing"]
            if values:
                measures[stage] = sum(values)
        for name, value in measures.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError("invalid timer")
            timings.setdefault(name, []).append(value)
        for event in events:
            if event["stage"] == "verification" and event.get("event") == "result":
                verdicts[event["verification"]["status"]] += 1
        cases.append(case)
    measured = [c for c in cases if c["ranking"] is not None]
    aggregate = {}
    for stage in ("before", "after"):
        aggregate[stage] = {}
        for k in KS:
            aggregate[stage][str(k)] = {
                "mrr" if key == "rr" else key: distribution([
                    c["ranking"][stage][str(k)][key] for c in measured
                    if c["ranking"][stage][str(k)][key] is not None])
                for key in ("hit", "recall", "rr", "ndcg", "facet_coverage")}
    return {"dataset_version": plan.dataset_version, "results_sha256": file_digest(run_dir / "results.jsonl"),
            "plan_sha256": digest_plan(plan), "cases": len(cases), "ranking_measured": len(measured),
            "ranking_missing": len(cases) - len(measured), "ranking": aggregate,
            "candidate_recall": distribution([c["ranking"]["candidate_recall"] for c in measured if c["ranking"]["candidate_recall"] is not None]),
            "final_evidence_coverage": distribution([c["final_evidence_coverage"] for c in cases if c["final_evidence_coverage"] is not None]),
            "latency_ms": {key: distribution(values) for key, values in timings.items()},
            "statuses": dict(Counter(c["status"] for c in cases)), "verifier_decisions": dict(verdicts),
            "repairs": sum(c["repair_attempts"] or 0 for c in cases), "per_case": cases,
            "limitations": [
                "No router/LLM query expansion in this RAG run.",
                "Binary relevance proxy: union of required positive gold support, deduplicated to structured units. Other valid sources may exist.",
                "Recall counts reference units; facet coverage respects all/any and alternative groups. Optional-only sources are excluded.",
                "Before = actual merged candidate order (including locator lookup); after = reranked same pool. Not an end-to-end reranker-off ablation.",
                "Final evidence coverage includes bounded reference lookup; it is not Recall@10.",
                "Missing ranking is N/A, never a fabricated zero or pass. Report its denominator alongside scores.",
                "Latency excludes runtime initialization. Retrieval time contains embedding/hybrid/rerank; do not sum nested timers.",
                "Verifier decisions and repair count are operational measures, not independently labelled detection accuracy."]}


def digest_plan(plan) -> str:
    from evaluation.snapshot import digest
    return digest(plan.model_dump(mode="json"))


def render(report: dict) -> str:
    lines = ["# Module evaluation", "", f"Dataset: {report['dataset_version']}; measured rankings {report['ranking_measured']}/{report['cases']}.", "",
             "| K | Metric | Before rerank | After rerank |", "|---|---|---:|---:|"]
    for k in KS:
        for metric in ("hit", "recall", "mrr", "ndcg", "facet_coverage"):
            values = [report["ranking"][stage][str(k)][metric]["mean"] for stage in ("before", "after")]
            shown = [f"{v:.4f}" if v is not None else "N/A" for v in values]
            lines.append(f"| {k} | {metric} | {shown[0]} | {shown[1]} |")
    lines += ["", "Candidate recall: " + str(report["candidate_recall"]), "",
              "Final evidence facet coverage: " + str(report["final_evidence_coverage"]), "",
              "| Stage (ms) | n | Mean | p50 | p95 |", "|---|---:|---:|---:|---:|"]
    for key, value in report["latency_ms"].items():
        lines.append(f"| {key} | {value['n']} | {value['mean']:.1f} | {value['p50']:.1f} | {value['p95']:.1f} |")
    lines += ["", "Statuses: " + json.dumps(report["statuses"]), "", "Verifier decisions: " + json.dumps(report["verifier_decisions"]),
              "", f"Repairs: {report['repairs']}", ""] + ["- " + value for value in report["limitations"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("choose a new module report directory")
    report = score_modules(args.run)
    write_new(args.output / "metrics.json", report)
    write_new(args.output / "REPORT.md", render(report))
    print(json.dumps({"cases": report["cases"], "ranking_measured": report["ranking_measured"]}))


if __name__ == "__main__":
    main()
