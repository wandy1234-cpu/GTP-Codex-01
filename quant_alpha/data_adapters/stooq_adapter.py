from __future__ import annotations

import pandas as pd

from data_adapters.base import BaseAdapter, FetchRequest


class StooqAdapter(BaseAdapter):
    name = "stooq"

    def fetch_ohlcv(self, req: FetchRequest) -> pd.DataFrame:
        # Phase 1 fallback skeleton: return empty when unavailable.
        return pd.DataFrame(columns=[])
