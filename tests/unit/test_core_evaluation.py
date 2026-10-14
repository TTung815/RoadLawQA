"""Evaluation infrastructure with deterministic fake outputs, not model scores."""

import json

import pytest
from pydantic import ValidationError

from ai.agent.evidence_grader import EvidenceGrade
from ai.llm.base import LLMProvider
from evaluation import core_runner as runner
from evaluation import core_scoring as scoring
from evaluation.core_runtime import CoreRuntime, hybrid_candidates, map_chunk
from evaluation.core_schema import Question, RunPlan, RunSettings, SemanticReview
from evaluation.snapshot import digest
from ingestion.legal_registry import read_json


def settings(**kwargs):
    return RunSettings(model="fake-test-only", embedding_revision="fixture", reranker_revision="fixture", **kwargs)


def plan(questions):
    return RunPlan(suite="held_out", dataset_version="test-fixture-not-real-heldout", dataset_binding="0" * 64,
                   snapshot_sha256="0" * 64, code_hashes={}, settings=settings(), questions=questions)


@pytest.mark.parametrize("field", ["gold", "reference_answer", "answer", "required_facets"])
def test_questions_reject_answer_leakage(field):
    with pytest.raises(ValidationError):
        Question.model_validate({"id": "fixture", "current_query": "query", field: "hidden"})


def test_question_pool_only_in_replay():
    with pytest.raises(ValidationError):
        Question(id="a", current_query="query", evidence_batches=[["x"]])
    with pytest.raises(ValidationError):
        Question(id="a", current_query="query", mode="fixed_evidence")
    with pytest.raises(ValidationError):
        Question(id="a", current_query="query", mode="fixed_evidence", evidence_batches=[["x", "x"]])


def test_duplicate_ids_fail_closed():
    q = Question(id="a", current_query="query")
    with pytest.raises(ValidationError):
        plan([q, q])


def test_heldout_prepare_accepts_questions_only_and_owner_package_approval(tmp_path):
    path = tmp_path / "questions.jsonl"
    path.write_text(Question(id="fixture", current_query="query").model_dump_json() + "\n")
    with pytest.raises(ValueError):
        runner.questions_for("held_out", path)
    questions, binding, version = runner.questions_for("held_out", path, owner_reviewed=True, dataset_version="fixture-v1")
    assert len(questions) == 1 and version == "fixture-v1"
    assert binding == runner.file_digest(path)


def test_usage_unknown_is_not_zero_and_thought_tokens_counted():
    missing = runner.summarize_usage([{"completed": False, "usage": None}], settings())
    assert missing["llm_calls"] == 1 and missing["input_tokens"] is None and missing["cost_usd"] is None
    usage = [{"completed": True, "usage": {"promptTokenCount": 100, "candidatesTokenCount": 50, "thoughtsTokenCount": 20}}]
    measured = runner.summarize_usage(usage, settings(input_usd_per_million=1, output_usd_per_million=2))
    assert measured["input_tokens"] == 100 and measured["output_tokens"] == 70
    assert measured["cost_usd"] == pytest.approx(.00024)
    usage[0]["usage"]["cachedContentTokenCount"] = 10
    assert runner.summarize_usage(usage, settings(input_usd_per_million=1, output_usd_per_million=2))["cost_usd"] is None


class ErrorRuntime:
    def usage(self):
        return []

    async def execute(self, question):
        if question.id == "bad":
            raise RuntimeError("secret must not enter outputs")
        return {"kind": "rewrite_probe", "rewritten_query": "rewritten"}


@pytest.mark.asyncio
async def test_runner_accounts_errors_and_continues_without_secret_text():
    p = RunPlan(suite="development", dataset_version="fixture", dataset_binding="0" * 64,
                snapshot_sha256="0" * 64, code_hashes={}, settings=settings(),
                questions=[Question(id=i, current_query="query", mode="rewrite_probe") for i in ["bad", "ok"]])
    records = await runner.run_questions(p, ErrorRuntime(), execution_kind="synthetic")
    assert [r["id"] for r in records] == ["bad", "ok"]
    assert records[0]["error"] == {"category": "provider_or_pipeline_error", "type": "RuntimeError"}
    assert "secret" not in json.dumps(records)
    assert records[1]["error"] is None


