"""Small Streamlit client for the V2 API; no models or retrieval in the UI."""

import os
from html import escape
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = os.environ.get("ROADLAWQA_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.session_state.setdefault("messages", [])


def submit_query(query: str) -> None:
    """Use one submission path for typed queries and starter questions."""
    query = query.strip()
    if not query or any("pending" in message for message in st.session_state.messages):
        return
    history = [{"role": m["role"], "content": m["content"]}
               for m in st.session_state.messages if "content" in m and not m.get("error")][-10:]
    st.session_state.messages.extend([
        {"role": "user", "content": query},
        {"role": "assistant", "pending": {"current_query": query, "chat_history": history, "top_k": 10}},
    ])


def submit_typed_query() -> None:
    submit_query(st.session_state.get("chat_query", ""))


def reset_chat() -> None:
    st.session_state.messages = []
    st.session_state.developer_inspection = False


st.set_page_config(page_title="RoadLawQA", page_icon="⚖️", layout="centered")
st.title("⚖️ RoadLawQA")
st.caption("Hỏi đáp luật giao thông Việt Nam · Nguồn luật tại ngày 22/09/2026")
busy = any("pending" in message for message in st.session_state.messages)
st.sidebar.button("Cuộc trò chuyện mới", on_click=reset_chat, disabled=busy, use_container_width=True)
with st.sidebar.expander("Dành cho nhà phát triển"):
    inspection_mode = st.toggle("Kiểm tra truy xuất", key="developer_inspection", disabled=busy)
    st.caption("Xem nguồn và thời gian truy xuất. Chế độ này không sinh đáp án hoặc xử lý lịch sử hội thoại.")
if inspection_mode:
    st.subheader("Kiểm tra nguồn trước khi sinh câu trả lời")
    st.caption("Chỉ embedding, hybrid search, rerank và tra nguồn bổ sung; không gọi LLM.")
    with st.form("retrieval_inspection"):
        inspection_query = st.text_area("Câu hỏi độc lập", "Người lái ô tô vượt đèn đỏ bị xử phạt như thế nào?")
        inspection_k = st.slider("Số chunk chính", 1, 20, 10)
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
    follow_ups = []
    for text in result.get("follow_up_questions", []):
        if text.strip() and normalize(text) not in seen:
            follow_ups.append(text)
            seen.add(normalize(text))
    return main, distinct, follow_ups


def show_result(result):
    answer = result.get("answer")
    main, limits, follow_ups = result_sections(result)
    status = result.get("status")
    if status == "needs_clarification":
        st.info("Cần làm rõ")
    elif status == "insufficient_evidence":
        st.warning("Chưa đủ căn cứ để trả lời")
    elif status == "partial_answer":
        st.info("Trả lời một phần — xem giới hạn bên dưới")
    elif status == "verification_failed":
        st.warning("Chưa thể xác minh câu trả lời")
    elif status == "out_of_scope":
        st.info("Ngoài phạm vi hỗ trợ")
    # The API uses plain-text line breaks; Markdown folds a single newline
    # into the claim paragraph. Separate citation lines for display only,
    # leaving the API answer and follow-up history unchanged.
    display = main.replace("\nCăn cứ pháp lý:", "\n\n**Căn cứ pháp lý:**") if answer else main
    st.markdown(display)
    for text in limits:
        st.info(text)
    for text in follow_ups:
        st.markdown(f"**{text}**")
    if answer:
        citations = {c["chunk_id"]: c["citation"]
                     for claim in answer["claims"] for c in claim["citations"]}
        sources = {c["id"]: c for c in result["retrieval"]["chunks"]}
        if citations:
            st.caption("Nguồn luật để đối chiếu")
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


st.markdown(
    "Mình hỗ trợ hỏi đáp **luật giao thông đường bộ Việt Nam** trong phạm vi nguồn đã có, "
    "kèm căn cứ để bạn đối chiếu. Bạn có thể hỏi về quy định hoặc mô tả tình huống cụ thể."
)
# Clear the starter card before a slow request so Streamlit cannot leave its
# old buttons visible as faded elements until the run finishes.
welcome = st.empty()
if not st.session_state.messages:
    with welcome.container(border=True):
        st.markdown("**Bạn muốn tìm hiểu điều gì?**")
        st.caption("Chọn một câu để bắt đầu, hoặc nhập câu hỏi của bạn bên dưới.")
        for index, suggestion in enumerate([
            "Đi xe máy có phải đội mũ bảo hiểm không?",
            "Vượt đèn đỏ bị phạt bao nhiêu?",
            "Được chở mấy người trên xe máy?",
        ]):
            st.button(suggestion, key=f"starter-{index}", on_click=submit_query,
                      args=(suggestion,), use_container_width=True)
        st.caption("Nếu tình huống còn thiếu thông tin hoặc chưa đủ nguồn, mình sẽ nêu rõ giới hạn.")

st.chat_input("Nhập câu hỏi hoặc bổ sung thông tin…", key="chat_query",
              on_submit=submit_typed_query, disabled=busy)

completed_request = False
# New and past turns use the same stable container structure. Replace the
# whole assistant body, including spinner/limitations/follow-ups, atomically.
for index, message in enumerate(st.session_state.messages):
    with st.container(key=f"chat-turn-{index}"):
        with st.chat_message(message["role"]):
            body = st.empty()
            if pending := message.get("pending"):
                try:
                    with body.container():
                        with st.status("Đang xử lý tin nhắn…", expanded=True):
                            st.write("Với câu hỏi pháp luật, mình sẽ tìm nguồn và kiểm tra căn cứ trước khi trả lời.")
                            st.caption("Một số câu hỏi có thể mất vài chục giây. Bạn có thể đọc lại hội thoại trong lúc chờ.")
                            response = httpx.post(f"{API_URL}/api/v1/answer", json=pending, timeout=300)
                            response.raise_for_status()
                            result = response.json()
                    message.update(content=result_content(result), result=result)
                except httpx.TimeoutException:
                    message.update(error=True, content="Phản hồi đang mất nhiều thời gian. Bạn có thể thử gửi lại câu hỏi.")
                except (httpx.HTTPError, ValueError, KeyError):
                    message.update(error=True, content="Chưa nhận được phản hồi từ hệ thống. Bạn hãy thử gửi lại câu hỏi.")
                message.pop("pending", None)
                completed_request = True
                body.empty()
            with body.container():
                if message.get("error"):
                    st.error(message["content"])
                elif "result" in message:
                    show_result(message["result"])
                else:
                    st.markdown(message["content"])

# Re-enable controls after resolving the pending turn. The completed result is
# already in history, so this rerun renders it without repeating the API call.
if completed_request:
    st.rerun()
