"""Lazy conversation store; the SQLite file is created on first use, not on import."""

from functools import lru_cache

from backend.services.conversations import ConversationStore
from configs.settings import PROJECT_ROOT, LLMSettings


@lru_cache(maxsize=1)
def get_conversation_store() -> ConversationStore:
    path = LLMSettings().chat_db_path
    # A relative CHAT_DB_PATH is resolved from the repository, not the shell's cwd.
    return ConversationStore(path if path.is_absolute() else PROJECT_ROOT / path)
