"""Bounded plain/real-schema compatibility diagnostics, never QA accuracy scoring."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Sequence

from ai.agent.answer_generator import GeneratedAnswer
from ai.agent.citation_verifier import SemanticVerification
from ai.agent.contextualizer import ContextualizedQuery
from ai.llm.base import LLMMessage
from evaluation.core_runtime import create_evaluation_provider
from evaluation.snapshot import digest
from ingestion.legal_registry import read_json


def schema_fixtures():
    """Synthetic non-legal fixtures; no benchmark questions or reference answers."""
    return [
        (ContextualizedQuery, {"standalone_query": "Compatibility diagnostic"}),
        (GeneratedAnswer, {"answer": {"claims": [{"text": "Compatibility diagnostic only.",
                                   "chunk_ids": ["diagnostic-only"], "support_state": "unknown"}]}}),
        (SemanticVerification, {"assessments": [{"claim_index": 0, "supported": False,
                                                "reason": "No legal evidence.", "support_state": "unknown"}],
                                "answer_complete": False, "completeness_reason": "Diagnostic only.",
                                "range_assessments": [{"branch_index": 0, "addressed": False,
                                                       "reason": "Diagnostic only."}]}),
    ]


async def check_provider(provider, timeout_seconds: float) -> list[dict]:
    checks = []
    try:
        await asyncio.wait_for(provider.generate([LLMMessage(role="user", content="Reply with OK.")],
                                                temperature=0.0), timeout_seconds)
    except Exception as exc:
        return [{"name": "plain", "passed": False, "error_type": type(exc).__name__}]
    checks.append({"name": "plain", "passed": True})
    for schema, value in schema_fixtures():
        fixture = schema.model_validate(value).model_dump(mode="json")
        try:
            result = await asyncio.wait_for(provider.generate_structured([
                LLMMessage(role="system", content="Schema compatibility diagnostic only. Copy the supplied JSON object exactly."),
                LLMMessage(role="user", content=json.dumps(fixture, ensure_ascii=False)),
            ], schema, temperature=0.0), timeout_seconds)
            if result.model_dump(mode="json") != fixture:
                raise ValueError("Structured diagnostic did not preserve the fixture")
        except Exception as exc:
            checks.append({"name": schema.__name__, "passed": False, "error_type": type(exc).__name__})
            break
        checks.append({"name": schema.__name__, "passed": True})
    return checks


async def run_preflight(plan_path: Path, output: Path) -> dict:
    from evaluation.core_runner import load_plan, summarize_usage, write_new
    if output.exists():
        raise FileExistsError("preflight output exists; choose a new file")
    plan = load_plan(plan_path)
    provider = None
    try:
        provider = create_evaluation_provider(plan.settings)
    except ValueError:
        checks = [{"name": "credentials", "passed": False, "error_type": "ConfigurationError"}]
    else:
        checks = await check_provider(provider, plan.settings.timeout_seconds)
    passed = len(checks) == len(schema_fixtures()) + 1 and all(check["passed"] for check in checks)
    result = {"format_version": 1, "kind": "llm_compatibility_preflight",
              "plan_sha256": read_json(plan_path)["plan_sha256"],
              "provider": plan.settings.provider, "model": plan.settings.model,
              "passed": passed, "checks": checks,
              "usage": summarize_usage(provider.observations if provider is not None else [], plan.settings),
              "qa_batch_started": False, "semantic_accuracy": None}
    result["receipt_sha256"] = digest(result)
    write_new(output, result)
    return result


def verify_preflight(path: Path, plan_path: Path) -> None:
    from evaluation.core_runner import load_plan
    plan = load_plan(plan_path)
    result = read_json(path)
    if result.get("receipt_sha256") != digest({k: v for k, v in result.items() if k != "receipt_sha256"}):
        raise ValueError("preflight receipt changed")
    expected = ["plain"] + [schema.__name__ for schema, _ in schema_fixtures()]
    if (result.get("format_version") != 1 or result.get("kind") != "llm_compatibility_preflight" or
            result.get("plan_sha256") != read_json(plan_path)["plan_sha256"] or
            result.get("provider") != plan.settings.provider or result.get("model") != plan.settings.model or
            result.get("passed") is not True or [c.get("name") for c in result.get("checks", [])] != expected or
            any(c.get("passed") is not True for c in result.get("checks", []))):
        raise ValueError("need a successful plain/all-schema preflight for this exact locked plan")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = asyncio.run(run_preflight(args.plan, args.output))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "llm_calls": result["usage"]["llm_calls"], "qa_batch_started": False}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
