"""Grounded complementary coverage, with scripted LLM output and no services."""

import pytest

from ai.agent.evidence_grader import EvidenceGrade, EvidenceGrader
from tests.unit.test_agentic_retrieval import ScriptedProvider
from tests.unit.test_neighborhood_expansion import Lookup, consequence, legal, service


QUESTION = 'Ô tô vượt quá tốc độ từ 20 đến 35 km/h bị xử phạt thế nào?'


def leaf(identifier, expression, clause='2', **kwargs):
    return legal(identifier, clause=clause,
                 text=f'Điều khiển xe chạy quá tốc độ quy định {expression};', **kwargs)


def assessment(chunks, *, question_quote='từ 20 đến 35 km/h', unit='km/h',
               compatible=None, sufficient=False, range_covered=False, **coverage):
    values = {'monetary_penalty': True, 'subject_violation': True,
              'threshold_range': range_covered, 'license_points': sufficient, **coverage}
    return {
        'range_coverage': {
            'question_quote': question_quote, 'unit': unit,
            'leaves': [{'chunk_id': chunk.id,
                        'range_quote': chunk.text.removeprefix('Điều khiển xe chạy quá tốc độ quy định ').rstrip(';'),
                        'compatible': (compatible or {}).get(chunk.id, True)} for chunk in chunks],
        },
        'coverage': [{'aspect': aspect, 'covered': covered} for aspect, covered in values.items()],
        'anchor_chunk_ids': [chunks[-1].id] if chunks else [],
        'sufficient': sufficient,
        'reason': 'Missing complete range and license consequence evidence.',
    }


async def grade(chunks, **kwargs):
    provider = ScriptedProvider([(EvidenceGrade, assessment(chunks, **kwargs))])
    return await EvidenceGrader(provider).grade(QUESTION, chunks)


def covered(result, aspect='threshold_range'):
    return next(item.covered for item in result.coverage if item.aspect == aspect)


@pytest.mark.asyncio
async def test_joint_range_repairs_false_facet_and_selects_both_anchors():
    first = leaf('through-boundary', 'từ 10 km/h đến 20 km/h')
    second = leaf('after-boundary', 'trên 20 km/h đến 35 km/h', clause='7')
    result = await grade([second, first])
    assert covered(result) is True
    assert result.anchor_chunk_ids == ['after-boundary', 'through-boundary']
    assert result.missing_aspects == ['license_points']
    assert result.sufficient is False  # Range support is not sanction support.
    assert 'Missing complete range' not in result.reason


@pytest.mark.asyncio
@pytest.mark.parametrize('expression', ['từ 10 km/h đến 20 km/h', 'trên 20 km/h đến 35 km/h'])
async def test_single_partial_leaf_cannot_claim_full_inclusive_range(expression):
    result = await grade([leaf('partial', expression)], sufficient=True, range_covered=True)
    assert covered(result) is False
    assert result.sufficient is False
    assert result.anchor_chunk_ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize('kwargs', [
    {'article': '8'}, {'law': 'Another document'},
    {'article_title': 'A different vehicle/person category'},
])
async def test_partial_leaves_from_inconsistent_metadata_cannot_be_combined(kwargs):
    first = leaf('through-boundary', 'từ 10 km/h đến 20 km/h')
    second = leaf('after-boundary', 'trên 20 km/h đến 35 km/h', **{
        key: value for key, value in kwargs.items() if key != 'article_title'})
    if 'article_title' in kwargs:
        first.metadata['article_title'] = 'Requested vehicle/person category'
        second.metadata['article_title'] = kwargs['article_title']
    result = await grade([first, second], sufficient=True, range_covered=True)
    assert covered(result) is False
    assert result.sufficient is False


@pytest.mark.asyncio
@pytest.mark.parametrize('category', ['xe máy', 'người đi bộ', 'another conduct'])
async def test_semantically_incompatible_leaf_is_not_numeric_support(category):
    first = leaf('through-boundary', 'từ 10 km/h đến 20 km/h')
    second = leaf('unrelated', 'trên 20 km/h đến 35 km/h')
    second.enriched_text = category + ': ' + second.text
    result = await grade([first, second], compatible={'unrelated': False},
                         sufficient=True, range_covered=True)
    assert covered(result) is False
    assert result.sufficient is False


