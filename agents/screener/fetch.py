# yfinance fetcher — pulls the raw data the screener needs for one ticker.
#
# Free, no API key. Yahoo throttles aggressive clients, so callers fetch
# sequentially with a small delay and back off on rate-limit errors.
# Output is a JSON-safe payload in the company's native currencies; FX and
# metric derivation happen later in metrics.py.

import math
import time

from agents.screener import cache

_INFO_KEYS = [
    "longName", "shortName", "sector", "industry", "country", "exchange",
    "fullExchangeName", "currency", "financialCurrency", "marketCap",
    "sharesOutstanding", "currentPrice", "regularMarketPrice", "trailingPE",
    "forwardPE", "returnOnEquity", "grossMargins", "operatingMargins",
    "revenueGrowth", "totalRevenue", "totalCash", "totalDebt", "ebitda",
    "freeCashflow", "operatingCashflow", "heldPercentInsiders", "52WeekChange",
    "beta", "quoteType",
]

# payload key -> candidate yfinance row labels, newest label conventions first
_INCOME_ROWS = {
    "revenue":          ["Total Revenue", "Operating Revenue"],
    "gross_profit":     ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "net_income":       ["Net Income", "Net Income Common Stockholders"],
    "eps":              ["Diluted EPS", "Basic EPS"],
    "shares":           ["Diluted Average Shares", "Basic Average Shares"],
    "tax":              ["Tax Provision", "Income Tax Expense"],
    "pretax":           ["Pretax Income", "Income Before Tax"],
    "sm_expense":       ["Selling And Marketing Expense"],
}
_BALANCE_ROWS = {
    "total_assets":        ["Total Assets"],
    "current_liabilities": ["Current Liabilities"],
    "equity":              ["Stockholders Equity", "Total Stockholders Equity"],
    "total_debt":          ["Total Debt", "Long Term Debt"],
    "cash":                ["Cash And Cash Equivalents",
                            "Cash Cash Equivalents And Short Term Investments"],
}
_CASHFLOW_ROWS = {
    "operating_cash_flow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex":               ["Capital Expenditure"],
    "free_cash_flow":      ["Free Cash Flow"],
}


class RateLimited(Exception):
    pass


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _by_year(df, rows: dict) -> dict:
    """{year: {key: value}} from a yfinance statement DataFrame."""
    out: dict = {}
    if df is None or getattr(df, "empty", True):
        return out
    for col in df.columns:
        year = str(getattr(col, "year", col))
        vals = out.setdefault(year, {})
        for key, labels in rows.items():
            for label in labels:
                if label in df.index:
                    v = _num(df.loc[label, col])
                    if v is not None:
                        vals[key] = v
                        break
    return out


def _is_rate_limit(e: Exception) -> bool:
    text = f"{type(e).__name__} {e}".lower()
    return "ratelimit" in text.replace(" ", "") or "too many requests" in text or "429" in text


def fetch(symbol: str) -> dict | None:
    """Raw payload for one ticker, or None if Yahoo has no usable data."""
    import yfinance as yf

    t = yf.Ticker(symbol)
    try:
        info = t.info or {}
    except Exception as e:
        if _is_rate_limit(e):
            raise RateLimited(str(e))
        return None
    if not info.get("marketCap") and not (info.get("longName") or info.get("shortName")):
        return None

    def stmt(attr):
        try:
            return getattr(t, attr)
        except Exception as e:
            if _is_rate_limit(e):
                raise RateLimited(str(e))
            return None

    income = _by_year(stmt("income_stmt"), _INCOME_ROWS)
    balance = _by_year(stmt("balance_sheet"), _BALANCE_ROWS)
    cashflow = _by_year(stmt("cashflow"), _CASHFLOW_ROWS)

    annual = []
    for year in sorted(income, reverse=True):
        row = {"year": year, **income[year], **balance.get(year, {}), **cashflow.get(year, {})}
        if row.get("revenue") is not None:
            annual.append(row)

    quarterly = []
    qdf = stmt("quarterly_income_stmt")
    if qdf is not None and not getattr(qdf, "empty", True):
        for col in sorted(qdf.columns, reverse=True):
            for label in _INCOME_ROWS["revenue"]:
                if label in qdf.index and _num(qdf.loc[label, col]) is not None:
                    quarterly.append({"period": str(col.date()) if hasattr(col, "date") else str(col),
                                      "revenue": _num(qdf.loc[label, col])})
                    break

    return {
        "symbol": symbol,
        "info": {k: info.get(k) for k in _INFO_KEYS if info.get(k) is not None},
        "annual": annual,               # newest first
        "quarterly_revenue": quarterly,  # newest first
    }


def fetch_all(symbols: list[str], delay: float = 0.5) -> dict:
    """Fetch and cache each symbol sequentially. Stops early (keeping what was
    fetched) if Yahoo keeps rate-limiting or looks unreachable.

    Empty results are not cached: yfinance reports a network failure the same
    way as an unknown ticker, and caching it would hide the ticker for days."""
    results: dict = {}
    total = len(symbols)
    empty_streak = 0
    for i, sym in enumerate(symbols, 1):
        for attempt in range(2):
            try:
                payload = fetch(sym)
                results[sym] = payload
                if payload:
                    cache.put(sym, payload)
                    empty_streak = 0
                else:
                    empty_streak += 1
                break
            except RateLimited:
                if attempt == 0:
                    print(f"\n  [yfinance] Rate limited at {sym} — pausing 60s...")
                    time.sleep(60)
                else:
                    print(f"  [yfinance] Still rate limited — stopping after {i - 1}/{total}. "
                          "Re-run later; cached tickers are kept.")
                    return results
            except Exception as e:
                print(f"\n  [yfinance] {sym}: {type(e).__name__} — skipped.")
                empty_streak += 1
                break
        if empty_streak >= 10 and not any(results.values()):
            print(f"\n  [yfinance] No data for the first {i} tickers — Yahoo Finance looks unreachable. "
                  "Check your internet connection (or proxy/VPN) and re-run.")
            return results
        if i % 10 == 0 or i == total:
            print(f"\r  [yfinance] Fetched {i}/{total}", end="", flush=True)
        time.sleep(delay)
    if total:
        print()
    return results


# -- FX -------------------------------------------------------------------------

# Yahoo quotes some markets in minor units (pence, cents).
MINOR_UNITS = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


def usd_rate(currency: str | None) -> float | None:
    """USD per one unit of `currency` (major units). Cached for a day."""
    if not currency:
        return None
    currency = MINOR_UNITS.get(currency, (currency, 1))[0].upper()
    if currency == "USD":
        return 1.0
    cached = cache.get_fx(currency)
    if cached:
        return cached
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{currency}USD=X").history(period="5d")
        rate = _num(hist["Close"].dropna().iloc[-1]) if not hist.empty else None
    except Exception:
        rate = None
    if rate:
        cache.put_fx(currency, rate)
    return rate
