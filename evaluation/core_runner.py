"""Prepare query-only locked plans and explicitly run the isolated V2 evaluator."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import time
from typing import Callable, Sequence

from evaluation import gold_support as corpus
from evaluation import revised_current_law_dataset as revised
from evaluation.core_schema import Question, RunPlan, RunSettings, unique_records
from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST, verify_frozen_snapshot
from evaluation.snapshot import digest
from ingestion.legal_registry import PROJECT_ROOT, file_digest, read_json


def write_new(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(corpus.artifact_bytes(value))


def code_hashes() -> dict[str, str]:
    # Bind actual serving prompts/agents/providers plus evaluator; no .env/secrets.
    paths = [p for base in ("ai/agent", "ai/prompts", "ai/llm", "ai/retrieval", "backend/services", "backend/schemas")
             for p in (PROJECT_ROOT / base).glob("*.py")]
    paths += [PROJECT_ROOT / "evaluation" / name for name in
              ("core_schema.py", "core_runtime.py", "core_runner.py", "core_scoring.py", "module_scoring.py", "legacy_probe.py", "llm_preflight.py", "diagnose.py", "revised_current_law_dataset.py")]
    paths += [PROJECT_ROOT / "evaluation/gold_support.py", PROJECT_ROOT / "ai/diagnostics.py", PROJECT_ROOT / "evaluation/snapshot.py"]
    paths += [PROJECT_ROOT / name for name in ("configs/settings.py", "backend/dependencies/retrieval.py",
                                              "backend/dependencies/answer.py", "ingestion/structured_corpus.py",
                                              "ingestion/structured_index.py", "ingestion/legal_dependency.py")]
    return {str(p.relative_to(PROJECT_ROOT)): file_digest(p) for p in sorted(paths)}


def default_settings() -> RunSettings:
    from configs.settings import Settings
    from ai.retrieval.devices import resolve_device
    snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
    llm = Settings()
    return RunSettings(provider=llm.llm_provider, model=llm.model_name,
                       retrieval_backend=llm.retrieval_backend, hybrid_alpha=llm.hybrid_alpha,
                       hybrid_candidate_limit=llm.hybrid_candidate_limit,
                       compound_candidate_limit=llm.compound_candidate_limit,
                       reranker_batch_size=llm.reranker_batch_size,
                       embedding_device=resolve_device(llm.embedding_device),
                       reranker_device=resolve_device(llm.reranker_device),
                       reasoning_effort=llm.openai_reasoning_effort if llm.llm_provider == "openai" else None,
                       max_output_tokens=llm.openai_max_output_tokens if llm.llm_provider == "openai" else None,
                       request_timeout_seconds=llm.llm_request_timeout_seconds,
                       max_transient_retries=llm.llm_max_transient_retries,
                       embedding_revision=snapshot["shadow_resources"]["embedding"]["revision"],
                       reranker_revision=llm.reranker_revision,
                       host=llm.weaviate_host, port=llm.weaviate_port, grpc_port=llm.weaviate_grpc_port,
                       top_k=llm.default_top_k, max_attempts=1, expansion=llm.structural_expansion_enabled)


def questions_for(suite: str, private_questions: Path | None = None, *, owner_reviewed: bool = False,
                  dataset_version: str | None = None) -> tuple[list[Question], str, str]:
    if suite == "held_out":
        if private_questions is None or not owner_reviewed or not dataset_version:
            raise ValueError("held-out needs query-only file, dataset version and owner approval")
        # Query-only contract deliberately rejects gold/answer fields.
        questions = [Question.model_validate_json(line) for line in private_questions.read_text().splitlines() if line.strip()]
        unique_records(questions)
        if not questions:
            raise ValueError("empty held-out questions")
        return questions, file_digest(private_questions), dataset_version
    if private_questions is not None:
        raise ValueError("internal suites use their reviewed frozen datasets")
    if suite == "reviewed":
        cases = revised.load_cases()
        questions = [Question(id=c.id, current_query=c.query, chat_history=c.chat_history) for c in cases]
        return questions, file_digest(revised.DEFAULT_DIR / "manifest.json"), revised.DATASET_ID
    raise ValueError("unknown suite")


def prepare_plan(suite: str, output: Path, *, settings: RunSettings | None = None,
                 private_questions: Path | None = None, owner_reviewed: bool = False,
                 dataset_version: str | None = None) -> RunPlan:
    verify_frozen_snapshot()
    settings = settings or default_settings()
    if settings.retrieval_backend == "structured":
        from ingestion.structured_corpus import DEFAULT_BUNDLE, load_bundle
        from ingestion.structured_index import DEFAULT_INDEX
        load_bundle()
        settings = settings.model_copy(update={
            "retrieval_corpus_sha256": file_digest(DEFAULT_BUNDLE / "chunks.json"),
            "retrieval_index_sha256": file_digest(DEFAULT_INDEX / "index.json")})
    questions, binding, version = questions_for(suite, private_questions, owner_reviewed=owner_reviewed,
                                                dataset_version=dataset_version)
    plan = RunPlan(suite=suite, dataset_version=version, dataset_binding=binding,
                   snapshot_sha256=file_digest(DEFAULT_SNAPSHOT_MANIFEST), code_hashes=code_hashes(),
                   settings=settings, questions=questions)
    write_new(output, {"plan": plan.model_dump(mode="json"), "plan_sha256": digest(plan.model_dump(mode="json"))})
    return plan


def load_plan(path: Path) -> RunPlan:
    document = read_json(path)
    plan = RunPlan.model_validate(document["plan"])
    if document["plan_sha256"] != digest(document["plan"]):
        raise ValueError("run plan changed")
    if plan.code_hashes != code_hashes():
        raise ValueError("code/prompt/protocol changed since run lock; prepare a new plan")
    verify_frozen_snapshot()
    if plan.snapshot_sha256 != file_digest(DEFAULT_SNAPSHOT_MANIFEST):
        raise ValueError("run lock uses a different snapshot")
    expected_revision = read_json(DEFAULT_SNAPSHOT_MANIFEST)["shadow_resources"]["embedding"]["revision"]
    if plan.settings.embedding_revision != expected_revision:
        raise ValueError("run lock cannot change the snapshot embedding revision")
    if plan.settings.retrieval_backend == "structured":
        from ingestion.structured_corpus import DEFAULT_BUNDLE, load_bundle
        from ingestion.structured_index import DEFAULT_INDEX
        load_bundle()
        if (plan.settings.retrieval_corpus_sha256 != file_digest(DEFAULT_BUNDLE / "chunks.json") or
                plan.settings.retrieval_index_sha256 != file_digest(DEFAULT_INDEX / "index.json")):
            raise ValueError("structured retrieval resources changed since run lock")
    if plan.suite != "held_out":
        questions, binding, version = questions_for(plan.suite)
        if questions != plan.questions or binding != plan.dataset_binding or version != plan.dataset_version:
            raise ValueError("query-only plan differs from the reviewed dataset")
    return plan


def summarize_usage(observations: list[dict], settings: RunSettings) -> dict:
    complete = bool(observations)
    input_tokens = output_tokens = 0
    cache_accounted = True
    for observation in observations:
        usage = observation.get("usage")
        if not observation.get("completed") or not isinstance(usage, dict):
            complete = False
            continue
        if "promptTokenCount" in usage:
            # Retain compatibility with frozen Gemini observations and old run receipts.
            from ai.llm.usage import normalize_usage
            usage = normalize_usage("gemini", usage)
        a, b = usage.get("input_tokens"), usage.get("output_tokens")
        if any(type(v) is not int or v < 0 for v in (a, b)):
            complete = False
            continue
        input_tokens += a
        output_tokens += b
        cache_accounted = cache_accounted and usage.get("cached_input_tokens") == 0 and usage.get("cache_write_input_tokens") == 0
    cost = None
    if complete and cache_accounted and settings.input_usd_per_million is not None and settings.output_usd_per_million is not None:
        cost = (input_tokens * settings.input_usd_per_million + output_tokens * settings.output_usd_per_million) / 1_000_000
    return {"llm_calls": len(observations), "usage_complete": complete,
            "input_tokens": input_tokens if complete else None,
            "output_tokens": output_tokens if complete else None, "cost_usd": cost}


async def run_questions(plan: RunPlan, runtime, *, execution_kind: str = "live",
                        on_record: Callable[[dict], None] | None = None) -> list[dict]:
    records = []
    for question in plan.questions:
        started = time.perf_counter()
        before = len(runtime.usage())
        output, error = None, None
        try:
            output = await asyncio.wait_for(runtime.execute(question), timeout=plan.settings.timeout_seconds)
            if not isinstance(output, dict):
                raise ValueError("runtime result must be an object")
            if question.mode == "end_to_end":
                from backend.schemas.answer import AnswerResult
                output = AnswerResult.model_validate(output).model_dump(mode="json")
        except Exception as exc:
            # Do not persist exception text/tracebacks that can contain keys or requests.
            error = {"category": "provider_or_pipeline_error", "type": type(exc).__name__}
            from ai.diagnostics import PipelineError
            if isinstance(exc, PipelineError):
                error.update(stage=exc.stage, type=exc.error_type)
            output = None
        record = {"id": question.id, "mode": question.mode, "execution_kind": execution_kind,
                  "output": output, "error": error,
                  "elapsed_ms": (time.perf_counter() - started) * 1000,
                  "usage": summarize_usage(runtime.usage()[before:], plan.settings)}
        if hasattr(runtime, "last_trace"):
            record["diagnostics"] = runtime.last_trace
        record["result_sha256"] = digest(record)
        records.append(record)
        if on_record is not None:
            # Persistence errors must stop the run, not become a model outcome.
            on_record(record)
    return records


def verify_run(directory: Path) -> tuple[RunPlan, list[dict]]:
    receipt = read_json(directory / "run.json")
    plan = RunPlan.model_validate(receipt["plan"])
    # Hash the original representation: v1 receipts do not contain v2 provider fields.
    if receipt["plan_sha256"] != digest(receipt["plan"]):
        raise ValueError("run plan digest changed")
    path = directory / "results.jsonl"
    if receipt["results_sha256"] != file_digest(path):
        raise ValueError("run results changed")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    if [r["id"] for r in records] != [q.id for q in plan.questions]:
        raise ValueError("run must account for every planned question exactly once")
    for record, question in zip(records, plan.questions, strict=True):
        if record["mode"] != question.mode or record["execution_kind"] != receipt["execution_kind"]:
            raise ValueError("run mode/kind mismatch")
        if record["result_sha256"] != digest({k: v for k, v in record.items() if k != "result_sha256"}):
            raise ValueError("result digest changed")
    return plan, records


async def execute_plan(plan_path: Path, output_dir: Path, preflight_path: Path | None = None) -> dict:
    plan = load_plan(plan_path)
    if output_dir.exists():
        raise FileExistsError("run output exists; choose a new directory")
    if preflight_path is None:
        raise ValueError("live runs require a successful plan-bound LLM preflight; pass --preflight")
    from evaluation.llm_preflight import verify_preflight
    verify_preflight(preflight_path, plan_path)
    from evaluation.core_runtime import create_live_runtime
    runtime = create_live_runtime(plan.settings, needs_retrieval=any(q.mode == "end_to_end" for q in plan.questions))
    # Resource/model preflight fails before creating output or charging an LLM call.
    output_dir.mkdir(parents=True)
    completed = 0

    def checkpoint(record: dict) -> None:
        nonlocal completed
        completed += 1
        # Incomplete runs have checkpoints but no final receipt; they cannot score.
        write_new(output_dir / "checkpoints" / f"{completed:03d}.json", record)
        print(json.dumps({"completed": completed, "total": len(plan.questions),
                          "id": record["id"], "status": (record["output"] or {}).get("status"),
                          "error": record["error"], "elapsed_ms": round(record["elapsed_ms"])}), flush=True)

    try:
        records = await run_questions(plan, runtime, on_record=checkpoint)
    finally:
        runtime.close()
    write_new(output_dir / "results.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    receipt = {"plan": plan.model_dump(mode="json"), "plan_sha256": digest(plan.model_dump(mode="json")),
               "execution_kind": "live", "results_sha256": file_digest(output_dir / "results.jsonl"),
               "case_count": len(records), "errors": sum(r["error"] is not None for r in records)}
    write_new(output_dir / "run.json", receipt)
    return {"case_count": receipt["case_count"], "errors": receipt["errors"], "semantic_review": "pending"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    lock = actions.add_parser("settings")
    lock.add_argument("--output", type=Path, required=True)
    prepare = actions.add_parser("prepare")
    prepare.add_argument("--suite", choices=["reviewed", "held_out"], required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--settings", type=Path)
    prepare.add_argument("--questions", type=Path)
    prepare.add_argument("--dataset-version")
    prepare.add_argument("--owner-reviewed", action="store_true")
    run = actions.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--live", action="store_true", required=True)
    run.add_argument("--preflight", type=Path)
    args = parser.parse_args(argv)
    if args.action == "settings":
        write_new(args.output, default_settings().model_dump(mode="json"))
        print(json.dumps({"settings_saved": True, "model_calls": 0}))
    elif args.action == "prepare":
        plan = prepare_plan(args.suite, args.output, settings=RunSettings.model_validate(read_json(args.settings)) if args.settings else None,
                            private_questions=args.questions, owner_reviewed=args.owner_reviewed, dataset_version=args.dataset_version)
        print(json.dumps({"suite": plan.suite, "cases": len(plan.questions), "model_calls": 0}))
    else:
        print(json.dumps(asyncio.run(execute_plan(args.plan, args.output, args.preflight))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
