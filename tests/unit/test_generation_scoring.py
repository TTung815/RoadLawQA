import json

import pytest

from evaluation.generation_scoring import (
    Atom, Decomposition, FactualJudgment, GroundingJudgment, GroundedAtom, Verdict, aggregate, ask, calculate,
    read_signed, signed, validate_decomposition, validate_factual, validate_grounding,
)
from evaluation.core_runner import write_new


def example():
    segments = [{"id": 1, "text": "Phạt 4–6 triệu.", "citations": ["fine", "irrelevant"]}]
    atoms = Decomposition(atoms=[Atom(segment=1, quote="4–6 triệu", text="Phạt 4–6 triệu")],
                          questions=["Phạt bao nhiêu?", "Mức phạt tiền?", "Tiền phạt?"])
    factual = FactualJudgment(response=[{"id": 1, "supported": True, "reason": "Đúng tiền"}], reference=[
        {"quote": "4–6 triệu", "text": "Phạt 4–6 triệu", "supported_by_response": True, "reason": "Đã nêu"},
        {"quote": "trừ 4 điểm", "text": "Trừ 4 điểm", "supported_by_response": False, "reason": "Thiếu điểm"}])
    grounding = GroundingJudgment(atoms=[{"id": 1, "supported": True, "source_ids": ["fine"],
                                         "cited_support": True, "reason": "Đúng nguồn"}],
        citations=[{"segment": 1, "source_id": "fine", "useful": True, "reason": "Hỗ trợ"},
                   {"segment": 1, "source_id": "irrelevant", "useful": False, "reason": "Không hỗ trợ"}], limitations=[])
    return segments, atoms, factual, grounding


def test_missing_points_keeps_faithfulness_but_lowers_factual_recall():
    _, atoms, factual, grounding = example()
    score = calculate(atoms, factual, grounding, [.8, .7, .9])
    assert score['factual_precision'] == 1
    assert score['factual_recall'] == .5
    assert score['factual_f1'] == pytest.approx(2/3)
    assert score['faithfulness'] == 1
    assert score['citation_recall'] == 1
    assert score['citation_precision'] == .5
    assert score['answer_relevancy'] == pytest.approx(.8)


def test_wrong_amount_with_real_source_id_is_not_a_pass():
    _, atoms, factual, grounding = example()
    factual.response[0].supported = False
    grounding.atoms[0].supported = False
    grounding.atoms[0].source_ids = []
    grounding.atoms[0].cited_support = False
    score = calculate(atoms, factual, grounding, [.9]*3)
    assert score['factual_f1'] == score['faithfulness'] == score['citation_precision'] == 0
    assert score['answer_relevancy'] == pytest.approx(.9)  # Relevancy cannot prove truth.


def test_one_bad_atom_blocks_precision_credit_for_composite_segment():
    _, atoms, factual, grounding = example()
    atoms.atoms.append(Atom(segment=1, quote='Phạt', text='Unsupported extra'))
    factual.response.append(Verdict(id=2, supported=False, reason='Bad'))
    grounding.atoms.append(GroundedAtom(id=2, supported=False, source_ids=[], cited_support=False, reason='Bad'))
    score = calculate(atoms, factual, grounding, [.8]*3)
    assert score['citation_recall'] == .5
    assert score['citation_precision'] == 0


def test_verbatim_quotes_and_item_coverage_prevent_fabricated_decomposition():
    segments, atoms, factual, _ = example()
    validate_decomposition(atoms, segments)
    validate_factual(factual, atoms.atoms, '4–6 triệu và trừ 4 điểm')
    atoms.atoms[0].quote = '30 triệu'
    with pytest.raises(ValueError, match='verbatim'):
        validate_decomposition(atoms, segments)
    factual.response.append(factual.response[0])
    with pytest.raises(ValueError, match='duplicated'):
        validate_factual(factual, atoms.atoms, '4–6 triệu và trừ 4 điểm')


def test_citation_judge_cannot_invent_support_or_omit_citations():
    segments, atoms, _, grounding = example()
    contexts = [{'id': 'fine'}, {'id': 'irrelevant'}]
    validate_grounding(grounding, atoms.atoms, segments, contexts, [])
    grounding.atoms[0].source_ids = ['invented']
    with pytest.raises(ValueError, match='supplied'):
        validate_grounding(grounding, atoms.atoms, segments, contexts, [])
    grounding.atoms[0].source_ids = ['fine']
    grounding.citations.pop()
    with pytest.raises(ValueError, match='citation'):
        validate_grounding(grounding, atoms.atoms, segments, contexts, [])


def test_abstention_and_judge_errors_have_explicit_denominators():
    _, atoms, factual, grounding = example()
    scores = calculate(atoms, factual, grounding, [.8]*3)
    empty = {k: None for k in scores if k != 'counts'}
    empty.update(factual_recall=0, factual_f1=0, answer_relevancy=0)
    report = aggregate([{'error': None, 'metrics': scores}, {'error': None, 'metrics': empty},
                        {'error': 'TimeoutError', 'metrics': None}])
    assert report['metrics']['faithfulness'] == {'mean': 1, 'n': 1, 'total': 3}
    assert report['metrics']['factual_f1']['mean'] == pytest.approx(1/3)
    assert report['metrics']['factual_f1']['n'] == 2
    assert report['judge_errors'] == 1


