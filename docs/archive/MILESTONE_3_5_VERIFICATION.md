# Milestone 3.5 live verification

Current verdict: **MILESTONE 3.5 VERIFIED** for the requested complementary
coverage/anchor fix. The final confirmation is documented below.

The initial five-case run below had verdict **MILESTONE 3.5 NEEDS FIX**;
its measurements and failure are retained as historical evidence.

Live verification now runs with the configured Gemini provider and the existing
RoadLawQA retrieval pipeline. Four of five cases passed evidence inspection. The
original inclusive 20–35 km/h query still exposes a coverage/anchor grading error.
Passing unit tests and successful Gemini requests do not resolve that failure.

## Configuration and previous blockers

- V2 settings, provider default and `.env.example` now use `gemini-2.5-flash`.
  The local `.env` uses the same model. Credentials are not included in this report.
- Earlier verification was blocked by Gemini quota exhaustion. After additional
  keys were configured, Gemini 3.8 requests encountered HTTP 503 and read timeouts.
  A separate minimal request returned the service message that the model was
  experiencing high demand; a request with another configured key succeeded.
- The provider now permits two transient retries per generation, with exponential
  backoff and jitter, uses the next configured key, skips quota-exhausted keys,
  and allows a 90-second read timeout. Nontransient HTTP errors and exhausted
  retries propagate. Concurrent calls retain their own key/quota bookkeeping.
  Logs use key indices rather than key fragments. The agent search limit is unchanged.
- With that provider change, the five-case Gemini 3.8 run had one successful
  monetary-only case, three HTTP 503 failures and one timeout. It was not a
  successful verification of structural expansion.

## Test results

```text
.venv/bin/python -m pytest tests/unit -q --tb=no
174 passed in 1.00s

.venv/bin/python -m pytest -q --tb=no
174 passed, 1 deselected in 1.04s

git diff --check
passed
```

Default configuration excludes the integration marker. Real verification below
was executed separately through the production service factory, not through mocks.

## Real execution

The five queries used `top_k=5`, the real legacy Hybrid + Reranker, local indexed
Weaviate data, the existing BM25 index and cached embedding/reranker models.
Structural expansion was enabled. No Uvicorn process was required.

All five service calls completed without Gemini HTTP/transport errors. History
was empty in these cases: each standalone query equaled its original query, and
no contextualization generation was invoked. This run does not claim additional
live multi-turn coverage.

| Original / standalone query | Searches | Added chunks | Grade before → final | Rewrite | Total seconds |
| --- | ---: | ---: | --- | --- | ---: |
| Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào? | 2 | 0 | insufficient → insufficient | yes | 41.64 |
| Ô tô vượt quá tốc độ trên 20 đến 35 km/h bị phạt bao nhiêu tiền? | 1 | 0 | sufficient → sufficient | no | 17.21 |
| Ô tô vượt quá tốc độ đúng 20 km/h bị xử phạt thế nào? | 1 | 4 | insufficient → sufficient | no | 36.65 |
| Ô tô vượt quá tốc độ trên 20 đến 35 km/h bị xử phạt thế nào? | 1 | 4 | insufficient → sufficient | no | 38.60 |
| Ô tô vượt quá tốc độ trên 20 đến 35 km/h có bị trừ điểm giấy phép lái xe không? | 1 | 1 | insufficient → sufficient | no | 33.37 |

Every selected snapshot was attempt 1. In the first case, attempt 2 returned the
same IDs in a different order and contributed no new evidence; retaining the
previous grade/snapshot was the existing intended behavior.

## Actual evidence paths

All citations in this section are from indexed Nghị định số 168/2024/NĐ-CP.

- Monetary-only: baseline điểm a khoản 6 Điều 6 covered the requested monetary
  aspect. No structural lookup or additional-sanction grading was needed.
- Exactly 20: baseline điểm đ khoản 5 Điều 6 became the anchor. Same-document,
  article-6 lookup inspected 81 siblings and selected điểm a khoản 16 Điều 6,
  whose local reference includes điểm đ khoản 5. It also supplied all three
  leaves of khoản 15 (điểm a, b, c), with complete-clause provenance for assessing
  additional-sanction applicability. The original five chunks were retained;
  final evidence contained nine unique chunks. License-point and
  additional-sanction coverage changed from false to true.
- Over 20 through 35: baseline điểm a khoản 6 Điều 6 anchored the same 81-sibling
  scope. Expansion selected điểm b khoản 16 Điều 6, which references khoản 6,
  plus all three leaves of khoản 15 with the same complete-clause provenance.
  Final evidence contained nine unique chunks. Both missing sanction facets
  changed from false to true.
- Explicit license points: the same khoản-6 anchor selected only điểm b khoản 16
  Điều 6. Additional-sanction leaves were not added because that aspect was not
  requested. Final evidence contained six unique chunks; license-point coverage
  changed from false to true.

These paths preserve the different legal references for exactly 20 and over 20.
The complete khoản-15 leaves are context for checking applicability; their
sanctions were not blindly attributed to the anchor offense.

