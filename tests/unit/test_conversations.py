"""Saved conversations: SQLite store and API, with a fake chat service and no models."""

import pytest
from fastapi.testclient import TestClient

from ai.agent.citation_verifier import CitationVerification
from ai.diagnostics import PipelineError
from backend.dependencies.answer import get_chat_service
from backend.dependencies.conversations import get_conversation_store
from backend.main import create_app
from backend.schemas.answer import AnswerResult
from backend.services.conversations import ConversationStore, title_from


def reply(message="Mình sẵn sàng hỗ trợ.", **fields):
    return AnswerResult(status="conversational", message=message, retrieval=None, evidence_citations=[],
                        verification=CitationVerification(status="not_run"), **fields)


class FakeChat:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.calls = list(results or []), error, []

    async def answer(self, query, history=(), top_k=10):
        self.calls.append({"query": query, "history": list(history), "top_k": top_k})
        if self.error is not None:
            raise self.error
        return self.results.pop(0) if self.results else reply(f"Đã nhận: {query}")


@pytest.fixture
def store(tmp_path):
    return ConversationStore(tmp_path / "chat" / "conversations.sqlite3")


@pytest.fixture
def api(store):
    chat = FakeChat()
    app = create_app()
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_chat_service] = lambda: chat
    return TestClient(app), chat


def test_store_titles_orders_and_cascades(store):
    first, second = store.create(), store.create()
    store.add_message(first["id"], "user", "  Vượt   đèn đỏ\nphạt bao nhiêu?  ")
    store.add_message(second["id"], "user", "x" * 100)
    assert [c["id"] for c in store.list()] == [second["id"], first["id"]]
    assert store.get(first["id"])["title"] == "Vượt đèn đỏ phạt bao nhiêu?"
    assert store.get(second["id"])["title"] == title_from("x" * 100) and len(title_from("x" * 100)) == 60
    store.add_message(first["id"], "assistant", "18–20 triệu", result={"status": "answered"})
    assert store.list()[0]["id"] == first["id"]  # updated_at moves the active chat to the top
    assert store.delete(first["id"]) and store.get(first["id"]) is None and not store.delete(first["id"])


def test_history_is_recent_successful_turns_in_order(store):
    conversation = store.create()["id"]
    for index in range(7):
        store.add_message(conversation, "user", f"Câu {index}")
        store.add_message(conversation, "assistant", f"Đáp {index}", error=index == 6)
    history = store.history(conversation)
    assert len(history) == 10 and history[-1] == {"role": "user", "content": "Câu 6"}
    assert all(turn["content"] != "Đáp 6" for turn in history)


def test_api_lifecycle_create_list_open_rename_delete(api):
    client, _ = api
    created = client.post("/api/v1/conversations")
    assert created.status_code == 201 and created.json()["message_count"] == 0
    conversation = created.json()["id"]
    assert [c["id"] for c in client.get("/api/v1/conversations").json()] == [conversation]
    renamed = client.patch(f"/api/v1/conversations/{conversation}", json={"title": "Đèn đỏ"})
    assert renamed.json()["title"] == "Đèn đỏ"
    assert client.get(f"/api/v1/conversations/{conversation}").json()["messages"] == []
    assert client.delete(f"/api/v1/conversations/{conversation}").status_code == 204
    for request in (client.get, client.delete):
        assert request(f"/api/v1/conversations/{conversation}").status_code == 404
    assert client.post(f"/api/v1/conversations/{conversation}/messages", json={"content": "Hi"}).status_code == 404


def test_messages_use_stored_history_and_are_saved_with_results(api):
    client, chat = api
    conversation = client.post("/api/v1/conversations").json()["id"]
    first = client.post(f"/api/v1/conversations/{conversation}/messages",
                        json={"content": "Vượt đèn đỏ phạt bao nhiêu?"}).json()
    assert first["user"]["content"] == "Vượt đèn đỏ phạt bao nhiêu?"
    assert first["assistant"]["result"]["status"] == "conversational"
    client.post(f"/api/v1/conversations/{conversation}/messages", json={"content": "Xe máy", "top_k": 5})
    assert chat.calls[0]["history"] == []
    # The follow-up receives prior turns from storage, not from the client.
    assert chat.calls[1] == {"query": "Xe máy", "top_k": 5, "history": [
        {"role": "user", "content": "Vượt đèn đỏ phạt bao nhiêu?"},
        {"role": "assistant", "content": "Đã nhận: Vượt đèn đỏ phạt bao nhiêu?"}]}
    detail = client.get(f"/api/v1/conversations/{conversation}").json()
    assert detail["title"] == "Vượt đèn đỏ phạt bao nhiêu?" and detail["message_count"] == 4


@pytest.mark.parametrize("limits, expected", [
    (["Chưa tìm được nguồn."], "Chưa tìm được nguồn."),
    (["Thiếu nguồn tiền phạt.", "Thiếu nguồn thời hạn."], "Thiếu nguồn tiền phạt. Thiếu nguồn thời hạn."),
])
def test_abstention_history_text_does_not_repeat_its_limitations(api, limits, expected):
    client, chat = api
    chat.results = [reply(" ".join(limits), limitations=limits)]
    conversation = client.post("/api/v1/conversations").json()["id"]
    sent = client.post(f"/api/v1/conversations/{conversation}/messages", json={"content": "Tình huống"}).json()
    assert sent["assistant"]["content"] == expected


def test_pipeline_failure_keeps_question_and_sanitized_error_outside_history(api, store):
    client, chat = TestClient(api[0].app, raise_server_exceptions=False), api[1]
    chat.error = PipelineError("generation", "TimeoutError")
    conversation = client.post("/api/v1/conversations").json()["id"]
    response = client.post(f"/api/v1/conversations/{conversation}/messages", json={"content": "Câu hỏi"})
    assert response.status_code == 502 and "stage" in response.json()
    messages = client.get(f"/api/v1/conversations/{conversation}").json()["messages"]
    assert [(m["role"], m["error"]) for m in messages] == [("user", False), ("assistant", True)]
    assert "TimeoutError" not in messages[1]["content"]
    assert store.history(conversation) == [{"role": "user", "content": "Câu hỏi"}]


def test_relative_chat_db_path_resolves_from_the_repository(monkeypatch):
    from backend.dependencies.conversations import get_conversation_store
    from configs.settings import PROJECT_ROOT
    monkeypatch.setenv("CHAT_DB_PATH", "outputs/chat/test-only.sqlite3")
    get_conversation_store.cache_clear()
    try:
        assert get_conversation_store().path == PROJECT_ROOT / "outputs/chat/test-only.sqlite3"
    finally:
        get_conversation_store.cache_clear()
