from __future__ import annotations

import streamlit as st

from app.utils.config_loader import load_yaml

st.title("参数设置")
cfg = load_yaml("config/model.yaml")
st.json(cfg)
st.info("Phase 1 提供只读展示；Phase 2 支持网页保存/加载。")
