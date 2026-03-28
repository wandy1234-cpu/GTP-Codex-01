"""Evaluation metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rank_ic(df: pd.DataFrame) -> float:
    d = df.dropna(subset=["predicted_excess_ret_5d", "future_excess_ret_5d"])
    if d.empty:
        return 0.0
    by_day = d.groupby("trade_date").apply(
        lambda x: x["predicted_excess_ret_5d"].corr(x["future_excess_ret_5d"], method="spearman")
    )
    return float(by_day.mean()) if len(by_day) else 0.0


def summary_top10(df: pd.DataFrame) -> dict[str, float]:
    d = df.sort_values(["trade_date", "final_score"], ascending=[True, False]).groupby("trade_date").head(10)
    return {
        "top10_avg_future_excess_ret_5d": float(d["future_excess_ret_5d"].mean()),
        "top10_up_hit_rate": float(d["future_up_5d"].mean()),
        "top10_big_up_hit_rate": float(d["future_big_up_5d"].mean()),
        "rank_ic": rank_ic(df),
    }


def sharpe(returns: pd.Series) -> float:
    if returns.std(ddof=0) == 0:
        return 0.0
    return float(np.sqrt(252) * returns.mean() / returns.std(ddof=0))
