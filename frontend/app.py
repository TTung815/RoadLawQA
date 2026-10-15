"""Streamlit chat client for the V2 API; conversations are stored by the API, not the UI."""

import os
from html import escape
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = os.environ.get("ROADLAWQA_API_URL", "http://127.0.0.1:8000").rstrip("/")
CONVERSATIONS = f"{API_URL}/api/v1/conversations"

st.session_state.setdefault("pending", None)


def current_conversation() -> str | None:
    """The open conversation lives in the URL (?c=...), so a reload keeps it."""
    return st.query_params.get("c")


def open_conversation(conversation_id: str) -> None:
    st.query_params["c"] = conversation_id
    st.session_state.developer_inspection = False


def new_chat() -> None:
    # Nothing is created until the first message, so no empty chats pile up.
    st.query_params.pop("c", None)
    st.session_state.developer_inspection = False


def ask_delete(conversation_id: str) -> None:
    st.session_state.confirm_delete = conversation_id


def cancel_delete() -> None:
    st.session_state.confirm_delete = None


def delete_conversation(conversation_id: str) -> None:
    st.session_state.confirm_delete = None
    try:
        httpx.delete(f"{CONVERSATIONS}/{conversation_id}", timeout=30).raise_for_status()
    except httpx.HTTPError:
        st.session_state.flash = "Chưa xóa được cuộc trò chuyện. Bạn hãy thử lại."
        return
    if current_conversation() == conversation_id:
        st.query_params.pop("c", None)


def submit_query(query: str) -> None:
    """Use one submission path for typed queries and starter questions."""
    query = query.strip()
    if not query or st.session_state.pending:
        return
    conversation_id = current_conversation()
    if conversation_id is None:
        try:
            response = httpx.post(CONVERSATIONS, timeout=30)
            response.raise_for_status()
            conversation_id = response.json()["id"]
        except (httpx.HTTPError, ValueError, KeyError):
            st.session_state.flash = "Chưa kết nối được API. Kiểm tra backend đang chạy rồi thử lại."
            return
        st.query_params["c"] = conversation_id
    st.session_state.pending = {"conversation_id": conversation_id, "content": query}


def submit_typed_query() -> None:
    submit_query(st.session_state.get("chat_query", ""))


MISSING = object()


def fetch(url: str):
    """GET JSON from the API: MISSING for 404, None when the API is unreachable."""
    try:
        response = httpx.get(url, timeout=30)
        if response.status_code == 404:
            return MISSING
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


st.set_page_config(page_title="RoadLawQA", page_icon="⚖️", layout="centered")
# Conversation list like other chat apps: one line per chat, left-aligned and
# truncated with an ellipsis (full title on hover); the open chat is a subtle
# highlight; the delete icon stays faint until its row is hovered.
st.markdown("""<style>
[class*="st-key-conversation-"] [data-testid="stHorizontalBlock"] { gap: 0.25rem; }
[class*="st-key-open-"] button {
    justify-content: flex-start; min-height: 2.25rem; padding: 0.25rem 0.6rem;
    border: none; background: transparent; box-shadow: none;
}
[class*="st-key-open-"] button > div { min-width: 0; width: 100%; }
[class*="st-key-open-"] button p {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left; font-size: 0.95rem;
}
[class*="st-key-open-"] button:hover { background: rgba(49, 51, 63, 0.08); color: inherit; }
[class*="st-key-open-"] button[kind="primary"] { background: rgba(49, 51, 63, 0.12); color: inherit; font-weight: 600; }
[class*="st-key-ask-delete-"] button {
    border: none; background: transparent; min-height: 2.25rem; padding: 0.25rem; opacity: 0.25;
}
[class*="st-key-conversation-"]:hover [class*="st-key-ask-delete-"] button { opacity: 0.8; }
</style>""", unsafe_allow_html=True)
st.title("⚖️ RoadLawQA")
st.caption("Hỏi đáp luật giao thông Việt Nam · Nguồn luật tại ngày 22/09/2026")
busy = st.session_state.pending is not None
st.sidebar.button("＋ Cuộc trò chuyện mới", on_click=new_chat, disabled=busy, use_container_width=True)
conversations = fetch(CONVERSATIONS)
if conversations is None or conversations is MISSING:
    st.sidebar.caption("Chưa kết nối được API để tải lịch sử trò chuyện.")
