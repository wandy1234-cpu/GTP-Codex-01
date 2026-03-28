"""Adapter router with fallback and anomaly check."""
from __future__ import annotations

from datetime import date
from typing import Sequence

import pandas as pd

from app.utils.logger import get_logger
from data_adapters.base import FetchRequest
from data_adapters.eastmoney_adapter import EastmoneyAdapter
from data_adapters.stooq_adapter import StooqAdapter
from data_adapters.tencent_adapter import TencentAdapter
from data_adapters.yahoo_adapter import YahooAdapter

logger = get_logger(__name__)


class AdapterRouter:
    def __init__(self) -> None:
        self.adapters = {
            "eastmoney": EastmoneyAdapter(),
            "tencent": TencentAdapter(),
            "yahoo": YahooAdapter(),
            "stooq": StooqAdapter(),
        }

    def fetch(
        self,
        symbols: Sequence[str],
        market: str,
        start: date,
        end: date,
        priority: Sequence[str],
    ) -> pd.DataFrame:
        req = FetchRequest(symbols=symbols, market=market, start=start, end=end)
        for src in priority:
            adapter = self.adapters.get(src)
            if adapter is None:
                continue
            try:
                df = adapter.fetch_ohlcv(req)
                if not df.empty:
                    logger.info("fetched %s rows from %s", len(df), src)
                    return df
            except Exception as exc:
                logger.warning("adapter %s failed: %s", src, exc)
        logger.error("all data sources failed for market=%s", market)
        return pd.DataFrame()
