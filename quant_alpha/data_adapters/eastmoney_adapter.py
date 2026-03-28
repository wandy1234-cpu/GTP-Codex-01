from __future__ import annotations

import pandas as pd

from data_adapters.base import BaseAdapter, FetchRequest


class EastmoneyAdapter(BaseAdapter):
    name = "eastmoney"

    def fetch_ohlcv(self, req: FetchRequest) -> pd.DataFrame:
        # Phase 1 risk-aware placeholder: external endpoint varies frequently.
        return pd.DataFrame(columns=[])
