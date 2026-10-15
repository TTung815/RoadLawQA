"""Rendering: page style, conversation sidebar, chat turns and the retrieval inspector."""

from html import escape

import httpx
import streamlit as st

from frontend import client, state

STARTER_QUESTIONS = [
    "Đi xe máy có phải đội mũ bảo hiểm không?",
    "Vượt đèn đỏ bị phạt bao nhiêu?",
    "Được chở mấy người trên xe máy?",
]
STATUS_BANNERS = {
    "needs_clarification": (st.info, "Cần làm rõ"),
    "insufficient_evidence": (st.warning, "Chưa đủ căn cứ để trả lời"),
    "partial_answer": (st.info, "Trả lời một phần — xem giới hạn bên dưới"),
    "verification_failed": (st.warning, "Chưa thể xác minh câu trả lời"),
    "out_of_scope": (st.info, "Ngoài phạm vi hỗ trợ"),
}
# Conversation list like other chat apps: one line per chat, left-aligned and
# truncated with an ellipsis (full title on hover); the open chat is a subtle
# highlight; the delete icon stays faint until its row is hovered.
SIDEBAR_CSS = """<style>
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
</style>"""


def header() -> None:
    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    st.title("⚖️ RoadLawQA")
    st.caption("Hỏi đáp luật giao thông Việt Nam · Nguồn luật tại ngày 22/09/2026")


def sidebar() -> bool:
    """Render the conversation list; returns whether developer inspection is on."""
    busy = state.busy()
    st.sidebar.button("＋ Cuộc trò chuyện mới", on_click=state.new_chat, disabled=busy, use_container_width=True)
    conversations = client.list_conversations()
    if conversations is None or conversations is client.MISSING:
        st.sidebar.caption("Chưa kết nối được API để tải lịch sử trò chuyện.")
    elif conversations:
        st.sidebar.caption("Gần đây")
        for conversation in conversations:
            conversation_item(conversation, busy)
    with st.sidebar.expander("Dành cho nhà phát triển"):
        enabled = st.toggle("Kiểm tra truy xuất", key="developer_inspection", disabled=busy)
        st.caption("Xem nguồn và thời gian truy xuất. Chế độ này không sinh đáp án hoặc xử lý lịch sử hội thoại.")
    return enabled


def conversation_item(conversation: dict, busy: bool) -> None:
    identity = conversation["id"]
    with st.sidebar.container(key=f"conversation-{identity}"):
        name, menu = st.columns([7, 1], vertical_alignment="center")
        name.button(conversation["title"], key=f"open-{identity}", on_click=state.open_conversation,
                    args=(identity,), disabled=busy, use_container_width=True, help=conversation["title"],
                    type="primary" if identity == state.current_conversation() else "secondary")
        # Keyed confirmation: unlike a popover, its open state follows the
        # conversation id, not its position, when the list changes.
        menu.button("", icon=":material/delete:", key=f"ask-delete-{identity}", on_click=state.ask_delete,
                    args=(identity,), disabled=busy, help="Xóa cuộc trò chuyện")
        if st.session_state.get("confirm_delete") == identity:
            st.caption("Xóa cuộc trò chuyện này?")
            confirm, cancel = st.columns(2)
            confirm.button("Xóa", key=f"delete-{identity}", type="primary", on_click=state.delete_conversation,
                           args=(identity,), use_container_width=True)
            cancel.button("Hủy", key=f"cancel-delete-{identity}", on_click=state.cancel_delete,
                          use_container_width=True)


def retrieval_inspector() -> None:
    st.subheader("Kiểm tra nguồn trước khi sinh câu trả lời")
    st.caption("Chỉ embedding, hybrid search, rerank và tra nguồn bổ sung; không gọi LLM.")
    with st.form("retrieval_inspection"):
        query = st.text_area("Câu hỏi độc lập", "Người lái ô tô vượt đèn đỏ bị xử phạt như thế nào?")
        top_k = st.slider("Số chunk chính", 1, 20, 10)
        submitted = st.form_submit_button("Tìm nguồn")
    if submitted and query.strip():
        try:
            with st.spinner("Đang truy xuất; lần đầu cần tải model và kiểm tra index…"):
                st.session_state.inspection = client.inspect_retrieval(query, top_k)
        except (httpx.HTTPError, ValueError):
            st.session_state.pop("inspection", None)
            st.error("Chưa truy xuất được. Kiểm tra API và index đã được xây.")
    if result := st.session_state.get("inspection"):
        st.markdown(f"**Câu hỏi đã truy xuất:** {result['query']}")
        st.write(result["note"])
        if devices := result.get("devices"):
            st.caption("Thiết bị thực tế · " + " · ".join(f"{name}: {device}" for name, device in devices.items()))
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


