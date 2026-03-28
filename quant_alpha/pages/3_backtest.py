from __future__ import annotations

import streamlit as st

from storage.parquet_store import ParquetStore

st.title("回测分析")
store = ParquetStore()
df = store.read("gold", "backtest_summary")
if df.empty:
    st.warning("暂无回测结果")
else:
    st.dataframe(df, use_container_width=True)
    if "top10_avg_future_excess_ret_5d" in df.columns:
        st.line_chart(df.set_index("fold")["top10_avg_future_excess_ret_5d"])
