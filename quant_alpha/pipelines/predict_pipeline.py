"""Prediction pipeline."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import uuid

import joblib
import pandas as pd

from app.utils.config_loader import load_all_configs
from ensemble.scoring import apply_final_score
from features.registry import BASE_FEATURES
from portfolio.selector import select_top_n
from storage.parquet_store import ParquetStore


class PredictPipeline:
    def __init__(self) -> None:
        self.cfg = load_all_configs()
        self.parquet = ParquetStore(base_dir=self.cfg["app"]["paths"]["data"])

    def run(self) -> pd.DataFrame:
        df = self.parquet.read("silver", "features_labels")
        model = joblib.load(Path(self.cfg["app"]["paths"]["artifacts"]) / "lgbm_ranker.pkl")
        df = df.copy()
        df["predicted_excess_ret_5d"] = model.predict(df, BASE_FEATURES)
        weights = self.cfg["model"]["model"]["weights"]
        scored = apply_final_score(df, weights)

        latest_date = str(scored["trade_date"].max()) if not scored.empty else str(date.today())
        top = select_top_n(
            scored,
            trade_date=latest_date,
            top_n=self.cfg["model"]["model"]["top_n"],
        )
        if top.empty:
            return top
        top["run_id"] = uuid.uuid4().hex[:12]
        top["trade_date"] = latest_date
        cols = [
            "run_id","trade_date","symbol","name","market","sector","industry","final_score",
            "predicted_excess_ret_5d","calibrated_prob_up_5d","calibrated_prob_big_up_5d",
            "risk_score","turnover_penalty","crowding_penalty","rank_in_market","rank_global",
            "selected_reason","key_factor_contributors",
        ]
        out = top[cols].copy()
        self.parquet.write(out, "gold", "today_picks")
        return out