def introduction() -> None:
    st.markdown(
        "Mình hỗ trợ hỏi đáp **luật giao thông đường bộ Việt Nam** trong phạm vi nguồn đã có, "
        "kèm căn cứ để bạn đối chiếu. Bạn có thể hỏi về quy định hoặc mô tả tình huống cụ thể."
    )
    if notice := st.session_state.pop("flash", None):
        st.warning(notice)


def open_conversation_messages() -> list[dict]:
    """Messages of the chat in the URL; a deleted or stale link falls back to a new chat."""
    conversation_id = state.current_conversation()
    if conversation_id is None:
        return []
    detail = client.get_conversation(conversation_id)
    if detail is client.MISSING and not state.busy():
        state.forget_conversation()
        return []
    if detail is None:
        st.error("Chưa tải được cuộc trò chuyện từ API. Kiểm tra backend rồi tải lại trang.")
        return []
    return detail.get("messages", []) if isinstance(detail, dict) else []


def starter_card(container) -> None:
    with container.container(border=True):
        st.markdown("**Bạn muốn tìm hiểu điều gì?**")
        st.caption("Chọn một câu để bắt đầu, hoặc nhập câu hỏi của bạn bên dưới.")
        for index, suggestion in enumerate(STARTER_QUESTIONS):
            st.button(suggestion, key=f"starter-{index}", on_click=state.submit_query,
                      args=(suggestion,), use_container_width=True)
        st.caption("Nếu tình huống còn thiếu thông tin hoặc chưa đủ nguồn, mình sẽ nêu rõ giới hạn.")


def chat_turn(message: dict) -> None:
    with st.container(key=f"message-{message['id']}"):
        with st.chat_message(message["role"]):
            if message.get("error"):
                st.error(message["content"])
            elif message["role"] == "assistant" and message.get("result"):
                answer_result(message["result"])
            else:
                st.markdown(message["content"])


def pending_turn(content: str) -> None:
    """Show the question and a status while the API answers it."""
    with st.chat_message("user"):
        st.markdown(content)
    with st.chat_message("assistant"):
        with st.status("Đang xử lý tin nhắn…", expanded=True):
            st.write("Với câu hỏi pháp luật, mình sẽ tìm nguồn và kiểm tra căn cứ trước khi trả lời.")
            st.caption("Một số câu hỏi có thể mất vài chục giây. Bạn có thể đọc lại hội thoại trong lúc chờ.")
            state.send_pending()


def result_sections(result: dict) -> tuple[str, list[str], list[str]]:
    """Keep all distinct content, without repeating abstention reasons as alerts."""
    answer = result.get("answer") or {}
    main = answer.get("text") or result["message"]
    normalize = lambda value: " ".join(value.split())
    limits = result.get("limitations", [])
    if normalize(main) == normalize(" ".join(limits)):
        limits = []
    seen = {normalize(main)}
    distinct, follow_ups = [], []
    for text in limits:
        if normalize(text) not in seen:
            distinct.append(text)
            seen.add(normalize(text))
    for text in result.get("follow_up_questions", []):
        if text.strip() and normalize(text) not in seen:
            follow_ups.append(text)
            seen.add(normalize(text))
    return main, distinct, follow_ups


def answer_result(result: dict) -> None:
    answer = result.get("answer")
    main, limits, follow_ups = result_sections(result)
    if banner := STATUS_BANNERS.get(result.get("status")):
        show, text = banner
        show(text)
    # The API uses plain-text line breaks; Markdown folds a single newline
    # into the claim paragraph. Separate citation lines for display only,
    # leaving the API answer and follow-up history unchanged.
    st.markdown(main.replace("\nCăn cứ pháp lý:", "\n\n**Căn cứ pháp lý:**") if answer else main)
    for text in limits:
        st.info(text)
    for text in follow_ups:
        st.markdown(f"**{text}**")
    if answer:
        citations(answer, result["retrieval"]["chunks"])


def citations(answer: dict, chunks: list[dict]) -> None:
    labels = {c["chunk_id"]: c["citation"] for claim in answer["claims"] for c in claim["citations"]}
    sources = {c["id"]: c for c in chunks}
    if labels:
        st.caption("Nguồn luật để đối chiếu")
    for identity, label in labels.items():
        with st.expander(label):
            source = sources.get(identity, {})
            excerpt = source.get("enriched_text") or source.get("text", "")
            # Keep the source's own line breaks and numbering; escape all
            # content so neither Markdown nor HTML can reinterpret the law.
            st.markdown('<div style="white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7">'
                        + escape(excerpt) + '</div>', unsafe_allow_html=True)
