# RoadLawQA V2 — current development context

Milestones 0–4 are implemented. Start with this page; read
[the answer contract](MILESTONE_4.md) when changing generation or verification.
Historical live reports and course PDFs are optional references, not routine context.

Milestone 5 hiện tạm dừng benchmark theo luật hiện hành để refresh corpus tại mốc
`2026-09-22`. Xem [tiến độ ngắn gọn](MILESTONE_5_STATUS.md),
[roadmap Milestone 5](MILESTONE_5.md) và [phạm vi pháp lý](LEGAL_SCOPE.md).
Baseline Pha 0 chỉ được giữ để tái lập kỹ thuật, không dùng so điểm pháp lý.

## Current workflow and boundaries

`history + query → contextualize → retrieve → grade → optional structural expansion
→ optional gap-directed rewrite/retrieval → accumulated evidence → generate → verify`

- All business LLM calls use `LLMProvider`; retrieval uses `Retriever` through
  `LegacyRetrieverAdapter`. The adapter lazily imports the existing pipeline and
  runs synchronous initialization/retrieval in a worker thread.
- Empty history uses the trimmed query directly. Any nonempty history invokes
  contextualization once; no keyword heuristic bypasses it. The prompt selects
  relevant history and preserves standalone meaning.
- The legacy Hybrid + Reranker, chunking/indexing and per-search top-k are preserved.
  No LangGraph, PostgreSQL or Next.js has been added.
- Health is pure liveness: it initializes no provider, database or models.

## Retrieval contract

- API requests contain `current_query`, chronological user/assistant `chat_history`
  and `top_k` (1–20, default 5).
- Grading checks the original standalone information need, including monetary
  penalties, license points, additional sanctions, subject/conduct, ranges and
  conditions when required. Relevance alone does not establish sufficiency.
- Required uncovered aspects override `sufficient=true`. Support states are
  `positive_support`, `negative_support`, `unknown`; missing states are unknown.
  Production currently accepts only positive support. See the answer contract.
- `MAX_RETRIEVAL_ATTEMPTS` defaults to 2 and allows only 1 or 2. At most one rewrite
  targets the remaining gap while preserving the original intent and constraints.
- Evidence accumulates across searches and expansion, deduplicated by ID with the
  first occurrence/order retained. Empty or duplicate-only retries retain evidence
  and grade. Different IDs with the same citation remain distinct.
- `attempts[].chunk_ids` describes each search; `evidence_chunk_ids` describes the
  pool graded together. `selected_attempt` identifies that accumulated snapshot.
  Provider, validation and retrieval errors propagate rather than becoming success.

## Structural expansion and numeric coverage

- Expansion requires known anchors with covered subject/conduct, no uncovered
  range/condition facet, and law/article/clause metadata. Sharing an article alone
  does not establish applicability.
- Complementary compatible leaves can jointly cover a requested numeric interval.
  Verbatim bounds, units, semantic compatibility and interval grounding are checked;
  closed boundary points remain distinct from open intervals. Incompatible scopes,
  gaps and ambiguous overlaps cannot establish joint coverage. Only one requested
  interval and the implemented Vietnamese numeric grammar are supported.
- At most one activated expansion occurs per request, for `license_points` or
  `additional_sanction` gaps. Lazy read-only article lookup inspects at most two
  anchored scopes; additions are bounded to 8 chunks and 12,000 characters counting
  both `text` and `enriched_text`. Existing evidence wins ID collisions.
- Consequence clauses and local references guide selection. A whole small
  additional-sanction clause may be added atomically, but its index membership
  **does not prove complete applicable-rule coverage or authorize a negative claim**.
  Cross-article/document, unsupported compressed point lists and multi-hop
  references are not resolved.
- Regrade only when evidence changes. Responses expose expansion anchors, scopes,
  inspected count, added chunks, before/after grades and timings.
  `STRUCTURAL_EXPANSION_ENABLED=false` disables expansion for baseline comparison;
  the production default is true.

## Run and test

Run from the repository root with the existing `.venv`. Live retrieval requires
indexed `LawChunks`, BM25 resources and embedding/reranker models; grading and
answering also require configured Gemini credentials. Configure `GEMINI_API_KEY`
or `GEMINI_API_KEYS` in `.env`; the default model is `gemini-2.5-flash`, overridden
by `GEMINI_MODEL_NAME`. Restart the API after settings changes: services are cached.

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m pytest -q
# Opt-in legacy retrieval smoke test; not a Gemini semantic evaluation:
.venv/bin/python -m pytest tests/integration -m integration -q
```

Use `/docs` for interactive requests. Endpoints: `GET /api/v1/health`,
`POST /api/v1/retrieve`, `POST /api/v1/retrieve/agentic`, `POST /api/v1/answer`.
The plain retrieve endpoint generates no answer and needs no LLM with empty history.
Default tests require no network, keys, database or model loading.

Legacy retrieval still uses local Weaviate ports 8080/50051 and a working-directory
BM25 path; V2 settings do not override those legacy choices. Keep
`WEAVIATE_CLUSTER_HOSTNAME` stable for an existing Docker volume. If an index
reports an unresolved node name, use its persisted name rather than deleting data.

## Historical references — read only when needed

- [Milestone 3.5 live verification](archive/MILESTONE_3_5_VERIFICATION.md).
- [Milestone 4 live verification](archive/MILESTONE_4_VERIFICATION.md). Recorded live
  outcomes predate the support-state fix; they are not verification of the new contract.
- `CS529_slide.pdf`: course presentation.
- `CS431_FINAL_REPORT.pdf`: retained course report.

Model judgments and corpus scope/currentness still need evaluation. Negative
answers remain blocked until trusted applicable-rule provenance exists. Further
evaluation, repair loops, persistence, streaming and performance work are postponed.
