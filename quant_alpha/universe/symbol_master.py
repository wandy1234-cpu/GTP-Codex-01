"""Symbol master for A/H markets."""
from __future__ import annotations

import pandas as pd


def get_default_symbol_master() -> pd.DataFrame:
    data = [
        ("600519", "贵州茅台", "A", "消费", "白酒"),
        ("000001", "平安银行", "A", "金融", "银行"),
        ("600036", "招商银行", "A", "金融", "银行"),
        ("00700", "腾讯控股", "H", "科技", "互联网"),
        ("00941", "中国移动", "H", "通信", "运营商"),
        ("09988", "阿里巴巴", "H", "科技", "互联网"),
    ]
    return pd.DataFrame(data, columns=["symbol", "name", "market", "sector", "industry"])
