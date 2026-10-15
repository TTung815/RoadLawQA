"""Exercise the chat client against the in-process API and a temporary SQLite store."""

import json
from html import escape
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from ai.agent.citation_verifier import CitationVerification
from ai.diagnostics import PipelineError
from ai.retrieval.base import RetrievedChunk
from backend.dependencies import answer as dependencies
from backend.dependencies.answer import get_chat_service
from backend.dependencies.conversations import get_conversation_store
from backend.main import create_app
from backend.schemas.answer import AnswerResult, EvidenceCitation, GroundedAnswer, VerifiedClaim
from backend.services.conversations import ConversationStore
from backend.services.lean_retrieval import EvidenceRetrievalResult
from tests.unit.test_conversations import FakeChat, reply

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "frontend/app.py")


def legal(status, message, *, answer=None, chunks=(), **fields):
    retrieval = EvidenceRetrievalResult(original_query="q", standalone_query="q", chunks=list(chunks),
                                        retrieval_queries=["q"])
    return AnswerResult(status=status, message=message, retrieval=retrieval, answer=answer,
                        evidence_citations=[EvidenceCitation(chunk_id=c.id, citation=c.citation) for c in chunks],
                        verification=CitationVerification(status="passed" if answer else "not_run"), **fields)


@pytest.fixture(autouse=True)
def isolated_frontend_environment(monkeypatch):
    # AppTest runs in this process: never import the owner's .env into tests.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("ROADLAWQA_API_URL", "http://test")
    monkeypatch.setenv("WARMUP_ON_STARTUP", "false")


@pytest.fixture
def backend(monkeypatch, tmp_path):
    """Route the UI's httpx calls into the real API with a temporary store."""
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    state = SimpleNamespace(store=store, chat=FakeChat(), calls=[], failure=None, inspection=None)
    app = create_app()
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_chat_service] = lambda: state.chat
    client = TestClient(app, raise_server_exceptions=False)

    def route(method):
        def call(url, *, json=None, timeout=None):
            path = url.removeprefix("http://test")
            state.calls.append((method, path, json))
            if method == "POST" and path.endswith("/messages") and state.failure:
                raise state.failure
            if path.endswith("/retrieve/inspect"):
                return httpx.Response(200, json=state.inspection, request=httpx.Request(method, url))
            return client.request(method, path, json=json)
        return call

    for method in ("get", "post", "delete"):
        monkeypatch.setattr(httpx, method, route(method.upper()))
    state.app = app
    return state


def send(app, text):
    app.chat_input[0].set_value(text).run()
    return app


def opened(app):
    """The conversation id in the URL (AppTest stores query values as lists)."""
    value = app.query_params.get("c")
    return value[0] if isinstance(value, list) else value


def message_posts(backend):
    return [call for call in backend.calls if call[0] == "POST" and call[1].endswith("/messages")]


def test_greeting_renders_and_is_stored_as_follow_up_history(backend, monkeypatch):
    def forbidden():
        raise AssertionError("Greeting loaded legal resources")
    monkeypatch.setattr(dependencies, "get_answer_service", forbidden)
    backend.app.dependency_overrides.pop(get_chat_service)  # real ChatService, social path only
    app = send(AppTest.from_file(APP).run(), "Chào bạn")
    assert not app.exception and not app.error
    assert "Chào bạn!" in app.chat_message[1].markdown[0].value
    assert not app.chat_message[1].expander
    send(app, "Cảm ơn bạn")
    assert not app.exception and len(app.chat_message) == 4
    conversation = opened(app)
    history = backend.store.history(conversation)
    assert history[0] == {"role": "user", "content": "Chào bạn"}
    assert history[1]["content"].startswith("Chào bạn!")


