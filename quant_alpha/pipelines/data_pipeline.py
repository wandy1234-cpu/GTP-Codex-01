"""Data update pipeline."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.utils.config_loader import load_all_configs
from app.utils.logger import get_logger
from data_adapters.router import AdapterRouter
from storage.duckdb_store import DuckDBStore
from storage.parquet_store import ParquetStore
from universe.symbol_master import get_default_symbol_master

logger = get_logger(__name__)


class DataPipeline:
    def __init__(self) -> None:
        self.cfg = load_all_configs()
        self.router = AdapterRouter()
        self.parquet = ParquetStore(base_dir=self.cfg["app"]["paths"]["data"])
        self.duck = DuckDBStore(db_path=self.cfg["app"]["paths"]["db"])

    def run(self) -> pd.DataFrame:
        master = get_default_symbol_master()
        end = date.today()
        start = end - timedelta(days=365)
        priority = self.cfg["data"]["data_sources"]["priority"]

        all_df = []
        for market in ["A", "H"]:
            symbols = master.loc[master["market"] == market, "symbol"].tolist()
            fetched = self.router.fetch(symbols=symbols, market=market, start=start, end=end, priority=priority)
            if fetched.empty:
                logger.warning("fallback to synthetic sample for market=%s", market)
                fetched = self._synthetic_data(master[master["market"] == market], start, end)
            all_df.append(fetched)

        df = pd.concat(all_df, ignore_index=True)
        df = df.merge(master, on=["symbol", "market"], how="left", suffixes=("", "_m"))
        for col in ["name", "sector", "industry"]:
            df[col] = df[col].fillna(df[f"{col}_m"])
            if f"{col}_m" in df.columns:
                df.drop(columns=[f"{col}_m"], inplace=True)

        self.parquet.write(df, layer="bronze", table="ohlcv")
        self.duck.upsert_df(df, table="ohlcv")
        return df

    @staticmethod
    def _synthetic_data(master: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
        dates = pd.bdate_range(start, end)
        rows = []
        for _, r in master.iterrows():
            px = 100.0
            for d in dates:
                ret = (hash((r["symbol"], str(d.date()))) % 200 - 100) / 5000
                px *= 1 + ret
                rows.append(
                    {
                        "symbol": r["symbol"], "name": r["name"], "market": r["market"], "trade_date": d.date(),
                        "open": px * 0.995, "high": px * 1.01, "low": px * 0.99, "close": px,
                        "volume": 1_000_000, "amount": px * 1_000_000, "turnover": 0.02, "vwap": px,
                        "adj_factor": 1.0, "suspended_flag": 0, "st_flag": 0,
                        "sector": r["sector"], "industry": r["industry"],
                        "market_cap": 1e11, "float_market_cap": 5e10,
                    }
                )
        return pd.DataFrame(rows)
