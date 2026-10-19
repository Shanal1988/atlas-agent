# Screener universes — free ticker lists stored as CSVs in data/universe/.
#
# Each universe is a CSV with columns symbol,name (Yahoo Finance symbols,
# exchange suffix included). Lines starting with '#' are comments. Some
# universes ship as small hand-picked seed lists; `refresh()` replaces them
# with full index constituents scraped from free public sources (Wikipedia,
# NSE archives, Nasdaq). Nothing here needs an API key.

import csv
import io
from pathlib import Path

UNIVERSE_DIR = Path(__file__).resolve().parents[2] / "data" / "universe"

_UA = {"User-Agent": "Mozilla/5.0 (atlas-agent screener; personal research)"}

_WIKI = "https://en.wikipedia.org/wiki/"

# name -> how to rebuild it. "symbol_cols" / "name_cols" are tried in order
# against each HTML table on the page; the first table with a match and at
# least `min_rows` rows wins.
SOURCES = {
    "us_sp500": {
        "url": _WIKI + "List_of_S%26P_500_companies", "symbol_cols": ["Symbol"],
        "name_cols": ["Security"], "suffix": "", "min_rows": 400,
    },
    "us_nasdaq100": {  # Wikipedia dropped its constituents table; Nasdaq's own API is free
        "json_url": "https://api.nasdaq.com/api/quote/list-type/nasdaq100",
        "symbol_cols": ["symbol"], "name_cols": ["companyName"], "suffix": "", "min_rows": 90,
    },
    "us_midcap400": {
        "url": _WIKI + "List_of_S%26P_400_companies", "symbol_cols": ["Symbol", "Ticker symbol"],
        "name_cols": ["Security", "Company"], "suffix": "", "min_rows": 300,
    },
    "us_smallcap600": {
        "url": _WIKI + "List_of_S%26P_600_companies", "symbol_cols": ["Symbol", "Ticker symbol"],
        "name_cols": ["Company", "Security"], "suffix": "", "min_rows": 450,
    },
    "uk_ftse100": {
        "url": _WIKI + "FTSE_100_Index", "symbol_cols": ["Ticker", "EPIC"],
        "name_cols": ["Company"], "suffix": ".L", "min_rows": 90,
    },
    "uk_ftse250": {
        "url": _WIKI + "FTSE_250_Index", "symbol_cols": ["Ticker", "EPIC"],
        "name_cols": ["Company"], "suffix": ".L", "min_rows": 200,
    },
    "europe_stoxx50": {
        "url": _WIKI + "EURO_STOXX_50", "symbol_cols": ["Ticker"],
        "name_cols": ["Name", "Company"], "suffix": None, "min_rows": 45,
    },
    "india_nifty500": {
        "csv_url": "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "symbol_cols": ["Symbol"], "name_cols": ["Company Name"], "suffix": ".NS", "min_rows": 400,
    },
}

# Region shortcuts for --regions
REGIONS = {
    "USA":    ["us_sp500", "us_midcap400"],
    "UK":     ["uk_ftse100", "uk_ftse250"],
    "Europe": ["europe_stoxx50"],
    "India":  ["india_nifty500"],
}

# Euro Stoxx 50 rows list a main listing venue rather than a Yahoo suffix.
_EU_VENUE_SUFFIX = {
    "xetra": ".DE", "frankfurt": ".DE", "paris": ".PA", "amsterdam": ".AS",
    "milan": ".MI", "borsa italiana": ".MI", "madrid": ".MC", "brussels": ".BR",
    "helsinki": ".HE", "dublin": ".IR", "lisbon": ".LS",
}


def available() -> list[str]:
    on_disk = {p.stem for p in UNIVERSE_DIR.glob("*.csv")}
    return sorted(on_disk | set(SOURCES))


def _path(name: str) -> Path:
    return UNIVERSE_DIR / f"{name}.csv"