@pytest.mark.asyncio
@pytest.mark.parametrize('first,second', [
    ('từ 10 km/h đến 25 km/h', 'trên 26 km/h đến 35 km/h'),
    ('từ 10 km/h đến 25 km/h', 'trên 24 km/h đến 30 km/h'),
    ('từ 10 km/h đến 25 km/h', 'trên 24 km/h đến 35 km/h'),
    ('từ 10 km/h đến 25 km/h', 'từ 25 km/h đến 35 km/h'),
    ('dưới 20 km/h', 'trên 20 km/h đến 35 km/h'),
])
async def test_gaps_and_ambiguous_overlaps_do_not_establish_full_coverage(first, second):
    result = await grade([leaf('first', first), leaf('second', second)],
                         sufficient=True, range_covered=True)
    assert covered(result) is False
    assert result.sufficient is False


@pytest.mark.asyncio
@pytest.mark.parametrize('question,quote,expected', [
    ('Ô tô vượt quá tốc độ đúng 20 km/h bị xử phạt thế nào?', 'đúng 20 km/h', ['through-boundary']),
    ('Ô tô vượt quá tốc độ trên 20 đến 35 km/h bị xử phạt thế nào?', 'trên 20 đến 35 km/h', ['after-boundary']),
])
async def test_exact_and_open_boundary_select_different_proven_anchors(question, quote, expected):
    chunks = [leaf('through-boundary', 'từ 10 km/h đến 20 km/h'),
              leaf('after-boundary', 'trên 20 km/h đến 35 km/h', clause='7')]
    provider = ScriptedProvider([(EvidenceGrade, assessment(chunks, question_quote=quote))])
    result = await EvidenceGrader(provider).grade(question, chunks)
    assert covered(result) is True
    assert result.anchor_chunk_ids == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('quote,unit,first,second', [
    ('từ 40 đến 55 km/h', 'km/h', 'từ 30 km/h đến 40 km/h', 'trên 40 km/h đến 55 km/h'),
    ('từ 0,2 đến 0,5 mg/l', 'mg/l', 'từ 0,1 mg/l đến 0,2 mg/l', 'trên 0,2 mg/l đến 0,5 mg/l'),
])
async def test_range_proof_is_not_specific_to_one_example_or_unit(quote, unit, first, second):
    chunks = [leaf('first', first), leaf('second', second)]
    provider = ScriptedProvider([(EvidenceGrade, assessment(
        chunks, question_quote=quote, unit=unit))])
    result = await EvidenceGrader(provider).grade('Requested subject/conduct ' + quote, chunks)
    assert covered(result) is True
    assert result.anchor_chunk_ids == ['first', 'second']


@pytest.mark.asyncio
async def test_truncated_upper_bound_does_not_expand_interval_to_infinity():
    chunks = [leaf('first', 'từ 10 km/h đến 20 km/h'), leaf('second', 'trên 20 km/h đến 30 km/h')]
    output = assessment(chunks, sufficient=True, range_covered=True)
    output['range_coverage']['leaves'][1]['range_quote'] = 'trên 20 km/h'
    provider = ScriptedProvider([(EvidenceGrade, output)])
    with pytest.raises(ValueError, match='Range proof must assess every supplied range candidate'):
        await EvidenceGrader(provider).grade(QUESTION, chunks)


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['invented-id', 'invented-source-quote', 'invented-question-quote', 'wrong-unit'])
async def test_ungrounded_provider_proof_propagates_as_error(change):
    chunks = [leaf('first', 'từ 10 km/h đến 20 km/h')]
    output = assessment(chunks)
    proof = output['range_coverage']
    if change == 'invented-id':
        proof['leaves'][0]['chunk_id'] = 'not-retrieved'
    elif change == 'invented-source-quote':
        proof['leaves'][0]['range_quote'] = 'từ 20 km/h đến 35 km/h'
    elif change == 'invented-question-quote':
        proof['question_quote'] = 'từ 20 đến 50 km/h'
    else:
        proof['unit'] = 'm/s'
    provider = ScriptedProvider([(EvidenceGrade, output)])
    with pytest.raises(ValueError, match='Range proof'):
        await EvidenceGrader(provider).grade(QUESTION, chunks)


@pytest.mark.asyncio
async def test_joint_range_anchor_set_allows_complementary_sanction_expansion():
    chunks = [leaf('through-boundary', 'từ 10 km/h đến 20 km/h', clause='2'),
              leaf('after-boundary', 'trên 20 km/h đến 35 km/h', clause='7')]
    points = [consequence('points-through', reference='khoản 2'),
              consequence('points-after', reference='khoản 7')]
    lookup = Lookup(points)
    agent, _, retriever = service([
        (EvidenceGrade, assessment(chunks)),
        (EvidenceGrade, assessment(chunks, sufficient=True, range_covered=True)),
    ], [chunks], lookup)
    result = await agent.retrieve(QUESTION)
    assert len(retriever.calls) == 1
    assert lookup.calls == [('Test regulation', '6')]
    trace = result.structural_expansions[0]
    assert trace.triggered is True
    assert trace.scopes[0].anchor_chunk_ids == ['through-boundary', 'after-boundary']
    assert set(trace.chunk_ids) == {'points-through', 'points-after'}
    assert covered(trace.grade_before) is True
    assert trace.grade_before.sufficient is False
    assert result.grade.sufficient is True
    assert {chunk.id for chunk in result.chunks} == {c.id for c in chunks + points}


