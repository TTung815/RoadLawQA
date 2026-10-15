"""Streamlit chat client for the RoadLawQA API; conversations are stored by the API.

Layout only: HTTP calls live in client.py, UI state and callbacks in state.py,
rendering in views.py.
"""

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # `streamlit run frontend/app.py` puts only frontend/ on the path.
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from frontend import state, views  # noqa: E402

state.init()
st.set_page_config(page_title="RoadLawQA", page_icon="⚖️", layout="centered")
views.header()
if views.sidebar():
    views.retrieval_inspector()
    st.stop()

views.introduction()
messages = views.open_conversation_messages()
pending = st.session_state.pending
# Clear the starter card before a slow request so Streamlit cannot leave its
# old buttons visible as faded elements until the run finishes.
welcome = st.empty()
if not messages and not pending:
    views.starter_card(welcome)
st.chat_input("Nhập câu hỏi hoặc bổ sung thông tin…", key="chat_query",
              on_submit=state.submit_typed_query, disabled=state.busy())
for message in messages:
    views.chat_turn(message)
if pending:
    welcome.empty()
    views.pending_turn(pending["content"])
    # Re-render from storage: saved turns, sidebar order and enabled controls.
    st.rerun()
