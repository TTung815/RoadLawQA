"""Bounded legal-neighborhood selection, independent of databases and LLMs."""

import re
import time
from collections import defaultdict
from typing import Awaitable, Callable, List, Sequence

from pydantic import BaseModel, Field

from ai.retrieval.base import RetrievedChunk

ArticleFetch = Callable[[str, str], Awaitable[Sequence[RetrievedChunk]]]


class LegalScope(BaseModel):
    law: str
    article_no: str
    anchor_chunk_ids: List[str]
    candidate_count: int = 0


class NeighborhoodSelection(BaseModel):
    triggered: bool
    reason: str
    missing_aspects: List[str]
    scopes: List[LegalScope] = Field(default_factory=list)
    chunks: List[RetrievedChunk] = Field(default_factory=list)
    lookup_ms: float = 0.0
    added_characters: int = 0


def _same_article_reference(text: str, anchor: RetrievedChunk) -> bool:
    """Match explicit references to an anchor clause/point, not legal thresholds.

    Only the local 'Điều này' reference form is supported. Other articles/documents
    and unrecognized reference forms are left for baseline retrieval and grading.
    """
    text = text.casefold()
    if 'điều này' not in text or re.search(r'\bđiều\s+\d+', text):
        return False
    clause = str(anchor.metadata.get('clause_no') or '')
    point = str(anchor.metadata.get('point') or '').casefold()
    for match in re.finditer(r'([^;.:]*?)\bkhoản\s+(\d+)\b', text):
        if match.group(2) != clause:
            continue
        prefix = match.group(1)
        points = re.findall(r'\bđiểm\s+([a-zđ])\b', prefix)
        # Reject compressed/unknown point-list syntax rather than broadening it.
        if points and re.search(r',\s*[a-zđ]\b', prefix):
            continue
        if not points or (point and point in points):
            return True
    return False


class LegalNeighborhoodExpander:
    """Select consequence siblings using aspect headings and local references.

    Complete additional-sanction clauses may supply negative applicability evidence;
    they are included atomically, never as a partial list implying exhaustiveness.
    No sanction is asserted to apply here. Final coverage belongs to the grader.
    """

    def __init__(self, fetch_article: ArticleFetch, max_chunks: int = 8,
                 max_characters: int = 12000, max_scopes: int = 2):
        if any(type(value) is not int or value < 1
               for value in (max_chunks, max_characters, max_scopes)):
            raise ValueError('Expansion budgets must be positive integers')
        self._fetch_article = fetch_article
        self.max_chunks = max_chunks
        self.max_characters = max_characters
        self.max_scopes = max_scopes

    async def expand(self, anchors: Sequence[RetrievedChunk],
                     missing_aspects: Sequence[str],
                     existing: Sequence[RetrievedChunk]) -> NeighborhoodSelection:
        supported = set(missing_aspects) & {'license_points', 'additional_sanction'}
        if not supported:
            return NeighborhoodSelection(triggered=False, reason='No supported consequence gap.',
                                         missing_aspects=list(missing_aspects))
        grouped = defaultdict(list)
        for anchor in anchors:
            law = str(anchor.metadata.get('law') or '').strip()
            article = str(anchor.metadata.get('article_no') or '').strip()
            clause = str(anchor.metadata.get('clause_no') or '').strip()
            if law and article and clause:
                grouped[(law, article)].append(anchor)
        if not grouped:
            return NeighborhoodSelection(triggered=False, reason='No reliable structural anchor.',
                                         missing_aspects=list(missing_aspects))

        result = NeighborhoodSelection(triggered=True, reason='Unresolved consequence coverage with reliable anchors.',
                                       missing_aspects=list(missing_aspects))
        started = time.perf_counter()
        existing_ids = {chunk.id for chunk in existing}
        seen = set(existing_ids)
        direct, complete_groups = [], []
        for (law, article), scope_anchors in list(grouped.items())[:self.max_scopes]:
            fetched = list(await self._fetch_article(law, article))
            scope = LegalScope(law=law, article_no=article,
                               anchor_chunk_ids=[chunk.id for chunk in scope_anchors],
                               candidate_count=len(fetched))
            result.scopes.append(scope)
            siblings = {}
            for chunk in fetched:
                # Defense in depth even if a database/mock violates the requested filter.
                if (str(chunk.metadata.get('law') or '').strip() == law and
                    str(chunk.metadata.get('article_no') or '').strip() == article):
                    siblings.setdefault(chunk.id, chunk)
            additional = defaultdict(list)
            clause_members = defaultdict(list)
            for chunk in sorted(siblings.values(), key=self._order):
                clause_members[str(chunk.metadata.get('clause_no') or '')].append(chunk)
                head = str(chunk.metadata.get('clause_head') or '').casefold()
                body = chunk.text.casefold()
                is_points = 'trừ điểm' in head
                is_additional = 'xử phạt bổ sung' in head
                matches = any(_same_article_reference(body, anchor) for anchor in scope_anchors)
                if matches and (('license_points' in supported and is_points) or
                                ('additional_sanction' in supported and is_additional)):
                    direct.append(chunk)
                if 'additional_sanction' in supported and is_additional:
                    additional[str(chunk.metadata.get('clause_no') or '')].append(chunk)
            for clause, group in additional.items():
                # When no point applies, the entire clause is needed to establish scope.
                if clause and len(group) == len(clause_members[clause]) and not any(any(_same_article_reference(chunk.text, anchor)
                               for anchor in scope_anchors) for chunk in group):
                    annotated = []
                    for chunk in group:
                        copy = chunk.model_copy(deep=True)
                        copy.metadata['structural_context'] = {
                            'complete_clause_chunk_ids': [member.id for member in group],
                            'purpose': 'additional_sanction_applicability',
                        }
                        annotated.append(copy)
                    complete_groups.append(annotated)
        result.lookup_ms = round((time.perf_counter() - started) * 1000, 2)

        def add_group(group):
            new = [chunk for chunk in group if chunk.id not in seen]
            cost = sum(len(chunk.text) + len(chunk.enriched_text) for chunk in new)
            if len(result.chunks) + len(new) > self.max_chunks or result.added_characters + cost > self.max_characters:
                return
            for chunk in new:
                seen.add(chunk.id)
                result.chunks.append(chunk)
            result.added_characters += cost

        for chunk in direct:
            add_group([chunk])
        for group in complete_groups:
            add_group(group)
        if not result.chunks:
            result.reason = 'Lookup added no new eligible evidence within budget.'
        return result

    @staticmethod
    def _order(chunk: RetrievedChunk):
        clause = str(chunk.metadata.get('clause_no') or '')
        return (int(clause) if clause.isdigit() else 10**9,
                str(chunk.metadata.get('point') or ''), chunk.id)
