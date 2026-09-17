"""Expose original query, standalone query, and retrieved legal chunks."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies.retrieval import get_agentic_retrieval_service, get_retrieval_service
from backend.schemas.retrieval import RetrievalRequest
from backend.services.retrieval import HistoryAwareRetrievalService, RetrievalResult
from backend.services.agentic_retrieval import AgenticRetrievalResult, AgenticRetrievalService

router = APIRouter(tags=["Retrieval"])


@router.post("/retrieve", response_model=RetrievalResult)
async def retrieve(
    request: RetrievalRequest,
    service: Annotated[HistoryAwareRetrievalService, Depends(get_retrieval_service)],
) -> RetrievalResult:
    return await service.retrieve(
        request.current_query,
        [turn.model_dump() for turn in request.chat_history],
        top_k=request.top_k,
    )


@router.post("/retrieve/agentic", response_model=AgenticRetrievalResult)
async def retrieve_agentic(
    request: RetrievalRequest,
    service: Annotated[AgenticRetrievalService, Depends(get_agentic_retrieval_service)],
) -> AgenticRetrievalResult:
    return await service.retrieve(
        request.current_query,
        [turn.model_dump() for turn in request.chat_history],
        top_k=request.top_k,
    )
