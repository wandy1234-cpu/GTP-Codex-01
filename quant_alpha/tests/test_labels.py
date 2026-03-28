from __future__ import annotations

import pandas as pd

from labels.builder import build_labels


def test_build_labels_generates_columns() -> None:
    df = pd.DataFrame(
        {
            "symbol": ["A", "A", "A", "A", "A", "A"],
            "market": ["A"] * 6,
            "trade_date": pd.date_range("2024-01-01", periods=6),
            "close": [1, 1.1, 1.2, 1.3, 1.4, 1.5],
        }
    )
    out = build_labels(df, horizon=1)
    assert "future_ret_5d" in out.columns
    assert "future_excess_ret_5d" in out.columns
    assert "future_up_5d" in out.columns
