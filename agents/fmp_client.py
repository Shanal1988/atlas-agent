# Shared FMP API client with 429 rate-limit retry + yfinance fallback helpers.
#
# FMP plans have per-minute request limits; pipeline stages fire bursts of
# calls (peer metrics, size filters, screeners) that can trip 429s. Retry
# with backoff instead of silently returning None. When the FMP daily quota
# is exhausted, callers fall back to yfinance via yf_company_metrics().

import os
import time
import requests

FMP_BASE = "https://financialmodelingprep.com/stable"

# Circuit breaker: when the DAILY quota is exhausted ("Limit Reach" body),
# retrying is pointless — skip all FMP calls for a cooldown period so
# pipelines fail fast to their yfinance fallbacks.
_quota_exhausted_until: float = 0.0
_QUOTA_COOLDOWN_S = 600  # re-check every 10 minutes


def fmp_get(endpoint: str, params: dict, retries: int = 3) -> list | None:
    """FMP API call. Retries on 429 with backoff; skips calls entirely while
    the daily quota is exhausted. Returns list or None."""
    global _quota_exhausted_until
    if time.time() < _quota_exhausted_until:
        return None

    params["apikey"] = os.environ.get("FMP_API_KEY", "")
    for attempt in range(retries + 1):
        try:
            resp = requests.get(f"{FMP_BASE}{endpoint}", params=params, timeout=15)
        except Exception:
            return None

        if resp.status_code == 429 or "Limit Reach" in resp.text[:300]:
            if "Limit Reach" in resp.text[:300]:
                # Daily quota exhausted — no point retrying with backoff
                print(f"  [FMP] Daily quota exhausted — skipping FMP for {_QUOTA_COOLDOWN_S // 60} min (using yfinance fallbacks).")
                _quota_exhausted_until = time.time() + _QUOTA_COOLDOWN_S
                return None
            if attempt < retries:
                wait = 2 * (2 ** attempt)  # 2s, 4s, 8s
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = min(int(retry_after), 30)
                print(f"  [FMP] Rate limited on {endpoint} — retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [FMP] Rate limited on {endpoint} — giving up after {retries} retries.")
            return None

        if resp.status_code in (401, 402, 403, 404):
            return None
        try:
            resp.raise_for_status()
            data = resp.json()
            return data if data else None
        except Exception:
            return None
    return None

def yf_company_metrics(ticker: str) -> dict | None:
    """
    yfinance fallback for company profile/ratio metrics when FMP is
    rate-limited or has no data. Returns the same shape used by peer
    metric builders, or None if yfinance has nothing.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        if not info.get("marketCap") and not info.get("longName"):
            return None
        return {
            "ticker":           ticker,
            "name":             info.get("longName") or info.get("shortName"),
            "market_cap":       info.get("marketCap"),
            "price":            info.get("currentPrice") or info.get("regularMarketPrice"),
            "sector":           info.get("sector"),
            "industry":         info.get("industry"),
            "pe_ratio":         info.get("trailingPE"),
            "roe":              info.get("returnOnEquity"),
            "roic":             None,  # not provided by yfinance
            "revenue_growth":   info.get("revenueGrowth"),
            "operating_margin": info.get("operatingMargins"),
            "fcf_yield":        None,
        }
    except Exception:
        return None
