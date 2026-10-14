"""Grounded legal QA endpoint, retaining evidence and explicit failure states."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies.answer import get_chat_service
from backend.schemas.answer import AnswerResult
from backend.schemas.retrieval import RetrievalRequest
from backend.services.chat import ChatService

router = APIRouter(tags=["Answer"])


@router.post("/answer", response_model=AnswerResult)
async def answer(
    request: RetrievalRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> AnswerResult:
    return await service.answer(
        request.current_query, [turn.model_dump() for turn in request.chat_history],
        top_k=request.top_k,
    )
