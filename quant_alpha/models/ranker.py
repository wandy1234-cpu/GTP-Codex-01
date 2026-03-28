"""LightGBM ranker wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd


@dataclass
class RankerConfig:
    objective: str = "rank_xendcg"
    learning_rate: float = 0.05
    n_estimators: int = 300
    num_leaves: int = 63
    min_data_in_leaf: int = 50
    random_state: int = 42


class LGBMRankerModel:
    def __init__(self, cfg: RankerConfig) -> None:
        self.cfg = cfg
        self.model = lgb.LGBMRanker(
            objective=cfg.objective,
            learning_rate=cfg.learning_rate,
            n_estimators=cfg.n_estimators,
            num_leaves=cfg.num_leaves,
            min_data_in_leaf=cfg.min_data_in_leaf,
            random_state=cfg.random_state,
        )

    def fit(self, df: pd.DataFrame, feature_cols: Sequence[str]) -> None:
        d = df.dropna(subset=list(feature_cols) + ["future_excess_ret_5d"]).copy()
        d["query"] = d["trade_date"].astype(str)
        group_sizes = d.groupby("query").size().to_numpy()
        x = d[list(feature_cols)]
        y = d["future_excess_ret_5d"]
        self.model.fit(x, y, group=group_sizes)

    def predict(self, df: pd.DataFrame, feature_cols: Sequence[str]) -> np.ndarray:
        x = df[list(feature_cols)].fillna(0.0)
        return self.model.predict(x)
