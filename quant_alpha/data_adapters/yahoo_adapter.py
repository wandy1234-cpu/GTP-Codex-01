from __future__ import annotations

from datetime import timedelta

import pandas as pd
import yfinance as yf

from data_adapters.base import BaseAdapter, FetchRequest


class YahooAdapter(BaseAdapter):
    name = "yahoo"

    def fetch_ohlcv(self, req: FetchRequest) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        for s in req.symbols:
            ticker = s if req.market == "H" else f"{s}.SS"
            data = yf.download(ticker, start=req.start, end=req.end + timedelta(days=1), progress=False)
            if data.empty:
                continue
            df = data.reset_index().rename(
                columns={"Date": "trade_date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
            )
            df["symbol"] = s
            df["name"] = s
            df["market"] = req.market
            df["amount"] = df["close"] * df["volume"]
            df["turnover"] = 0.0
            df["vwap"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
            df["adj_factor"] = 1.0
            df["suspended_flag"] = 0
            df["st_flag"] = 0
            df["sector"] = "UNKNOWN"
            df["industry"] = "UNKNOWN"
            df["market_cap"] = None
            df["float_market_cap"] = None
            rows.append(df)
        if not rows:
            return pd.DataFrame()
        return self.normalize(pd.concat(rows, ignore_index=True))
