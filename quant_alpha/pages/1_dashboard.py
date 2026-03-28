from __future__ import annotations

import streamlit as st

from app.services.orchestrator import Orchestrator

st.title("Dashboard / 总控台")
orch = Orchestrator()

if st.button("一键更新数据"):
    st.success(orch.update_data())
if st.button("一键训练模型"):
    st.success(orch.train_model())
if st.button("一键运行预测"):
    st.success(orch.run_predict())
if st.button("一键运行回测"):
    st.success(orch.run_backtest())
