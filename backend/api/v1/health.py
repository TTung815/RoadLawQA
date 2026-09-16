# -*- coding: utf-8 -*-
"""
Health Check Router
Provides a liveness check endpoint without loading any ML models or external connections.
"""
from fastapi import APIRouter
from backend.schemas.common import HealthResponse

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

