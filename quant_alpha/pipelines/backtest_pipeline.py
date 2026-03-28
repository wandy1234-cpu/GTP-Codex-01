"""Backtest pipeline with walk-forward skeleton."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.utils.config_loader import load_all_configs
from backtest.walk_forward import WFConfig, make_walk_forward_splits
from evaluation.metrics import summary_top10
from storage.parquet_store import ParquetStore


class BacktestPipeline:
    def __init__(self) -> None:
        self.cfg = load_all_configs()
        self.parquet = ParquetStore(base_dir=self.cfg["app"]["paths"]["data"])

    def run(self) -> pd.DataFrame:
        df = self.parquet.read("silver", "features_labels")
        if df.empty:
            return pd.DataFrame()
        dts = pd.to_datetime(df["trade_date"]).tolist()
        cfg = self.cfg["backtest"]["walk_forward"]
        splits = make_walk_forward_splits(dts, WFConfig(**cfg))

        rows = []
        for i, (_, test_dates) in enumerate(splits, 1):
            part = df[df["trade_date"].isin([d.date() for d in test_dates])].copy()
            part["final_score"] = part.get("ret_5", 0.0).fillna(0.0)
            met = summary_top10(part)
            met["fold"] = i
            rows.append(met)

        out = pd.DataFrame(rows)
        self.parquet.write(out, "gold", "backtest_summary")
        report = Path("reports") / "backtest_summary.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(out.to_markdown(index=False), encoding="utf-8")
        return out