@pytest.mark.asyncio
async def test_checkpoint_persists_before_next_case_and_failure_stops_run():
    seen = []

    class Runtime(ErrorRuntime):
        async def execute(self, question):
            if question.id == "second":
                assert seen == ["first"]
            return await super().execute(question)

    p = RunPlan(suite="development", dataset_version="fixture", dataset_binding="0" * 64,
                snapshot_sha256="0" * 64, code_hashes={}, settings=settings(),
                questions=[Question(id=i, current_query="query", mode="rewrite_probe")
                           for i in ["first", "second"]])
    await runner.run_questions(p, Runtime(), execution_kind="synthetic",
                               on_record=lambda record: seen.append(record["id"]))
    assert seen == ["first", "second"]

    def failed_checkpoint(record):
        raise OSError("fixture disk failure")

    with pytest.raises(OSError, match="disk failure"):
        await runner.run_questions(p, Runtime(), execution_kind="synthetic", on_record=failed_checkpoint)


class GradeProvider(LLMProvider):
    def __init__(self):
        self.pools = []

    async def generate(self, *args, **kwargs):
        raise AssertionError("no unstructured generation")

    async def generate_structured(self, messages, response_schema, **kwargs):
        assert response_schema is EvidenceGrade
        ids = [c["id"] for c in json.loads(messages[-1].content)["chunks"]]
        self.pools.append(ids)
        return EvidenceGrade(sufficient=False, reason="fixture", coverage=[])


@pytest.mark.asyncio
async def test_replay_accumulates_all_batches_without_full_corpus_search():
    from evaluation import current_law_dataset as corpus
    chunks = read_json(corpus.DEFAULT_OUTPUT)["chunks"][:2]
    provider = GradeProvider()
    runtime = CoreRuntime(provider, chunks, settings())
    question = Question(id="fixture", current_query="fixture query", mode="fixed_evidence",
                        evidence_batches=[[chunks[0]["id"]], [chunks[1]["id"]]])
    output = await runtime.execute(question)
    assert len(provider.pools[0]) == 1 and len(provider.pools[1]) == 2
    assert output["evidence_chunk_ids"] == [c["id"] for c in chunks]


@pytest.mark.asyncio
async def test_neighborhood_lookup_preserves_publication_metadata():
    from evaluation import current_law_dataset as corpus
    chunk = next(c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"] if not c["publication_eligible"])
    runtime = CoreRuntime(GradeProvider(), [chunk], settings())
    found = await runtime.fetch_article(chunk["law"], chunk["article_no"])
    assert found[0].metadata["publication_eligible"] is False
    assert found[0].metadata["source_spans"] == chunk["source_spans"]


def test_hybrid_preserves_legacy_citation_merge_without_mutating_rows():
    rows = [{"id": "a", "display_citation": "c1"}, {"id": "b", "display_citation": "c2"}]
    result = hybrid_candidates(rows, [(0, 10), (1, 5)], [(rows[1], .8)], .5, 2)
    assert [c["id"] for c, _ in result] == ["b", "a"]
    assert result[0][1] == pytest.approx(.65)
    assert "score" not in rows[0]


def write_run(tmp_path, *, kind="live", output=None, error=None):
    directory = tmp_path / "run"
    directory.mkdir()
    p = plan([Question(id="fixture", current_query="query")])
    record = {"id": "fixture", "mode": "end_to_end", "execution_kind": kind,
              "output": output, "error": error, "elapsed_ms": 100,
              "usage": {"llm_calls": 0, "input_tokens": None, "output_tokens": None, "cost_usd": None}}
    record["result_sha256"] = digest(record)
    runner.write_new(directory / "results.jsonl", json.dumps(record) + "\n")
    runner.write_new(directory / "run.json", {"plan": p.model_dump(mode="json"), "plan_sha256": digest(p.model_dump(mode="json")),
                     "execution_kind": kind, "results_sha256": runner.file_digest(directory / "results.jsonl")})
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({"id": "fixture", "reference_answer": "reference", "disposition": "publish", "required_facets": {"f1": "rule"}}) + "\n")
    return directory, gold, record


