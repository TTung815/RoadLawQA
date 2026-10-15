"""Combine saved runs, rubric-judge results and stage metrics into one ablation table.

No model call: reads verified run receipts, signed judge metrics and the
module scorer. Each row is one locked configuration on the same 50 questions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.core_runner import verify_run, write_new
from evaluation.generation_scoring import read_signed
from evaluation.module_scoring import score_modules


def row(label: str, run_dir: Path, judge_dir: Path) -> dict:
    plan, records = verify_run(run_dir)
    judge = read_signed(judge_dir / "metrics.json")
    plan_judged = read_signed(judge_dir / "plan.json")
    if plan_judged["source_results_sha256"] != json.loads((run_dir / "run.json").read_text())["results_sha256"]:
        raise ValueError(f"{label}: judge scored a different run")
    modules = score_modules(run_dir)
    ranking = modules["ranking"]["after"]["10"]
    latency = modules["latency_ms"]
    tokens = [r["usage"] for r in records]
    return {"label": label, "which": judge["which"], "rerank": plan.settings.rerank,
            "expansion": plan.settings.expansion, "alpha": plan.settings.hybrid_alpha, "cases": len(records),
            "pipeline_errors": sum(r["error"] is not None for r in records),
            "recall10": ranking["recall"]["mean"], "mrr10": ranking["mrr"]["mean"], "ndcg10": ranking["ndcg"]["mean"],
            "final_evidence_coverage": modules["final_evidence_coverage"]["mean"],
            "accuracy": judge["accuracy"], "accuracy_ci95": judge["accuracy_ci95"],
            "hallucination_rate": judge["hallucination_rate"], "hallucination_ci95": judge["hallucination_ci95"],
            "facet_score": judge["facet_score"], "labels": judge["labels"], "judge_errors": judge["judge_errors"],
            "latency_p50_s": latency["end_to_end"]["p50"] / 1000, "latency_p95_s": latency["end_to_end"]["p95"] / 1000,
            "latency_mean_s": latency["end_to_end"]["mean"] / 1000,
            "rerank_mean_s": (latency.get("rerank") or {}).get("mean", 0) / 1000 if latency.get("rerank") else 0.0,
            "llm_calls": sum(t["llm_calls"] for t in tokens),
            "input_tokens": sum(t["input_tokens"] or 0 for t in tokens),
            "output_tokens": sum(t["output_tokens"] or 0 for t in tokens),
            "repairs": modules["repairs"], "statuses": modules["statuses"]}


def render(rows: list[dict]) -> str:
    pct = lambda v: f"{v:.1%}"
    ci = lambda v: f"[{v[0]:.0%}–{v[1]:.0%}]" if v else ""
    lines = ["# End-to-end evaluation — reviewed 50", "",
             "Accuracy/hallucination: rubric-judge-v1 (LLM, validated against owner labels). "
             "Retrieval metrics: proxy relevance from gold sources.", "",
             "| Configuration | Recall@10 | MRR@10 | Accuracy | Hallucination | Facet score | p50 / p95 (s) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['label']} | {r['recall10']:.3f} | {r['mrr10']:.3f} | {pct(r['accuracy'])} {ci(r['accuracy_ci95'])} | "
                     f"{pct(r['hallucination_rate'])} {ci(r['hallucination_ci95'])} | {pct(r['facet_score'])} | "
                     f"{r['latency_p50_s']:.1f} / {r['latency_p95_s']:.1f} |")
    lines += ["", "| Configuration | Labels | Statuses | Repairs | LLM calls | Tokens in / out |", "|---|---|---|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['label']} | {json.dumps(r['labels'])} | {json.dumps(r['statuses'])} | {r['repairs']} | "
                     f"{r['llm_calls']} | {r['input_tokens']:,} / {r['output_tokens']:,} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row", nargs=3, action="append", metavar=("LABEL", "RUN", "JUDGE"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [row(label, Path(run), Path(judge)) for label, run, judge in args.row]
    write_new(args.output / "metrics.json", {"rows": rows})
    write_new(args.output / "REPORT.md", render(rows))
    print(render(rows))


if __name__ == "__main__":
    main()
