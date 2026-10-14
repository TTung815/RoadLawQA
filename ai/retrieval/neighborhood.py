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
    """Select consequence siblings using aspect headings and local references.

    Complete additional-sanction clauses may supply negative applicability evidence;
    they are included atomically, never as a partial list implying exhaustiveness.
    No sanction is asserted to apply here. Final coverage belongs to the grader.
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

    async def expand(self, anchors: Sequence[RetrievedChunk],
                     missing_aspects: Sequence[str],
                     existing: Sequence[RetrievedChunk]) -> NeighborhoodSelection:
        supported = set(missing_aspects) & {'license_points', 'additional_sanction',
                                          'condition_exception', 'subject_violation', 'monetary_penalty'}
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
        direct, complete_groups, context = [], [], []
        reference_requests = []
        for anchor in anchors:
            named_laws = set(re.findall(
                r'Luật\s+(?:Trật tự,\s*an toàn giao thông đường bộ|Đường bộ)',
                anchor.text, re.IGNORECASE,
            ))
            # A document can follow several references separated by parenthetical
            # vehicle conditions, e.g. khoản 1 Điều 56 (...), khoản 2 Điều 56 (...)
            # của Luật ... . Resolve only when the named document is unambiguous.
            if len(named_laws) == 1:
                target = next(iter(named_laws))
                for match in re.finditer(r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\b', anchor.text, re.I):
                    reference_requests.append((target, match[2], match[1], anchor.id))
            for match in re.finditer(
                r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+(Luật\s+[^;\n.()]+|này)',
                anchor.text, re.IGNORECASE,
            ):
                target = match[3].strip()
                # Only explicit document names or the same document are resolved.
                if target.casefold() == 'này':
                    target = str(anchor.metadata.get('law') or '')
                reference_requests.append((target, match[2], match[1], anchor.id))
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
                    str(chunk.metadata.get('article_no') or '').strip() == article
                    and publishable_chunk(chunk)):
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
            if supported & {'condition_exception', 'subject_violation', 'monetary_penalty'}:
                # Broad context is a search candidate, never an applicability proof.
                referenced_clauses = {number for c in siblings.values()
                                      for number in re.findall(r'\bkhoản\s+(\d+)\b', c.text, re.I)}
                context.extend(sorted(siblings.values(), key=lambda c: (
                    str(c.metadata.get('clause_no') or '') not in referenced_clauses,
                    bool(c.metadata.get('point')), self._order(c))))
        referenced = []
        seen_scopes = {(scope.law, scope.article_no) for scope in result.scopes}
        reference_groups = defaultdict(list)
        for law, article, clause, anchor_id in reference_requests:
            reference_groups[(law, article)].append((clause, anchor_id))
        for (law, article), requests in reference_groups.items():
            if len(seen_scopes) >= self.max_scopes:
                break
            if (law, article) in seen_scopes:
                continue
            seen_scopes.add((law, article))
            fetched = list(await self._fetch_article(law, article))
            result.scopes.append(LegalScope(law=law, article_no=article,
                                           anchor_chunk_ids=list(dict.fromkeys(r[1] for r in requests)),
                                           candidate_count=len(fetched)))
            clauses = {clause for clause, _ in requests}
            referenced.extend(c for c in fetched if publishable_chunk(c)
                              and str(c.metadata.get('article_no') or '') == article
                              and (None in clauses or str(c.metadata.get('clause_no') or '') in clauses))
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
        for chunk in referenced:
            add_group([chunk])
        for chunk in context:
            add_group([chunk])
        if not result.chunks:
            result.reason = 'Lookup added no new eligible evidence within budget.'
        return result

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
        for law, article in scopes:
            fetched = [c for c in await self._fetch_article(law, article)
                       if publishable_chunk(c) and str(c.metadata.get('article_no') or '') == article
                       and law.casefold() in str(c.metadata.get('law') or '').casefold()]
            if len({c.metadata.get('law') for c in fetched}) > 1:
                fetched = []
            result.scopes.append(LegalScope(law=law, article_no=article,
                anchor_chunk_ids=list(dict.fromkeys([i for _, i in requests[(law, article)]] +
                                                    [c.id for c in local[(law, article)]])),
                candidate_count=len(fetched)))
            for clause in dict.fromkeys(c for c, _ in requests[(law, article)]):
                add_group(sorted([c for c in fetched if clause is None or
                                  str(c.metadata.get('clause_no') or '') == clause or
                                  c.metadata.get('granularity') == 'article'], key=self._order))
            for candidate in sorted(fetched, key=self._order):
                head = str(candidate.metadata.get('clause_head') or '').casefold()
                if ('trừ điểm' in head or 'xử phạt bổ sung' in head) and any(
                        _same_article_reference(candidate.text, a) for a in local[(law, article)]):
                    add_group([candidate])
                elif not any(term in (head + ' ' + candidate.text.casefold())
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
