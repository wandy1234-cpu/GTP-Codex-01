"""Feature engineering pipeline."""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "trade_date"]).copy()
    grp = df.groupby("symbol", group_keys=False)

    for n in [1, 3, 5, 10, 20, 60]:
        df[f"ret_{n}"] = grp["close"].pct_change(n)
    for n in [5, 10, 20, 60]:
        df[f"vol_{n}"] = grp["ret_1"].rolling(n).std().reset_index(level=0, drop=True)

    df["turnover_mean_5"] = grp["turnover"].rolling(5).mean().reset_index(level=0, drop=True)
    df["amount_mean_5"] = grp["amount"].rolling(5).mean().reset_index(level=0, drop=True)
    df["amihud_5"] = (grp["ret_1"].rolling(5).mean().reset_index(level=0, drop=True).abs() / (df["amount_mean_5"].abs() + 1e-6))

    df["cs_rank_ret_5"] = df.groupby(["market", "trade_date"])["ret_5"].rank(pct=True)
    df["cs_z_ret_5"] = df.groupby(["market", "trade_date"])["ret_5"].transform(
        lambda x: (x - x.mean()) / (x.std(ddof=0) + 1e-6)
    )

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df
