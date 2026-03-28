from __future__ import annotations

import pandas as pd

from data_adapters.base import BaseAdapter, FetchRequest


class TencentAdapter(BaseAdapter):
    name = "tencent"

    def fetch_ohlcv(self, req: FetchRequest) -> pd.DataFrame:
        # Phase 1 risk-aware placeholder: external endpoint may be unstable.
        return pd.DataFrame(columns=[])
