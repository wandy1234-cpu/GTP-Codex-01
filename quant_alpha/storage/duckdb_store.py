"""DuckDB persistence and querying."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


class DuckDBStore:
    def __init__(self, db_path: str = "db/quant_alpha.duckdb") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def upsert_df(self, df: pd.DataFrame, table: str) -> None:
        con = duckdb.connect(str(self.db_path))
        con.register("df_view", df)
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df_view LIMIT 0")
        con.execute(f"DELETE FROM {table}")
        con.execute(f"INSERT INTO {table} SELECT * FROM df_view")
        con.close()

    def query(self, sql: str) -> pd.DataFrame:
        con = duckdb.connect(str(self.db_path))
        out = con.execute(sql).fetchdf()
        con.close()
        return out
