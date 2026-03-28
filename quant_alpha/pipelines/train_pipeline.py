"""Training pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from app.utils.config_loader import load_all_configs
from features.builder import build_features
from features.registry import BASE_FEATURES
from labels.builder import build_labels
from models.ranker import LGBMRankerModel, RankerConfig
from storage.parquet_store import ParquetStore


class TrainPipeline:
    def __init__(self) -> None:
        self.cfg = load_all_configs()
        self.parquet = ParquetStore(base_dir=self.cfg["app"]["paths"]["data"])

    def run(self) -> str:
        df = self.parquet.read("bronze", "ohlcv")
        feats = build_features(df)
        labeled = build_labels(
            feats,
            horizon=self.cfg["model"]["label"]["horizon"],
            big_up_threshold=self.cfg["model"]["label"]["big_up_threshold"],
        )
        self.parquet.write(labeled, "silver", "features_labels")

        mcfg = self.cfg["model"]["model"]["lgbm_ranker"]
        model = LGBMRankerModel(RankerConfig(**mcfg))
        model.fit(labeled, BASE_FEATURES)

        artifacts = Path(self.cfg["app"]["paths"]["artifacts"])
        artifacts.mkdir(parents=True, exist_ok=True)
        model_path = artifacts / "lgbm_ranker.pkl"
        joblib.dump(model, model_path)

        meta = {"feature_version": "v1", "features": BASE_FEATURES}
        (artifacts / "model_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(model_path)
