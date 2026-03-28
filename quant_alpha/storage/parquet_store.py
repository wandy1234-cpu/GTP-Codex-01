"""Parquet persistence helpers."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


class ParquetStore:
    def __init__(self, base_dir: str = "data") -> None:
        self.base_dir = Path(base_dir)

    def write(self, df: pd.DataFrame, layer: str, table: str) -> Path:
        path = self.base_dir / layer
        path.mkdir(parents=True, exist_ok=True)
        target = path / f"{table}.parquet"
        df.to_parquet(target, index=False)
        return target

    def read(self, layer: str, table: str) -> pd.DataFrame:
        target = self.base_dir / layer / f"{table}.parquet"
        if not target.exists():
            return pd.DataFrame()
        return pd.read_parquet(target)
