# Shared FMP API client with 429 rate-limit retry.
#
# FMP plans have per-minute request limits; pipeline stages fire bursts of
# calls (peer metrics, size filters, screeners) that can trip 429s. Retry
# with backoff instead of silently returning None.

import os
import time
import requests

FMP_BASE = "https://financialmodelingprep.com/stable"


def fmp_get(endpoint: str, params: dict, retries: int = 3) -> list | None:
    """FMP API call. Retries on 429 with backoff. Returns list or None."""
    params["apikey"] = os.environ.get("FMP_API_KEY", "")
    for attempt in range(retries + 1):
        try:
            resp = requests.get(f"{FMP_BASE}{endpoint}", params=params, timeout=15)
        except Exception:
            return None

        if resp.status_code == 429:
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
