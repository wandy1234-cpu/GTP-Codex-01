import argparse
import csv
import datetime as dt
import http.client
import json
import math
import os
import random
import sqlite3
import ssl
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class Row:
    date: dt.date
    ticker: str
    close: float
    high: float
    low: float
    volume: float


@dataclass
class Sample:
    date: dt.date
    ticker: str
    features: List[float]
    target: int
    close: float


@dataclass
class Metrics:
    accuracy: float
    precision: float
    recall: float
    auc: float


FEATURE_NAMES = [
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "rel_ret_5d",
    "vol_20d",
    "vol_ratio",
    "ma_gap_10_30",
    "price_pos_20d",
]

DEFAULT_TICKERS = [
    "000300.SS", "600519.SS", "000858.SZ", "601318.SS", "601166.SS", "600036.SS", "600276.SS",
    "601888.SS", "600900.SS", "600031.SS", "300750.SZ", "002594.SZ", "000333.SZ", "002415.SZ",
    "000651.SZ", "0700.HK", "9988.HK", "0939.HK", "1299.HK", "0388.HK", "2318.HK",
]

DEFAULT_CN_ETF_TICKERS = [
    "510300.SS", "510050.SS", "510500.SS", "159919.SZ", "159915.SZ", "159949.SZ", "159928.SZ",
    "512880.SS", "512170.SS", "512660.SS", "512010.SS", "512690.SS", "512800.SS", "512480.SS",
    "512400.SS", "512760.SS", "512200.SS", "515790.SS", "516160.SS", "516970.SS", "516510.SS",
    "588000.SS", "588080.SS", "159995.SZ", "159967.SZ", "159825.SZ", "159852.SZ", "159980.SZ",
    "513100.SS", "513500.SS", "513050.SS", "513180.SS", "513080.SS", "159920.SZ", "511010.SS",
]

STOCK_NAME_MAP = {
    "000858.SZ": "五粮液",
    "600519.SS": "贵州茅台",
    "601318.SS": "中国平安",
    "000300.SS": "沪深300ETF近似",
    "0700.HK": "腾讯控股",
    "9988.HK": "阿里巴巴-W",
    "0939.HK": "建设银行",
    "1299.HK": "友邦保险",
    "0388.HK": "香港交易所",
    "2318.HK": "中国平安(港股)",
}


def sigmoid(x: float) -> float:
    if x < -40:
        return 0.0
    if x > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def rolling_mean(seq: Sequence[float]) -> float:
    return sum(seq) / len(seq) if seq else 0.0


def rolling_std(seq: Sequence[float]) -> float:
    if len(seq) < 2:
        return 0.0
    m = rolling_mean(seq)
    var = sum((x - m) ** 2 for x in seq) / (len(seq) - 1)
    return math.sqrt(max(var, 0.0))


