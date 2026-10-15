"""Saved conversations: summaries, messages and the send-message contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from ai.pipeline.results import AnswerResult

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    result: AnswerResult | None = None
    error: bool = False
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]


class ConversationRename(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class MessageRequest(BaseModel):
    content: Text
    top_k: int = Field(default=10, ge=1, le=20)


class MessageExchange(BaseModel):
    user: ConversationMessage
    assistant: ConversationMessage
