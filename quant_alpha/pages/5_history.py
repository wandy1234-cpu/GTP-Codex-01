from __future__ import annotations

import streamlit as st

from storage.parquet_store import ParquetStore

st.title("历史推荐")
store = ParquetStore()
df = store.read("gold", "today_picks")
if df.empty:
    st.warning("暂无历史记录")
else:
    st.dataframe(df, use_container_width=True)
