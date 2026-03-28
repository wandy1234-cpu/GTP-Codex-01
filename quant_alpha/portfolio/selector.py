"""Top-N selector with basic constraints."""
from __future__ import annotations

import pandas as pd


def select_top_n(
    df: pd.DataFrame,
    trade_date: str,
    top_n: int,
    max_per_sector: int = 3,
    max_per_market: int = 7,
) -> pd.DataFrame:
    d = df[df["trade_date"].astype(str) == str(trade_date)].copy()
    d = d.sort_values("final_score", ascending=False)

    selected = []
    sector_cnt: dict[str, int] = {}
    market_cnt: dict[str, int] = {}

    for _, row in d.iterrows():
        sec = str(row.get("sector", "UNKNOWN"))
        mkt = str(row.get("market", "A"))
        if sector_cnt.get(sec, 0) >= max_per_sector:
            continue
        if market_cnt.get(mkt, 0) >= max_per_market:
            continue
        selected.append(row)
        sector_cnt[sec] = sector_cnt.get(sec, 0) + 1
        market_cnt[mkt] = market_cnt.get(mkt, 0) + 1
        if len(selected) >= top_n:
            break

    out = pd.DataFrame(selected)
    if out.empty:
        return out
    out["rank_global"] = range(1, len(out) + 1)
    out["rank_in_market"] = out.groupby("market")["final_score"].rank(ascending=False, method="first").astype(int)
    out["selected_reason"] = "high_excess_ret+probability+risk_adjusted"
    out["key_factor_contributors"] = "ret_5,ret_10,vol_20,turnover_mean_5"
    return out
