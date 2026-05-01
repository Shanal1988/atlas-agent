"""
Eval 3 -- Parser Coverage

Reads all existing data/theses/*.json files and checks how often each field
falls back to a default or null value. Tracks parser quality and model drift
over time. No API calls -- runs instantly on existing data.

Usage:
    python evals/parser_coverage_eval.py
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_THESES_DIR  = Path(__file__).parent.parent / "data" / "theses"
_RESULTS_DIR = Path(__file__).parent / "results"

_FALLBACK_REASONING = {"No response parsed."}
_FALLBACK_RATING    = {"N/A"}
_VALID_DECISIONS    = {"INVEST", "WATCHLIST", "PASS"}


def _load_theses() -> list[dict]:
    theses = []
    for path in sorted(_THESES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            theses.append(json.load(f))
    return theses


def _check_theses(theses: list[dict]) -> list[dict]:
    counters: dict[str, dict] = {
        "bmp.answers.rating":            {"total": 0, "fallback": 0},
        "fisher.points.reasoning":       {"total": 0, "fallback": 0},
        "fisher.points.all_zero":        {"total": 0, "fallback": 0},
        "selection.answers.rating":      {"total": 0, "fallback": 0},
        "risk.factors.reasoning":        {"total": 0, "fallback": 0},
        "thesis.executive_summary":      {"total": 0, "fallback": 0},
        "thesis.decision":               {"total": 0, "fallback": 0},
        "profile.pe_ratio":              {"total": 0, "fallback": 0},
        "profile.roe":                   {"total": 0, "fallback": 0},
        "profile.insider_ownership_pct": {"total": 0, "fallback": 0},
    }

    for t in theses:
        scores  = t.get("scores", {})
        profile = t.get("profile", {})
        thesis  = t.get("thesis", {})

        # BMP answer ratings
        for a in scores.get("bmp", {}).get("answers", []):
            counters["bmp.answers.rating"]["total"] += 1
            if a.get("rating") in _FALLBACK_RATING:
                counters["bmp.answers.rating"]["fallback"] += 1

        # Fisher point reasoning
        pts = scores.get("fisher", {}).get("points", [])
        for p in pts:
            counters["fisher.points.reasoning"]["total"] += 1
            if p.get("reasoning") in _FALLBACK_REASONING:
                counters["fisher.points.reasoning"]["fallback"] += 1

        # Fisher all-zero detection (per thesis — suspicious default)
        counters["fisher.points.all_zero"]["total"] += 1
        if pts and all(p.get("score", 0.0) == 0.0 for p in pts):
            counters["fisher.points.all_zero"]["fallback"] += 1

        # Selection answer ratings
        for a in scores.get("selection", {}).get("answers", []):
            counters["selection.answers.rating"]["total"] += 1
            if a.get("rating") in _FALLBACK_RATING:
                counters["selection.answers.rating"]["fallback"] += 1

        # Risk factor reasoning
        for f in scores.get("risk", {}).get("factors", []):
            counters["risk.factors.reasoning"]["total"] += 1
            if f.get("reasoning") in _FALLBACK_REASONING:
                counters["risk.factors.reasoning"]["fallback"] += 1

        # Thesis sections
        counters["thesis.executive_summary"]["total"] += 1
        if not thesis.get("executive_summary", "").strip():
            counters["thesis.executive_summary"]["fallback"] += 1

        counters["thesis.decision"]["total"] += 1
        if thesis.get("decision") not in _VALID_DECISIONS:
            counters["thesis.decision"]["fallback"] += 1

        # Profile nullable fields
        for field in ("pe_ratio", "roe", "insider_ownership_pct"):
            counters[f"profile.{field}"]["total"] += 1
            if profile.get(field) is None:
                counters[f"profile.{field}"]["fallback"] += 1

    results = []
    for field, data in counters.items():
        total    = data["total"]
        fallback = data["fallback"]
        rate     = (fallback / total) if total > 0 else 0.0
        results.append({
            "field":    field,
            "total":    total,
            "fallback": fallback,
            "rate":     round(rate, 4),
            "status":   "WARN" if rate > 0.20 else "PASS",
        })
    return results


def main() -> None:
    today  = date.today().isoformat()
    theses = _load_theses()

    if not theses:
        print(f"\nParser Coverage Eval -- no thesis files found in {_THESES_DIR}")
        print("  Run the pipeline on at least one company first.\n")
        return

    results = _check_theses(theses)
    warns   = [r for r in results if r["status"] == "WARN"]

    print(f"\nParser Coverage Report -- {len(theses)} thesis/theses analysed  [{today}]")
    print("-" * 72)
    print(f"  {'Field':<36} {'Null/Fallback':<16} {'Rate':<10} Status")
    print("-" * 72)
    for r in results:
        frac = f"{r['fallback']} / {r['total']}"
        rate = f"{r['rate'] * 100:.1f}%"
        flag = "  <-- WARN" if r["status"] == "WARN" else ""
        print(f"  {r['field']:<36} {frac:<16} {rate:<10} {r['status']}{flag}")
    print("-" * 72)

    if warns:
        print(f"\n  {len(warns)} field(s) above 20% fallback threshold:")
        for w in warns:
            print(f"  ! {w['field']}: {w['rate']*100:.1f}%  ({w['fallback']}/{w['total']})")
    else:
        print("\n  All fields within 20% fallback threshold.")
    print()

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"parser_coverage_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"date": today, "n_theses": len(theses), "results": results},
            f, indent=2,
        )
    print(f"  Results saved: {out_path}\n")


if __name__ == "__main__":
    main()
