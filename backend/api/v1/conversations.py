"""Saved conversations: list, open, rename, delete and send a message with stored history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.dependencies.answer import get_chat_service
from backend.dependencies.conversations import get_conversation_store
from backend.schemas.answer import AnswerResult
from backend.schemas.conversations import (
    ConversationDetail, ConversationRename, ConversationSummary, MessageExchange, MessageRequest,
)
from backend.services.chat import ChatService
from backend.services.conversations import ConversationStore

router = APIRouter(prefix="/conversations", tags=["Conversations"])
Store = Annotated[ConversationStore, Depends(get_conversation_store)]
FAILED_REPLY = "Chưa nhận được phản hồi từ hệ thống. Bạn hãy thử gửi lại câu hỏi."


def assistant_content(result: AnswerResult) -> str:
    """Plain text kept as conversation history for later follow-up questions."""
    normalize = lambda value: " ".join(value.split())
    main = result.answer.text if result.answer else result.message
    limits = result.limitations
    if normalize(main) == normalize(" ".join(limits)):
        # An abstention message is its own limitations; do not repeat them.
        limits = []
    parts, seen = [main], {normalize(main)}
    for text in [*limits, *result.follow_up_questions]:
        if text.strip() and normalize(text) not in seen:
            parts.append(text)
            seen.add(normalize(text))
    return "\n".join(parts)


def require(store: ConversationStore, conversation_id: str) -> dict:
    conversation = store.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    return conversation


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(store: Store) -> list[dict]:
    return store.list()


@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(store: Store) -> dict:
    return store.create()


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, store: Store) -> dict:
    return require(store, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation(conversation_id: str, request: ConversationRename, store: Store) -> dict:
    conversation = store.rename(conversation_id, request.title)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, store: Store) -> Response:
    if not store.delete(conversation_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    return Response(status_code=204)


@router.post("/{conversation_id}/messages", response_model=MessageExchange)
async def send_message(
    conversation_id: str, request: MessageRequest, store: Store,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict:
    require(store, conversation_id)
    # History is read before saving the new turn, so it holds only prior turns.
    history = store.history(conversation_id)
    user = store.add_message(conversation_id, "user", request.content)
    try:
        result = await service.answer(request.content, history, top_k=request.top_k)
    except Exception:
        # Keep the question and a sanitized failure so a reload shows what
        # happened; the error turn is excluded from later history.
        store.add_message(conversation_id, "assistant", FAILED_REPLY, error=True)
        raise
    assistant = store.add_message(conversation_id, "assistant", assistant_content(result),
                                  result=result.model_dump(mode="json"))
    return {"user": user, "assistant": assistant}