@pytest.mark.asyncio
@pytest.mark.parametrize('uncertain', ['subject_violation', 'condition_exception'])
async def test_range_union_does_not_override_other_safety_constraints(uncertain):
    chunks = [leaf('first', 'từ 10 km/h đến 20 km/h'), leaf('second', 'trên 20 km/h đến 35 km/h')]
    lookup = Lookup(AssertionError('Safety gate must remain conservative'))
    agent, _, _ = service([(EvidenceGrade, assessment(chunks, **{uncertain: False}))], [chunks], lookup)
    result = await agent.retrieve(QUESTION)
    assert result.grade.sufficient is False
    assert lookup.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize('omission', ['partial-list', 'no-proof', 'duplicate-assessment'])
async def test_provider_cannot_silently_skip_a_complementary_range_leaf(omission):
    chunks = [leaf('first', 'từ 10 km/h đến 20 km/h'), leaf('second', 'trên 20 km/h đến 35 km/h')]
    output = assessment(chunks)
    if omission == 'partial-list':
        output['range_coverage']['leaves'] = output['range_coverage']['leaves'][1:]
    elif omission == 'no-proof':
        output['range_coverage'] = None
    else:
        output['range_coverage']['leaves'].append({**output['range_coverage']['leaves'][0], 'compatible': False})
    provider = ScriptedProvider([(EvidenceGrade, output)])
    with pytest.raises(ValueError, match='Range proof must assess every supplied range candidate'):
        await EvidenceGrader(provider).grade(QUESTION, chunks)
    candidates = provider.calls[0]['payload']['range_candidates']
    assert [item['chunk_id'] for item in candidates['leaves']] == ['first', 'second']
    assert candidates['leaves'][0]['requested_intersection'] == {
        'lower': '20', 'upper': '20', 'lower_closed': True, 'upper_closed': True,
    }
    assert candidates['leaves'][1]['requested_intersection'] == {
        'lower': '20', 'upper': '35', 'lower_closed': False, 'upper_closed': True,
    }


@pytest.mark.asyncio
async def test_irrelevant_condition_facet_does_not_block_proven_range_anchor_set():
    chunks = [leaf('first', 'từ 10 km/h đến 20 km/h'), leaf('second', 'trên 20 km/h đến 35 km/h', clause='7')]
    output = assessment(chunks)
    output['coverage'].append({'aspect': 'condition_exception', 'covered': False, 'required': False})
    lookup = Lookup([consequence('points', reference='khoản 2; khoản 7')])
    agent, _, _ = service([
        (EvidenceGrade, output),
        (EvidenceGrade, assessment(chunks, sufficient=True, range_covered=True)),
    ], [chunks], lookup)
    result = await agent.retrieve(QUESTION)
    assert result.structural_expansions[0].triggered is True
    assert result.structural_expansions[0].missing_aspects == ['license_points']
    assert result.grade.sufficient is True


def test_irrelevant_facets_cannot_make_an_empty_grade_sufficient():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match='explicit coverage'):
        EvidenceGrade(sufficient=True, reason='No required coverage.', coverage=[
            {'aspect': 'condition_exception', 'required': False, 'covered': True},
        ])


@pytest.mark.asyncio
@pytest.mark.parametrize('expression,partial_quote', [
    ('từ 10 km/h đến dưới 20 km/h', 'từ 10 km/h'),
    ('trên 10 km/h nhưng dưới 20 km/h', 'trên 10 km/h'),
])
async def test_unsupported_compound_bounds_are_not_inferred_as_unbounded(expression, partial_quote):
    chunks = [leaf('compound', expression)]
    output = assessment(chunks, sufficient=True, range_covered=True)
    output['range_coverage']['leaves'][0]['range_quote'] = partial_quote
    provider = ScriptedProvider([(EvidenceGrade, output)])
    result = await EvidenceGrader(provider).grade(QUESTION, chunks)
    assert covered(result) is False
    assert result.sufficient is False