## Reproduced failure: inclusive 20–35

Attempt 1 contained both:

- Điểm a khoản 6 Điều 6: `Điều khiển xe chạy quá tốc độ quy định trên 20 km/h đến 35 km/h;`
- Điểm đ khoản 5 Điều 6: `Điều khiển xe chạy quá tốc độ quy định từ 10 km/h đến 20 km/h;`

The second leaf covers the exact-20 boundary. Nevertheless, the grader set
`threshold_range=false`, selected only the khoản-6 anchor, and said evidence did
not include exactly 20. It also set `condition_exception=false` without describing
that aspect in its reason. License-point and additional-sanction gaps were valid;
the range assessment/anchor omission was not.

The conservative activation gate therefore returned `No reliable structural
anchor.` before each search retry. No article lookup occurred. The rewrite was:

```text
Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị trừ điểm giấy phép lái xe và các hình thức xử phạt bổ sung nào?
```

It preserved the subject, violation, range and missing consequences. Attempt 2
returned exactly the same five IDs, so it could not supply complementary GPLX
evidence. The final result correctly remained insufficient for its actual pool.

The remaining issue is the grader's coverage/anchor interpretation of multiple
compatible range leaves. The existing safety gate should not simply be removed
to force expansion. The next fix should improve coverage/anchor grading and add
regression coverage with this actual multi-leaf evidence before rerunning this
case. This verification did not modify the grader or retrieval algorithm.

## Expansion overhead

| Case | Siblings inspected | Added text characters | Lookup ms | Regrade ms |
| --- | ---: | ---: | ---: | ---: |
| Exactly 20 | 81 | 3,700 | 40.43 | 17,618.77 |
| Over 20 through 35 | 81 | 3,494 | 60.99 | 17,446.83 |
| Explicit license points | 81 | 895 | 37.76 | 11,117.10 |

Characters count `text` plus `enriched_text`; serialized metadata is additional.
Lookup inspected siblings internally, but only one or four new chunks reached
the grader, within the eight-chunk / 12,000-character addition budget.
These are single-run timings, not benchmark percentiles.

## Chunk identities

| Citation shorthand (all Điều 6 of the same regulation) | V2 ID |
| --- | --- |
| khoản 5 điểm đ | `chunk_3055016426770fb75aebc4fc862de5691ecc57dbd064653229d56690a8b3480b` |
| khoản 6 điểm a | `chunk_a79291b3dad755130b6fd39a04c42a738cc7cd2204ba6049136ad8edea29d4c4` |
| khoản 16 điểm a | `chunk_b17a214485b66bcdc40d640446bc103e289389c88c57abce41a78e2f7159885e` |
| khoản 16 điểm b | `chunk_fbae2c31909a1844104788646730074173fe4513dedca1bfc502e65a096c4d7c` |
| khoản 15 điểm a | `chunk_c2e7cd06070709fd7f01bfb61eb819ae25a980b91835d379490af951dc320637` |
| khoản 15 điểm b | `chunk_45f59e16a13c196c46798f5cd4cbb49007b09db23909edce7edbe41e84c73a80` |
| khoản 15 điểm c | `chunk_9584c2eb4e981f718e252f3b442071ecc2f6350786312a5fa102e6b97b58317b` |

The full local run trace is `/tmp/roadlawqa_m35_gemini25_final.json`, including
baseline chunk contents, queries, each structured LLM output, accumulated
evidence, expansion scope, grades and timings. It contains no API keys.

## Scope and remaining evaluation

This rerun changed model configuration and added this report. Earlier provider
resilience and Milestone 3.5 changes remain in the working tree. Legacy retrieval,
chunking/indexing, scoring, candidate cap, embeddings, reranking and top-k defaults
were preserved; no answer generation or citation verification was started.

Files involved across Milestone 3.5 and the subsequent provider fixes:

- Structural retrieval: `ai/retrieval/neighborhood.py`,
  `ai/retrieval/weaviate_lookup.py`, `ai/retrieval/legacy_adapter.py`.
- Grading and orchestration: `ai/agent/evidence_grader.py`,
  `ai/prompts/evidence_grading.py`, `backend/services/agentic_retrieval.py`,
  `backend/dependencies/retrieval.py`.
- Provider/configuration: `ai/llm/gemini.py`, `configs/settings.py`, `.env.example`
  and local ignored `.env`.
- Tests: `tests/unit/test_neighborhood_expansion.py`,
  `tests/unit/test_weaviate_article_lookup.py`, `tests/unit/test_gemini_provider.py`,
  `tests/unit/test_schemas.py`.
- Documentation: `docs/MILESTONE_3_5.md` and this verification report.

Git status also contains the user's changes to `backend/generator.py`; this
verification task did not edit that file.

Structural selection still supports only license-point/additional-sanction gaps
and its current local-reference syntax. Complete-clause provenance describes the
indexed corpus, not proof that the source corpus contains every later legal
amendment. The five cases demonstrate functionality and one failure, not general
legal accuracy. Broader benchmark comparison and human coverage/applicability
review remain necessary after fixing the inclusive-range case.

