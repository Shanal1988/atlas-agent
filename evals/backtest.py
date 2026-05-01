"""
Eval 4 -- Historical Backtest

Reads all saved thesis JSONs, fetches current price via yfinance, computes
return % since thesis date, and groups results by Diamond-to-Egg category,
conviction level, and decision.

Becomes statistically meaningful at 20+ theses accumulated over 12+ months.

Usage:
    python evals/backtest.py
"""

import json
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf

_THESES_DIR  = Path(__file__).parent.parent / "data" / "theses"
_RESULTS_DIR = Path(__file__).parent / "results"

warnings.filterwarnings("ignore")  # suppress yfinance FutureWarning noise


def _load_theses() -> list[dict]:
    theses = []
    for path in sorted(_THESES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            theses.append(json.load(f))
    return theses


def _fetch_return(ticker: str, thesis_date_str: str) -> float | None:
    """
    Price return (%) from thesis_date to today.
    Returns None if data is unavailable or thesis date is today.
    """
    try:
        thesis_date = datetime.strptime(thesis_date_str, "%Y-%m-%d").date()
        today = date.today()
        if thesis_date >= today:
            return None

        hist = yf.Ticker(ticker).history(
            start=thesis_date_str, end=today.isoformat()
        )
        if hist.empty or len(hist) < 2:
            return None

        price_then  = float(hist["Close"].iloc[0])
        price_today = float(hist["Close"].iloc[-1])

        if price_then <= 0:
            return None
        return round((price_today - price_then) / price_then * 100, 2)
    except Exception:
        return None


def _avg_returns(records: list[dict], key: str) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for r in records:
        if r["return_pct"] is None:
            continue
        groups.setdefault(r.get(key, "Unknown"), []).append(r["return_pct"])
    return {g: round(sum(v) / len(v), 2) for g, v in sorted(groups.items())}


def main() -> None:
    today  = date.today().isoformat()
    theses = _load_theses()

    if not theses:
        print(f"\nHistorical Backtest -- no thesis files found in {_THESES_DIR}")
        print("  Run the pipeline on at least one company first.\n")
        return

    print(f"\nHistorical Backtest -- {len(theses)} thesis/theses  [{today}]")
    print("  Fetching price data from yfinance...")
    print()

    records = []
    for t in theses:
        ticker      = t.get("ticker", "")
        thesis_date = t.get("date", "")
        risk        = t.get("scores", {}).get("risk", {})
        category    = risk.get("category", "Unknown")
        conviction  = risk.get("conviction", "Unknown")
        decision    = t.get("thesis", {}).get("decision", "Unknown")
        position_pct = risk.get("position_pct", 0)

        ret = _fetch_return(ticker, thesis_date)

        records.append({
            "ticker":       ticker,
            "date":         thesis_date,
            "category":     category,
            "conviction":   conviction,
            "decision":     decision,
            "position_pct": position_pct,
            "return_pct":   ret,
        })

        ret_str = f"{ret:+.2f}%" if ret is not None else "N/A (same day or no data)"
        print(
            f"  {ticker:<12}  {thesis_date}  "
            f"{category:<10} {conviction:<8} {decision:<10}  "
            f"Return: {ret_str}"
        )

    valid  = [r for r in records if r["return_pct"] is not None]
    n_valid = len(valid)

    by_category  = _avg_returns(records, "category")
    by_conviction = _avg_returns(records, "conviction")
    by_decision  = _avg_returns(records, "decision")

    def _count(key, val):
        return sum(1 for r in valid if r.get(key) == val)

    print()
    print("  --- BY RISK CATEGORY ---")
    if by_category:
        for cat, avg in by_category.items():
            print(f"  {cat:<10} {_count('category', cat):>3} companies   Avg return: {avg:+.2f}%")
    else:
        print("  No return data available yet.")

    print()
    print("  --- BY CONVICTION ---")
    if by_conviction:
        for conv, avg in by_conviction.items():
            print(f"  {conv:<10} {_count('conviction', conv):>3} companies   Avg return: {avg:+.2f}%")
    else:
        print("  No return data available yet.")

    print()
    print("  --- BY DECISION ---")
    if by_decision:
        for dec, avg in by_decision.items():
            print(f"  {dec:<10} {_count('decision', dec):>3} companies   Avg return: {avg:+.2f}%")
    else:
        print("  No return data available yet.")

    if n_valid < 20:
        print(
            f"\n  Note: sample too small for statistical significance "
            f"({n_valid} with return data; 20+ recommended over 12+ months)."
        )
    print()

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"backtest_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date":            today,
                "n_theses":        len(theses),
                "n_with_returns":  n_valid,
                "records":         records,
                "by_category":     by_category,
                "by_conviction":   by_conviction,
                "by_decision":     by_decision,
            },
            f, indent=2,
        )
    print(f"  Results saved: {out_path}\n")


if __name__ == "__main__":
    main()
