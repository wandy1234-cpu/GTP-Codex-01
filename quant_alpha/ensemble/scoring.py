"""Final scoring module."""
from __future__ import annotations

import pandas as pd


def zscore(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / (x.std(ddof=0) + 1e-6)


def apply_final_score(df: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    out["risk_score"] = out.get("vol_20", 0.0).fillna(0.0)
    out["turnover_penalty"] = (1.0 / (out.get("turnover_mean_5", 0.0).fillna(0.0) + 1e-6)).clip(0, 1e3)
    out["crowding_penalty"] = out.get("cs_rank_ret_5", 0.5).fillna(0.5)
    out["calibrated_prob_up_5d"] = 0.5 + 0.25 * zscore(out.get("ret_5", 0.0).fillna(0.0))
    out["calibrated_prob_big_up_5d"] = 0.3 + 0.2 * zscore(out.get("ret_10", 0.0).fillna(0.0))

    out["final_score"] = (
        weights["w1"] * zscore(out["predicted_excess_ret_5d"]) +
        weights["w2"] * zscore(out["calibrated_prob_up_5d"]) +
        weights["w3"] * zscore(out["calibrated_prob_big_up_5d"]) -
        weights["w4"] * zscore(out["risk_score"]) -
        weights["w5"] * zscore(out["turnover_penalty"]) -
        weights["w6"] * zscore(out["crowding_penalty"])
    )
    return out
