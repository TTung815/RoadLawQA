"""Request contract for retrieval without answer generation."""

from typing import Annotated, List, Literal

from pydantic import BaseModel, Field, StringConstraints


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class RetrievalRequest(BaseModel):
    current_query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    chat_history: List[HistoryMessage] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
