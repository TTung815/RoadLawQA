# -*- coding: utf-8 -*-
"""
Common / Shared Schemas
"""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness health check response model."""
    status: str = "ok"
    app: str = "VietLaw-Agent"
    version: str = "2.0.0"