## Complementary coverage fix: final live confirmation

The remaining issue was in coverage/anchor reasoning, not baseline retrieval.
The grader now receives every recognized source range and its mathematical
intersection with the requested range. It must assess every candidate, including
incompatible leaves. Numeric source grounding, exact units, open/closed boundaries
and metadata scope are checked in `ai/agent/range_coverage.py`. A verified union
can select multiple anchors and correct the threshold facet, while required
subject/condition gaps still block the unchanged structural gate.

`AspectCoverage.required` explicitly identifies unrelated facets; absent flags
default to true for conservative compatibility. Irrelevant facets are omitted
as in the original contract. The prompt preserves the whole question during
combined-evidence grading, including point-sized boundary intersections.

Final tests:

```text
.venv/bin/python -m pytest tests/unit -q --tb=no
207 passed in 1.01s

.venv/bin/python -m pytest -q --tb=no
207 passed, 1 deselected in 0.94s

git diff --check
passed
```

The 33 added cases cover complementary intervals, missing individual leaves,
incompatible vehicle/person/conduct or metadata scopes, gaps, interior/boundary
overlap, exact versus open thresholds, other numbers/units, ungrounded/omitted/
duplicated candidate assessments, unsupported compound bounds, expansion with
two anchors, and preservation of required-condition/subject safety checks.

The diagnosed query was rerun using the real configured `gemini-2.5-flash`,
Weaviate, BM25, embeddings and reranker. The final two live runs both succeeded.
The final confirmation used the current source-expression guards. An offline
audit additionally revalidated both successful traces against the current code.

Final confirmation baseline top-5 citations (same indexed regulation):

1. Điểm a khoản 6 Điều 6 — over 20 through 35, relevant.
2. Điểm a khoản 7 Điều 6 — over 35, outside the requested range.
3. Điểm a khoản 8 Điều 7 — incompatible vehicle scope.
4. Điểm đ khoản 5 Điều 6 — through 20, supplies exactly 20.
5. Điểm a khoản 4 Điều 7 — incompatible vehicle scope.

The selected anchor set was điểm a khoản 6 and điểm đ khoản 5, both Điều 6 of
Nghị định số 168/2024/NĐ-CP. Their computed requested intersections were `(20,35]`
and `[20,20]`, respectively. No single leaf was asserted to cover `[20,35]`.

| Required coverage | Before expansion | Final |
| --- | --- | --- |
| monetary_penalty | true | true |
| subject_violation | true | true |
| threshold_range | true | true |
| license_points | false | true |
| additional_sanction | false | true |

Expansion inspected 81 same-document/article siblings and added exactly:

- Điểm a khoản 16 Điều 6 — local reference to điểm đ khoản 5.
- Điểm b khoản 16 Điều 6 — local reference to khoản 6.
- Điểm a, điểm b and điểm c khoản 15 Điều 6 — the complete additional-sanction
  clause with provenance, used to check applicability for both anchors.

All are from Nghị định số 168/2024/NĐ-CP. Both GPLX provisions are present;
the exact-20 consequence was not replaced with the over-20 consequence.
Existing baseline evidence was retained and deduplicated. Five additions cost
4,595 text/enriched-text characters; the final pool had ten unique chunks.

Final grade: **sufficient=true**. There was one baseline search, one structural
lookup, and two grading calls; no rewrite or second baseline search. Selected
attempt: **1**. Original and standalone queries remained exactly the same.

| Successful run | Baseline ms | First grade ms | Lookup ms | Regrade ms | Total ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| First | 15,217.77 | 23,126.42 | 48.14 | 33,186.84 | 71,582.79 |
| Final confirmation | 13,473.24 | 57,443.13 | 65.61 | 34,061.95 | 105,050.86 |

These include real provider latency/handling and cold resource initialization;
they are individual runs, not performance percentiles.

Local traces: `/tmp/roadlawqa_m35_joint_coverage_intersections.json` and
`/tmp/roadlawqa_m35_joint_coverage_confirmation.json`. Both were audited for
grounded anchor sets, complete candidate review, retained baseline IDs,
deduplication, bounded additions and absence of API keys.

Files touched for this scoped fix:

- `ai/agent/evidence_grader.py`
- `ai/agent/range_coverage.py` (new)
- `ai/prompts/evidence_grading.py`
- `tests/unit/test_complementary_coverage.py` (new)
- `tests/unit/test_neighborhood_expansion.py` (update scripted range assessments)
- `docs/MILESTONE_3_5.md`
- `docs/MILESTONE_3_5_VERIFICATION.md`

The legacy Hybrid + Reranker, chunking/indexing, top-k, structural expansion
algorithm, retry limits and safety gate were not changed by this fix.
No Milestone 4 work was started. Per-leaf semantic applicability still depends
on the provider; interval verification supports its documented numeric grammar,
not a general legal reasoner or unit-conversion system.