def test_new_chat_keeps_old_chat_in_sidebar_and_reload_reopens_it(backend):
    app = AppTest.from_file(APP).run()
    assert not app.chat_message and "luật giao thông đường bộ Việt Nam" in app.markdown[0].value
    suggestion = app.button(key="starter-0").label
    app.button(key="starter-0").click().run()
    first = opened(app)
    send(app, "Còn người ngồi sau?")
    assert len(app.chat_message) == 4
    # The follow-up received the first turn from storage.
    assert backend.chat.calls[1]["history"][0] == {"role": "user", "content": suggestion}
    next(b for b in app.sidebar.button if "mới" in b.label).click().run()
    assert not app.chat_message and opened(app) is None
    assert app.button(key=f"open-{first}").label == suggestion  # chat 1 is still listed
    send(app, "Ô tô không thắt dây an toàn phạt bao nhiêu?")
    second = opened(app)
    assert second != first and len(app.chat_message) == 2
    assert backend.chat.calls[2]["history"] == []  # chat 2 starts fresh
    assert [c["id"] for c in backend.store.list()] == [second, first]
    app.button(key=f"open-{first}").click().run()
    assert opened(app) == first and len(app.chat_message) == 4
    # A reload is a fresh session with only the URL: the open chat comes back.
    reloaded = AppTest.from_file(APP)
    reloaded.query_params["c"] = first
    reloaded.run()
    assert not reloaded.exception and len(reloaded.chat_message) == 4
    assert reloaded.chat_message[0].markdown[0].value == suggestion
    assert reloaded.button(key=f"open-{first}").proto.type == "primary"


def test_delete_asks_for_confirmation_then_returns_to_new_chat(backend):
    app = send(AppTest.from_file(APP).run(), "Câu hỏi cần xóa")
    conversation = opened(app)
    app.button(key=f"ask-delete-{conversation}").click().run()
    app.button(key=f"cancel-delete-{conversation}").click().run()
    assert backend.store.get(conversation) is not None and not [
        b for b in app.button if b.key == f"delete-{conversation}"]
    app.button(key=f"ask-delete-{conversation}").click().run()
    app.button(key=f"delete-{conversation}").click().run()
    assert not app.exception and backend.store.get(conversation) is None
    assert opened(app) is None and not app.chat_message
    assert not [b for b in app.sidebar.button if b.key == f"open-{conversation}"]


def test_confirmation_stays_with_its_chat_when_the_list_shifts(backend):
    # Observed with a popover: deleting the top chat left the menu open on
    # the next one. The keyed confirmation must not move to another chat.
    app = send(AppTest.from_file(APP).run(), "Chat cũ")
    older = opened(app)
    next(b for b in app.sidebar.button if "mới" in b.label).click().run()
    send(app, "Chat mới")
    newer = opened(app)
    app.button(key=f"ask-delete-{newer}").click().run()
    app.button(key=f"delete-{newer}").click().run()
    assert [c["id"] for c in backend.store.list()] == [older]
    assert not [b for b in app.button if b.key in {f"delete-{older}", f"cancel-delete-{older}"}]


def test_stale_link_falls_back_to_new_chat(backend):
    app = AppTest.from_file(APP)
    app.query_params["c"] = "deleted-elsewhere"
    app.run()
    assert not app.exception and opened(app) is None
    assert app.button(key="starter-0")


def test_citation_preserves_real_source_lines_and_escapes_markup(backend):
    bundle = json.loads((ROOT / "data/processed/structured-law-v2/chunks.json").read_text())
    unit = next(c for c in bundle["chunks"]
                if "Điều 33." in c["embedding_text"] and "2. Người lái xe" in c["text"]
                and "phải đội mũ bảo hiểm" in c["text"])
    excerpt = unit["embedding_text"]
    assert "\nĐiều 33." in excerpt and "\n2. Người lái xe" in excerpt
    # Include markup to guard against source content being interpreted as HTML.
    excerpt += '\n<script>alert("source")</script> **literal**'
    source = RetrievedChunk(id=unit["id"], text=unit["text"], enriched_text=excerpt,
                            citation="khoản 2 Điều 33", score=1.0)
    citation = EvidenceCitation(chunk_id=source.id, citation=source.citation)
    answer = GroundedAnswer(text="Câu trả lời demo", claims=[
        VerifiedClaim(text="Câu trả lời demo", support_state="positive_support", citations=[citation])])
    backend.chat.results = [legal("answered", "Đã kiểm chứng", answer=answer, chunks=[source])]
    app = send(AppTest.from_file(APP).run(), "Có phải đội mũ bảo hiểm không?")
    assert not app.exception
    rendered = app.chat_message[1].expander[0].markdown[0].value
    assert "white-space: pre-wrap" in rendered
    assert escape(excerpt) in rendered and "<script>" not in rendered


