#!/usr/bin/env python3
"""
Atlas Hidden Gems Discovery — CLI entry point.

Usage:
    python discover.py                          # defaults: USA, all sectors
    python discover.py --regions USA UK India   # multiple regions
    python discover.py --sector Technology      # filter by sector
    python discover.py --save                   # save results to data/discover/
"""

import sys
import argparse
import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# UTF-8 stdout fix (same as main.py)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents.discover import run


def main():
    parser = argparse.ArgumentParser(
        description="Discover hidden gem stocks — potential multibaggers across global markets"
    )
    parser.add_argument(
        "--regions", nargs="+", default=["USA"],
        choices=["USA", "UK", "Europe", "India"],
        help="Regions to scan (default: USA)",
    )
    parser.add_argument(
        "--sector", type=str, default=None,
        help="Filter by sector (e.g. Technology, Healthcare, 'Consumer Defensive')",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to data/discover/ as JSON",
    )
    args = parser.parse_args()

    results = run(args.regions, args.sector)

    if args.save and results:
        out_dir = os.path.join("data", "discover")
        os.makedirs(out_dir, exist_ok=True)

        region_tag = "_".join(args.regions)
        date_tag = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_tag}_{region_tag}"
        if args.sector:
            filename += f"_{args.sector.replace(' ', '_')}"
        filename += ".json"

        out_path = os.path.join(out_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": date_tag,
                "regions": args.regions,
                "sector": args.sector,
                "results": results,
            }, f, indent=2, default=str)
        print(f"  Results saved to {out_path}")


if __name__ == "__main__":
    main()
