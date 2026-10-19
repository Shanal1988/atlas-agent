# Screener orchestrator: universe -> cache/fetch -> metrics -> filter -> rank.
#
# Free-tier by design: yfinance only, no FMP calls, no LLM calls. The top
# names are meant to be handed to `python main.py <ticker>` for the full
# Atlas analysis.

import csv
import json
from datetime import datetime
from pathlib import Path

from agents.screener import cache, criteria, fetch, metrics, universe

RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "screener" / "results"

_COLUMNS = [  # (metric, header, kind)
    ("market_cap_usd", "MktCap", "money"),
    ("revenue_cagr", "RevCAGR", "pct"),
    ("revenue_growth_q", "RevQ", "pct"),
    ("gross_margin", "GM", "pct"),
    ("roic_avg", "ROIC", "pct"),
    ("fcf_margin", "FCF%", "pct"),
    ("pe", "P/E", "x"),
    ("oey", "OEY", "pct"),
]


def _fmt(v, kind: str) -> str:
    if v is None:
        return "—"
    if kind == "money":
        return f"${v / 1e12:.1f}T" if v >= 1e12 else f"${v / 1e9:.1f}B" if v >= 1e9 else f"${v / 1e6:.0f}M"
    if kind == "pct":
        return f"{v * 100:.0f}%"
    return f"{v:.1f}"


def _print_results(name: str, description: str, universe_size: int, scored: int,
                   stats: list[dict], results: list[dict], top: int) -> None:
    W = 100
    print(f"\n{'=' * W}")
    print(f"  ATLAS SCREENER: {name}")
    if description:
        print(f"  {' '.join(description.split())}")
    print(f"{'=' * W}")

    print(f"\n  Funnel: {universe_size} in universe → {scored} with data")
    for s in stats:
        extra = f", {s['missing']} missing data" if s["missing"] else ""
        print(f"    {s['rule']:<45} {s['failed']:>5} failed{extra}")
    print(f"  → {len(results)} passed all filters")

    if not results:
        print("\n  No stocks matched. Loosen a filter or widen the universe.")
        print(f"\n{'=' * W}\n")
        return

    shown = results[:top]
    header = f"  {'#':>3}  {'Ticker':<13}{'Name':<26}{'Score':>6}" + "".join(f"{h:>9}" for _, h, _ in _COLUMNS)
    print(f"\n{header}")
    print(f"  {'-' * (len(header) - 2)}")
    for i, r in enumerate(shown, 1):
        name_str = (r.get("name") or "")[:24]
        cols = "".join(f"{_fmt(r.get(m), k):>9}" for m, _, k in _COLUMNS)
        score = r.get("screen_score")
        score_str = f"{score:.1f}" if score is not None else "—"
        print(f"  {i:>3}  {r['ticker']:<13}{name_str:<26}{score_str:>6}{cols}")
    if len(results) > top:
        print(f"\n  ... {len(results) - top} more passed (use --top to show more, --save for the full list)")

    print(f"\n  Next step — run the full Atlas analysis on a pick:")
    print(f"    python main.py {shown[0]['ticker']}")
    print(f"\n{'=' * W}\n")


def _save(name: str, config: dict, stats: list[dict], results: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_{name}"
    json_path = RESULTS_DIR / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"screen": name, "run_at": datetime.now().isoformat(timespec="seconds"),
                   "config": config, "funnel": stats, "results": results}, f, indent=2, default=str)
    csv_cols = ["ticker", "name", "sector", "industry", "country", "screen_score"] + list(metrics.METRICS)
    with open(RESULTS_DIR / f"{stem}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(csv_cols)), extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    return json_path


def run(preset: str | None = None, universes: list[str] | None = None,
        tickers: list[str] | None = None, extra_filters: list[str] | None = None,
        rank_by: list[str] | None = None, top: int = 25, limit: int | None = None, max_age_days: float = 7,
        refresh: bool = False, offline: bool = False, delay: float = 0.5,
        save: bool = False) -> list[dict]:
    config = criteria.load_preset(preset) if preset else {}
    name = preset or "custom"
    rules = [criteria.parse_rule(r) for r in (config.get("filters") or []) + (extra_filters or [])]
    weights = criteria.parse_weights(rank_by) if rank_by else (config.get("rank") or {})
    missing = config.get("missing", "fail")

    # 1. Universe
    if tickers:
        members = [{"symbol": t.upper(), "name": "", "universe": "custom"} for t in tickers]
    else:
        names = universes or config.get("universes") or universe.REGIONS["USA"]
        members = universe.load_many(names)
    if limit:
        members = members[:limit]
    symbols = [m["symbol"] for m in members]
    print(f"\nAtlas Screener — {name}")
    print(f"  Universe: {len(symbols)} tickers")
    if not symbols:
        return []

    # 2. Cache, then fetch whatever is missing or stale
    fresh, stale = cache.get_many(symbols, 0 if refresh else max_age_days)
    print(f"  Cache:    {len(fresh)} fresh, {len(stale)} to fetch")
    if stale and offline:
        print("  Offline mode — skipping fetch; screening cached tickers only.")
    elif stale:
        est_min = len(stale) * (delay + 1.5) / 60
        print(f"  Fetching from Yahoo Finance (~{est_min:.0f} min; results are cached for {max_age_days:g} days)...")
        fresh.update(fetch.fetch_all(stale, delay=delay))

    # 3. Metrics
    rows = []
    for sym in symbols:
        payload = fresh.get(sym)
        if not payload:
            continue
        try:
            row = metrics.derive(payload, fetch.usd_rate)
        except Exception as e:
            print(f"  [Metrics] {sym}: {type(e).__name__}: {e} — skipped.")
            continue
        if row.get("quote_type") not in (None, "EQUITY"):
            continue
        rows.append(row)

    # 4. Filter + rank
    passed, stats = criteria.apply_filters(rows, rules, missing=missing)
    if weights:
        results = criteria.rank(passed, weights)
    else:  # no ranking given — largest first, no composite score
        results = sorted(passed, key=lambda r: r.get("market_cap_usd") or 0, reverse=True)

    _print_results(name, config.get("description", ""), len(symbols), len(rows), stats, results, top)

    if save:
        path = _save(name, {"preset": preset, "universes": universes or config.get("universes"),
                            "filters": [r["text"] for r in rules], "rank": weights,
                            "missing": missing}, stats, results)
        print(f"  Saved {len(results)} results to {path} (+ .csv)")
    return results
