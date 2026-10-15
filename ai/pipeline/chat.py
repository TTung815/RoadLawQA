"""Handle unambiguous social turns before loading the legal QA pipeline."""

import re
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence

from ai.agent.citation_verifier import CitationVerification
from ai.agent.conversation_router import ConversationRouter
from ai.diagnostics import traced
from ai.pipeline.results import AnswerResult, AnswerTimings
from ai.pipeline.answer import AnswerService


_ADDRESSEE = r"(?:\s+(?:ban|bot|chatbot|roadlawqa))?"
_PARTICLE = r"(?:\s+(?:a|nhe|nha|nhi|nhe a))?"
_GREETING = rf"(?:xin chao|chao|hello|hi|hey){_ADDRESSEE}{_PARTICLE}"
_THANKS = rf"(?:cam on|cam on ban|cam on nhieu|cam on ban nhieu|thank you|thanks){_PARTICLE}"
_GOODBYE = rf"(?:tam biet|hen gap lai|bye|goodbye){_ADDRESSEE}{_PARTICLE}"
_HELP = (
    r"(?:ban la ai|ban (?:co the )?lam (?:duoc )?(?:gi|nhung gi)|"
    r"ban (?:co the )?giup (?:(?:toi|minh) )?(?:duoc )?(?:gi|nhung gi)|"
    r"huong dan su dung|cach su dung|help)"
)
_SOCIAL_TURN = re.compile(rf"(?:{_GREETING}|{_THANKS}|{_GOODBYE}|{_HELP})(?:\s+(?:{_GREETING}|{_THANKS}|{_GOODBYE}|{_HELP}))*")
_INTRODUCTION = (
    "Mình là RoadLawQA, trợ lý hỏi đáp luật giao thông đường bộ Việt Nam. "
    "Bạn có thể mô tả tình huống hoặc hỏi về quy định; mình sẽ tìm căn cứ "
    "và dẫn nguồn để bạn đối chiếu. Ví dụ: “Đi xe máy có phải đội mũ bảo hiểm không?”"
)
_SCOPE_MESSAGE = (
    "Hiện mình hỗ trợ hỏi đáp pháp luật giao thông đường bộ Việt Nam. "
    "Chủ đề bạn vừa hỏi nằm ngoài phạm vi hỗ trợ của RoadLawQA. "
    "Bạn có thể hỏi về quy tắc đi đường, giấy phép lái xe hoặc xử lý vi phạm giao thông."
)
_MIXED_LIMITATION = "Mình chỉ xử lý phần câu hỏi về giao thông đường bộ; phần chủ đề khác nằm ngoài phạm vi hỗ trợ."


def social_reply(query: str) -> str | None:
    """Match the whole turn: a greeting prefix must never hide a legal question.

    Bare acknowledgements (yes/no/OK) remain available to contextualization.
    This intentionally covers common social turns, not open-ended conversation.
    """
    normalized = unicodedata.normalize("NFD", query.casefold().replace("đ", "d"))
    normalized = "".join(
        " " if unicodedata.category(char)[0] in {"P", "S"} else char
        for char in normalized if unicodedata.category(char) != "Mn"
    )
    normalized = " ".join(normalized.split())
    if len(normalized) > 240 or not _SOCIAL_TURN.fullmatch(normalized):
        return None
    if re.search(_HELP, normalized):
        return _INTRODUCTION
    if re.search(_GOODBYE, normalized):
        return "Tạm biệt bạn! Khi cần tìm hiểu luật giao thông, bạn cứ quay lại nhé."
    if re.search(_THANKS, normalized):
        return "Rất vui được hỗ trợ bạn! Bạn có thể hỏi tiếp nếu còn tình huống cần làm rõ."
    return "Chào bạn! " + _INTRODUCTION


class ChatService:
    def __init__(self, legal_service: Callable[[], AnswerService],
                 router: Callable[[], ConversationRouter]):
        self._legal_service = legal_service
        self._router = router

    @traced("answer")
    async def answer(
        self, current_query: str, chat_history: Sequence[Mapping[str, str]] = (),
        top_k: int = 10,
    ) -> AnswerResult:
        started = time.perf_counter()
        message = social_reply(current_query)
        intent = "social"
        routing_ms = 0.0
        if message is None:
            decision = await self._router().route(current_query, chat_history)
            routing_ms = (time.perf_counter() - started) * 1000
            intent = decision.intent
            message = {
                "help": _INTRODUCTION,
                "social": "Mình sẵn sàng hỗ trợ bạn tìm hiểu luật giao thông. Bạn muốn hỏi điều gì?",
                "out_of_scope": _SCOPE_MESSAGE,
                "clarify": "Bạn hãy nêu câu hỏi hoặc tình huống giao thông muốn tìm hiểu nhé.",
            }.get(intent)
        if message is not None:
            return AnswerResult(
                status="out_of_scope" if intent == "out_of_scope" else "conversational",
                message=message, retrieval=None,
                evidence_citations=[], verification=CitationVerification(status="not_run"),
                timings=AnswerTimings(routing_ms=routing_ms, total_ms=(time.perf_counter() - started) * 1000),
            )
        search_options = {"retrieval_query": decision.retrieval_query} if decision.retrieval_query else {}
        result = await self._legal_service().answer(
            current_query, chat_history, top_k=top_k, prepared_query=decision.standalone_query, **search_options,
        )
        if intent == "mixed":
            result.limitations.append(_MIXED_LIMITATION)
            if result.status == "answered":
                result.status = "partial_answer"
                result.message = "Đã trả lời phần câu hỏi về giao thông có căn cứ."
        result.timings.routing_ms = routing_ms
        result.timings.total_ms = (time.perf_counter() - started) * 1000
        return result
