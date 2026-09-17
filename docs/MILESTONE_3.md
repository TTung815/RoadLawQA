# Evidence grading and bounded retrieval retry

Milestone 3 adds `POST /api/v1/retrieve/agentic` with the same request schema as
Milestone 2: `current_query`, chronological `chat_history`, and `top_k` (1–20).
`POST /api/v1/retrieve` retains the Milestone 2 behavior for later comparison.

The new flow contextualizes once, retrieves, and grades the chunks against the
original standalone legal information need. A weak grade triggers one query rewrite
and a second retrieve/grade step. A sufficient grade ends the workflow immediately.
No legal answer or citation verification is performed.

The asynchronous service uses `AgentState` internally and calls `Retriever.search()`.
Grading and rewriting use structured output exclusively through `LLMProvider`.
There is no LangGraph dependency: this workflow has one branch and at most two
iterations. Components remain independently testable for later orchestration changes.

## Routing and evidence selection

- `EvidenceGrade` contains `sufficient`, a nonempty `reason`, and required `coverage`
  entries (`aspect`, `covered`). The model identifies required aspects from the original
  question. Explicit monetary-only questions need monetary evidence; explicit sanction
  questions need that sanction; broad sanction questions must also establish applicable
  license points and additional sanctions, rather than silently narrowing to money.
  Missing coverage forces `sufficient=false` even if the provider sets it true. Empty
  sufficient coverage, duplicate aspects and malformed values fail validation. Similarity
  scores are excluded. The model still determines semantic applicability; this is not
  a hard-coded legal answer or a guarantee against every model grading error.
- Empty chunks deterministically receive an insufficient grade without a grader LLM call.
- Rewriting receives the original standalone question, the attempted query, and
  the evidence gap and structured `missing_aspects`. A retry targets missing coverage
  while preserving the original subject, violation, numeric range and requested
  consequence. Its prompt preserves legal intent and constraints and forbids
  invented legal facts, citations, penalty values, or article numbers.
- `MAX_RETRIEVAL_ATTEMPTS` defaults to 2 and accepts only 1 or 2. It is read from
  the process environment or repository-root `.env` on first service construction.
  The service validates the bound and uses a finite loop. Rewriting runs only if
  another retrieval attempt remains, so there is at most one rewrite per request.
- Retrieval candidates are accumulated and deduplicated by chunk ID, keeping the
  first occurrence and order. Each changed evidence pool is graded together against
  the original standalone question. The grader ignores unrelated chunks and can use
  complementary passages; no extra relevance filter risks discarding useful context.
  The returned pool may contain up to `max_attempts * top_k` chunks; per-attempt top-k
  is unchanged. Distinct IDs sharing a citation remain distinct.
- Empty/duplicate-only retries preserve the previous evidence and grade without another
  grader call. If both attempts are weak, the combined pool is returned as insufficient.
  If all attempts are empty, the result contains no chunks.
- `attempts[].chunk_ids` and `citations` describe that attempt's raw retrieval results;
  `evidence_chunk_ids` describes the accumulated pool judged by its `grade`.
  `selected_attempt` identifies the accumulated snapshot supplying the final grade,
  not the exclusive source of returned chunks. No cross-query score comparison is used.
- Provider, validation, and retrieval errors propagate as server errors, not as
  successful insufficient results. The workflow retries evidence gaps, not infrastructure failures.

LLM-based sufficiency and semantic constraint preservation still need evaluation;
unit tests establish contracts and routing with scripted providers, not real-model accuracy.

## Running

Use the existing Milestone 2 prerequisites and run from the repository root:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/v1/retrieve/agentic \
  -H 'Content-Type: application/json' \
  --data '{"current_query":"Ô tô vượt đèn đỏ thì sao?","chat_history":[{"role":"user","content":"Xe máy vượt đèn đỏ có bị tước giấy phép lái xe không?"}],"top_k":3}'
```

The agentic route normally needs Gemini credentials for grading even with empty
chat history. The baseline Milestone 2 route still bypasses LLM use when history is
empty. Health remains independent of credentials, retrieval resources, and retry configuration.
Restart the API after configuration changes because service composition is cached.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/unit -q
```

Default tests use fakes and in-memory HTTP transports. The existing opt-in integration
test exercises legacy retrieval, not live grading/rewrite quality. It is unchanged.

## Debug examples

The following are excerpts generated using scripted test providers and test chunks.
They demonstrate routing and observation fields, not actual legal evidence.

First-attempt success:

```json
{
  "retrieval_queries": [
    "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?"
  ],
  "retrieval_attempts": 1,
  "rewritten_query": null,
  "grade": {
    "sufficient": true,
    "reason": "Requested sanction is supported.",
    "coverage": [
      {
        "aspect": "additional_sanction",
        "covered": true
      }
    ]
  },
  "selected_attempt": 1,
  "attempts": [
    {
      "attempt": 1,
      "query": "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?",
      "grade": {
        "sufficient": true,
        "reason": "Requested sanction is supported.",
        "coverage": [
          {
            "aspect": "additional_sanction",
            "covered": true
          }
        ]
      },
      "chunk_ids": [
        "first"
      ],
      "citations": [
        "Test citation first"
      ],
      "evidence_chunk_ids": [
        "first"
      ]
    }
  ]
}
```

Weak evidence followed by successful retry:

```json
{
  "retrieval_queries": [
    "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?",
    "Chế tài tước giấy phép lái xe đối với người điều khiển ô tô vượt đèn đỏ?"
  ],
  "retrieval_attempts": 2,
  "rewritten_query": "Chế tài tước giấy phép lái xe đối với người điều khiển ô tô vượt đèn đỏ?",
  "grade": {
    "sufficient": true,
    "reason": "Requested sanction is supported.",
    "coverage": [
      {
        "aspect": "additional_sanction",
        "covered": true
      }
    ]
  },
  "selected_attempt": 2,
  "attempts": [
    {
      "attempt": 1,
      "query": "Ô tô vượt đèn đỏ có bị tước giấy phép lái xe không?",
      "grade": {
        "sufficient": false,
        "reason": "Missing license-suspension evidence for cars running red lights.",
        "coverage": [
          {
            "aspect": "additional_sanction",
            "covered": false
          }
        ]
      },
      "chunk_ids": [
        "first"
      ],
      "citations": [
        "Test citation first"
      ],
      "evidence_chunk_ids": [
        "first"
      ]
    },
    {
      "attempt": 2,
      "query": "Chế tài tước giấy phép lái xe đối với người điều khiển ô tô vượt đèn đỏ?",
      "grade": {
        "sufficient": true,
        "reason": "Requested sanction is supported.",
        "coverage": [
          {
            "aspect": "additional_sanction",
            "covered": true
          }
        ]
      },
      "chunk_ids": [
        "second"
      ],
      "citations": [
        "Test citation second"
      ],
      "evidence_chunk_ids": [
        "first",
        "second"
      ]
    }
  ]
}
```

Responses also retain `original_query`, `standalone_query`, and complete final `chunks`.
This trace supports later comparison with legacy single-turn and Milestone 2 retrieval.
Answer generation, citation verification, evaluation/calibration, and decisions about
additional workflow orchestration remain outside Milestone 3.
