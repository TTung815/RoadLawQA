# Repository Guidelines

## Project Goal

RoadLawQA V2 is a production-oriented Vietnamese Legal Agentic RAG system.

The current implemented domain is road-traffic law, but the architecture should
remain extensible to additional legal domains such as business, real estate and
labor law.

The project evolves the original RoadLawQA RAG prototype into a modular,
evaluation-driven system with:
- independent backend APIs
- provider-neutral LLM integration
- history-aware and agentic retrieval
- grounded answer generation
- citation/evidence verification
- explicit legal-safety behavior
- components that can be evaluated and improved independently

V2 is the primary codebase. The goal is not to maintain the original V1
architecture permanently, but to preserve reproducible baselines while migrating
and improving the system.

## Project Structure & Module Organization

RoadLawQA V2 is a Vietnamese legal Agentic RAG system. Its current implemented
domain is road-traffic law, while the architecture is intended to support
additional legal domains later.

`ai/` holds agents, prompts, providers and retrieval adapters. `backend/` contains
FastAPI routes, services, dependencies and Pydantic schemas. `frontend/app.py`
is the legacy Streamlit UI; `configs/` holds settings. Legal data lives in
`data/{raw,processed}/`. Tests live in `tests/{unit,integration}/`.

Read `docs/README.md` first and `docs/MILESTONE_4.md` when working with the
current answer-generation and verification contracts.

## Current State

Milestones 0–4 completed. End-to-end flow:
`history + query → contextualize → retrieve → coverage grade → optional structural
expansion/rewrite/retry → accumulated evidence → grounded answer → citation verification`.
Production negative legal conclusions remain blocked without reliable negative-support
provenance. Next: evaluation and technical reassessment before further features.

## Build, Test, and Development Commands

Run from repository root with Python 3.11+ and `.venv`:

```bash
.venv/bin/python -m pip install -r requirements.txt
docker compose --env-file .env -f docker/docker-compose.yml up -d  # Weaviate
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m pytest -q  # Offline default suite
.venv/bin/python -m pytest tests/integration -m integration -q  # Live smoke
```

API docs: `/docs`. Run `backend/clean_and_split.py` and `backend/build_index.py`
only for intentional regeneration.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions/modules, `PascalCase` classes
and `UPPER_CASE` constants. Annotate boundaries; use Pydantic schemas.
Prompts belong in ai/prompts/. LLM provider implementations belong in ai/llm/;
provider construction belongs in dependency wiring.
No formatter/linter is configured; follow nearby code and run `git diff --check`.

## Architecture & Safety

Use `LLMProvider` and `Retriever`; business logic must not import Gemini SDKs or
legacy retrieval directly. Legacy modules preserve the measured baseline:
`backend/{retriever_custom,
generator,prompts,clean_and_split,build_index,rag_qa,rag_quiz}.py` and `frontend/app.py`.
They are migration debt, not permanent architecture. Avoid casual edits;
deliberate, benchmarked migration/refactoring may replace them later.
Health initializes no models, database or provider. Keep retries bounded.
Missing evidence is not proof of non-applicability. Never fabricate completeness metadata.

## Engineering Principles

Code, tests and benchmark evidence outrank stale assumptions. Challenge outdated
design decisions when evidence supports change. Introduce major techniques for
demonstrated needs, never merely because they are fashionable.

## Testing Guidelines

Use pytest/pytest-asyncio with deterministic fakes: `test_*.py`, `test_<behavior>`.
Default tests need no network, keys, Weaviate or models. Mark live tests
`integration` (excluded by default). Add behavior regressions; no coverage threshold
is configured.

## Commit & Pull Request Guidelines

Use imperative subjects with history's `feat:`/`docs:` prefixes. PRs explain
behavior, validation and limitations; link issues and include UI screenshots.

## Configuration

Use `.env.example`; never commit secrets. Restart after settings changes.
Preserve Docker volumes and persisted node hostnames.
