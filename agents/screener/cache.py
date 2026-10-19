# SQLite cache for raw yfinance payloads and FX rates.
#
# The screener fetches each ticker once and re-uses it until it is older than
# --max-age-days, so repeat screens cost zero network calls. Raw payloads are
# stored (not derived metrics) so metric/scoring changes apply without a refetch.
# Bump SCHEMA_VERSION when fetch.py changes the payload shape.

import json
import sqlite3
import time
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "screener" / "cache.db"
SCHEMA_VERSION = 1


def _conn() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS tickers ("
                 "symbol TEXT PRIMARY KEY, fetched_at REAL, schema INTEGER, payload TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS fx ("
                 "currency TEXT PRIMARY KEY, fetched_at REAL, usd_rate REAL)")
    return conn


def get_many(symbols: list[str], max_age_days: float) -> tuple[dict, list[str]]:
    """Return ({symbol: payload} for fresh entries, [symbols needing a fetch]).
    A payload of None means the symbol was fetched recently and had no data."""
    cutoff = time.time() - max_age_days * 86400
    fresh: dict = {}
    with _conn() as conn:
        for i in range(0, len(symbols), 500):
            chunk = symbols[i:i + 500]
            q = f"SELECT symbol, fetched_at, schema, payload FROM tickers WHERE symbol IN ({','.join('?' * len(chunk))})"
            for sym, fetched_at, schema, payload in conn.execute(q, chunk):
                if schema == SCHEMA_VERSION and fetched_at >= cutoff:
                    fresh[sym] = json.loads(payload) if payload else None
    stale = [s for s in symbols if s not in fresh]
    return fresh, stale


def put(symbol: str, payload: dict | None) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO tickers VALUES (?, ?, ?, ?)",
                     (symbol, time.time(), SCHEMA_VERSION,
                      json.dumps(payload, default=str) if payload else None))


def get_fx(currency: str, max_age_days: float = 1.0) -> float | None:
    with _conn() as conn:
        row = conn.execute("SELECT fetched_at, usd_rate FROM fx WHERE currency = ?",
                           (currency,)).fetchone()
    if row and row[0] >= time.time() - max_age_days * 86400:
        return row[1]
    return None


def put_fx(currency: str, usd_rate: float) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO fx VALUES (?, ?, ?)",
                     (currency, time.time(), usd_rate))
