# -*- coding: utf-8 -*-
"""
Health Check Router
Provides a liveness check endpoint without loading any ML models or external connections.
"""
from fastapi import APIRouter, Request
from backend.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Application liveness health check.
    Does NOT connect to Weaviate, Gemini, or load PyTorch models.
    """
    return HealthResponse(
        status="ok",
        app="VietLaw-Agent",
        version="2.0.0",
    )



@router.get("/ready", response_model=ReadinessResponse)
async def get_readiness(request: Request) -> ReadinessResponse:
    """Report whether retrieval resources are loaded, without loading them."""
    from backend.dependencies.retrieval import get_current_retriever
    loaded = bool(get_current_retriever.cache_info().currsize) and get_current_retriever().loaded
    state = getattr(request.app.state, "readiness", {"warmup": "not_started"})
    return ReadinessResponse(retrieval_loaded=loaded, warmup=state["warmup"])
