#!/usr/bin/env python3
"""
Atlas Stock Screener — CLI entry point. Free tier: yfinance only, no API keys.

Usage:
    python screen.py --list-presets
    python screen.py --preset seessel_compounders
    python screen.py --preset hidden_gems --regions India --top 30 --save
    python screen.py --preset quality_at_fair_price --filter "pe <= 20"
    python screen.py --universe us_sp500 --filter "roic_avg >= 20%" --filter "revenue_cagr >= 15%"
    python screen.py --tickers AAPL MSFT ADYEN.AS --filter "gross_margin >= 50%"
    python screen.py --refresh-universe            # download full index constituents
    python screen.py --list-metrics
"""

import sys
import argparse

from dotenv import load_dotenv

load_dotenv()

# UTF-8 stdout fix (same as main.py)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents.screener import criteria, universe
from agents.screener.metrics import METRICS
from agents.screener.run import run


def main():
    parser = argparse.ArgumentParser(
        description="Screen stocks against Atlas criteria using free Yahoo Finance data")
    parser.add_argument("--preset", help="Preset from agents/screener/presets/ (see --list-presets)")
    parser.add_argument("--regions", nargs="+", choices=list(universe.REGIONS),
                        help="Region shortcuts — overrides the preset's universes")
    parser.add_argument("--universe", nargs="+", help="Universe names — overrides the preset's universes")
    parser.add_argument("--tickers", nargs="+", help="Screen these Yahoo tickers instead of a universe")
    parser.add_argument("--filter", action="append", default=[], dest="filters",
                        help='Extra rule, repeatable, e.g. --filter "roic_avg >= 20%%"')
    parser.add_argument("--rank", nargs="+", dest="rank_by", metavar="METRIC:WEIGHT",
                        help="Ranking weights, overrides the preset's (negative = lower is better), "
                             "e.g. --rank roic_avg:0.5 pe:-0.5")
    parser.add_argument("--top", type=int, default=25, help="Rows to print (default 25)")
    parser.add_argument("--limit", type=int, help="Only screen the first N tickers (quick trial runs)")
    parser.add_argument("--max-age-days", type=float, default=7, help="Re-fetch cached data older than this (default 7)")
    parser.add_argument("--refresh", action="store_true", help="Ignore the cache and re-fetch everything")
    parser.add_argument("--offline", action="store_true", help="Use cached data only, never call Yahoo")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between Yahoo requests (default 0.5)")
    parser.add_argument("--save", action="store_true", help="Save JSON + CSV to data/screener/results/")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--list-metrics", action="store_true")
    parser.add_argument("--list-universes", action="store_true")
    parser.add_argument("--refresh-universe", nargs="*", metavar="NAME",
                        help="Download constituents for the named universes (all if none given)")
    args = parser.parse_args()

    if args.list_presets:
        for p in criteria.list_presets():
            print(f"  {p['name']:<24} {' '.join(p['description'].split())}")
        return
    if args.list_metrics:
        for name, desc in METRICS.items():
            print(f"  {name:<24} {desc}")
        return
    if args.list_universes:
        for name in universe.available():
            print(f"  {name}")
        print("\n  Regions: " + ", ".join(f"{r} = {'+'.join(u)}" for r, u in universe.REGIONS.items()))
        return
    if args.refresh_universe is not None:
        for name in args.refresh_universe or list(universe.SOURCES):
            universe.refresh(name)
        return

    if not (args.preset or args.filters or args.tickers or args.universe or args.regions):
        parser.error("give a --preset, or --filter rules with --universe/--regions/--tickers")

    universes = args.universe
    if args.regions:
        universes = [u for r in args.regions for u in universe.REGIONS[r]]

    try:
        run(preset=args.preset, universes=universes, tickers=args.tickers,
            extra_filters=args.filters, rank_by=args.rank_by, top=args.top, limit=args.limit,
            max_age_days=args.max_age_days, refresh=args.refresh, offline=args.offline,
            delay=args.delay, save=args.save)
    except ValueError as e:
        parser.error(str(e))


if __name__ == "__main__":
    main()
