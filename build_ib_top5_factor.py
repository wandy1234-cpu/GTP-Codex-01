import argparse
import csv
import datetime as dt
import math
from collections import defaultdict
from typing import Dict, List, Tuple


def parse_raw_rows(path: str) -> List[Tuple[dt.date, str, str, float]]:
    """
    Input CSV columns:
      - date (YYYY-MM-DD)
      - ticker (e.g. 600519.SS / 0700.HK)
      - broker (foreign IB name)
      - position_weight OR signal_score
    """
    rows: List[Tuple[dt.date, str, str, float]] = []
    with open(path, "r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        fields = set(rd.fieldnames or [])
        required = {"date", "ticker", "broker"}
        if not required.issubset(fields):
            miss = sorted(required - fields)
            raise ValueError(f"raw CSV missing required columns: {miss}")
        value_col = "position_weight" if "position_weight" in fields else "signal_score"
        if value_col not in fields:
            raise ValueError("raw CSV needs either `position_weight` or `signal_score` column")

        for r in rd:
            d = dt.datetime.strptime(str(r["date"]), "%Y-%m-%d").date()
            ticker = str(r["ticker"]).strip()
            broker = str(r["broker"]).strip()
            if not ticker or not broker:
                continue
            try:
                val = float(r[value_col])
            except (TypeError, ValueError):
                continue
            rows.append((d, ticker, broker, val))
    return rows


def robust_zscore(values: List[float]) -> List[float]:
    if not values:
        return []
    mu = sum(values) / len(values)
    var = sum((x - mu) ** 2 for x in values) / max(len(values) - 1, 1)
    std = math.sqrt(max(var, 1e-12))
    return [(x - mu) / std for x in values]


def build_factor(raw_rows: List[Tuple[dt.date, str, str, float]], top_k: int) -> List[Tuple[dt.date, str, float]]:
    by_dt_tk: Dict[Tuple[dt.date, str], List[Tuple[str, float]]] = defaultdict(list)
    for d, tk, brk, v in raw_rows:
        by_dt_tk[(d, tk)].append((brk, v))

    daily: Dict[dt.date, List[Tuple[str, float]]] = defaultdict(list)
    for (d, tk), arr in by_dt_tk.items():
        # Deduplicate by broker: keep last value in file order
        bmap: Dict[str, float] = {}
        for brk, v in arr:
            bmap[brk] = v
        vals = sorted(bmap.values(), key=lambda x: abs(x), reverse=True)[: max(top_k, 1)]
        if not vals:
            continue
        conviction = sum(abs(x) for x in vals)
        signed_mean = sum(vals) / len(vals)
        score = signed_mean * math.log1p(conviction)
        daily[d].append((tk, score))

    out: List[Tuple[dt.date, str, float]] = []
    for d in sorted(daily.keys()):
        arr = daily[d]
        z = robust_zscore([x[1] for x in arr])
        for (tk, _), zz in zip(arr, z):
            out.append((d, tk, zz))
    return out


def write_factor(path: str, rows: List[Tuple[dt.date, str, float]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "score"])
        for d, tk, sc in rows:
            w.writerow([d.isoformat(), tk, f"{sc:.8f}"])


def main():
    ap = argparse.ArgumentParser(description="Build top-5 foreign IB holdings factor CSV for quant_alpha_system.py")
    ap.add_argument("--input", required=True, help="Raw holdings CSV (date,ticker,broker,position_weight|signal_score)")
    ap.add_argument("--output", required=True, help="Output factor CSV (date,ticker,score)")
    ap.add_argument("--top-k", type=int, default=5, help="Top brokers per ticker/date by abs(signal)")
    args = ap.parse_args()

    raw = parse_raw_rows(args.input)
    fac = build_factor(raw, top_k=args.top_k)
    write_factor(args.output, fac)
    print(f"[OK] factor rows: {len(fac)} -> {args.output}")


if __name__ == "__main__":
    main()