def load(name: str) -> tuple[list[dict], bool]:
    """Return (rows, is_seed). Downloads the universe if no CSV exists yet."""
    path = _path(name)
    if not path.exists():
        print(f"  [Universe] {name}.csv not found — downloading constituents...")
        if not refresh(name):
            return [], False

    rows, is_seed = [], False
    with open(path, encoding="utf-8") as f:
        lines = []
        for line in f:
            if line.startswith("#"):
                is_seed = is_seed or "seed" in line.lower()
                continue
            lines.append(line)
    for r in csv.DictReader(lines):
        sym = (r.get("symbol") or "").strip()
        if sym:
            rows.append({"symbol": sym, "name": (r.get("name") or "").strip()})
    return rows, is_seed


def load_many(names: list[str]) -> list[dict]:
    seen, out = set(), []
    for name in names:
        rows, is_seed = load(name)
        if is_seed:
            print(f"  [Universe] {name} is a small seed list ({len(rows)} names). "
                  f"Run `python screen.py --refresh-universe {name}` for full constituents.")
        for r in rows:
            if r["symbol"] not in seen:
                seen.add(r["symbol"])
                out.append({**r, "universe": name})
    return out


# -- Refresh from free public sources ------------------------------------------

def _yahoo_symbol(raw: str, suffix: str | None, venue: str = "") -> str | None:
    sym = str(raw).strip().upper()
    if not sym or sym == "NAN":
        return None
    if suffix is None:  # Euro Stoxx: symbol may already carry a suffix
        if "." in sym:
            return sym
        v = venue.lower()
        for key, sfx in _EU_VENUE_SUFFIX.items():
            if key in v:
                return sym + sfx
        return None
    if suffix == "":
        return sym.replace(".", "-")  # BRK.B -> BRK-B
    sym = sym.rstrip(".")
    return sym.replace(".", "-") + suffix  # BT.A -> BT-A.L


def _pick_col(columns, candidates):
    for cand in candidates:
        for col in columns:
            if str(col).strip().lower() == cand.lower():
                return col
    return None


def refresh(name: str) -> bool:
    """Download full constituents for a universe. Returns True on success."""
    import pandas as pd
    import requests

    src = SOURCES.get(name)
    if not src:
        print(f"  [Universe] No download source for '{name}' — edit data/universe/{name}.csv by hand.")
        return False
    try:
        if "json_url" in src:
            resp = requests.get(src["json_url"], headers=_UA, timeout=20)
            resp.raise_for_status()
            tables = [pd.DataFrame(resp.json()["data"]["data"]["rows"])]
        elif "csv_url" in src:
            resp = requests.get(src["csv_url"], headers=_UA, timeout=20)
            resp.raise_for_status()
            tables = [pd.read_csv(io.StringIO(resp.text))]
        else:
            resp = requests.get(src["url"], headers=_UA, timeout=20)
            resp.raise_for_status()
            tables = pd.read_html(io.StringIO(resp.text))
    except Exception as e:
        print(f"  [Universe] Download failed for {name}: {type(e).__name__}: {e}")
        return False

    for df in tables:
        sym_col = _pick_col(df.columns, src["symbol_cols"])
        if sym_col is None or len(df) < src["min_rows"]:
            continue
        name_col = _pick_col(df.columns, src["name_cols"])
        venue_col = _pick_col(df.columns, ["Main listing", "Exchange", "Listing"])
        rows = []
        for _, r in df.iterrows():
            sym = _yahoo_symbol(r[sym_col], src["suffix"],
                                str(r[venue_col]) if venue_col is not None else "")
            if sym:
                rows.append({"symbol": sym,
                             "name": str(r[name_col]).strip() if name_col is not None else ""})
        if len(rows) >= src["min_rows"]:
            UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_path(name), "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["symbol", "name"])
                w.writeheader()
                w.writerows(rows)
            print(f"  [Universe] {name}: saved {len(rows)} constituents.")
            return True

    print(f"  [Universe] Could not find a constituents table for {name} — page layout may have changed.")
    return False
