"""Label generation with strict forward windows."""
from __future__ import annotations

import pandas as pd


def build_labels(df: pd.DataFrame, horizon: int = 5, big_up_threshold: float = 0.05) -> pd.DataFrame:
    df = df.sort_values(["symbol", "trade_date"]).copy()
    grp = df.groupby("symbol", group_keys=False)
    future_close = grp["close"].shift(-horizon)
    df["future_ret_5d"] = future_close / df["close"] - 1

    bench = df.groupby(["market", "trade_date"])["future_ret_5d"].transform("median")
    df["future_excess_ret_5d"] = df["future_ret_5d"] - bench
    df["future_up_5d"] = (df["future_ret_5d"] > 0).astype(int)
    df["future_big_up_5d"] = (df["future_ret_5d"] > big_up_threshold).astype(int)
    return df
