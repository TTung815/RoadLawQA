"""Bounded troubleshooting on selected known cases; never a benchmark report."""

import argparse
import asyncio
import json
from pathlib import Path

from evaluation.core_runner import load_plan, run_questions, write_new
from evaluation.core_runtime import create_live_runtime
from evaluation.llm_preflight import verify_preflight
from ingestion.legal_registry import file_digest


async def diagnose(plan_path: Path, preflight: Path, case_ids: list[str], output: Path):
    plan = load_plan(plan_path)
    if plan.suite != "legacy":
        raise ValueError("diagnostics only use known questions, never private held-out")
    if len(case_ids) != len(set(case_ids)) or not 1 <= len(case_ids) <= 15:
        raise ValueError("select 1–15 unique known cases")
    selected = [q for q in plan.questions if q.id in case_ids]
    if len(selected) != len(case_ids):
        raise ValueError("unknown case ID")
    if output.exists():
        raise FileExistsError("diagnostic directory already exists")
    verify_preflight(preflight, plan_path)
    runtime = create_live_runtime(plan.settings)
    output.mkdir(parents=True)
    answers = ["# Đáp án chẩn đoán pipeline", "", "Đây là các câu đã chọn để debug, không phải điểm benchmark.", ""]
    try:
        # One case at a time, persisting progress before the next network request.
        for question in selected:
            case_plan = plan.model_copy(update={"questions": [question]})
            record = (await run_questions(case_plan, runtime))[0]
            write_new(output / f"{question.id}.json", record)
            actual = record.get("output") or {}
            answers.extend([f"## {question.id}", "", question.current_query, "",
                            f"**Trạng thái:** {actual.get('status', 'pipeline_error')}", "",
                            (actual.get("answer") or {}).get("text") or actual.get("message") or
                            "Pipeline lỗi, chưa có đáp án được công bố.", ""])
            answers.extend("- Giới hạn: " + value for value in actual.get("limitations", []))
            answers.extend("- Cần làm rõ: " + value for value in actual.get("follow_up_questions", []))
            answers.extend("- Kiểm chứng: " + value for value in (actual.get("verification") or {}).get("issues", []))
            if record["error"]:
                answers.append("Lỗi: " + json.dumps(record["error"], ensure_ascii=False))
            answers.extend(["", f"[Output và trace nội bộ]({question.id}.json)", ""])
            print(json.dumps({"id": question.id, "status": (record.get("output") or {}).get("status"),
                              "error": record["error"]}), flush=True)
    finally:
        runtime.close()
    write_new(output / "ANSWERS.md", "\n".join(answers))
    summary = {"kind": "selected_case_diagnostics", "not_a_benchmark_score": True,
               "parent_plan_sha256": file_digest(plan_path), "case_ids": [q.id for q in selected],
               "artifacts": {p.name: file_digest(p) for p in sorted(output.glob("current_law_*.json"))}}
    write_new(output / "receipt.json", summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    asyncio.run(diagnose(args.plan, args.preflight, args.case, args.output))


if __name__ == "__main__":
    main()
