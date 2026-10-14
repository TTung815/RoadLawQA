"""Exercise the chat client with API responses, without live models or network."""

import json
from html import escape
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend.dependencies import answer as dependencies
from backend.main import create_app


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_frontend_environment(monkeypatch):
    # AppTest runs in this process: never import the owner's .env into tests.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("ROADLAWQA_API_URL", "http://test")


def test_greeting_renders_and_remains_in_follow_up_history(monkeypatch):
    def forbidden():
        raise AssertionError("Greeting loaded legal resources")
    monkeypatch.setattr(dependencies, "get_answer_service", forbidden)
    client = TestClient(create_app())
    requests = []

    def post(url, *, json, timeout):
        requests.append(json)
        return client.post("/api/v1/answer", json=json)

    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py")).run()
    app.chat_input[0].set_value("Chào bạn").run()
    assert not app.exception and not app.error
    assert "Chào bạn!" in app.chat_message[1].markdown[0].value
    assert not app.chat_message[1].expander
    app.chat_input[0].set_value("Cảm ơn bạn").run()
    assert not app.exception and not app.error
    assert requests[1]["chat_history"][0] == {"role": "user", "content": "Chào bạn"}
    assert requests[1]["chat_history"][1]["content"].startswith("Chào bạn!")
    assert len(app.chat_message) == 4


def test_citation_preserves_real_source_lines_and_escapes_markup():
    bundle = json.loads((ROOT / "data/processed/structured-law-v2/chunks.json").read_text())
    source = next(c for c in bundle["chunks"]
                  if "Điều 33." in c["embedding_text"] and "2. Người lái xe" in c["text"]
                  and "phải đội mũ bảo hiểm" in c["text"])
    excerpt = source["embedding_text"]
    assert "\nĐiều 33." in excerpt and "\n2. Người lái xe" in excerpt
    # Include markup to guard against source content being interpreted as HTML.
    excerpt += '\n<script>alert("source")</script> **literal**'
    result = {
        "message": "Đã kiểm chứng", "answer": {"text": "Câu trả lời demo", "claims": [
            {"citations": [{"chunk_id": source["id"], "citation": "khoản 2 Điều 33"}]}]},
        "retrieval": {"chunks": [{"id": source["id"], "enriched_text": excerpt}]},
    }
    app = AppTest.from_file(str(ROOT / "frontend/app.py"))
    app.session_state["messages"] = [{"role": "assistant", "content": "Demo", "result": result}]
    app.run()
    assert not app.exception
    rendered = app.chat_message[0].expander[0].markdown[0].value
    assert "white-space: pre-wrap" in rendered
    assert escape(excerpt) in rendered and "<script>" not in rendered


