"""Data adapter base classes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd


STANDARD_COLUMNS = [
    "symbol",
    "name",
    "market",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover",
    "vwap",
    "adj_factor",
    "suspended_flag",
    "st_flag",
    "sector",
    "industry",
    "market_cap",
    "float_market_cap",
]


@dataclass
class FetchRequest:
    symbols: Iterable[str]
    market: str
    start: date
    end: date


class BaseAdapter(ABC):
    name: str

    @abstractmethod
    def fetch_ohlcv(self, req: FetchRequest) -> pd.DataFrame:
        raise NotImplementedError

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None
        out = df[STANDARD_COLUMNS].copy()
        out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
        return out
