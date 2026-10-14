# -*- coding: utf-8 -*-
"""
Initial Chat Schemas (Minimal for V2 Foundation)
"""
from typing import List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Initial chat request model."""
    message: str = Field(..., min_length=1, description="User legal query")
    top_k: int = Field(default=10, ge=1, le=20, description="Number of chunks to retrieve")


class ChatResponse(BaseModel):
    """Initial chat response model."""
    answer: str
    citations: List[str] = Field(default_factory=list)

