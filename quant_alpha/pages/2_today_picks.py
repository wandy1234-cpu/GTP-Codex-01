from __future__ import annotations

import pandas as pd
import streamlit as st

from storage.parquet_store import ParquetStore

st.title("今日推荐")
store = ParquetStore()
df = store.read("gold", "today_picks")
if df.empty:
    st.warning("暂无推荐，请先运行预测")
else:
    market = st.selectbox("市场", ["ALL", "A", "H"])
    view = df if market == "ALL" else df[df["market"] == market]
    st.dataframe(view, use_container_width=True)
    st.download_button("下载CSV", data=view.to_csv(index=False).encode("utf-8"), file_name="today_picks.csv")
