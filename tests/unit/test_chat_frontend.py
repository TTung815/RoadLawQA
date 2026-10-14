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
    assert not app.expander
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
    rendered = app.expander[0].markdown[0].value
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
