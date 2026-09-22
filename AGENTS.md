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
is the legacy Streamlit UI; `configs/` holds settings. Legal source artifacts live
under `data/raw/legal/`, their registry/reviews under `data/legal_sources/`, and
derived current-law artifacts under `data/processed/current-law/`. Tests live in
`tests/{unit,integration}/`.

Read `docs/README.md` and `docs/SESSION_HANDOFF.md` first. Read
`docs/MILESTONE_5_STATUS.md`, `docs/MILESTONE_5.md` and `docs/LEGAL_SCOPE.md`
before corpus or evaluation work. Read `docs/MILESTONE_4.md` when changing the
answer-generation and verification contracts.

## Current State

Milestones 0–4 are implemented. End-to-end flow:
`history + query → contextualize → retrieve → coverage grade → optional structural
expansion/rewrite/retry → accumulated evidence → grounded answer → citation verification`.
Production negative legal conclusions remain blocked without reliable negative-support
provenance.

Milestone 5 is in progress. The legal cutoff is `2026-09-22`. Source/extraction
review and the effective view of Nghị định 168/2024/NĐ-CP amended by
238/2026/NĐ-CP have passed. The next task is to build deterministic current-law
processed chunks, an isolated shadow Weaviate/BM25 index, and a frozen snapshot
receipt. Do not audit benchmark gold or run C0–C4 before that snapshot is frozen.

## Build, Test, and Development Commands

Run from repository root with Python 3.11+ and `.venv`:

```bash
.venv/bin/python -m pip install -r requirements.txt
docker compose --env-file .env -f docker/docker-compose.yml up -d  # Weaviate
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m pytest -q  # Offline default suite
.venv/bin/python -m pytest tests/integration -m integration -q  # Live smoke
```

API docs: `/docs`. `backend/clean_and_split.py` is hard-coded to the 2025 sources.
`backend/build_index.py` deletes and recreates the production `LawChunks`
collection and indexes legacy top-level JSON files. Do not run either script for
Milestone 5 current-law/shadow work. Build isolated tools and resources instead.

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

## Current Legal Data Contract

- `data/legal_sources/registry.json` and its checksums/reviews are the source of
  truth; do not silently replace source files or update hashes without provenance.
- Use 49/VBHN-VPQH and 55/VBHN-VPQH as canonical reading texts. Keep lineage to
  the original laws; do not index both copies as active rules.
- Treat 238/2026/NĐ-CP as an overlay on 168/2024/NĐ-CP, not a complete replacement.
  The effective view is a technical artifact, not an official consolidated text.
- Preserve `legal_as_of`, source locators, amendment provenance, temporal status
  and publication eligibility through processing and indexing.
- Three mixed-date 2028 locators and three future 2029 locators remain blocked
  from publication as recorded in `nd168_effective_view_review.json`. General
  legal review approval does not remove those record-level blocks.
- The 50 historical benchmark questions are candidates only. Rebuild every answer,
  citation and gold label after the current-law snapshot is frozen; do not compare
  V1 scores with V2.
- Do not ingest additional traffic-law documents without a scoped dependency need
  and review. Questions requiring a missing dependency must fail closed.

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
