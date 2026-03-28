"""Streamlit entrypoint."""
from __future__ import annotations

import streamlit as st

from app.state.session import init_session
from app.services.orchestrator import Orchestrator

st.set_page_config(page_title="Quant Alpha", layout="wide")
init_session()

st.title("Quant Alpha A/H 指数增强荐股系统")
st.caption("Phase 1: 可运行基础版")

orch = Orchestrator()

col1, col2, col3, col4 = st.columns(4)
if col1.button("更新数据"):
    st.session_state["last_action"] = orch.update_data()
if col2.button("训练模型"):
    st.session_state["last_action"] = orch.train_model()
if col3.button("运行预测"):
    st.session_state["last_action"] = orch.run_predict()
if col4.button("运行回测"):
    st.session_state["last_action"] = orch.run_backtest()

st.info(st.session_state.get("last_action", "等待操作"))
