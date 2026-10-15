"""Deterministic evidence checks + separate semantic reviews, never exact-match gold."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Sequence

from evaluation import gold_support as corpus
from evaluation import revised_current_law_dataset as revised
from evaluation.core_runner import verify_run, write_new
from evaluation.core_schema import SemanticReview, SimpleGold, unique_records
from evaluation.legacy_probe import runtime_id
from ingestion.legal_registry import file_digest, read_json


def load_gold(plan, private_gold: Path | None = None) -> dict:
    if plan.suite == "held_out":
        if private_gold is None:
            raise ValueError("held-out scoring requires private gold; runner never reads it")
        gold = unique_records([SimpleGold.model_validate_json(line) for line in private_gold.read_text().splitlines() if line.strip()])
        result = {identity: {"reference_answer": g.reference_answer, "disposition": g.disposition,
                            "facets": g.required_facets, "gold": None, "stage": None,
                            "expected_citations": g.expected_citations} for identity, g in gold.items()}
    elif plan.suite == "reviewed":
        cases = revised.load_cases()
        if (plan.dataset_version != revised.DATASET_ID or
                file_digest(revised.DEFAULT_DIR / "manifest.json") != plan.dataset_binding):
            raise ValueError("run/gold version mismatch")
        result = {c.id: gold_view(c.gold) for c in cases}
    else:
        raise ValueError("only the reviewed benchmark and held-out suites are scored")
    if set(result) != {q.id for q in plan.questions}:
        raise ValueError("gold must match every planned ID exactly")
    return result


def gold_view(gold) -> dict:
    return {"reference_answer": gold.reference_answer, "disposition": gold.publication.disposition,
            "facets": {f.id: f.description for f in gold.required_facets if f.required},
            "gold": gold, "stage": None, "expected_citations": []}


def quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    point = (len(ordered) - 1) * fraction
    lower = int(point)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (point - lower)


def rate(numerator: float, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def deterministic_checks(record: dict, item: dict, chunks: dict, aliases: dict) -> dict:
    output = record["output"] or {}
    checks = {"evidence_completeness": None, "citation_validity": None,
              "blocked_source_publication": False, "probe_grade_matches": None,
              "coverage_grade_matches": None}
    if record["error"] is not None:
        return checks
    if record["mode"] == "rewrite_probe":
        return checks
    if record["mode"] in {"fixed_evidence", "publication_guard_probe"}:
        stage = item["stage"]
        if stage is not None:
            grade = output["final_grade"]["sufficient"]
            checks["probe_grade_matches"] = grade == (stage.expected_pool_coverage == "sufficient")
        return checks
    retrieval = output.get("retrieval", {})
    evidence = retrieval.get("chunks", [])
    available = set()
    for c in evidence:
        identity = aliases.get(c["id"], c["id"])
        canonical = chunks.get(identity)
        if canonical and c["text"] == canonical["text"] and c["enriched_text"] == canonical["enriched_text"]:
            available.update(canonical.get("source_processed_ids", [identity]))
    gold = item["gold"]
    if gold is not None:
        supported = [f for f in gold.required_facets if f.required and f.support_state == "positive_support"]
        proxy = type("GoldView", (), {"gold": gold})()
        missing = set(corpus.missing_facets(proxy, list(available)))
        checks["evidence_completeness"] = rate(sum(f.id not in missing for f in supported), len(supported))
        if gold.expected_coverage in {"sufficient", "insufficient"} and retrieval.get("grade") is not None:
            checks["coverage_grade_matches"] = retrieval["grade"]["sufficient"] == (not missing)
    evidence_by_id = {c["id"]: c for c in evidence}
    citations = [ref for claim in (output.get("answer") or {}).get("claims", []) for ref in claim["citations"]]
    valid = 0
    for ref in citations:
        identity = aliases.get(ref["chunk_id"], ref["chunk_id"])
        chunk = chunks.get(identity)
        provided = evidence_by_id.get(ref["chunk_id"])
        ok = chunk is not None and provided is not None and ref["citation"] == chunk["display_citation"]
        ok = ok and provided["text"] == chunk["text"] and provided["enriched_text"] == chunk["enriched_text"]
        valid += bool(ok)
        if chunk is not None and (not chunk["publication_eligible"] or chunk["active_at_cutoff"] is not True):
            checks["blocked_source_publication"] = True
    checks["citation_validity"] = rate(valid, len(citations))
    return checks


def make_review_packet(run_dir: Path, output_dir: Path, private_gold: Path | None = None) -> dict:
    plan, records = verify_run(run_dir)
    gold = load_gold(plan, private_gold)
    chunks = revised.source_chunks() if plan.suite == "reviewed" else {
        c["id"]: c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"]}
    if output_dir.exists():
        raise FileExistsError("review packet exists; do not overwrite reviewer decisions")
    templates, lines = [], ["# Phiếu chấm nội dung", "", "0 = sai/thiếu; 0.5 = thiếu chi tiết không quyết định, không claim sai; 1 = đúng/đủ.",
                          "Sai chủ thể/số/đơn vị/biên/ngày/điều kiện quyết định = 0. Không dùng exact match.",
                          "Citation tồn tại không chứng minh nội dung được hỗ trợ. null là chưa chấm, không là pass.", ""]
    for question, record in zip(plan.questions, records, strict=True):
        item = gold[question.id]
        templates.append({"id": question.id, "result_sha256": record["result_sha256"], "reviewer": None,
                          "facet_scores": {key: None for key in item["facets"]} if question.mode == "end_to_end" else {},
                          "citation_support": None, "safe_publication": None, "refusal_appropriate": None,
                          "rewrite_preserved": None, "notes": None})
        if plan.suite == "reviewed":
            templates[-1]["response_appropriate"] = None
        lines.extend([f"## {question.id} — {question.mode}", "", question.current_query, "",
                      f"History: {json.dumps([m.model_dump() for m in question.chat_history], ensure_ascii=False)}", "",
                      "### Câu trả lời thực tế", ""])
        actual = record["output"] or {}
        lines.extend([f"Trạng thái: {actual.get('status', 'pipeline_error')}", "",
                      (actual.get("answer") or {}).get("text") or actual.get("message") or
                      "Pipeline lỗi; chưa có đáp án được công bố.", ""])
        lines.extend("- Giới hạn: " + value for value in actual.get("limitations", []))
        lines.extend("- Cần làm rõ: " + value for value in actual.get("follow_up_questions", []))
        lines.extend(["", f"Gold ({item['disposition']}): {item['reference_answer']}", "", "Required facets:", ""])
        lines.extend(f"- {key}: {value}" for key, value in item["facets"].items())
        if plan.suite == "reviewed":
            lines.extend(["", "Tiêu chí trạng thái (response_appropriate):", ""])
            lines.extend(f"- {key}: {value}" for key, value in item["gold"].publication.status_criteria.items())
        references = [ref.processed_id for group in item["gold"].evidence_groups for ref in group.references] if item["gold"] else []
        if item["expected_citations"]:
            lines.extend(["", "Expected citations: " + "; ".join(item["expected_citations"])])
        for identity in dict.fromkeys(references):
            chunk = chunks[identity]
            lines.extend(["", "Source: " + chunk["display_citation"], "", "```text", chunk["enriched_text"], "```",
                          "Source spans: " + json.dumps(chunk["source_spans"], ensure_ascii=False),
                          "Temporal/publication: " + json.dumps({key: chunk[key] for key in
                              ("temporal_status", "temporal_rules", "publication_eligible", "active_at_cutoff")}, ensure_ascii=False)])
        if item["stage"] is not None:
            lines.extend(["", "Probe expectation: " + item["stage"].assertion,
                          "Pool sufficient: " + str(item["stage"].expected_pool_coverage)])
        lines.extend(["", "```json", json.dumps(record, ensure_ascii=False, indent=2), "```", ""])
    write_new(output_dir / "reviews_template.jsonl", "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in templates))
    write_new(output_dir / "REVIEW.md", "\n".join(lines))
    return {"cases": len(records), "semantic_reviews": "pending"}


def score_run(run_dir: Path, reviews_path: Path | None = None, private_gold: Path | None = None) -> dict:
    plan, records = verify_run(run_dir)
    if any(r["execution_kind"] != "live" for r in records):
        raise ValueError("synthetic smoke is not a model quality benchmark")
    gold = load_gold(plan, private_gold)
    reviews = unique_records([SemanticReview.model_validate_json(line) for line in reviews_path.read_text().splitlines() if line.strip()]) if reviews_path else {}
    if not set(reviews) <= set(gold):
        raise ValueError("review contains unknown IDs")
    chunks = revised.source_chunks() if plan.suite == "reviewed" else {
        c["id"]: c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"]}
    aliases = {runtime_id(chunk): identity for identity, chunk in chunks.items()}
    if plan.settings.retrieval_backend == "structured":
        from ingestion.structured_corpus import load_bundle
        for unit in load_bundle()["chunks"]:
            chunks[unit["id"]] = {**unit["metadata"], "id": unit["id"], "text": unit["text"],
                                   "enriched_text": unit["embedding_text"]}
            aliases[unit["id"]] = unit["id"]
    groups = defaultdict(list)
    for record in records:
        item, review = gold[record["id"]], reviews.get(record["id"])
        if review is not None:
            if review.result_sha256 != record["result_sha256"]:
                raise ValueError("review refers to a different output")
            expected = set(item["facets"]) if record["mode"] == "end_to_end" else set()
            if set(review.facet_scores) != expected:
                raise ValueError("review must score exactly every required facet")
            if any(value == 0.5 for value in review.facet_scores.values()) and not review.notes.strip():
                raise ValueError("partial scores need a justification")
        checks = deterministic_checks(record, item, chunks, aliases)
        groups[record["mode"]].append((record, item, review, checks))
    result = {"suite": plan.suite, "dataset_version": plan.dataset_version, "snapshot_id": plan.snapshot_id,
              "run_settings": plan.settings.model_dump(mode="json"), "plan_format_version": plan.format_version,
              "case_count": len(records), "semantic_review_count": len(reviews), "modes": {},
              "limitations": ["Internal owner-reviewed small datasets; no domain-wide or production claim.",
                              "Answer/citation semantic correctness requires reviews; unreviewed is pending.",
                              "Citation membership and evidence recall are not semantic correctness."]}
    if plan.suite == "reviewed":
        result["rubric_version"] = "owner-reviewed-v2-conditional-responses"
    for mode, rows in groups.items():
        total, errors = len(rows), sum(r["error"] is not None for r, _, _, _ in rows)
        report = {"cases": total, "pipeline_errors": rate(errors, total),
                  "latency_ms": {"median": quantile([r["elapsed_ms"] for r, _, _, _ in rows], .5),
                                 "p95": quantile([r["elapsed_ms"] for r, _, _, _ in rows], .95)},
                  "llm_calls": sum(r["usage"]["llm_calls"] for r, _, _, _ in rows)}
        for key in ("input_tokens", "output_tokens", "cost_usd"):
            values = [r["usage"][key] for r, _, _, _ in rows]
            report[key] = sum(values) if all(v is not None for v in values) else None
        if mode != "end_to_end":
            matches = [c["probe_grade_matches"] for _, _, _, c in rows if c["probe_grade_matches"] is not None]
            report["grade_expectation_match"] = rate(sum(matches), len(matches))
            report["probe_success_over_all_cases"] = rate(sum(matches), total) if mode != "rewrite_probe" else None
            rewrites = [v.rewrite_preserved for _, _, v, _ in rows if v and v.rewrite_preserved is not None]
            report["rewrite_preserved"] = rate(sum(rewrites), len(rewrites))
            report["semantic_pending"] = total - len(rewrites) if mode == "rewrite_probe" else 0
        else:
            response_statuses = {"answered", "partial_answer", "needs_clarification"}
            def published_claims(record):
                output = record["output"] or {}
                return (record["error"] is None and output.get("status") in response_statuses
                        and bool((output.get("answer") or {}).get("claims")))
            answered = [(r, i, v, c) for r, i, v, c in rows if r["error"] is None and r["output"].get("status") == "answered"]
            report["answer_rate"] = rate(len(answered), total)
            for status in ("partial_answer", "needs_clarification"):
                report[status + "_rate"] = rate(sum(r["error"] is None and (r["output"] or {}).get("status") == status
                                                   for r, _, _, _ in rows), total)
            facet_values = [score for _, _, v, _ in rows if v for score in v.facet_scores.values()]
            report["facet_accuracy_reviewed"] = rate(sum(facet_values), len(facet_values))
            assessed = [(r, i, v, c) for r, i, v, c in rows if v and v.safe_publication is not None and
                        ((published_claims(r) or (r["output"] or {}).get("status") == "answered") and v.citation_support is not None or
                         not published_claims(r) and (r["output"] or {}).get("status") != "answered" and v.refusal_appropriate is not None)]
            passed = 0
            if plan.suite == "reviewed":
                assessed = [(r, i, v, c) for r, i, v, c in assessed if v.response_appropriate is not None]
            for r, i, v, c in assessed:
                if r["error"] is not None or not all(score == 1 for score in v.facet_scores.values()) or not v.safe_publication or c["blocked_source_publication"]:
                    continue
                if plan.suite == "reviewed":
                    if (v.response_appropriate is True
                            and r["output"].get("status") in i["gold"].publication.allowed_statuses
                            and v.citation_support is True and c["citation_validity"]["value"] == 1):
                        passed += 1
                    continue
                is_answer = r["output"].get("status") == "answered"
                if is_answer and i["disposition"] != "abstain" and v.citation_support and c["citation_validity"]["value"] == 1:
                    passed += 1
                elif r["output"].get("status") not in response_statuses and i["disposition"] != "publish" and v.refusal_appropriate is True:
                    passed += 1
            report["all_required_pass_reviewed"] = rate(passed, len(assessed))
            report["all_required_pass_confirmed_over_all"] = rate(passed, total)
            report["semantic_pending"] = total - len(assessed)
            cites = [c["citation_validity"] for _, _, _, c in rows if c["citation_validity"] is not None]
            report["citation_validity"] = rate(sum(v["numerator"] for v in cites), sum(v["denominator"] for v in cites))
            support = [v.citation_support for r, _, v, _ in rows if
                       (published_claims(r) or (r["output"] or {}).get("status") == "answered")
                       and v and v.citation_support is not None]
            report["citation_support_reviewed"] = rate(sum(support), len(support))
            risky = [(r, i, v, c) for r, i, v, c in rows if i["disposition"] in {"abstain", "conditional"}]
            unsafe = sum(c["blocked_source_publication"] or
                         (r["error"] is None and r["output"].get("status") == "answered" and i["disposition"] == "abstain") or
                         (v is not None and v.safe_publication is False) for r, i, v, c in risky)
            report["unsafe_publication_confirmed"] = rate(unsafe, len(risky))
            report["unsafe_review_pending"] = sum(r["error"] is None and r["output"].get("status") in response_statuses and
                                                 i["disposition"] == "conditional" and (v is None or v.safe_publication is None) for r, i, v, _ in risky)
            publish = [(r, i) for r, i, _, _ in rows if i["disposition"] == "publish"]
            abstained = sum(r["error"] is None and r["output"].get("status") not in response_statuses for r, _ in publish)
            report["unnecessary_abstention"] = rate(abstained, len(publish))
            completeness = [c["evidence_completeness"] for _, _, _, c in rows if c["evidence_completeness"] is not None]
            report["evidence_completeness"] = rate(sum(v["numerator"] for v in completeness), sum(v["denominator"] for v in completeness))
            grades = [c["coverage_grade_matches"] for _, _, _, c in rows if c["coverage_grade_matches"] is not None]
            report["coverage_grade_matches_gold_pool"] = rate(sum(grades), len(grades))
        result["modes"][mode] = report
    result["per_case"] = [{"id": r["id"], "mode": mode, "error": r["error"], "checks": c,
                          "reviewed": v is not None} for mode, rows in groups.items() for r, _, v, c in rows]
    result["run_results_sha256"] = file_digest(run_dir / "results.jsonl")
    result["reviews_sha256"] = file_digest(reviews_path) if reviews_path else None
    result["private_gold_sha256"] = file_digest(private_gold) if private_gold else None
    return result


def render_report(report: dict) -> str:
    lines = [f"# Evaluation — {report['suite']}", "", f"Dataset: {report['dataset_version']}; snapshot: {report['snapshot_id']}", "",
             f"Cases: {report['case_count']}; semantic reviews: {report['semantic_review_count']}. Không gộp modes/suites.", ""]
    settings = report["run_settings"]
    lines.extend([f"Provider: {settings['provider']}; model: {settings['model']}; reasoning effort: {settings['reasoning_effort']}", ""])
    for mode, metrics in report["modes"].items():
        lines.extend([f"## {mode}", "", "| Metric | Result |", "| --- | --- |"])
        for key, value in metrics.items():
            if isinstance(value, dict) and "denominator" in value:
                shown = f"{value['numerator']}/{value['denominator']}" + (f" ({value['value']:.1%})" if value["value"] is not None else " (N/A)")
            else:
                shown = json.dumps(value, ensure_ascii=False)
            lines.append(f"| {key} | {shown} |")
        lines.append("")
    lines.extend(["## Limitations", ""] + ["- " + line for line in report["limitations"]])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["review-packet", "score"])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--gold", type=Path)
    args = parser.parse_args(argv)
    if args.action == "review-packet":
        result = make_review_packet(args.run, args.output, args.gold)
    else:
        if args.output.exists():
            raise FileExistsError("report output exists; choose a new version")
        result = score_run(args.run, args.reviews, args.gold)
        write_new(args.output / "metrics.json", result)
        write_new(args.output / "REPORT.md", render_report(result))
    print(json.dumps({key: value for key, value in result.items() if key not in {"per_case", "modes"}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