def test_clarification_is_rendered_once_across_follow_up_and_reruns(monkeypatch):
    question = "Bạn muốn hỏi về vấn đề giao thông nào?"
    initial = {"message": "Cần thêm thông tin", "answer": None,
               "limitations": ["Bạn chưa nêu tình huống."], "follow_up_questions": [question]}
    reply = {"message": "Mình hỗ trợ các câu hỏi về luật giao thông đường bộ.", "answer": None}
    requests = []
    def post(url, *, json, timeout):
        requests.append(json)
        return httpx.Response(200, json=reply, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py"))
    app.session_state["messages"] = [
        {"role": "user", "content": "Tôi muốn hỏi"},
        {"role": "assistant", "content": question, "result": initial},
    ]
    app.run()
    app.chat_input[0].set_value("tôi cần phải đặt câu hỏi về gì?").run()
    for _ in range(2):
        assert not app.exception
        assert sum(question in item.value for item in app.markdown) == 1
        assert len(app.chat_message) == 4
        assert len(requests) == 1
        app.run()


@pytest.mark.parametrize("limits", [["Chưa tìm được nguồn phù hợp."],
                                     ["Thiếu nguồn về tiền phạt.", "Thiếu nguồn về thời hạn."]])
def test_abstention_reason_is_not_duplicated_in_alert_or_history(monkeypatch, limits):
    result = {"status": "insufficient_evidence", "message": " ".join(limits),
              "answer": None, "limitations": limits}
    def post(url, *, json, timeout):
        return httpx.Response(200, json=result, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py")).run()
    app.chat_input[0].set_value("Tình huống cần tra cứu").run()
    assert not app.exception and not app.info
    assert app.chat_message[1].markdown[0].value == result["message"]
    assert app.session_state["messages"][1]["content"] == result["message"]


def test_starter_questions_and_new_chat_use_the_same_submission_flow(monkeypatch):
    requests = []
    def post(url, *, json, timeout):
        requests.append(json)
        return httpx.Response(200, json={"message": "Phản hồi thử nghiệm", "answer": None},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py")).run()
    assert not requests and not app.chat_message
    assert "luật giao thông đường bộ Việt Nam" in app.markdown[0].value
    assert app.sidebar.expander[0].label == "Dành cho nhà phát triển"
    assert not app.sidebar.expander[0].proto.expanded
    assert not app.toggle[0].value
    suggestion = app.button(key="starter-0").label
    app.button(key="starter-0").click().run()
    app.run()
    assert not app.exception and len(requests) == 1
    assert requests[0] == {"current_query": suggestion, "chat_history": [], "top_k": 10}
    assert len(app.chat_message) == 2
    assert not app.chat_input[0].disabled
    app.chat_input[0].set_value("Còn người ngồi sau?").run()
    assert requests[1]["chat_history"] == [
        {"role": "user", "content": suggestion},
        {"role": "assistant", "content": "Phản hồi thử nghiệm"},
    ]
    app.sidebar.button[0].click().run()
    assert not app.chat_message and not app.session_state["messages"]
    assert app.button(key="starter-0").label == suggestion
    assert len(requests) == 2


def test_developer_mode_preserves_chat_and_only_calls_inspection(monkeypatch):
    requests = []
    def post(url, *, json, timeout):
        requests.append((url, json))
        return httpx.Response(200, json={
            "query": json["current_query"], "note": "Kiểm tra thử nghiệm",
            "timings_ms": {"retrieval": 10}, "chunks": [], "added_chunk_ids": [],
            "context_preview": [],
        }, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py"))
    app.session_state["messages"] = [{"role": "user", "content": "Hội thoại đang có"}]
    app.run()
    app.toggle[0].set_value(True).run()
    assert not app.chat_input and not requests
    next(b for b in app.button if b.label == "Tìm nguồn").click().run()
    assert not app.exception and len(requests) == 1
    assert requests[0][0].endswith("/retrieve/inspect")
    assert "chat_history" not in requests[0][1]
    assert requests[0][1]["top_k"] == 10
    app.toggle[0].set_value(False).run()
    assert app.chat_message[0].markdown[0].value == "Hội thoại đang có"
    assert app.chat_input and len(requests) == 1


@pytest.mark.parametrize(("status", "label", "alert"), [
    ("needs_clarification", "Cần làm rõ", "info"),
    ("insufficient_evidence", "Chưa đủ căn cứ để trả lời", "warning"),
    ("partial_answer", "Trả lời một phần", "info"),
    ("verification_failed", "Chưa thể xác minh câu trả lời", "warning"),
    ("out_of_scope", "Ngoài phạm vi hỗ trợ", "info"),
])
def test_status_is_visible_and_duplicate_follow_up_is_removed(status, label, alert):
    question = "Bạn đang hỏi về loại xe nào?"
    result = {"status": status, "message": "Thông tin thử nghiệm", "answer": None,
              "limitations": ["Giới hạn thử nghiệm"],
              "follow_up_questions": [question, "  " + question, ""]}
    app = AppTest.from_file(str(ROOT / "frontend/app.py"))
    app.session_state["messages"] = [{"role": "assistant", "content": "Demo", "result": result}]
    app.run()
    assert not app.exception
    assert label in getattr(app.chat_message[0], alert)[0].value
    assert sum(question in m.value for m in app.markdown) == 1
    assert "Giới hạn thử nghiệm" in [m.value for m in app.info]


@pytest.mark.parametrize("failure", ["timeout", "connection", "invalid_json"])
def test_request_failure_unlocks_chat_without_automatic_retry(monkeypatch, failure):
    requests = []
    def post(url, *, json, timeout):
        requests.append(json)
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive detail")
        if failure == "connection":
            raise httpx.ConnectError("sensitive detail")
        return httpx.Response(200, text="invalid", request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    app = AppTest.from_file(str(ROOT / "frontend/app.py")).run()
    app.chat_input[0].set_value("Câu hỏi thử nghiệm").run()
    app.run()
    assert not app.exception and len(requests) == 1
    assert len(app.chat_message[1].error) == 1
    assert "sensitive" not in app.error[0].value
    assert not app.chat_input[0].disabled and not app.toggle[0].disabled
    assert not app.sidebar.button[0].disabled
    assert all("pending" not in m for m in app.session_state["messages"])
