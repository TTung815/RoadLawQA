# -*- coding: utf-8 -*-
"""
Common / Shared Schemas
"""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness health check response model."""
    status: str = "ok"
    app: str = "RoadLawQA"
    version: str = "2.0.0"


class ReadinessResponse(BaseModel):
    """Whether serving retrieval resources are loaded; reading it loads nothing."""
    retrieval_loaded: bool
    warmup: str = Field(description="not_started, disabled, running, done or failed")
