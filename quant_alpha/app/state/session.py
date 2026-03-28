"""Session state helpers."""
from __future__ import annotations

import streamlit as st


def init_session() -> None:
    if "last_action" not in st.session_state:
        st.session_state["last_action"] = "系统已初始化"
