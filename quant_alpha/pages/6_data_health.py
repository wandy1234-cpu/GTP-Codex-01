from __future__ import annotations

import streamlit as st

from storage.parquet_store import ParquetStore

st.title("数据健康")
store = ParquetStore()
df = store.read("bronze", "ohlcv")
if df.empty:
    st.warning("暂无数据")
else:
    st.metric("行数", len(df))
    st.metric("缺失值比例", f"{df.isna().mean().mean():.2%}")
    st.write(df.head())