def parse_csv(path: str) -> Dict[str, List[Row]]:
    by_ticker: Dict[str, List[Row]] = defaultdict(list)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"date", "ticker", "close", "high", "low", "volume"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            missing = required - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")

        for r in reader:
            by_ticker[r["ticker"]].append(
                Row(
                    date=dt.datetime.strptime(r["date"], "%Y-%m-%d").date(),
                    ticker=r["ticker"],
                    close=float(r["close"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    volume=float(r["volume"]),
                )
            )

    for t in by_ticker:
        by_ticker[t].sort(key=lambda x: x.date)
    return by_ticker


def fetch_json(url: str, timeout: int = 20, retries: int = 3) -> dict:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_exc: Exception | None = None

    for i in range(retries):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (
            HTTPError,
            URLError,
            TimeoutError,
            http.client.RemoteDisconnected,
            ConnectionResetError,
            ssl.SSLError,
            json.JSONDecodeError,
        ) as exc:
            last_exc = exc
            # 轻量重试，避免偶发连接中断直接退出
            if i < retries - 1:
                time.sleep(0.6 * (i + 1))
                continue
            break

    raise RuntimeError(f"Request failed after {retries} retries: {last_exc}") from last_exc


def fetch_yahoo_history(ticker: str, start: dt.date, end: dt.date) -> List[Row]:
    period1 = int(time.mktime(start.timetuple()))
    period2 = int(time.mktime((end + dt.timedelta(days=1)).timetuple()))
    params = urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{params}"
    payload = fetch_json(url)

    try:
        result = payload["chart"]["result"][0]
        stamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        closes = quote["close"]
        highs = quote["high"]
        lows = quote["low"]
        vols = quote["volume"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Yahoo payload for {ticker}") from exc

    rows: List[Row] = []
    for ts, c, h, l, v in zip(stamps, closes, highs, lows, vols):
        if c is None or h is None or l is None or v is None:
            continue
        rows.append(
            Row(
                date=dt.datetime.utcfromtimestamp(ts).date(),
                ticker=ticker,
                close=float(c),
                high=float(h),
                low=float(l),
                volume=float(v),
            )
        )
    rows.sort(key=lambda r: r.date)
    return rows


def to_eastmoney_secid(ticker: str) -> str:
    # A股: 1.600519 / 0.000858 ; 港股: 116.00700
    code, _, market = ticker.partition(".")
    code = code.strip()
    market = market.strip().upper()
    if market == "SS":
        return f"1.{code}"
    if market == "SZ":
        return f"0.{code}"
    if market == "HK":
        return f"116.{code.zfill(5)}"
    raise RuntimeError(f"unsupported ticker for eastmoney: {ticker}")


def fetch_eastmoney_history(ticker: str, start: dt.date, end: dt.date) -> List[Row]:
    secid = to_eastmoney_secid(ticker)
    params = urlencode(
        {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": "101",  # 日线
            "fqt": "1",  # 前复权
            "secid": secid,
            "beg": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
        }
    )
    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{params}"
    payload = fetch_json(url)
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        raise RuntimeError(f"Eastmoney returned empty data for {ticker}")

    rows: List[Row] = []
    for line in klines:
        # "2026-03-20,88.10,89.01,90.20,87.88,123456,1098765432,2.63,2.00,1.74,0.98"
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            d = dt.datetime.strptime(parts[0], "%Y-%m-%d").date()
            close = float(parts[2])
            high = float(parts[3])
            low = float(parts[4])
            volume = float(parts[5])
            rows.append(Row(date=d, ticker=ticker, close=close, high=high, low=low, volume=volume))
        except ValueError:
            continue

    if not rows:
        raise RuntimeError(f"Eastmoney parsed zero rows for {ticker}")
    rows.sort(key=lambda r: r.date)
    return rows


def to_tencent_symbol(ticker: str) -> str:
    code, _, market = ticker.partition(".")
    market = market.upper().strip()
    if market == "SS":
        return f"sh{code}"
    if market == "SZ":
        return f"sz{code}"
    if market == "HK":
        return f"hk{code.zfill(5)}"
    raise RuntimeError(f"unsupported ticker for tencent: {ticker}")


def fetch_tencent_history(ticker: str, start: dt.date, end: dt.date) -> List[Row]:
    symbol = to_tencent_symbol(ticker)
    params = urlencode({"param": f"{symbol},day,,,520,qfq"})
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?{params}"
    payload = fetch_json(url)
    data_obj = payload.get("data", {}).get(symbol, {})
    day_data = data_obj.get("qfqday") or data_obj.get("day") or []
    if not day_data:
        raise RuntimeError(f"Tencent returned empty data for {ticker}")

    rows: List[Row] = []
    for arr in day_data:
        if len(arr) < 6:
            continue
        try:
            d = dt.datetime.strptime(arr[0], "%Y-%m-%d").date()
            if d < start or d > end:
                continue
            close = float(arr[2])
            high = float(arr[3])
            low = float(arr[4])
            volume = float(arr[5])
            rows.append(Row(date=d, ticker=ticker, close=close, high=high, low=low, volume=volume))
        except (ValueError, TypeError):
            continue
    if not rows:
        raise RuntimeError(f"Tencent parsed zero rows for {ticker}")
    rows.sort(key=lambda r: r.date)
    return rows


def to_stooq_symbol(ticker: str) -> str:
    # 600519.SS -> 600519.cn ; 000858.SZ -> 000858.cn ; 0700.HK -> 0700.hk
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return f"{ticker.split('.')[0]}.cn"
    if ticker.endswith(".HK"):
        return f"{ticker.split('.')[0]}.hk"
    return ticker.lower()


def fetch_stooq_history(ticker: str, start: dt.date, end: dt.date) -> List[Row]:
    sym = to_stooq_symbol(ticker)
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Stooq fetch failed for {ticker}: {exc}") from exc

    lines = [x.strip() for x in body.splitlines() if x.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"Stooq returned empty data for {ticker}")

    rows: List[Row] = []
    reader = csv.DictReader(lines)
    for r in reader:
        try:
            d = dt.datetime.strptime(r["Date"], "%Y-%m-%d").date()
            if d < start or d > end:
                continue
            close = float(r["Close"])
            high = float(r["High"])
            low = float(r["Low"])
            vol = float(r.get("Volume", "0") or 0)
            rows.append(Row(date=d, ticker=ticker, close=close, high=high, low=low, volume=vol))
        except (KeyError, ValueError):
            continue

    if not rows:
        raise RuntimeError(f"Stooq parsed zero rows for {ticker}")

    rows.sort(key=lambda r: r.date)
    return rows


def fetch_latest_quote_yahoo(tickers: List[str]) -> Dict[str, Tuple[float, dt.datetime]]:
    if not tickers:
        return {}
    sym = ",".join(tickers)
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}"
    payload = fetch_json(url)

    out: Dict[str, Tuple[float, dt.datetime]] = {}
    results = payload.get("quoteResponse", {}).get("result", [])
    for r in results:
        t = r.get("symbol")
        p = r.get("regularMarketPrice")
        ts = r.get("regularMarketTime")
        if t and p is not None and ts is not None:
            out[t] = (float(p), dt.datetime.utcfromtimestamp(int(ts)))
    return out


def fetch_latest_quote_eastmoney(tickers: List[str]) -> Dict[str, Tuple[float, dt.datetime]]:
    out: Dict[str, Tuple[float, dt.datetime]] = {}
    for ticker in tickers:
        secid = to_eastmoney_secid(ticker)
        params = urlencode(
            {
                "invt": "2",
                "fltt": "2",
                "fields": "f43,f57,f58,f86",
                "secid": secid,
            }
        )
        url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
        payload = fetch_json(url)
        data = payload.get("data") or {}
        px_raw = data.get("f43")
        ts_raw = data.get("f86")
        if px_raw is None:
            continue

        try:
            px = float(px_raw) / 100.0
            # f86 usually unix seconds; if missing fallback now.
            if ts_raw is None:
                ts = dt.datetime.utcnow()
            else:
                ts = dt.datetime.utcfromtimestamp(int(ts_raw))
            out[ticker] = (px, ts)
        except (ValueError, TypeError, OSError):
            continue
    return out


def fetch_latest_quote_tencent(tickers: List[str]) -> Dict[str, Tuple[float, dt.datetime]]:
    if not tickers:
        return {}
    symbols = [to_tencent_symbol(t) for t in tickers]
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=20) as resp:
            text = resp.read().decode("gbk", errors="ignore")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Tencent quote failed: {exc}") from exc

    out: Dict[str, Tuple[float, dt.datetime]] = {}
    inv = {to_tencent_symbol(t): t for t in tickers}
    for ln in [x.strip() for x in text.split(";") if x.strip()]:
        if "~" not in ln:
            continue
        left, right = ln.split("=", 1)
        symbol = left.split("_")[-1].strip()
        fields = right.strip().strip("\"").split("~")
        if len(fields) < 4:
            continue
        try:
            px = float(fields[3])
            if px <= 0:
                continue
            tk = inv.get(symbol)
            if tk:
                out[tk] = (px, dt.datetime.utcnow())
        except ValueError:
            continue
    return out


def fetch_stock_names_eastmoney(tickers: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for ticker in tickers:
        try:
            secid = to_eastmoney_secid(ticker)
            params = urlencode({"fields": "f58,f57", "secid": secid})
            url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
            payload = fetch_json(url)
            data = payload.get("data") or {}
            name = data.get("f58")
            if isinstance(name, str) and name.strip():
                out[ticker] = name.strip()
        except Exception:
            continue
    return out


def fetch_stock_names_tencent(tickers: List[str]) -> Dict[str, str]:
    if not tickers:
        return {}
    symbols = [to_tencent_symbol(t) for t in tickers]
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=20) as resp:
            text = resp.read().decode("gbk", errors="ignore")
    except Exception:
        return {}

    inv = {to_tencent_symbol(t): t for t in tickers}
    out: Dict[str, str] = {}
    for ln in [x.strip() for x in text.split(";") if x.strip()]:
        if "~" not in ln:
            continue
        left, right = ln.split("=", 1)
        symbol = left.split("_")[-1].strip()
        fields = right.strip().strip("\"").split("~")
        if len(fields) < 2:
            continue
        name = fields[1].strip()
        tk = inv.get(symbol)
        if tk and name:
            out[tk] = name
    return out


def is_mainland_etf_code(code: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    sh_prefix = ("510", "511", "512", "513", "515", "516", "517", "518", "56", "58")
    sz_prefix = ("159", "16")
    return code.startswith(sh_prefix) or code.startswith(sz_prefix)


def fetch_cn_etf_universe_eastmoney(limit: int = 2000) -> List[str]:
    """
    获取大陆 ETF 列表（沪深基金市场），失败时由上层回退内置 ETF 池。
    """
    params = {
        "pn": "1",
        "pz": str(max(50, min(limit, 5000))),
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:1 t:8,m:0 t:8",
        "fields": "f12,f13,f14",
    }
    url = f"https://push2.eastmoney.com/api/qt/clist/get?{urlencode(params)}"
    payload = fetch_json(url)
    diff = ((payload.get("data") or {}).get("diff")) or []
    out: List[str] = []
    for item in diff:
        code = str(item.get("f12") or "").strip()
        market = int(item.get("f13") or -1)
        if not is_mainland_etf_code(code):
            continue
        if market == 1:
            out.append(f"{code}.SS")
        elif market == 0:
            out.append(f"{code}.SZ")
    return list(dict.fromkeys(out))


def fetch_live_data(
    tickers: List[str], start: dt.date, end: dt.date, providers: List[str]
) -> Dict[str, List[Row]]:
    data: Dict[str, List[Row]] = defaultdict(list)
    errors: List[str] = []
    stale_cutoff = end - dt.timedelta(days=7)

    for t in tickers:
        best_rows: List[Row] = []
        best_last_date = dt.date(1900, 1, 1)
        for provider in providers:
            try:
                if provider == "yahoo":
                    rows = fetch_yahoo_history(t, start, end)
                elif provider == "eastmoney":
                    rows = fetch_eastmoney_history(t, start, end)
                elif provider == "tencent":
                    rows = fetch_tencent_history(t, start, end)
                elif provider == "stooq":
                    rows = fetch_stooq_history(t, start, end)
                else:
                    raise RuntimeError(f"unknown provider: {provider}")

                if len(rows) >= 120:
                    last_date = rows[-1].date
                    if (last_date > best_last_date) or (last_date == best_last_date and len(rows) > len(best_rows)):
                        best_rows = rows
                        best_last_date = last_date
            except RuntimeError as exc:
                errors.append(f"{provider}:{t}: {exc}")

        if best_rows:
            if best_last_date < stale_cutoff:
                errors.append(f"stale data for {t}: latest={best_last_date.isoformat()} cutoff={stale_cutoff.isoformat()}")
            else:
                data[t] = best_rows
        else:
            errors.append(f"all providers failed for {t}")

    if not data:
        raise RuntimeError("Live download failed for all tickers. " + " | ".join(errors[:8]))

    if errors:
        print("[WARN] Some provider/ticker combinations failed and were skipped.")

    return data


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (ticker, date)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS realtime_quotes (
            ticker TEXT PRIMARY KEY,
            price REAL NOT NULL,
            ts_utc TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS instrument_names (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_utc TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_history_to_db(db_path: str, data: Dict[str, List[Row]]) -> None:
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for ticker, rows in data.items():
        for r in rows:
            cur.execute(
                """
                INSERT OR REPLACE INTO price_history (ticker, date, close, high, low, volume)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ticker, r.date.isoformat(), r.close, r.high, r.low, r.volume),
            )
    conn.commit()
    conn.close()


def save_quotes_to_db(db_path: str, quotes: Dict[str, Tuple[float, dt.datetime]]) -> None:
    if not quotes:
        return
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for ticker, (price, ts) in quotes.items():
        cur.execute(
            "INSERT OR REPLACE INTO realtime_quotes (ticker, price, ts_utc) VALUES (?, ?, ?)",
            (ticker, price, ts.isoformat()),
        )
    conn.commit()
    conn.close()


def load_history_from_db(db_path: str, tickers: List[str], start: dt.date, end: dt.date) -> Dict[str, List[Row]]:
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    data: Dict[str, List[Row]] = defaultdict(list)
    for tk in tickers:
        cur.execute(
            """
            SELECT date, close, high, low, volume
            FROM price_history
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (tk, start.isoformat(), end.isoformat()),
        )
        for d, c, h, l, v in cur.fetchall():
            data[tk].append(
                Row(
                    date=dt.datetime.strptime(d, "%Y-%m-%d").date(),
                    ticker=tk,
                    close=float(c),
                    high=float(h),
                    low=float(l),
                    volume=float(v),
                )
            )
    conn.close()
    return data


def load_latest_quotes_from_db(db_path: str, tickers: List[str]) -> Dict[str, Tuple[float, dt.datetime]]:
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    out: Dict[str, Tuple[float, dt.datetime]] = {}
    for tk in tickers:
        cur.execute("SELECT price, ts_utc FROM realtime_quotes WHERE ticker = ?", (tk,))
        row = cur.fetchone()
        if row:
            out[tk] = (float(row[0]), dt.datetime.fromisoformat(row[1]))
    conn.close()
    return out


def merge_with_db_history(
    live_data: Dict[str, List[Row]],
    db_data: Dict[str, List[Row]],
) -> Dict[str, List[Row]]:
    """
    Merge live and DB history by ticker/date.
    Priority: live row > db row when date overlaps.
    """
    out: Dict[str, List[Row]] = {}
    tickers = set(live_data.keys()) | set(db_data.keys())
    for tk in tickers:
        merged: Dict[dt.date, Row] = {}
        for r in db_data.get(tk, []):
            merged[r.date] = r
        for r in live_data.get(tk, []):
            merged[r.date] = r
        if merged:
            out[tk] = [merged[d] for d in sorted(merged.keys())]
    return out


def filter_fresh_quotes(
    quotes: Dict[str, Tuple[float, dt.datetime]],
    min_ts_utc: dt.datetime,
) -> Dict[str, Tuple[float, dt.datetime]]:
    """
    Keep only quotes newer than min_ts_utc.
    This avoids mixing stale db-only quotes with fresh live-mode quotes.
    """
    out: Dict[str, Tuple[float, dt.datetime]] = {}
    for tk, (px, ts) in quotes.items():
        if ts >= min_ts_utc:
            out[tk] = (px, ts)
    return out


def save_names_to_db(db_path: str, names: Dict[str, str]) -> None:
    if not names:
        return
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ts = dt.datetime.utcnow().isoformat()
    for tk, nm in names.items():
        cur.execute(
            "INSERT OR REPLACE INTO instrument_names (ticker, name, updated_utc) VALUES (?, ?, ?)",
            (tk, nm, ts),
        )
    conn.commit()
    conn.close()


def load_names_from_db(db_path: str, tickers: List[str]) -> Dict[str, str]:
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    out: Dict[str, str] = {}
    for tk in tickers:
        cur.execute("SELECT name FROM instrument_names WHERE ticker = ?", (tk,))
        row = cur.fetchone()
        if row and row[0]:
            out[tk] = str(row[0])
    conn.close()
    return out


def generate_demo_data(seed: int = 42) -> Dict[str, List[Row]]:
    random.seed(seed)
    tickers = DEFAULT_TICKERS
    start = dt.date(2022, 1, 3)
    days = 900
    out: Dict[str, List[Row]] = defaultdict(list)

    for ticker in tickers:
        price = random.uniform(30, 300)
        base_vol = random.uniform(8e5, 4e6)
        drift = random.uniform(0.0001, 0.0007)
        cyc = random.uniform(0.0, 0.0005)

        d = start
        made = 0
        while made < days:
            if d.weekday() >= 5:
                d += dt.timedelta(days=1)
                continue

            noise = random.gauss(0, 0.018)
            phase = math.sin(made / 35.0)
            ret = drift + cyc * phase + noise
            next_price = max(price * (1 + ret), 1.0)

            high = max(price, next_price) * (1 + abs(random.gauss(0, 0.005)))
            low = min(price, next_price) * (1 - abs(random.gauss(0, 0.005)))
            volume = max(base_vol * (1 + random.gauss(0, 0.2)), 1)

            out[ticker].append(Row(date=d, ticker=ticker, close=next_price, high=high, low=low, volume=volume))
            price = next_price
            d += dt.timedelta(days=1)
            made += 1

    return out


def build_benchmark_ret_map(data: Dict[str, List[Row]], benchmark_ticker: str) -> Dict[dt.date, float]:
    rows = data.get(benchmark_ticker, [])
    if len(rows) < 40:
        return {}
    by_date = {r.date: r.close for r in rows}
    dates = sorted(by_date.keys())
    ret_map: Dict[dt.date, float] = {}
    for i in range(5, len(dates)):
        d0 = dates[i - 5]
        d1 = dates[i]
        c0 = by_date[d0]
        c1 = by_date[d1]
        if c0 > 0:
            ret_map[d1] = c1 / c0 - 1.0
    return ret_map


def build_benchmark_close_map(data: Dict[str, List[Row]], benchmark_ticker: str) -> Dict[dt.date, float]:
    rows = data.get(benchmark_ticker, [])
    return {r.date: r.close for r in rows}


def build_samples(data: Dict[str, List[Row]], horizon: int, benchmark_ticker: str) -> List[Sample]:
    samples: List[Sample] = []
    eps = 1e-9
    bm_5d_ret = build_benchmark_ret_map(data, benchmark_ticker)
    bm_close_map = build_benchmark_close_map(data, benchmark_ticker)

    for ticker, rows in data.items():
        if ticker == benchmark_ticker:
            continue
        closes = [r.close for r in rows]
        highs = [r.high for r in rows]
        lows = [r.low for r in rows]
        vols = [r.volume for r in rows]

        for i in range(30, len(rows) - horizon):
            ret_1d = closes[i] / closes[i - 1] - 1.0
            ret_5d = closes[i] / closes[i - 5] - 1.0
            ret_20d = closes[i] / closes[i - 20] - 1.0
            bm_ret_5d = bm_5d_ret.get(rows[i].date, 0.0)
            rel_ret_5d = ret_5d - bm_ret_5d
            daily_rets = [closes[j] / closes[j - 1] - 1.0 for j in range(i - 19, i + 1)]
            vol_20d = rolling_std(daily_rets)
            vol_ratio = vols[i] / (rolling_mean(vols[i - 19 : i + 1]) + eps)
            ma10 = rolling_mean(closes[i - 9 : i + 1])
            ma30 = rolling_mean(closes[i - 29 : i + 1])
            ma_gap = (ma10 - ma30) / (ma30 + eps)
            low20 = min(lows[i - 19 : i + 1])
            high20 = max(highs[i - 19 : i + 1])
            pos20 = (closes[i] - low20) / (high20 - low20 + eps)
            future_ret = closes[i + horizon] / closes[i] - 1.0
            # v6: 以“同起止日期的超额收益”作为标签，更贴近指数增强目标
            d0 = rows[i].date
            d1 = rows[i + horizon].date
            if d0 in bm_close_map and d1 in bm_close_map and bm_close_map[d0] > 0:
                future_bm_ret = bm_close_map[d1] / bm_close_map[d0] - 1.0
                target = 1 if (future_ret - future_bm_ret) > 0 else 0
            else:
                target = 1 if future_ret > 0 else 0

            samples.append(
                Sample(
                    date=rows[i].date,
                    ticker=ticker,
                    features=[ret_1d, ret_5d, ret_20d, rel_ret_5d, vol_20d, vol_ratio, ma_gap, pos20],
                    target=target,
                    close=closes[i],
                )
            )

    samples.sort(key=lambda x: x.date)
    return samples


def train_test_split(samples: List[Sample], split_ratio: float = 0.8) -> Tuple[List[Sample], List[Sample]]:
    dates = sorted({s.date for s in samples})
    cutoff = dates[max(1, int(len(dates) * split_ratio)) - 1]
    train = [s for s in samples if s.date <= cutoff]
    test = [s for s in samples if s.date > cutoff]
    return train, test


def standardize(
    train: List[Sample], test: List[Sample]
) -> Tuple[List[List[float]], List[int], List[List[float]], List[int], List[float], List[float]]:
    n = len(train[0].features)
    means = [0.0] * n
    stds = [0.0] * n

    for k in range(n):
        col = [s.features[k] for s in train]
        means[k] = rolling_mean(col)
        stds[k] = max(rolling_std(col), 1e-8)

    def norm(v: List[float]) -> List[float]:
        return [(v[k] - means[k]) / stds[k] for k in range(n)]

    x_train = [norm(s.features) for s in train]
    y_train = [s.target for s in train]
    x_test = [norm(s.features) for s in test]
    y_test = [s.target for s in test]
    return x_train, y_train, x_test, y_test, means, stds


def train_logistic_sgd(
    x: List[List[float]], y: List[int], epochs: int = 45, lr: float = 0.035, l2: float = 2e-4
) -> Tuple[List[float], float]:
    n_feat = len(x[0])
    w = [0.0] * n_feat
    b = 0.0
    rng = random.Random(123)
    idx = list(range(len(x)))

    for _ in range(epochs):
        rng.shuffle(idx)
        for i in idx:
            z = sum(w[j] * x[i][j] for j in range(n_feat)) + b
            p = sigmoid(z)
            err = p - y[i]
            for j in range(n_feat):
                grad = err * x[i][j] + l2 * w[j]
                w[j] -= lr * grad
            b -= lr * err
    return w, b


def predict_prob(w: List[float], b: float, x: List[List[float]]) -> List[float]:
    return [sigmoid(sum(w[j] * row[j] for j in range(len(w))) + b) for row in x]


def best_threshold(y_true: List[int], y_prob: List[float]) -> float:
    best_t, best_f1 = 0.5, -1.0
    for k in range(20, 81):
        t = k / 100
        y_pred = [1 if p >= t else 0 for p in y_prob]
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
    return best_t


def compute_metrics(y_true: List[int], y_prob: List[float], threshold: float = 0.5) -> Metrics:
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    acc = (tp + tn) / max(len(y_true), 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)

    pos_scores = [p for p, y in zip(y_prob, y_true) if y == 1]
    neg_scores = [p for p, y in zip(y_prob, y_true) if y == 0]
    if not pos_scores or not neg_scores:
        auc = 0.5
    else:
        better = 0.0
        total = len(pos_scores) * len(neg_scores)
        for p in pos_scores:
            for n in neg_scores:
                if p > n:
                    better += 1
                elif p == n:
                    better += 0.5
        auc = better / total

    return Metrics(accuracy=acc, precision=prec, recall=rec, auc=auc)


def rank_latest(
    samples: List[Sample],
    w: List[float],
    b: float,
    means: List[float],
    stds: List[float],
    topn: int,
    latest_quote: Optional[Dict[str, Tuple[float, dt.datetime]]] = None,
):
    latest_date = max(s.date for s in samples)
    latest = [s for s in samples if s.date == latest_date]

    ranked = []
    for s in latest:
        x = [(s.features[i] - means[i]) / stds[i] for i in range(len(means))]
        p = sigmoid(sum(w[j] * x[j] for j in range(len(w))) + b)
        risk_20d = s.features[4] if len(s.features) > 4 else 0.0

        if latest_quote and s.ticker in latest_quote:
            live_px, live_ts = latest_quote[s.ticker]
            ranked.append((s.ticker, live_px, p, risk_20d, f"live@{live_ts.isoformat()}Z"))
        else:
            ranked.append((s.ticker, s.close, p, risk_20d, f"daily@{latest_date.isoformat()}"))

    ranked.sort(key=lambda x: x[2], reverse=True)
    top = ranked[:topn]
    while len(top) < topn:
        top.append((f"N/A_{len(top)+1}", 0.0, 0.0, 0.0, "insufficient_universe"))
    return latest_date, top


def load_prev_weights(path: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not path:
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                tk = (r.get("ticker") or "").strip()
                wt = (r.get("weight") or "").strip()
                if not tk:
                    continue
                try:
                    out[tk] = float(wt)
                except ValueError:
                    continue
    except FileNotFoundError:
        return {}
    return out


def save_weights(path: str, portfolio: List[Tuple[str, float, float, float, str]]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "weight", "up_prob", "risk_20d", "source"])
        for tk, wt, p, risk, src in portfolio:
            writer.writerow([tk, f"{wt:.8f}", f"{p:.6f}", f"{risk:.6f}", src])


def estimate_turnover(prev_w: Dict[str, float], new_w: Dict[str, float]) -> float:
    names = set(prev_w.keys()) | set(new_w.keys())
    return 0.5 * sum(abs(new_w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in names)


def build_portfolio(
    top_ranked: List[Tuple[str, float, float, float, str]],
    max_weight: float = 0.2,
    risk_aversion: float = 0.15,
    cost_penalty: float = 0.10,
    prev_weights: Optional[Dict[str, float]] = None,
) -> List[Tuple[str, float, float, float, str]]:
    if not top_ranked:
        return []
    prev_weights = prev_weights or {}

    scores = []
    for tk, _, p, risk20, _ in top_ranked:
        base_alpha = max(p - 0.5, 0.0)
        trade_cost_proxy = prev_weights.get(tk, 0.0)
        score = base_alpha - risk_aversion * max(risk20, 0.0) - cost_penalty * max(0.0, 1.0 - trade_cost_proxy)
        scores.append(max(score, 0.0))
    if sum(scores) <= 1e-12:
        scores = [p for _, _, p, _, _ in top_ranked]

    s = sum(scores)
    w = [x / s for x in scores]
    w = [min(x, max_weight) for x in w]

    # re-normalize after cap
    s2 = sum(w)
    if s2 > 0:
        w = [x / s2 for x in w]

    portfolio = []
    for (tk, _, p, risk20, src), weight in zip(top_ranked, w):
        portfolio.append((tk, weight, p, risk20, src))
    return portfolio


def parse_tickers(tickers_str: str) -> List[str]:
    return [t.strip() for t in tickers_str.split(",") if t.strip()]


def ensure_ticker_pool_size(tickers: List[str], topn: int, benchmark: str) -> List[str]:
    needed = max(topn + 1, 12)  # +1 because benchmark may be excluded from candidates
    out = list(dict.fromkeys(tickers))
    if benchmark not in out:
        out.insert(0, benchmark)
    for tk in DEFAULT_TICKERS:
        if len(out) >= needed:
            break
        if tk not in out:
            out.append(tk)
    return out


def stock_name(ticker: str, runtime_names: Optional[Dict[str, str]] = None) -> str:
    if runtime_names and ticker in runtime_names and runtime_names[ticker]:
        return runtime_names[ticker]
    return STOCK_NAME_MAP.get(ticker, ticker)


def parse_int_list(s: str) -> List[int]:
    out: List[int] = []
    for x in s.split(","):
        x = x.strip()
        if not x:
            continue
        out.append(int(x))
    return out


def parse_float_list(s: str) -> List[float]:
    out: List[float] = []
    for x in s.split(","):
        x = x.strip()
        if not x:
            continue
        out.append(float(x))
    return out


def normalize_weights(ws: List[float], n: int) -> List[float]:
    if len(ws) != n or sum(ws) <= 0:
        return [1.0 / n] * n
    s = sum(ws)
    return [x / s for x in ws]


def write_one_year_report(
    path: str,
    horizons: List[int],
    horizon_weight_map: Dict[int, float],
    per_horizon_test: Dict[int, List[Tuple[dt.date, str, float, int]]],
) -> Tuple[float, int]:
    """
    返回 (overall_win_rate, total_selected)
    """
    if not path:
        return 0.0, 0

    # 聚合多周期测试集概率
    from collections import defaultdict

    agg_num = defaultdict(float)
    agg_den = defaultdict(float)
    labels: Dict[Tuple[dt.date, str], int] = {}
    for h in horizons:
        recs = per_horizon_test.get(h, [])
        w = horizon_weight_map.get(h, 0.0)
        for d, tk, p, y in recs:
            k = (d, tk)
            agg_num[k] += w * p
            agg_den[k] += w
            labels[k] = y

    by_day: Dict[dt.date, List[Tuple[float, int]]] = defaultdict(list)
    for k, num in agg_num.items():
        den = agg_den[k]
        if den <= 0:
            continue
        p = num / den
        by_day[k[0]].append((p, labels.get(k, 0)))

    rows = []
    total_sel = 0
    total_win = 0
    for d in sorted(by_day.keys()):
        arr = by_day[d]
        arr.sort(key=lambda x: x[0], reverse=True)
        n = max(1, int(len(arr) * 0.2))  # top20%
        sel = arr[:n]
        wins = sum(1 for p, y in sel if y == 1)
        wr = wins / n if n else 0.0
        total_sel += n
        total_win += wins
        rows.append((d.isoformat(), n, wins, wr))

    overall_wr = (total_win / total_sel) if total_sel else 0.0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "selected_count", "wins", "daily_win_rate"])
        w.writerows(rows)
        w.writerow([])
        w.writerow(["overall", total_sel, total_win, f"{overall_wr:.6f}"])

    return overall_wr, total_sel


def auto_tune_horizon_weights(
    horizons: List[int],
    per_horizon_test: Dict[int, List[Tuple[dt.date, str, float, int]]],
) -> List[float]:
    """
    根据每个周期在测试集上 top20% 的胜率自动分配融合权重。
    权重分数 = max(win_rate - 0.5, 0.0001) * log(1 + selected_count)
    """
    scores: List[float] = []
    for h in horizons:
        recs = per_horizon_test.get(h, [])
        if not recs:
            scores.append(0.0)
            continue
        by_day: Dict[dt.date, List[Tuple[float, int]]] = defaultdict(list)
        for d, _tk, p, y in recs:
            by_day[d].append((p, y))
        total_sel = 0
        total_win = 0
        for d in by_day:
            arr = sorted(by_day[d], key=lambda x: x[0], reverse=True)
            n = max(1, int(len(arr) * 0.2))
            sel = arr[:n]
            wins = sum(1 for _p, y in sel if y == 1)
            total_sel += n
            total_win += wins
        wr = (total_win / total_sel) if total_sel else 0.0
        edge = max(wr - 0.5, 0.0001)
        score = edge * math.log1p(total_sel)
        scores.append(score)
    return normalize_weights(scores, len(horizons))


def parse_providers(providers_str: str) -> List[str]:
    out = [p.strip().lower() for p in providers_str.split(",") if p.strip()]
    valid = {"eastmoney", "tencent", "yahoo", "stooq"}
    for p in out:
        if p not in valid:
            raise ValueError(f"unsupported provider: {p}")
    return out


def main():
    parser = argparse.ArgumentParser(description="A/H Alpha Pro v10 (multi-horizon ensemble for index enhancement)")
    parser.add_argument("--input-csv", type=str, default="", help="CSV path with columns: date,ticker,close,high,low,volume")
    parser.add_argument(
        "--tickers",
        type=str,
        default=",".join(DEFAULT_TICKERS),
        help="Tickers for live download mode",
    )
    parser.add_argument("--cn-etf-rotation", action="store_true", help="Use mainland ETF universe for rotation recommendation")
    parser.add_argument("--cn-etf-limit", type=int, default=800, help="Max ETF symbols to load from Eastmoney universe API")
    parser.add_argument("--providers", type=str, default="eastmoney,tencent,yahoo,stooq", help="Data providers in priority order")
    parser.add_argument("--start", type=str, default="2021-01-01")
    parser.add_argument("--end", type=str, default=dt.date.today().isoformat())
    parser.add_argument("--horizon", type=int, default=5, help="Single horizon fallback (legacy)")
    parser.add_argument("--horizons", type=str, default="5,10,20", help="Multi-horizon labels, e.g. 5,10,20")
    parser.add_argument("--horizon-weights", type=str, default="0.2,0.3,0.5", help="Weights for horizons")
    parser.add_argument(
        "--auto-tune-horizon-weights",
        action="store_true",
        help="Auto-tune horizon fusion weights from backtest win-rate on the holdout split.",
    )
    parser.add_argument("--topn", type=int, default=5)
    parser.add_argument("--benchmark", type=str, default="000300.SS", help="Benchmark ticker for excess-return label")
    parser.add_argument("--max-weight", type=float, default=0.35, help="Max single-stock weight in suggested portfolio")
    parser.add_argument("--risk-aversion", type=float, default=0.15, help="Penalty coefficient for risk_20d in portfolio scoring")
    parser.add_argument("--cost-penalty", type=float, default=0.10, help="Penalty coefficient for turnover proxy in scoring")
    parser.add_argument("--prev-weights", type=str, default="", help="Previous portfolio weights CSV path (ticker,weight)")
    parser.add_argument("--save-weights", type=str, default="", help="Output CSV path to save new suggested weights")
    parser.add_argument("--report-csv", type=str, default="", help="Export one-year backtest daily win-rate report CSV")
    parser.add_argument("--db-path", type=str, default="alpha_realtime.db", help="SQLite path for realtime/history cache")
    parser.set_defaults(db_only=False)
    parser.add_argument("--db-only", dest="db_only", action="store_true", help="Run using local realtime database only")
    parser.add_argument("--no-db-only", dest="db_only", action="store_false", help="Allow network fetch/refresh (default)")
    parser.add_argument("--demo", action="store_true", help="Force synthetic demo data")
    parser.add_argument("--no-realtime", action="store_true", help="Disable realtime quote refresh")
    parser.add_argument("--min-samples", type=int, default=500, help="Minimum sample count required per horizon")
    args = parser.parse_args()

    latest_quote: Dict[str, Tuple[float, dt.datetime]] = {}
    runtime_names: Dict[str, str] = {}

    if args.input_csv:
        data = parse_csv(args.input_csv)
        source = f"CSV: {args.input_csv}"
        save_history_to_db(args.db_path, data)
    elif args.demo:
        data = generate_demo_data(seed=42)
        source = "synthetic demo data"
        save_history_to_db(args.db_path, data)
    else:
        start = dt.datetime.strptime(args.start, "%Y-%m-%d").date()
        end = dt.datetime.strptime(args.end, "%Y-%m-%d").date()
        if args.cn_etf_rotation:
            try:
                etf_pool = fetch_cn_etf_universe_eastmoney(limit=args.cn_etf_limit)
                if not etf_pool:
                    raise RuntimeError("empty ETF universe from eastmoney")
            except RuntimeError as exc:
                print(f"[WARN] cn-etf universe fetch failed, fallback built-in ETF pool: {exc}")
                etf_pool = DEFAULT_CN_ETF_TICKERS[:]
            if args.benchmark == "000300.SS":
                args.benchmark = "510300.SS"
            tickers = ensure_ticker_pool_size(etf_pool, max(args.topn, 20), args.benchmark)
        else:
            tickers = ensure_ticker_pool_size(parse_tickers(args.tickers), args.topn, args.benchmark)
        providers = parse_providers(args.providers)
        if args.db_only:
            data = load_history_from_db(args.db_path, tickers, start, end)
            latest_quote = load_latest_quotes_from_db(args.db_path, tickers)
            fresh_cutoff = dt.datetime.combine(end, dt.time.min)
            latest_quote = filter_fresh_quotes(latest_quote, fresh_cutoff)
            runtime_names = load_names_from_db(args.db_path, tickers)
            source = f"local realtime db [{args.db_path}] [{start}..{end}]"
        else:
            try:
                live_data = fetch_live_data(tickers, start, end, providers)
                source = f"latest daily via {providers} [{start}..{end}]"
                db_data = load_history_from_db(args.db_path, tickers, start, end)
                data = merge_with_db_history(live_data, db_data)
                save_history_to_db(args.db_path, data)
            except RuntimeError as exc:
                print(f"[WARN] live fetch failed, fallback to db: {exc}")
                data = load_history_from_db(args.db_path, tickers, start, end)
                source = f"fallback local db [{args.db_path}] [{start}..{end}]"

            if not args.no_realtime:
                try:
                    latest_quote = fetch_latest_quote_eastmoney(list(data.keys()))
                    if not latest_quote:
                        latest_quote = fetch_latest_quote_tencent(list(data.keys()))
                    if not latest_quote:
                        latest_quote = fetch_latest_quote_yahoo(list(data.keys()))
                    save_quotes_to_db(args.db_path, latest_quote)
                except RuntimeError as exc:
                    print(f"[WARN] realtime quote refresh failed, use db quote: {exc}")
                    latest_quote = load_latest_quotes_from_db(args.db_path, list(data.keys()))
            fresh_cutoff = dt.datetime.combine(end, dt.time.min)
            latest_quote = filter_fresh_quotes(latest_quote, fresh_cutoff)

            # 优先获取股票中文名并入库
            runtime_names = fetch_stock_names_eastmoney(list(data.keys()))
            if len(runtime_names) < len(data):
                more = fetch_stock_names_tencent(list(data.keys()))
                runtime_names.update({k: v for k, v in more.items() if k not in runtime_names})
            if runtime_names:
                save_names_to_db(args.db_path, runtime_names)
            else:
                runtime_names = load_names_from_db(args.db_path, list(data.keys()))

    horizons = parse_int_list(args.horizons) or [args.horizon]
    h_weights = normalize_weights(parse_float_list(args.horizon_weights), len(horizons))

    per_horizon_maps: Dict[int, Dict[str, Tuple[float, float, float, str]]] = {}
    per_horizon_test: Dict[int, List[Tuple[dt.date, str, float, int]]] = {}
    metrics_rows: List[Tuple[int, int, int, float, float, float, float]] = []
    latest_dates: List[dt.date] = []

    min_samples_required = max(50, args.min_samples)
    if args.cn_etf_rotation and args.min_samples == 500:
        min_samples_required = 180

    for h in horizons:
        samples_h = build_samples(data, horizon=h, benchmark_ticker=args.benchmark)
        if len(samples_h) < min_samples_required:
            continue
        train, test = train_test_split(samples_h, split_ratio=0.8)
        if not train or not test:
            continue
        x_train, y_train, x_test, y_test, means, stds = standardize(train, test)
        w, b = train_logistic_sgd(x_train, y_train)
        probs = predict_prob(w, b, x_test)
        t = best_threshold(y_test, probs)
        m = compute_metrics(y_test, probs, threshold=t)
        metrics_rows.append((h, len(train), len(test), t, m.accuracy, m.precision, m.auc))
        per_horizon_test[h] = [(row.date, row.ticker, pp, yy) for row, pp, yy in zip(test, probs, y_test)]

        latest_date = max(s.date for s in samples_h)
        latest_dates.append(latest_date)
        latest = [s for s in samples_h if s.date == latest_date]
        mapp: Dict[str, Tuple[float, float, float, str]] = {}
        for s in latest:
            x = [(s.features[i] - means[i]) / stds[i] for i in range(len(means))]
            p = sigmoid(sum(w[j] * x[j] for j in range(len(w))) + b)
            risk20 = s.features[4] if len(s.features) > 4 else 0.0
            if latest_quote and s.ticker in latest_quote:
                px, ts = latest_quote[s.ticker]
                src = f"live@{ts.isoformat()}Z"
            else:
                px, src = s.close, f"daily@{latest_date.isoformat()}"
            mapp[s.ticker] = (px, p, risk20, src)
        per_horizon_maps[h] = mapp

    if not per_horizon_maps and args.cn_etf_rotation:
        print("[WARN] ETF mode: multi-horizon samples insufficient, fallback to single horizon=5 with relaxed threshold.")
        h = 5
        samples_h = build_samples(data, horizon=h, benchmark_ticker=args.benchmark)
        if len(samples_h) >= 120:
            train, test = train_test_split(samples_h, split_ratio=0.8)
            if train and test:
                x_train, y_train, x_test, y_test, means, stds = standardize(train, test)
                w, b = train_logistic_sgd(x_train, y_train)
                probs = predict_prob(w, b, x_test)
                t = best_threshold(y_test, probs)
                m = compute_metrics(y_test, probs, threshold=t)
                metrics_rows.append((h, len(train), len(test), t, m.accuracy, m.precision, m.auc))
                per_horizon_test[h] = [(row.date, row.ticker, pp, yy) for row, pp, yy in zip(test, probs, y_test)]
                latest_date = max(s.date for s in samples_h)
                latest_dates.append(latest_date)
                latest = [s for s in samples_h if s.date == latest_date]
                mapp: Dict[str, Tuple[float, float, float, str]] = {}
                for s in latest:
                    x = [(s.features[i] - means[i]) / stds[i] for i in range(len(means))]
                    p = sigmoid(sum(w[j] * x[j] for j in range(len(w))) + b)
                    risk20 = s.features[4] if len(s.features) > 4 else 0.0
                    if latest_quote and s.ticker in latest_quote:
                        px, ts = latest_quote[s.ticker]
                        src = f"live@{ts.isoformat()}Z"
                    else:
                        px, src = s.close, f"daily@{latest_date.isoformat()}"
                    mapp[s.ticker] = (px, p, risk20, src)
                per_horizon_maps[h] = mapp
                horizons = [h]
                h_weights = [1.0]

    if not per_horizon_maps:
        raise ValueError("Not enough samples across configured horizons. Try longer history, --min-samples 180, or --db-only/--demo.")

    latest_date = max(latest_dates) if latest_dates else dt.date.today()
    tickers_union = set()
    for mp in per_horizon_maps.values():
        tickers_union.update(mp.keys())

    if args.auto_tune_horizon_weights:
        h_weights = auto_tune_horizon_weights(horizons, per_horizon_test)
    horizon_weight_map = {h: h_weights[i] for i, h in enumerate(horizons)}
    ranked_all: List[Tuple[str, float, float, float, str]] = []
    for tk in tickers_union:
        num = 0.0
        den = 0.0
        pick_price = 0.0
        pick_risk = 0.0
        pick_src = "N/A"
        # prefer longer horizon for quote/risk display
        for h in sorted(per_horizon_maps.keys(), reverse=True):
            mp = per_horizon_maps[h]
            if tk in mp:
                px, p, rk, src = mp[tk]
                w_h = horizon_weight_map.get(h, 0.0)
                num += w_h * p
                den += w_h
                if pick_src == "N/A":
                    pick_price, pick_risk, pick_src = px, rk, src
        if den <= 0:
            continue
        ranked_all.append((tk, pick_price, num / den, pick_risk, pick_src))

    ranked_all.sort(key=lambda x: x[2], reverse=True)
    top = ranked_all[: args.topn]
    while len(top) < args.topn:
        top.append((f"N/A_{len(top)+1}", 0.0, 0.0, 0.0, "insufficient_universe"))
    prev_w = load_prev_weights(args.prev_weights)
    portfolio = build_portfolio(
        top,
        max_weight=max(min(args.max_weight, 1.0), 0.01),
        risk_aversion=max(args.risk_aversion, 0.0),
        cost_penalty=max(args.cost_penalty, 0.0),
        prev_weights=prev_w,
    )
    new_w = {tk: wt for tk, wt, _, _, _ in portfolio}
    turnover = estimate_turnover(prev_w, new_w) if prev_w else 0.0
    save_weights(args.save_weights, portfolio)
    report_wr, report_n = write_one_year_report(args.report_csv, horizons, horizon_weight_map, per_horizon_test)

    run_ts = dt.datetime.utcnow().isoformat() + "Z"
    print("==============================================")
    print(" A/H ALPHA TERMINAL PRO v10")
    print(" Index Enhancement | Excess Return Engine")
    print("==============================================")
    print(f"Run Time (UTC) : {run_ts}")
    print(f"Data Source    : {source}")
    print(f"Realtime DB    : {args.db_path}")
    print(f"DB Only Mode   : {'ON' if args.db_only else 'OFF'}")
    if args.cn_etf_rotation:
        print(f"Universe Mode  : CN ETF Rotation ({len(tickers)} symbols)")
    print(f"Benchmark      : {args.benchmark}")
    print("Label Mode     : excess return > 0 (fallback: absolute return > 0)")
    print(f"Feature Set    : {', '.join(FEATURE_NAMES)}")
    print("----------------------------------------------")
    print(f"Horizons       : {horizons}")
    print(f"HorizonWeights : {[round(x, 4) for x in h_weights]}")
    if args.auto_tune_horizon_weights:
        print("HorizonWeightMode : auto_tuned_from_holdout")
    for h, trn, tst, thr, acc, prec, auc in metrics_rows:
        print(f"H{h:>2} -> Train/Test {trn:,}/{tst:,} | Thr {thr:.2f} | Acc {acc:.4f} | Prec {prec:.4f} | AUC {auc:.4f}")
    print("----------------------------------------------")
    print(f"TOP {args.topn} CANDIDATES @ model_date={latest_date.isoformat()}")
    for tk, px, p, risk20, src in top:
        nm = stock_name(tk, runtime_names)
        shown = f"{tk}({nm})"
        print(f"{shown:26s} px={px:10.3f} up_prob={p:.4f} risk20={risk20:.4f} [{src}]")

    print("----------------------------------------------")
    print("SUGGESTED PORTFOLIO (alpha+risk+cost)")
    for tk, wt, p, risk20, src in portfolio:
        nm = stock_name(tk, runtime_names)
        shown = f"{tk}({nm})"
        print(f"{shown:26s} weight={wt:6.2%} up_prob={p:.4f} risk20={risk20:.4f} [{src}]")
    if args.prev_weights:
        print(f"Estimated turnover vs prev portfolio: {turnover:.2%}")
    if args.save_weights:
        print(f"Saved new weights to: {args.save_weights}")
    if args.report_csv:
        print(f"Saved report CSV : {args.report_csv}")
        print(f"One-year Top20% win rate: {report_wr:.4f} (n={report_n})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("[ERROR] Strategy run failed.")
        print(f"[ERROR] {exc}")
        print("[HINT] Try: --providers tencent,yahoo,stooq  or  --db-only  or  --demo")
        raise SystemExit(1)
