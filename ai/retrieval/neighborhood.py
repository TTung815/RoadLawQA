"""Bounded legal-neighborhood selection, independent of databases and LLMs."""

import re
import time
from collections import defaultdict
from typing import Awaitable, Callable, List, Sequence

from pydantic import BaseModel, Field

from ai.retrieval.base import RetrievedChunk
from ai.agent.evidence import publishable_chunk

ArticleFetch = Callable[[str, str], Awaitable[Sequence[RetrievedChunk]]]
RuleFetch = Callable[[Sequence[str]], Awaitable[Sequence[RetrievedChunk]]]


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
    """Bounded lookup of explicit references and consequence leaves around retrieved sources.

    No sanction is asserted to apply here; generation and verification decide.
    """

    def __init__(self, fetch_article: ArticleFetch, max_chunks: int = 8,
                 max_characters: int = 12000, max_scopes: int = 2,
                 combination_lookup: RuleFetch | None = None):
        if any(type(value) is not int or value < 1
               for value in (max_chunks, max_characters, max_scopes)):
            raise ValueError('Expansion budgets must be positive integers')
        self._fetch_article = fetch_article
        self._combination_lookup = combination_lookup
        self.max_chunks = max_chunks
        self.max_characters = max_characters
        self.max_scopes = max_scopes

    async def expand_references(self, anchors: Sequence[RetrievedChunk], question: str = "") -> NeighborhoodSelection:
        """Follow explicit references and reverse consequence links once, within budgets.

        This selects candidates, never asserts applicability or completeness. Full
        referenced clauses are added atomically; unknown reference syntax is skipped.
        """
        started = time.perf_counter()
        requests = defaultdict(list)
        local = defaultdict(list)
        for anchor in anchors:
            if not publishable_chunk(anchor):
                continue
            law = str(anchor.metadata.get('law') or '').strip()
            article = str(anchor.metadata.get('article_no') or '').strip()
            if not law or not article:
                continue
            local[(law, article)].append(anchor)
            if 'references' in anchor.metadata:
                for ref in anchor.metadata['references']:
                    if ref['resolved'] and ref['chunk_ids']:
                        requests[(ref['law'], ref['article_no'])].append((ref['clause_no'], anchor.id))
                continue
            names = set(re.findall(
                r'Luật\s+(?:Trật tự,\s*an toàn giao thông đường bộ|Đường bộ)', anchor.text, re.I))
            if len(names) == 1:
                target = next(iter(names))
                for match in re.finditer(r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\b', anchor.text, re.I):
                    requests[(target, match[2])].append((match[1], anchor.id))
            if not names:
                for match in re.finditer(r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+(?:của\s+)?(?:Nghị định|Luật) này|(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+này', anchor.text, re.I):
                    requests[(law, match[2] or match[4])].append((match[1] or match[3], anchor.id))
                if 'điều này' in anchor.text.casefold() and not re.search(r'\bđiều\s+\d+', anchor.text, re.I):
                    for clause in re.findall(r'\bkhoản\s+(\d+)\b', anchor.text, re.I):
                        requests[(law, article)].append((clause, anchor.id))
        result = NeighborhoodSelection(triggered=bool(local), missing_aspects=[],
                                       reason='Bounded explicit references and consequence links; no coverage grade.')
        seen = {c.id for c in anchors}

        def add_group(group):
            new = {c.id: c for c in group if c.id not in seen}
            cost = sum(len(c.text) + len(c.enriched_text) for c in new.values())
            if len(result.chunks) + len(new) > self.max_chunks or result.added_characters + cost > self.max_characters:
                return
            result.chunks.extend(new.values())
            seen.update(new)
            result.added_characters += cost

        # A question about combined consequences needs the general combination
        # rule, which individual sanction leaves need not explicitly cite. This
        # lexical lookup selects evidence only, never computes the legal result.
        aggregate = re.search(r"\bcùng (?:một )?lần\b|\btổng(?: cộng| hợp| tiền| số| mức| điểm)\b|\bcộng (?:dồn|lại)\b", question, re.I)
        if aggregate and self._combination_lookup is not None:
            laws = list(dict.fromkeys(law for law, _ in local))[:self.max_scopes]
            rules = [c for c in await self._combination_lookup(laws)
                     if publishable_chunk(c) and c.metadata.get('law') in laws]
            add_group(rules)
            result.reason += ' Included candidates for combined consequences.'

        # Referenced articles precede anchor articles, avoiding starvation by top-k.
        scopes = sorted(dict.fromkeys([*requests, *local]), key=lambda scope: (
            scope not in requests,
            # Cross-document applicability references precede other sanction
            # articles, whose long clauses can otherwise consume the budget.
            any(scope[0].casefold() in law.casefold() for law, _ in local),
        ))[:self.max_scopes]
        fetched_by_scope = {}
        for law, article in scopes:
            fetched = [c for c in await self._fetch_article(law, article)
                       if publishable_chunk(c) and str(c.metadata.get('article_no') or '') == article
                       and law.casefold() in str(c.metadata.get('law') or '').casefold()]
            if len({c.metadata.get('law') for c in fetched}) > 1:
                fetched = []
            fetched_by_scope[(law, article)] = sorted(fetched, key=self._order)
            result.scopes.append(LegalScope(law=law, article_no=article,
                anchor_chunk_ids=list(dict.fromkeys([i for _, i in requests[(law, article)]] +
                                                    [c.id for c in local[(law, article)]])),
                candidate_count=len(fetched)))

        def is_consequence(chunk):
            head = str(chunk.metadata.get('clause_head') or '').casefold()
            return 'trừ điểm' in head or 'xử phạt bổ sung' in head

        def add_referenced(scope):
            for clause in dict.fromkeys(c for c, _ in requests[scope]):
                add_group([c for c in fetched_by_scope[scope] if clause is None or
                           str(c.metadata.get('clause_no') or '') == clause or
                           c.metadata.get('granularity') == 'article'])

        def cross_document(scope):
            return not any(scope[0].casefold() in law.casefold() for law, _ in local)

        # Budget order: cross-document applicability conditions, then the
        # point-level points/additional-sanction leaves naming a retrieved
        # violation (short and specific, in rank order), then other explicit
        # references, whose whole clauses can otherwise consume the budget.
        for scope in fetched_by_scope:
            if scope in requests and cross_document(scope):
                add_referenced(scope)
        for anchor in anchors:
            scope = (str(anchor.metadata.get('law') or '').strip(),
                     str(anchor.metadata.get('article_no') or '').strip())
            if publishable_chunk(anchor) and scope in fetched_by_scope:
                for candidate in fetched_by_scope[scope]:
                    if is_consequence(candidate) and _same_article_reference(candidate.text, anchor):
                        add_group([candidate])
        for scope in fetched_by_scope:
            if scope in requests and not cross_document(scope):
                add_referenced(scope)
        for (law, article), fetched in fetched_by_scope.items():
            for candidate in fetched:
                head = str(candidate.metadata.get('clause_head') or '').casefold()
                if is_consequence(candidate) and any(
                        _same_article_reference(candidate.text, a) for a in local[(law, article)]):
                    continue
                if not any(term in (head + ' ' + candidate.text.casefold())
                           for term in ('phạt tiền', 'trừ điểm', 'tước quyền')):
                    # Reverse links in scope/condition rules may use compressed
                    # point lists. Clause overlap retrieves a candidate, not proof
                    # that a particular point or vehicle qualifies.
                    body = candidate.text.casefold()
                    clauses = set(re.findall(r'\bkhoản\s+(\d+)\b', body))
                    anchor_clauses = {str(a.metadata.get('clause_no') or '')
                                      for a in local[(law, article)]}
                    if 'điều này' in body and not re.search(r'\bđiều\s+\d+', body) and clauses & anchor_clauses:
                        add_group([candidate])
                        for clause in sorted(clauses):
                            add_group(sorted([c for c in fetched if str(c.metadata.get('clause_no') or '') == clause],
                                             key=self._order))
        result.lookup_ms = round((time.perf_counter() - started) * 1000, 2)
        return result

    @staticmethod
    def _order(chunk: RetrievedChunk):
        clause = str(chunk.metadata.get('clause_no') or '')
        return (int(clause) if clause.isdigit() else 10**9,
                str(chunk.metadata.get('point') or ''), chunk.id)
