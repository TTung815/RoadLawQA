"""SQLite storage for chat conversations: titles, turns and saved answer results."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

TITLE_LENGTH = 60
HISTORY_TURNS = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    result TEXT,
    error INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(conversation_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def title_from(text: str) -> str:
    """Name a conversation after its first question, without an LLM call."""
    text = " ".join(text.split())
    return text if len(text) <= TITLE_LENGTH else text[:TITLE_LENGTH - 1].rstrip() + "…"


class ConversationStore:
    """One SQLite file; each operation opens a short connection (thread-safe)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._init_lock = threading.Lock()
        self._ready = False

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Commit on success, roll back on error, and always close."""
        with self._init_lock:
            if not self._ready:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.executescript(SCHEMA)
                self._ready = True
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection

    def create(self, title: str = "Cuộc trò chuyện mới") -> dict:
        stamp = now()
        conversation = {"id": uuid.uuid4().hex, "title": title_from(title), "created_at": stamp, "updated_at": stamp}
        with self._connect() as connection:
            connection.execute("INSERT INTO conversations VALUES (:id, :title, :created_at, :updated_at)", conversation)
        return {**conversation, "message_count": 0}

    def list(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT c.*, COUNT(m.id) AS message_count FROM conversations c "
                "LEFT JOIN messages m ON m.conversation_id = c.id "
                "GROUP BY c.id ORDER BY c.updated_at DESC, c.rowid DESC").fetchall()
        return [dict(row) for row in rows]

    def get(self, conversation_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if row is None:
                return None
            messages = connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)).fetchall()
        return {**dict(row), "message_count": len(messages), "messages": [self._message(m) for m in messages]}

    def rename(self, conversation_id: str, title: str) -> dict | None:
        with self._connect() as connection:
            updated = connection.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                                         (title_from(title), now(), conversation_id)).rowcount
        return self._summary(conversation_id) if updated else None

    def delete(self, conversation_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,)).rowcount == 1

    def add_message(self, conversation_id: str, role: str, content: str, *,
                    result: dict | None = None, error: bool = False) -> dict:
        stamp = now()
        with self._connect() as connection:
            first_user = role == "user" and connection.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ? AND role = 'user'",
                (conversation_id,)).fetchone()[0] == 0
            cursor = connection.execute(
                "INSERT INTO messages (conversation_id, role, content, result, error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, role, content, json.dumps(result, ensure_ascii=False) if result else None,
                 int(error), stamp))
            if first_user:
                connection.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                                   (title_from(content), stamp, conversation_id))
            else:
                connection.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (stamp, conversation_id))
            row = connection.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._message(row)

    def history(self, conversation_id: str, turns: int = HISTORY_TURNS) -> list[dict]:
        """Recent successful turns sent to the router; failed replies are not context."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE conversation_id = ? AND error = 0 "
                "ORDER BY id DESC LIMIT ?", (conversation_id, turns)).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def _summary(self, conversation_id: str) -> dict | None:
        conversation = self.get(conversation_id)
        if conversation is not None:
            conversation.pop("messages")
        return conversation

    @staticmethod
    def _message(row: sqlite3.Row) -> dict:
        message = dict(row)
        message["result"] = json.loads(message["result"]) if message["result"] else None
        message["error"] = bool(message["error"])
        return message