def test_synthetic_smoke_cannot_be_reported_as_model_quality(tmp_path):
    directory, gold, _ = write_run(tmp_path, kind="synthetic", error={"type": "FixtureError"})
    with pytest.raises(ValueError, match="synthetic"):
        scoring.score_run(directory, private_gold=gold)


def test_pipeline_error_remains_in_denominator_not_abstention(tmp_path):
    directory, gold, _ = write_run(tmp_path, error={"type": "FixtureError"})
    report = scoring.score_run(directory, private_gold=gold)["modes"]["end_to_end"]
    assert report["pipeline_errors"]["value"] == 1
    assert report["all_required_pass_confirmed_over_all"]["denominator"] == 1
    assert report["unnecessary_abstention"]["numerator"] == 0
    assert report["facet_accuracy_reviewed"]["value"] is None
    assert report["cost_usd"] is None


def test_unreviewed_answer_is_not_semantic_pass(tmp_path):
    directory, gold, _ = write_run(tmp_path, output={"status": "answered", "retrieval": {"chunks": []},
                                                   "answer": {"claims": []}})
    report = scoring.score_run(directory, private_gold=gold)["modes"]["end_to_end"]
    assert report["answer_rate"]["value"] == 1
    assert report["semantic_pending"] == 1
    assert report["all_required_pass_confirmed_over_all"]["value"] == 0


def test_review_is_bound_to_actual_result_and_every_facet(tmp_path):
    directory, gold, record = write_run(tmp_path, error={"type": "FixtureError"})
    reviews = tmp_path / "reviews.jsonl"
    review = SemanticReview(id="fixture", result_sha256="0" * 64, reviewer="test reviewer",
                            facet_scores={"f1": 0}, notes="fixture")
    reviews.write_text(review.model_dump_json() + "\n")
    with pytest.raises(ValueError, match="different output"):
        scoring.score_run(directory, reviews, gold)
    review.result_sha256 = record["result_sha256"]
    review.facet_scores = {"wrong": 1}
    reviews.write_text(review.model_dump_json() + "\n")
    with pytest.raises(ValueError, match="every required facet"):
        scoring.score_run(directory, reviews, gold)


