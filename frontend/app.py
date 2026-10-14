"""Small Streamlit client for the V2 API; no models or retrieval in the UI."""

import os
from html import escape
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = os.environ.get("ROADLAWQA_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="RoadLawQA", page_icon="⚖️", layout="centered")
st.title("⚖️ RoadLawQA")
st.caption("Hỏi đáp luật giao thông Việt Nam · Nguồn luật tại ngày 22/09/2026")
mode = st.sidebar.radio("Chế độ", ["Hỏi đáp", "Kiểm tra truy xuất"])
if mode == "Kiểm tra truy xuất":
    st.subheader("Kiểm tra nguồn trước khi sinh câu trả lời")
    st.caption("Chỉ embedding, hybrid search, rerank và tra nguồn bổ sung; không gọi LLM.")
    with st.form("retrieval_inspection"):
        inspection_query = st.text_area("Câu hỏi độc lập", "Người lái ô tô vượt đèn đỏ bị xử phạt như thế nào?")
        inspection_k = st.slider("Số chunk chính", 1, 10, 5)
        submitted = st.form_submit_button("Tìm nguồn")
    if submitted and inspection_query.strip():
        try:
            with st.spinner("Đang truy xuất; lần đầu cần tải model và kiểm tra index…"):
                response = httpx.post(f"{API_URL}/api/v1/retrieve/inspect", json={
                    "current_query": inspection_query, "top_k": inspection_k,
                }, timeout=300)
                response.raise_for_status()
                st.session_state.inspection = response.json()
        except (httpx.HTTPError, ValueError):
            st.session_state.pop("inspection", None)
            st.error("Chưa truy xuất được. Kiểm tra API và index đã được xây.")
    if result := st.session_state.get("inspection"):
        st.markdown(f"**Câu hỏi đã truy xuất:** {result['query']}")
        st.write(result["note"])
        if devices := result.get("devices"):
            st.caption("Thiết bị thực tế · " + " · ".join(
                f"{name}: {device}" for name, device in devices.items()))
        st.table([{"Bước": stage, "Thời gian (giây)": round(ms / 1000, 3)}
                  for stage, ms in result["timings_ms"].items()])
        for i, chunk in enumerate(result["chunks"], 1):
            added = chunk["id"] in result["added_chunk_ids"]
            with st.expander(f"{i}. {'Bổ sung' if added else 'Truy xuất'} — {chunk['citation']}", expanded=i == 1):
                if not added:
                    st.write({"reranker_score": chunk["score"], "hybrid_score": chunk["metadata"].get("hybrid_score")})
                st.text(chunk["enriched_text"])
                st.json(chunk["metadata"], expanded=False)
        with st.expander("Context sau khi gộp ngữ cảnh cha"):
            st.json(result["context_preview"])
    st.stop()
st.session_state.setdefault("messages", [])
if st.sidebar.button("Cuộc trò chuyện mới"):
    st.session_state.messages = []
    st.rerun()


def result_sections(result):
    """Keep all distinct content, without repeating abstention reasons as alerts."""
    answer = result.get("answer") or {}
    main = answer.get("text") or result["message"]
    normalize = lambda value: " ".join(value.split())
    limits = result.get("limitations", [])
    if normalize(main) == normalize(" ".join(limits)):
        limits = []
    seen = {normalize(main)}
    distinct = []
    for text in limits:
        if normalize(text) not in seen:
            distinct.append(text)
            seen.add(normalize(text))
    return main, distinct, result.get("follow_up_questions", [])


def show_result(result):
    answer = result.get("answer")
    main, limits, follow_ups = result_sections(result)
    st.markdown(main)
    for text in limits:
        st.info(text)
    for text in follow_ups:
        st.markdown(f"**Cần làm rõ:** {text}")
    if answer:
        citations = {c["chunk_id"]: c["citation"]
                     for claim in answer["claims"] for c in claim["citations"]}
        sources = {c["id"]: c for c in result["retrieval"]["chunks"]}
        for identity, label in citations.items():
            with st.expander(label):
                source = sources.get(identity, {})
                excerpt = source.get("enriched_text") or source.get("text", "")
                # Keep the source's own line breaks and numbering; escape all
                # content so neither Markdown nor HTML can reinterpret the law.
                st.markdown(
                    '<div style="white-space: pre-wrap; overflow-wrap: anywhere; '
                    'line-height: 1.7">' + escape(excerpt) + '</div>',
                    unsafe_allow_html=True,
                )


def result_content(result):
    main, limits, follow_ups = result_sections(result)
    return "\n".join([main, *limits, *follow_ups])


if query := st.chat_input("Nhập câu hỏi về luật giao thông…"):
    history = [{"role": m["role"], "content": m["content"]}
               for m in st.session_state.messages if "content" in m and not m.get("error")][-10:]
    st.session_state.messages.extend([
        {"role": "user", "content": query},
        {"role": "assistant", "pending": {"current_query": query, "chat_history": history, "top_k": 5}},
    ])

# New and past turns use the same stable container structure. Replace the
# whole assistant body, including spinner/limitations/follow-ups, atomically.
for index, message in enumerate(st.session_state.messages):
    with st.container(key=f"chat-turn-{index}"):
        with st.chat_message(message["role"]):
            body = st.empty()
            if pending := message.pop("pending", None):
                try:
                    with body.container():
                        with st.spinner("Đang xử lý tin nhắn…"):
                            response = httpx.post(f"{API_URL}/api/v1/answer", json=pending, timeout=300)
                            response.raise_for_status()
                            result = response.json()
                    message.update(content=result_content(result), result=result)
                except (httpx.HTTPError, ValueError, KeyError):
                    message.update(error=True, content="Chưa nhận được câu trả lời. Kiểm tra API đang chạy và thử lại.")
                body.empty()
            with body.container():
                if message.get("error"):
                    st.error(message["content"])
                elif "result" in message:
                    show_result(message["result"])
                else:
                    st.markdown(message["content"])
