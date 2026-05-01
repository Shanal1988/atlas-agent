"""
Eval 2 -- Prompt Regression Suite

Runs the full pipeline on known companies and checks whether scores fall
within expected ranges. Run after any prompt change to detect regressions.
Exits with code 1 if any check fails (CI-compatible).

Expected ranges are wide enough for natural LLM variance but narrow enough
to catch real regressions from prompt changes.

Usage:
    python evals/regression_suite.py
"""

import contextlib
import io
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from agents.discovery import run as discover
from agents.bmp_gate import run as bmp_gate
from agents.fisher import run as fisher
from agents.stock_selection import run as stock_selection
from agents.risk_scoring import run as risk_scoring
from agents.thesis_writer import run as thesis_writer

_RESULTS_DIR = Path(__file__).parent / "results"

# Expected ranges from first real pipeline runs.
# Update these after any intentional prompt improvement.
SUITE = {
    "CRWD": {
        "bmp":       (2.5, 4.0),
        "fisher":    (8.0, 12.0),
        "selection": (4.5, 7.0),
        "decision":  {"INVEST", "WATCHLIST"},
    },
    "WISE.L": {
        "bmp":       (3.5, 5.0),
        "fisher":    (10.0, 15.0),
        "selection": (6.0, 8.0),
        "decision":  {"INVEST"},
    },
    "ADYEN.AS": {
        "bmp":       (3.0, 5.0),
        "fisher":    (12.0, 15.0),
        "selection": (5.0, 8.0),
        "decision":  {"INVEST", "WATCHLIST"},
    },
}


@contextlib.contextmanager
def _suppress():
    """Redirect stdout/stderr so pipeline output doesn't flood the terminal."""
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            yield


def _run_pipeline(ticker: str) -> dict:
    """Run the full 6-stage pipeline, return key scores."""
    with _suppress():
        profile = discover(ticker)
        bmp     = bmp_gate(profile)
        fish    = fisher(profile, bmp["verdict"])
        sel     = stock_selection(profile, bmp["verdict"])
        risk    = risk_scoring(profile, bmp, fish, sel)
        thesis  = thesis_writer(profile, bmp, fish, sel, risk)

    return {
        "bmp_score":       bmp["score"],
        "fisher_total":    fish["total"] if fish else None,
        "selection_score": sel["score"]  if sel  else None,
        "decision":        thesis["decision"],
    }


def _check(result: dict, expected: dict) -> list[dict]:
    checks = []

    # BMP
    lo, hi = expected["bmp"]
    v = result["bmp_score"]
    checks.append({
        "field":    "bmp",
        "value":    v,
        "expected": f"{lo}-{hi}",
        "status":   "PASS" if lo <= v <= hi else "FAIL",
    })

    # Fisher
    lo, hi = expected["fisher"]
    v = result["fisher_total"]
    checks.append({
        "field":    "fisher",
        "value":    v if v is not None else "N/A",
        "expected": f"{lo}-{hi}",
        "status":   "PASS" if (v is not None and lo <= v <= hi) else "FAIL",
    })

    # Selection
    lo, hi = expected["selection"]
    v = result["selection_score"]
    checks.append({
        "field":    "selection",
        "value":    v if v is not None else "N/A",
        "expected": f"{lo}-{hi}",
        "status":   "PASS" if (v is not None and lo <= v <= hi) else "FAIL",
    })

    # Decision
    d = result["decision"]
    checks.append({
        "field":    "decision",
        "value":    d,
        "expected": str(expected["decision"]),
        "status":   "PASS" if d in expected["decision"] else "FAIL",
    })

    return checks


def main() -> None:
    today    = date.today().isoformat()
    any_fail = False
    all_results: dict = {}

    print(f"\nPrompt Regression Suite -- {today}")
    print("-" * 75)
    print(f"  {'Company':<12} {'BMP':<14} {'Fisher':<14} {'Selection':<14} {'Decision':<14} Status")
    print("-" * 75)

    for ticker, expected in SUITE.items():
        print(f"  {ticker:<12}", end="  ", flush=True)
        try:
            result = _run_pipeline(ticker)
            checks = _check(result, expected)
            cm = {c["field"]: c for c in checks}
            row_fail = any(c["status"] == "FAIL" for c in checks)
            if row_fail:
                any_fail = True

            def _fmt(field):
                c = cm[field]
                return f"{c['value']} {c['status']}"

            print(
                f"{_fmt('bmp'):<14} "
                f"{_fmt('fisher'):<14} "
                f"{_fmt('selection'):<14} "
                f"{_fmt('decision'):<14} "
                f"{'FAIL' if row_fail else 'PASS'}"
            )
            all_results[ticker] = {"result": result, "checks": checks,
                                   "status": "FAIL" if row_fail else "PASS"}

        except Exception as e:
            print(f"ERROR: {e}")
            any_fail = True
            all_results[ticker] = {"error": str(e), "status": "FAIL"}

    print("-" * 75)
    status_line = "FAIL -- regression detected" if any_fail else "PASS -- all within expected ranges"
    print(f"\n  Result: {status_line}")

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"regression_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"date": today, "suite": SUITE, "results": all_results},
            f, indent=2, default=str,
        )
    print(f"  Results saved: {out_path}\n")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