@pytest.mark.asyncio
async def test_resume_reuses_bound_checkpoint_without_charging_again(tmp_path):
    _, atoms, _, _ = example()
    class Fake:
        observations = []
        async def generate_structured(self, *args, **kwargs):
            self.observations.append({'completed': True, 'usage': None})
            return atoms
    fake = Fake()
    check = lambda value: None
    await ask(fake, tmp_path, 'decompose', 'p', {'a': 1}, Decomposition, check, 1)
    await ask(fake, tmp_path, 'decompose', 'p', {'a': 1}, Decomposition, check, 1)
    assert len(fake.observations) == 1
    with pytest.raises(ValueError, match='differs'):
        await ask(fake, tmp_path, 'decompose', 'p', {'a': 2}, Decomposition, check, 1)


@pytest.mark.asyncio
async def test_failed_judge_has_bounded_retry_and_sanitized_error(tmp_path):
    class Fake:
        observations = []
        async def generate_structured(self, *args, **kwargs):
            self.observations.append({'completed': False, 'usage': None})
            raise RuntimeError('secret provider response must not be stored')
    fake = Fake()
    with pytest.raises(ValueError, match='bounded'):
        await ask(fake, tmp_path, 'judge', 'p', {}, Decomposition, lambda v: None, 1)
    assert len(fake.observations) == 2
    for p in tmp_path.glob('*.json'):
        assert 'secret' not in p.read_text()
        assert read_signed(p)['error'] == 'RuntimeError'


def test_artifact_tamper_and_bad_cosine_are_rejected(tmp_path):
    p = tmp_path/'x.json'
    write_new(p, signed({'value': 1}))
    assert read_signed(p)['value'] == 1
    data = json.loads(p.read_text());data['value'] = 2;p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='digest'):
        read_signed(p)
    _, atoms, factual, grounding = example()
    with pytest.raises(ValueError, match='cosine'):
        calculate(atoms, factual, grounding, [float('nan')]*3)


@pytest.mark.asyncio
async def test_actual_judge_payloads_keep_gold_out_of_grounding_and_query_out_of_reverse_questions(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    from evaluation.generation_scoring import evaluate_case
    segments, atoms, factual, grounding = example()
    calls = []
    class Fake:
        observations = []
        async def generate_structured(self, messages, schema, **kwargs):
            calls.append(json.loads(messages[1].content))
            self.observations.append({'completed': True, 'usage': None})
            return {Decomposition: atoms, FactualJudgment: factual, GroundingJudgment: grounding}[schema]
    monkeypatch.setattr('evaluation.core_runtime.create_evaluation_provider', lambda settings: Fake())
    embedder = SimpleNamespace(encode=lambda *a, **kw: np.array([[1., 0.], [.8, .6], [.6, .8], [1., 0.]]))
    record = {'id': 'test', 'result_sha256': 'a'*64, 'output': {'status': 'partial_answer',
              'answer': {'claims': [{'text': segments[0]['text'], 'citations': [{'chunk_id': 'fine'}, {'chunk_id': 'irrelevant'}]}]},
              'retrieval': {'chunks': [{'id': 'fine', 'enriched_text': 'SOURCE_ONLY'}, {'id': 'irrelevant', 'enriched_text': 'X'}]}}}
    result = await evaluate_case(record, SimpleNamespace(current_query='QUERY_ONLY'),
                                 {'reference_answer': 'REFERENCE_ONLY 4–6 triệu và trừ 4 điểm'},
                                 SimpleNamespace(timeout_seconds=1), tmp_path, embedder)
    assert result['error'] is None
    assert len(calls) == 3
    assert 'QUERY_ONLY' not in json.dumps(calls[0])
    assert 'REFERENCE_ONLY' not in json.dumps(calls[0])
    assert 'REFERENCE_ONLY' in json.dumps(calls[1])
    assert 'SOURCE_ONLY' not in json.dumps(calls[1])
    assert 'REFERENCE_ONLY' not in json.dumps(calls[2])
    assert 'SOURCE_ONLY' in json.dumps(calls[2])


@pytest.mark.asyncio
async def test_empty_response_does_not_initialize_or_call_provider(tmp_path, monkeypatch):
    from evaluation.generation_scoring import evaluate_case
    def forbidden(*args):
        pytest.fail('empty answers must not call a judge')
    monkeypatch.setattr('evaluation.core_runtime.create_evaluation_provider', forbidden)
    result = await evaluate_case({'id': 'empty', 'result_sha256': 'a'*64, 'output': {'status': 'insufficient_evidence'}},
                                 None, {}, None, tmp_path, None)
    assert result['metrics']['factual_f1'] == 0
    assert result['metrics']['faithfulness'] is None