def test_clarification_is_rendered_once_across_follow_up_and_reruns(backend):
    question = "Bạn muốn hỏi về vấn đề giao thông nào?"
    backend.chat.results = [
        legal("needs_clarification", "Cần thêm thông tin", limitations=["Bạn chưa nêu tình huống."],
              follow_up_questions=[question]),
        reply("Mình hỗ trợ các câu hỏi về luật giao thông đường bộ."),
    ]
    app = send(send(AppTest.from_file(APP).run(), "Tôi muốn hỏi"), "tôi cần phải đặt câu hỏi về gì?")
    for _ in range(2):
        assert not app.exception
        assert sum(question in item.value for item in app.markdown) == 1
        assert len(app.chat_message) == 4 and len(message_posts(backend)) == 2
        app.run()


@pytest.mark.parametrize(("status", "label", "alert"), [
    ("needs_clarification", "Cần làm rõ", "info"),
    ("insufficient_evidence", "Chưa đủ căn cứ để trả lời", "warning"),
    ("partial_answer", "Trả lời một phần", "info"),
    ("verification_failed", "Chưa thể xác minh câu trả lời", "warning"),
    ("out_of_scope", "Ngoài phạm vi hỗ trợ", "info"),
])
def test_status_is_visible_and_duplicate_follow_up_is_removed(backend, status, label, alert):
    question = "Bạn đang hỏi về loại xe nào?"
    fields = {"limitations": ["Giới hạn thử nghiệm"], "follow_up_questions": [question, "  " + question, ""]}
    backend.chat.results = [(AnswerResult(status=status, message="Thông tin thử nghiệm", retrieval=None,
                                          evidence_citations=[], verification=CitationVerification(status="not_run"),
                                          **fields) if status == "out_of_scope"
                             else legal(status, "Thông tin thử nghiệm", **fields))]
    app = send(AppTest.from_file(APP).run(), "Câu hỏi")
    assert not app.exception
    assert label in getattr(app.chat_message[1], alert)[0].value
    assert sum(question in m.value for m in app.markdown) == 1
    assert "Giới hạn thử nghiệm" in [m.value for m in app.info]


def test_developer_mode_preserves_chat_and_only_calls_inspection(backend):
    backend.inspection = {"query": "q", "note": "Kiểm tra thử nghiệm", "timings_ms": {"retrieval": 10},
                          "chunks": [], "added_chunk_ids": [], "context_preview": []}
    app = send(AppTest.from_file(APP).run(), "Hội thoại đang có")
    app.toggle[0].set_value(True).run()
    assert not app.chat_input
    next(b for b in app.button if b.label == "Tìm nguồn").click().run()
    inspections = [call for call in backend.calls if call[1].endswith("/retrieve/inspect")]
    assert not app.exception and len(inspections) == 1
    assert "chat_history" not in inspections[0][2] and inspections[0][2]["top_k"] == 10
    app.toggle[0].set_value(False).run()
    assert app.chat_message[0].markdown[0].value == "Hội thoại đang có"
    assert app.chat_input and len(message_posts(backend)) == 1


@pytest.mark.parametrize("failure", ["timeout", "connection"])
def test_unreached_api_unlocks_chat_without_automatic_retry(backend, failure):
    backend.failure = (httpx.ReadTimeout if failure == "timeout" else httpx.ConnectError)("sensitive detail")
    app = send(AppTest.from_file(APP).run(), "Câu hỏi thử nghiệm")
    # The notice is shown once on the run that follows the failed request.
    assert not app.exception and len(message_posts(backend)) == 1
    assert app.warning and "sensitive" not in app.warning[0].value
    app.run()
    assert len(message_posts(backend)) == 1
    assert not app.chat_input[0].disabled and not app.toggle[0].disabled
    assert app.session_state["pending"] is None


def test_server_failure_is_saved_and_shown_after_reload(backend):
    backend.chat.error = PipelineError("generation", "TimeoutError")
    app = send(AppTest.from_file(APP).run(), "Câu hỏi thử nghiệm")
    assert not app.exception and len(app.chat_message) == 2
    assert len(app.chat_message[1].error) == 1 and "TimeoutError" not in app.error[0].value
    reloaded = AppTest.from_file(APP)
    reloaded.query_params["c"] = opened(app)
    reloaded.run()
    assert len(reloaded.chat_message[1].error) == 1