elif conversations:
    st.sidebar.caption("Gần đây")
    for conversation in conversations:
        with st.sidebar.container(key=f"conversation-{conversation['id']}"):
            name, menu = st.columns([7, 1], vertical_alignment="center")
            name.button(conversation["title"], key=f"open-{conversation['id']}", on_click=open_conversation,
                        args=(conversation["id"],), disabled=busy, use_container_width=True,
                        help=conversation["title"],
                        type="primary" if conversation["id"] == current_conversation() else "secondary")
            # Keyed confirmation: unlike a popover, its open state follows the
            # conversation id, not its position, when the list changes.
            menu.button("🗑", key=f"ask-delete-{conversation['id']}", on_click=ask_delete,
                        args=(conversation["id"],), disabled=busy, help="Xóa cuộc trò chuyện")
            if st.session_state.get("confirm_delete") == conversation["id"]:
                st.caption("Xóa cuộc trò chuyện này?")
                confirm, cancel = st.columns(2)
                confirm.button("Xóa", key=f"delete-{conversation['id']}", type="primary",
                               on_click=delete_conversation, args=(conversation["id"],), use_container_width=True)
                cancel.button("Hủy", key=f"cancel-delete-{conversation['id']}", on_click=cancel_delete,
                              use_container_width=True)
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


st.markdown(
    "Mình hỗ trợ hỏi đáp **luật giao thông đường bộ Việt Nam** trong phạm vi nguồn đã có, "
    "kèm căn cứ để bạn đối chiếu. Bạn có thể hỏi về quy định hoặc mô tả tình huống cụ thể."
)
if flash := st.session_state.pop("flash", None):
    st.warning(flash)

conversation_id = current_conversation()
detail = fetch(f"{CONVERSATIONS}/{conversation_id}") if conversation_id else None
if detail is MISSING and not busy:
    # Deleted elsewhere or a stale link: fall back to a new chat.
    st.query_params.pop("c", None)
    conversation_id, detail = None, None
elif conversation_id and detail is None:
    st.error("Chưa tải được cuộc trò chuyện từ API. Kiểm tra backend rồi tải lại trang.")
messages = detail.get("messages", []) if isinstance(detail, dict) else []
pending = st.session_state.pending

# Clear the starter card before a slow request so Streamlit cannot leave its
# old buttons visible as faded elements until the run finishes.
welcome = st.empty()
if not messages and not pending:
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

for message in messages:
    with st.container(key=f"message-{message['id']}"):
        with st.chat_message(message["role"]):
            if message.get("error"):
                st.error(message["content"])
            elif message["role"] == "assistant" and message.get("result"):
                show_result(message["result"])
            else:
                st.markdown(message["content"])

if pending:
    welcome.empty()
    with st.chat_message("user"):
        st.markdown(pending["content"])
    with st.chat_message("assistant"):
        with st.status("Đang xử lý tin nhắn…", expanded=True):
            st.write("Với câu hỏi pháp luật, mình sẽ tìm nguồn và kiểm tra căn cứ trước khi trả lời.")
            st.caption("Một số câu hỏi có thể mất vài chục giây. Bạn có thể đọc lại hội thoại trong lúc chờ.")
            try:
                # The API reads earlier turns from storage and saves both new turns.
                httpx.post(f"{CONVERSATIONS}/{pending['conversation_id']}/messages",
                           json={"content": pending["content"], "top_k": 10}, timeout=300).raise_for_status()
            except httpx.HTTPStatusError:
                # The API was reached and stored the failed turn itself.
                pass
            except httpx.TimeoutException:
                st.session_state.flash = ("Phản hồi đang mất nhiều thời gian. Câu trả lời sẽ hiện trong "
                                          "cuộc trò chuyện khi hoàn tất; bạn có thể tải lại sau ít phút.")
            except httpx.HTTPError:
                st.session_state.flash = "Chưa nhận được phản hồi từ hệ thống. Bạn hãy thử gửi lại câu hỏi."
    st.session_state.pending = None
    # Re-render from storage: saved turns, sidebar order and enabled controls.
    st.rerun()