def test_run_results_tampering_and_missing_ids_are_rejected(tmp_path):
    directory, _, _ = write_run(tmp_path, error={"type": "FixtureError"})
    (directory / "results.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        runner.verify_run(directory)


def test_quantiles_and_zero_denominator_are_explicit():
    assert scoring.quantile([], .95) is None
    assert scoring.quantile([10, 20], .5) == 15
    assert scoring.rate(0, 0)["value"] is None


def test_valid_citation_and_reviewer_support_are_separate(tmp_path):
    from evaluation import current_law_dataset as corpus
    chunk = read_json(corpus.DEFAULT_OUTPUT)["chunks"][0]
    retrieved = map_chunk(chunk).model_dump(mode="json")
    output = {"status": "answered", "retrieval": {"chunks": [retrieved]}, "answer": {"claims": [
        {"text": "fixture claim", "citations": [{"chunk_id": retrieved["id"], "citation": chunk["display_citation"]}]}]}}
    directory, gold, record = write_run(tmp_path, output=output)
    reviews = tmp_path / "reviews.jsonl"
    review = SemanticReview(id="fixture", result_sha256=record["result_sha256"], reviewer="test reviewer",
                            facet_scores={"f1": 1}, citation_support=False, safe_publication=True,
                            notes="valid locator does not support this fixture claim")
    reviews.write_text(review.model_dump_json() + "\n")
    result = scoring.score_run(directory, reviews, gold)["modes"]["end_to_end"]
    assert result["citation_validity"]["value"] == 1
    assert result["citation_support_reviewed"]["value"] == 0
    assert result["all_required_pass_reviewed"]["value"] == 0
    review.citation_support = True
    reviews.write_text(review.model_dump_json() + "\n")
    assert scoring.score_run(directory, reviews, gold)["modes"]["end_to_end"]["all_required_pass_reviewed"]["value"] == 1


def test_citation_same_id_but_wrong_source_text_fails():
    from evaluation import current_law_dataset as corpus
    chunk = read_json(corpus.DEFAULT_OUTPUT)["chunks"][0]
    retrieved = map_chunk(chunk).model_dump(mode="json")
    retrieved["text"] = "wrong text"
    output = {"retrieval": {"chunks": [retrieved]}, "answer": {"claims": [
        {"citations": [{"chunk_id": retrieved["id"], "citation": chunk["display_citation"]}]}]}}
    record = {"mode": "end_to_end", "error": None, "output": output}
    checks = scoring.deterministic_checks(record, {"gold": None}, {chunk["id"]: chunk}, {retrieved["id"]: chunk["id"]})
    assert checks["citation_validity"]["value"] == 0


def test_blocked_citation_is_detected_even_if_locator_is_valid():
    from evaluation import current_law_dataset as corpus
    chunk = next(c for c in read_json(corpus.DEFAULT_OUTPUT)["chunks"] if not c["publication_eligible"])
    retrieved = map_chunk(chunk).model_dump(mode="json")
    output = {"retrieval": {"chunks": [retrieved]}, "answer": {"claims": [
        {"citations": [{"chunk_id": retrieved["id"], "citation": chunk["display_citation"]}]}]}}
    checks = scoring.deterministic_checks({"mode": "end_to_end", "error": None, "output": output},
                                          {"gold": None}, {chunk["id"]: chunk}, {retrieved["id"]: chunk["id"]})
    assert checks["citation_validity"]["value"] == 1
    assert checks["blocked_source_publication"] is True


def test_review_packet_is_create_only_and_has_pending_not_fake_scores(tmp_path):
    directory, gold, _ = write_run(tmp_path, error={"type": "FixtureError"})
    packet = tmp_path / "packet"
    scoring.make_review_packet(directory, packet, gold)
    template = json.loads((packet / "reviews_template.jsonl").read_text())
    assert template["facet_scores"] == {"f1": None} and template["reviewer"] is None
    with pytest.raises(FileExistsError):
        scoring.make_review_packet(directory, packet, gold)


@pytest.mark.parametrize('status', ['partial_answer', 'needs_clarification'])
def test_partial_responses_are_neither_full_answers_nor_silent_refusals(tmp_path, status):
    from evaluation import current_law_dataset as corpus
    chunk = next(c for c in read_json(corpus.DEFAULT_OUTPUT)['chunks'] if c['publication_eligible'])
    retrieved = map_chunk(chunk).model_dump(mode='json')
    output = {'status': status, 'retrieval': {'chunks': [retrieved]},
              'answer': {'text': 'Phần đã có căn cứ.', 'claims': [{'text': 'Phần đã có căn cứ.', 'citations': [
                  {'chunk_id': retrieved['id'], 'citation': chunk['display_citation']}]}]},
              'limitations': ['Chưa đủ dữ kiện để kết luận toàn bộ.'], 'follow_up_questions': ['Vị trí nào?']}
    directory, gold, record = write_run(tmp_path, output=output)
    reviews = tmp_path / 'reviews.jsonl'
    reviews.write_text(SemanticReview(id='fixture', result_sha256=record['result_sha256'], reviewer='test',
                      facet_scores={'f1': .5}, citation_support=True, safe_publication=True,
                      notes='Correct but incomplete').model_dump_json() + '\n')
    metrics = scoring.score_run(directory, reviews, gold)['modes']['end_to_end']
    assert metrics['answer_rate']['numerator'] == 0
    assert metrics[status + '_rate']['numerator'] == 1
    assert metrics['unnecessary_abstention']['numerator'] == 0
    assert metrics['all_required_pass_confirmed_over_all']['numerator'] == 0
    assert metrics['semantic_pending'] == 0
    assert metrics['citation_support_reviewed']['value'] == 1
    packet = tmp_path / 'packet'
    scoring.make_review_packet(directory, packet, gold)
    text = (packet / 'REVIEW.md').read_text()
    assert text.index('Phần đã có căn cứ.') < text.index('Gold (')
    assert 'Giới hạn: Chưa đủ dữ kiện' in text
