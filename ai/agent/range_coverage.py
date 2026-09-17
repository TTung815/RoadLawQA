"""Verify grounded, compatible numeric range support; never infer legal answers."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import List, Optional, Sequence

from pydantic import BaseModel, StrictBool

from ai.retrieval.base import RetrievedChunk


class RangeLeaf(BaseModel):
    chunk_id: str
    range_quote: str
    compatible: StrictBool


class RangeCoverage(BaseModel):
    question_quote: str
    unit: str
    leaves: List[RangeLeaf]


_NUMBER = r"\d+(?:[.,]\d+)?"
_EXPRESSION = re.compile(
    rf"(?<![\w.,])(?:(?:từ(?: trên)?|trên)\s+{_NUMBER}\s+(?:đến|tới)\s+{_NUMBER}"
    rf"|(?:đúng|trên|dưới|không quá|từ)\s+{_NUMBER})(?![\d.,])"
)
_REQUEST = re.compile(
    rf"(?<!\w)(?:(?:từ(?: trên)?|trên)\s+{_NUMBER}(?:\s+[^\s\d;,.?!]+)?\s+(?:đến|tới)\s+{_NUMBER}"
    rf"|(?:đúng|trên|dưới|không quá|từ)\s+{_NUMBER})\s+(?P<unit>[^\s\d;,.?!]+)"
)


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


def _source_expressions(text: str, unit: str) -> List[str]:
    quantity = rf"{_NUMBER}\s*{re.escape(unit)}"
    pattern = re.compile(
        rf"(?<!\w)(?:(?:từ(?: trên)?|trên)\s+{_NUMBER}(?:\s*{re.escape(unit)})?\s+(?:đến|tới)\s+{quantity}"
        rf"|(?:đúng|trên|dưới|không quá|từ)\s+{quantity})(?!\w)"
    )
    matches = list(pattern.finditer(text.casefold()))
    for match in matches:
        before, after = text[:match.start()].casefold(), text[match.end():].casefold()
        # Unsupported compound bounds must not become an unbounded half interval.
        if (re.search(r'\b(?:đến|tới)\s*$', before) or
                re.search(r'\b(?:đến|tới)\b', re.split(r'[;.\n]', after, maxsplit=1)[0])):
            return []
    unique = list(dict.fromkeys(_normal(match.group()) for match in matches))
    # Multiple bounds inside one leaf may express AND rather than OR.
    return unique if len(unique) == 1 else []


def range_candidates(question: str, chunks: Sequence[RetrievedChunk]):
    """Expose source expressions for per-leaf semantic review, never applicability.

    Unit tokens are read from the question rather than a vehicle/conduct keyword
    heuristic. Only the existing supported numeric grammar is recognized.
    """
    match = _REQUEST.search(question.casefold())
    if match is None:
        return None
    quote, unit = match.group(), match['unit']
    requested = _normal(quote.replace(unit, ' '))
    expressions = [m.group() for m in _EXPRESSION.finditer(_normal(question.casefold().replace(unit, ' ')))]
    target = _parse(requested)
    if target is None or expressions != [requested]:
        return None
    candidates = []
    seen = set()
    for chunk in chunks:
        for text in (chunk.text, chunk.enriched_text):
            for source in _source_expressions(text, unit):
                key = (chunk.id, source)
                if key not in seen:
                    seen.add(key)
                    interval = _parse(_normal(source.replace(unit, ' ')))
                    overlap = _clip(interval, target) if interval is not None else None
                    candidates.append({
                        'chunk_id': chunk.id, 'range_quote': source,
                        'requested_intersection': None if overlap is None else {
                            'lower': str(overlap.lower), 'upper': str(overlap.upper),
                            'lower_closed': overlap.lower_closed,
                            'upper_closed': overlap.upper_closed,
                        },
                    })
    return {'question_quote': quote, 'unit': unit, 'leaves': candidates} if candidates else None


@dataclass(frozen=True)
class _Interval:
    lower: Decimal
    upper: Decimal
    lower_closed: bool
    upper_closed: bool


def _parse(expression: str) -> Optional[_Interval]:
    pair = re.fullmatch(rf"(từ(?: trên)?|trên) ({_NUMBER}) (?:đến|tới) ({_NUMBER})", expression)
    if pair:
        result = _Interval(Decimal(pair[2].replace(',', '.')), Decimal(pair[3].replace(',', '.')),
                           pair[1] == 'từ', True)
    else:
        single = re.fullmatch(rf"(đúng|trên|dưới|không quá|từ) ({_NUMBER})", expression)
        if not single:
            return None
        value = Decimal(single[2].replace(',', '.'))
        if single[1] == 'đúng':
            result = _Interval(value, value, True, True)
        elif single[1] in ('trên', 'từ'):
            result = _Interval(value, Decimal('Infinity'), single[1] == 'từ', False)
        else:
            result = _Interval(Decimal('-Infinity'), value, False, single[1] == 'không quá')
    return result if result.lower <= result.upper else None


def _clip(interval: _Interval, target: _Interval) -> Optional[_Interval]:
    lower, upper = max(interval.lower, target.lower), min(interval.upper, target.upper)
    left = all(x.lower_closed for x in (interval, target) if x.lower == lower)
    right = all(x.upper_closed for x in (interval, target) if x.upper == upper)
    if lower > upper or lower == upper and not (left and right):
        return None
    return _Interval(lower, upper, left, right)


def range_anchors(question: str, chunks: Sequence[RetrievedChunk], proof: RangeCoverage) -> List[str]:
    """Return a jointly covering anchor set within one scope, or no proven set.

    Semantic applicability is explicitly judged per leaf by the provider. Here
    we verify quoted source bounds, unit identity, metadata scope and union math.
    Distinct overlapping interiors remain ambiguous and are not combined. Only
    one requested numeric interval is supported; unsupported syntax fails closed.
    """
    unit, quote = _normal(proof.unit), _normal(proof.question_quote)
    if not unit or unit not in quote or quote not in _normal(question):
        raise ValueError('Range proof must quote the question and its original unit')
    requested = _normal(quote.replace(unit, ' '))
    question_ranges = [m.group() for m in _EXPRESSION.finditer(_normal(_normal(question).replace(unit, ' ')))]
    target = _parse(requested)
    if target is None or question_ranges != [requested]:
        return []

    known = {chunk.id: chunk for chunk in chunks}
    groups = defaultdict(list)
    seen = set()
    for leaf in proof.leaves:
        if leaf.chunk_id not in known:
            raise ValueError('Range proof references a chunk outside supplied evidence')
        chunk = known[leaf.chunk_id]
        expression = _normal(leaf.range_quote)
        sources = [_normal(chunk.text), _normal(chunk.enriched_text)]
        if not expression or unit not in expression or not any(expression in text for text in sources):
            raise ValueError('Range proof must quote supplied evidence in the original unit')
        stripped = _normal(expression.replace(unit, ' '))
        # Reject a truncated bound, e.g. quoting only "trên L" from "trên L đến U".
        full_expressions = [_normal(expression.replace(unit, ' '))
                            for text in sources for expression in _source_expressions(text, unit)]
        interval = _parse(stripped) if stripped in full_expressions else None
        if not leaf.compatible or interval is None or (leaf.chunk_id, stripped) in seen:
            continue
        seen.add((leaf.chunk_id, stripped))
        scope = tuple(_normal(str(chunk.metadata.get(key) or ''))
                      for key in ('law', 'article_no', 'article_title'))
        if not scope[0] or not scope[1]:
            continue
        clipped = _clip(interval, target)
        if clipped is not None:
            groups[scope].append((clipped, leaf.chunk_id))

    for scope in sorted(groups):
        members = sorted(groups[scope], key=lambda member: (
            member[0].lower, not member[0].lower_closed, member[0].upper, member[1]))
        for interval, identifier in members:
            if interval == target:
                return [identifier]
        current, identifiers = members[0][0], [members[0][1]]
        for interval, identifier in members[1:]:
            if (interval.lower != current.upper or
                    current.upper_closed == interval.lower_closed):
                break  # Gap or ambiguous overlap, including a missing boundary point.
            current = _Interval(current.lower, interval.upper, current.lower_closed, interval.upper_closed)
            identifiers.append(identifier)
        else:
            if current == target:
                selected = set(identifiers)
                return [chunk.id for chunk in chunks if chunk.id in selected]
    return []
