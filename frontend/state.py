"""UI state: the open conversation (in the URL), the pending message and callbacks."""

import httpx
import streamlit as st

from frontend import client


def init() -> None:
    st.session_state.setdefault("pending", None)


def busy() -> bool:
    return st.session_state.pending is not None


def current_conversation() -> str | None:
    """The open conversation lives in the URL (?c=...), so a reload keeps it."""
    return st.query_params.get("c")


def forget_conversation() -> None:
    st.query_params.pop("c", None)


def flash(message: str) -> None:
    """Show a notice once, on the next run."""
    st.session_state.flash = message


def open_conversation(conversation_id: str) -> None:
    st.query_params["c"] = conversation_id
    st.session_state.developer_inspection = False


def new_chat() -> None:
    # Nothing is created until the first message, so no empty chats pile up.
    forget_conversation()
    st.session_state.developer_inspection = False


def ask_delete(conversation_id: str) -> None:
    st.session_state.confirm_delete = conversation_id


def cancel_delete() -> None:
    st.session_state.confirm_delete = None


def delete_conversation(conversation_id: str) -> None:
    st.session_state.confirm_delete = None
    try:
        client.delete_conversation(conversation_id)
    except httpx.HTTPError:
        flash("Chưa xóa được cuộc trò chuyện. Bạn hãy thử lại.")
        return
    if current_conversation() == conversation_id:
        forget_conversation()


def submit_query(query: str) -> None:
    """One submission path for typed queries and starter questions."""
    query = query.strip()
    if not query or busy():
        return
    conversation_id = current_conversation()
    if conversation_id is None:
        try:
            conversation_id = client.create_conversation()
        except (httpx.HTTPError, ValueError, KeyError):
            flash("Chưa kết nối được API. Kiểm tra backend đang chạy rồi thử lại.")
            return
        st.query_params["c"] = conversation_id
    st.session_state.pending = {"conversation_id": conversation_id, "content": query}


def submit_typed_query() -> None:
    submit_query(st.session_state.get("chat_query", ""))


def send_pending() -> None:
    """Send the pending message; the next run re-renders the saved turns."""
    pending = st.session_state.pending
    try:
        client.send_message(pending["conversation_id"], pending["content"])
    except httpx.HTTPStatusError:
        pass  # The API was reached and stored the failed turn itself.
    except httpx.TimeoutException:
        flash("Phản hồi đang mất nhiều thời gian. Câu trả lời sẽ hiện trong "
              "cuộc trò chuyện khi hoàn tất; bạn có thể tải lại sau ít phút.")
    except httpx.HTTPError:
        flash("Chưa nhận được phản hồi từ hệ thống. Bạn hãy thử gửi lại câu hỏi.")
    st.session_state.pending = None
