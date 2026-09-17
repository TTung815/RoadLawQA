# Coverage-directed legal neighborhood expansion

`POST /api/v1/retrieve/agentic` now optionally expands structural evidence after an
insufficient grade and before rewriting. Milestone 2 `/retrieve`, hierarchical
chunking, embedding, Hybrid + Reranker scoring, candidate cap and per-search top-k
remain unchanged. No answer generation or citation verification is performed.

## Boundary and activation

The grader reports `anchor_chunk_ids` from supplied evidence. The workflow accepts
anchors only with covered `subject_violation` and no uncovered range/condition
aspect. IDs outside the supplied pool are validation errors. Anchors also need
nonempty law, article and clause metadata. This model-based relevance judgment is
conservative but still needs evaluation; same article alone does not prove applicability.

For supported numeric questions, grading receives source range candidates and
their computed intersections with the question. Each candidate must be assessed,
including irrelevant leaves. Structured `range_coverage` records verbatim bounds,
the unchanged unit, and per-leaf semantic compatibility. Grounding and decimal
interval checks can establish joint threshold coverage and select an anchor set:
a closed boundary leaf and the adjacent open interval can jointly cover a closed
requested range. No individual leaf needs to cover the whole request. Different
documents/articles/article titles, missing boundary points and ambiguous overlap
are not joined. Only one requested interval and the supported Vietnamese numeric
grammar are verified; unsupported compound bounds are not inferred as unbounded.

`AspectCoverage.required` distinguishes applicable information needs from
irrelevant facets. Irrelevant facets are omitted as before; missing required
subject/condition evidence still blocks the existing safety gate. Older outputs
default to `required=true`. Numeric coverage does not supply sanction coverage or
override uncertain semantic applicability. Omitted/duplicated candidate reviews,
invented quotes and unknown IDs are provider-output errors and propagate.

`LegalNeighborhoodExpander` receives an asynchronous article-fetch callable, known
anchors, missing aspects and existing evidence. It imports no database, model or
LLM provider. `WeaviateArticleLookup` implements lazy, read-only, paginated lookup
in a worker thread, closes its client on success/failure and verifies exact document
and article identity after WORD-tokenized database filtering. It reuses the legacy
adapter's mapping function so structural and baseline IDs deduplicate consistently.
Agent orchestration has no Weaviate or legacy implementation dependency.

Expansion currently supports `license_points` and `additional_sanction` gaps.
Other gaps retain baseline retrieve/rewrite behavior. There is at most one activated
expansion per request; skipped checks with no reliable anchor can precede it. The
Hybrid + Reranker loop remains bounded to one or two searches as in Milestone 3.

## Selection and budgets

- At most two anchored document/article scopes are inspected.
- Consequence siblings are identified by their actual `clause_head`, not fixed
  regulation/article/clause numbers. Local `khoản ... Điều này` references to the
  anchor clause/point receive priority. No inference about numeric thresholds is
  made from matching numbers in the question.
- Exact-20 and over-20-through-35 use distinct retrieved anchors and references;
  a question spanning both can use both anchors. No range is rewritten or collapsed.
- When an additional-sanction clause has no matching reference, the entire small
  clause can be included for negative applicability assessment. It is not asserted
  to apply. Such a clause is added atomically, never as an incomplete exhaustive list.
- Evidence additions are limited to eight new chunks and 12,000 characters counting
  both `text` and `enriched_text`; metadata/JSON overhead is additional. Oversize
  chunks/groups are skipped. Structural chunk order is deterministic and existing
  evidence always wins ID collisions. Unrelated articles/documents and unmatched
  license-point references are excluded.
- References to other articles/documents, compressed/unsupported point-list syntax
  and multi-hop references are not resolved by this first implementation.

The combined pool is regraded against the original standalone question only if
new evidence was added. A sufficient grade stops immediately. Otherwise the remaining
coverage gap guides the existing single rewrite/retry. Infrastructure and validation
errors propagate; no failed structural lookup becomes a successful weak result.

## Trace and comparison

Responses expose `structural_expansion_enabled` and `structural_expansions`:
activation/reason, missing aspects, anchor IDs and law/article scopes, sibling count,
added IDs/citations, accumulated evidence IDs, before/after grade, lookup/regrade
milliseconds, and added text characters. `attempts` keeps each baseline search's
trace; structural grading appears separately. `selected_attempt` identifies the
search snapshot extended by expansion, not the exclusive source of final chunks.

Set `STRUCTURAL_EXPANSION_ENABLED=false` to compare unchanged Milestone 3 behavior;
the production default is true. Restart the API after changing this flag because
composition is cached. Pure liveness remains independent of resource initialization.

Default tests use scripted providers and fake lookups/client modules. Live verification
requires the existing configured Gemini key, Weaviate data, BM25 and cached models.
Evaluate actual reference chains and evidence coverage with human labels, as well
as false-positive grades, wrong vehicle/range/document additions, chunk overhead
and latency. The grader boolean alone is not the success metric.
