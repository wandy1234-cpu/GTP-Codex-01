from __future__ import annotations

import pandas as pd

from features.builder import build_features


def test_build_features_basic() -> None:
    df = pd.DataFrame(
        {
            "symbol": ["A"] * 30,
            "market": ["A"] * 30,
            "trade_date": pd.date_range("2024-01-01", periods=30),
            "close": [100 + i for i in range(30)],
            "turnover": [0.02] * 30,
            "amount": [1e8] * 30,
        }
    )
    out = build_features(df)
    assert "ret_5" in out.columns
    assert "vol_20" in out.columns
