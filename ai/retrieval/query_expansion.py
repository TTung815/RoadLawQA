"""Bounded search paraphrases; never a replacement for the answer question."""

import re


def question_focus(query: str) -> str | None:
    """An extra search view of a question after a temporal lead-in.

    Keep the original query for search, explicit locators and generation.
    Do not strip an if/unless condition or invent a paraphrase.
    """
    if not re.match(r"^(?:khi|trong khi|trong lúc)\s+(?!nào\b)", query, re.I):
        return None
    _, separator, question = query.partition(",")
    question = question.strip()
    if separator and re.search(r"\b(?:có phải|có được|phải|cần)\b", question, re.I):
        return question
    return None


def checked_expansion(query: str, expansion: str | None) -> tuple[str | None, str]:
    """Reject empty, duplicate, oversized or numerically changed paraphrases.

    This is a structural guard, not proof of semantic equivalence. The router
    must preserve conditions; generation/verification retain the original query.
    """
    if expansion is None:
        return None, "not_requested"
    expansion = expansion.strip()
    if not expansion:
        return None, "empty"
    if len(expansion) > 800:
        return None, "too_long"
    normalize = lambda text: " ".join(re.findall(r"\w+", text.casefold()))
    if normalize(query) == normalize(expansion):
        return None, "duplicate"
    # Preserve the existing focused question view within the two-view budget.
    # An extra paraphrase must not displace this view or dilute its ranking.
    if question_focus(query):
        return None, "existing_question_focus"
    numbers = lambda text: set(re.findall(r"\d+(?:[.,/]\d+)*", text))
    if numbers(query) != numbers(expansion):
        return None, "changed_numbers"
    # Conservatively keep short negative phrases verbatim. This can reject a
    # valid paraphrase; original-only retrieval is preferable to silently losing
    # an explicit denial. A trailing question particle "không?" does not match.
    negatives = re.findall(r"\b(?:không|chưa|chẳng)(?:[ \t]+\w+){1,2}", query.casefold())
    normalized_expansion = " " + normalize(expansion) + " "
    if any(" " + normalize(phrase) + " " not in normalized_expansion for phrase in negatives):
        return None, "changed_negation"
    return expansion, "accepted"


def rerank_question(query: str, expansion: str | None) -> str:
    # Repeating both full questions can overwhelm the cross-encoder with the
    # original colloquial wording and shorten the available document context.
    # The faithful original is still searched and used for generation/verification.
    return expansion or query
