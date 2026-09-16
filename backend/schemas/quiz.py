# -*- coding: utf-8 -*-
"""
Initial Quiz Schemas (Minimal for V2 Foundation)
"""
from typing import Dict, List
from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    """Multiple-choice quiz question item."""
    question: str
    options: Dict[str, str] = Field(..., description="Map of option keys (A, B, C, D) to choices")
    correct_answer: str
    explanation: str
    citation: str


class QuizRequest(BaseModel):
    """Request to generate quiz questions."""
    topic: str = Field(..., min_length=1, description="Topic or law keyword")
    num_questions: int = Field(default=3, ge=1, le=10)


class QuizResponse(BaseModel):
    """Response containing generated quiz questions."""
    questions: List[QuizQuestion] = Field(default_factory=list)

