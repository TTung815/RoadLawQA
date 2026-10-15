"""Expose original query, standalone query, and retrieved legal chunks."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies.retrieval import get_current_retriever, get_lean_retrieval_service, get_retrieval_service
from backend.schemas.retrieval import RetrievalRequest
from ai.pipeline.retrieval import HistoryAwareRetrievalService
from ai.pipeline.results import RetrievalResult
from ai.pipeline.results import EvidenceRetrievalResult
from ai.pipeline.retrieval import LeanRetrievalService

router = APIRouter(tags=["Retrieval"])


@router.post("/retrieve/inspect")
async def inspect_sources(request: RetrievalRequest, retriever=Depends(get_current_retriever)) -> dict:
    from backend.services.retrieval_inspection import inspect_retrieval
    from fastapi import HTTPException
    if request.chat_history:
        raise HTTPException(status_code=422, detail="Màn hình truy xuất nhận câu hỏi độc lập, không gọi LLM để xử lý lịch sử.")
    return await inspect_retrieval(retriever, request.current_query, request.top_k)


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


@router.post("/retrieve/evidence", response_model=EvidenceRetrievalResult)
async def retrieve_evidence(
    request: RetrievalRequest,
    service: Annotated[LeanRetrievalService, Depends(get_lean_retrieval_service)],
) -> EvidenceRetrievalResult:
    return await service.retrieve(
        request.current_query,
        [turn.model_dump() for turn in request.chat_history],
        top_k=request.top_k,
    )
