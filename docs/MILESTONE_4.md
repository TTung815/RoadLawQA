# Milestone 4: grounded answers and citation verification

## Runtime contract

`POST /api/v1/answer` accepts the existing retrieval request:

```json
{
  "current_query": "Còn ô tô thì sao?",
  "chat_history": [
    {"role": "user", "content": "Xe máy vượt đèn đỏ phạt bao nhiêu?"}
  ],
  "top_k": 5
}
```

The lazy answer dependency composes the existing agentic retrieval service with
an `AnswerGenerator` and `CitationVerifier`. Business logic uses `LLMProvider`;
the concrete Gemini provider stays in dependency wiring. Importing the API or
requesting health does not initialize the provider, database or baseline models.

1. Contextualize when history exists; use the current query directly otherwise.
2. Run the existing bounded retrieve/grade/structural expansion/rewrite workflow.
3. Keep the final accumulated, deduplicated evidence and final coverage grade.
4. If insufficient, return `insufficient_evidence` without generation/verification.
5. Otherwise generate a structured list of claims with source chunk IDs.
6. Validate citation provenance deterministically against that final evidence.
7. Verify every claim against its attached sources and overall question coverage.
8. Publish server-rendered claims and citations only when verification passes.

## Citation contract

The model returns `DraftAnswer.claims[{text, chunk_ids, support_state}]`. There is no uncited
answer preamble or arbitrary model-generated citation field. Claims must contain
nonempty text and at least one source ID. Inline numbered legal references are
disallowed: legal references are rendered from the actual chunk's `citation`.
Unknown IDs, duplicate claim IDs, missing citation metadata, empty drafts and
inline legal references fail before any semantic verifier call.

The public answer contains a readable `text` and structured
`claims[{text, support_state, citations[{chunk_id, citation}]}]`. Citations are resolved only by
the server. Multiple leaves can support one claim. Different legal boundaries
must retain their separate consequences rather than collapsing into one range.

For numeric questions, `required_range` carries the retrieval's grounded range
proof into both LLM stages: the source leaves selected by the existing union
validator, their original ranges and the intersections with the requested range.
A closed point intersection is an obligatory branch. An answer that fails to
cite any required branch fails deterministically before semantic verification.

## Verification and failure behavior

Provenance validity is independent of semantic support. The semantic verifier
receives each claim with only its attached chunks for support, and the complete
final evidence for answer completeness. It checks facts, numeric boundaries,
conditions, consequences and negative conclusions. Structural clause membership
only proves which leaves were found in the index; it does not prove complete
applicable-rule coverage or resolved cross-references.

## Legal support states

Coverage items, generated claims and semantic claim assessments carry
`support_state`: `positive_support`, `negative_support` or `unknown`.
Missing states default to `unknown`, never positive or negative support.

`positive_support` means the supplied evidence supports that the rule/consequence
applies (or affirms the subject, conduct or threshold for a coverage aspect).
`negative_support` would require trusted evidence/provenance establishing that
the consequence does not apply within a defined legal scope. `unknown` cannot
authorize a definitive legal conclusion.

Production currently has **no provenance that proves negative applicability**.
The deterministic publication policy therefore allows only `positive_support`.
The grader normalizes negative/unknown coverage to uncovered `unknown`, overriding
an optimistic `sufficient=true`. The answer service also checks the final support
states before generation. Negative/unknown draft claims fail verification before
a semantic call. Semantic assessments are classified independently of draft labels;
negative/unknown assessments override `supported=true` and prevent publication.

Neither `complete_clause_chunk_ids`, arbitrary completeness metadata, nor model
confidence can authorize negative support. The synthetic completeness fixture in
unit tests is explicitly test-only and remains blocked by the production policy.
Enabling negative answers later requires a real provenance enhancement, not a
model-generated completeness flag or a relaxed prompt. Semantic classification
of natural-language claims remains a model judgment; the deterministic guards
enforce the represented states rather than formally proving sentence meaning.

Exactly one assessment per claim is required. Missing, duplicated or unknown
assessment indices fail closed. Every claim must be supported and the answer
complete. A valid source ID cannot override an unsupported claim.

The semantic verifier must also assess each required numeric branch exactly
once through `range_assessments[{branch_index, addressed, reason}]`. The server
adds the actual `chunk_id` to public range assessments; the verifier does not
recopy long source hashes. Missing, duplicate
or unknown branches fail closed. A branch marked unaddressed overrides an
optimistic overall completeness flag. Merely citing every source is insufficient:
the claims must answer each branch with its appropriate consequences. This
contract fixes a reproduced live false positive where the generator omitted the
lower inclusive boundary and a single overall completeness flag missed it.

There is one generation call and at most one semantic verification call.
Verification failure returns `verification_failed`, `answer: null`, explicit
verification issues and the original useful evidence. The unverified draft is
not published. `repair_attempts` is always zero; there is no repair loop.

Insufficient retrieval returns `answer: null`, verification `not_run`, coverage
gaps and useful evidence. It explicitly does not equate missing retrieval with
the absence of a legal sanction. Negative legal answers are currently blocked,
including the car/red-light/license-suspension case; `insufficient_evidence` is
a valid outcome for that question.

Provider, malformed structured-output and retrieval failures propagate as
service errors (HTTP 500 for unhandled failures), never as legal answers.

## Observability and architectural scope

`retrieval` retains the original and standalone queries, attempts, final coverage,
selected snapshot, final chunks and structural expansion trace. `evidence_citations`
lists final source IDs and citation metadata. `verification` distinguishes
provenance, semantic support and completeness. No prompts or unverified draft
are exposed in the response.

`retrieval.timings` measures contextualization, baseline retrieval, grading
(including regrading), rewrite, structural lookup and retrieval total.
`timings` measures generation, verification and end-to-end total. Values are
milliseconds; total includes orchestration overhead, so component sums may differ.
Empty-history contextualization records its tiny local execution cost with no
LLM call. Timing is observational and does not change retrieval decisions.

LangGraph is not introduced: a service with explicit branches and the existing
fixed retrieval bound is enough. No legacy algorithm, chunking, indexing, top-k,
answer persistence, frontend or provider configuration changes are required.
The unused initial chat schemas and AgentState placeholders remain unchanged.

The verifier is a model-based check, not a formal legal proof. Its reliability
and the corpus's scope/currentness still require benchmark evaluation. A repair
strategy, persistence, streaming and broad latency optimization are postponed.
