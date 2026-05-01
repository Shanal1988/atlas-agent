"""
Eval 1 -- Scoring Consistency

Runs Groq scoring calls N times on the same company and measures variance.
Discovery is run once and cached to avoid burning discovery tokens.
Tavily evidence for Fisher is also cached -- variance should come from Groq only.

Usage:
    python evals/consistency_eval.py --ticker CRWD --runs 5
    python evals/consistency_eval.py --ticker CRWD --runs 5 --refresh
"""

import argparse
import json
import os
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
import agents.bmp_gate as bmp_mod
import agents.fisher as fisher_mod
import agents.stock_selection as sel_mod
import agents.risk_scoring as risk_mod
from agents.discovery import run as discover

_CACHE_DIR   = Path(__file__).parent / "cache"
_RESULTS_DIR = Path(__file__).parent / "results"


# -- Cache helpers -------------------------------------------------------------

def _profile_cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.replace('.', '_')}_profile.json"

def _evidence_cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.replace('.', '_')}_fisher_evidence.txt"

def _load_profile_cache(ticker: str) -> dict | None:
    p = _profile_cache_path(ticker)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None

def _save_profile_cache(ticker: str, profile: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_profile_cache_path(ticker), "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, default=str)

def _load_evidence_cache(ticker: str) -> str | None:
    p = _evidence_cache_path(ticker)
    return p.read_text(encoding="utf-8") if p.exists() else None

def _save_evidence_cache(ticker: str, evidence: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _evidence_cache_path(ticker).write_text(evidence, encoding="utf-8")


# -- Single scoring pass -------------------------------------------------------

def _run_one(profile: dict, evidence: str, extra: dict) -> dict:
    """
    One complete Groq-only scoring pass (BMP + Fisher + Selection + Risk).
    No discovery, no Tavily, no printing.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    # -- BMP --
    bmp_ctx = bmp_mod._profile_context(profile)
    bmp_user = (
        f"Company data:\n{bmp_ctx}\n\n"
        f"Answer the following BMP checklist questions:\n{bmp_mod._BMP_QUESTIONS}"
    )
    bmp_resp = client.chat.completions.create(
        model=bmp_mod.GROQ_MODEL,
        messages=[
            {"role": "system", "content": bmp_mod._BMP_SYSTEM},
            {"role": "user",   "content": bmp_user},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    bmp_answers = bmp_mod._parse_answers(bmp_resp.choices[0].message.content)
    bmp_score   = bmp_mod._score(bmp_answers)
    bmp_verdict = bmp_mod._verdict(bmp_score)
    bmp_result  = {"answers": bmp_answers, "score": bmp_score, "verdict": bmp_verdict}

    # -- Fisher --
    fisher_ctx = fisher_mod._profile_context(profile)
    fisher_raw = fisher_mod._score_with_groq(
        profile.get("name", profile.get("ticker", "")), fisher_ctx, evidence
    )
    fisher_points = fisher_mod._parse_scores(fisher_raw)
    fisher_total  = round(sum(p["score"] for p in fisher_points), 2)
    fisher_result = {
        "points": fisher_points,
        "total":  fisher_total,
        "rating": fisher_mod._fisher_rating(fisher_total),
    }

    # -- Selection --
    sel_ctx     = sel_mod._build_context(profile, extra)
    sel_raw     = sel_mod._score_with_groq(sel_ctx)
    sel_answers = sel_mod._parse_answers(sel_raw)
    sel_score   = sel_mod._score(sel_answers)
    sel_result  = {
        "answers": sel_answers,
        "score":   sel_score,
        "verdict": sel_mod._verdict(sel_score),
    }

    # -- Risk --
    nos_bmp,  items_bmp  = risk_mod._count_nos_bmp(bmp_result)
    nos_fish, items_fish = risk_mod._count_nos_fisher(fisher_result)
    nos_sel,  items_sel  = risk_mod._count_nos_selection(sel_result)
    no_items    = items_bmp + items_fish + items_sel
    risk_ctx    = risk_mod._build_context(
        profile, bmp_result, fisher_result, sel_result, no_items
    )
    risk_raw    = risk_mod._score_risk_factors(risk_ctx)
    risk_factors, conviction = risk_mod._parse_risk_factors(risk_raw)
    total_penalty = sum(f["penalty"] for f in risk_factors)
    adjusted_nos  = (nos_bmp + nos_fish + nos_sel) + total_penalty
    category, alloc_label, lo_pct, hi_pct = risk_mod._get_category(adjusted_nos)
    position_pct = risk_mod._position_size(category, lo_pct, hi_pct, conviction)

    return {
        "bmp_score":         bmp_score,
        "bmp_answers":       {a["label"]: a["rating"] for a in bmp_answers},
        "fisher_total":      fisher_total,
        "fisher_points":     {p["key"]: p["score"] for p in fisher_points},
        "selection_score":   sel_score,
        "selection_answers": {a["key"]: a["rating"] for a in sel_answers},
        "risk_conviction":   conviction,
        "risk_position_pct": position_pct,
        "risk_adjusted_nos": adjusted_nos,
    }


# -- Stats analysis ------------------------------------------------------------

def _analyse(runs: list[dict]) -> list[dict]:
    stats = []

    def _numeric(field, values):
        mean  = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        stats.append({
            "field":  field,
            "type":   "numeric",
            "mean":   round(mean, 3),
            "stdev":  round(stdev, 3),
            "values": values,
            "status": "WARN" if stdev > 0.5 else "PASS",
        })

    def _categorical(field, values):
        mode      = max(set(values), key=values.count)
        agreement = values.count(mode) / len(values)
        stats.append({
            "field":     field,
            "type":      "categorical",
            "mode":      mode,
            "agreement": round(agreement, 3),
            "values":    values,
            "status":    "WARN" if agreement < 0.6 else "PASS",
        })

    _numeric("bmp_score",         [r["bmp_score"]         for r in runs])
    _numeric("fisher_total",      [r["fisher_total"]      for r in runs])
    _numeric("selection_score",   [r["selection_score"]   for r in runs])
    _numeric("risk_position_pct", [r["risk_position_pct"] for r in runs])
    _numeric("risk_adjusted_nos", [r["risk_adjusted_nos"] for r in runs])

    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        _categorical(f"bmp_{q}", [r["bmp_answers"].get(q, "N/A") for r in runs])

    for pk in [f"P{i}" for i in range(1, 16)]:
        _numeric(f"fisher_{pk}", [r["fisher_points"].get(pk, 0.0) for r in runs])

    for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]:
        _categorical(f"selection_{q}", [r["selection_answers"].get(q, "N/A") for r in runs])

    _categorical("risk_conviction", [r["risk_conviction"] for r in runs])

    return stats


# -- Printer -------------------------------------------------------------------

def _print_summary(ticker: str, n_runs: int, stats: list[dict]) -> None:
    warns = [s for s in stats if s["status"] == "WARN"]

    print(f"\nScoring Consistency Eval -- {ticker} ({n_runs} runs)")
    print("-" * 65)
    print(f"  {'Field':<30} {'Mean / Mode':<14} {'StdDev / Agree':<16} Status")
    print("-" * 65)

    for s in stats:
        if s["type"] == "numeric":
            col2 = str(s["mean"])
            col3 = str(s["stdev"])
        else:
            col2 = s["mode"]
            col3 = f"{s['agreement'] * 100:.0f}%"
        flag = "  <-- WARN" if s["status"] == "WARN" else ""
        print(f"  {s['field']:<30} {col2:<14} {col3:<16} {s['status']}{flag}")

    print("-" * 65)
    if warns:
        print(f"\n  {len(warns)} field(s) flagged:")
        for w in warns:
            if w["type"] == "numeric":
                print(f"  ! {w['field']}: stdev={w['stdev']} (threshold 0.5)")
            else:
                print(f"  ! {w['field']}: agreement={w['agreement']*100:.0f}% (threshold 60%)")
    else:
        print("\n  All fields within thresholds.")
    print()


# -- Entry point ---------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Scoring Consistency Eval")
    parser.add_argument("--ticker",  required=True, help="Stock ticker (e.g. CRWD, WISE.L)")
    parser.add_argument("--runs",    type=int, default=5, help="Number of scoring runs (default: 5)")
    parser.add_argument("--refresh", action="store_true",
                        help="Ignore cache and re-fetch discovery + Fisher evidence")
    args   = parser.parse_args()
    ticker = args.ticker.upper()
    n_runs = args.runs
    today  = date.today().isoformat()

    print(f"\nAtlas Consistency Eval -- {ticker} ({n_runs} runs)  [{today}]")

    # Step 1 -- profile (cached across runs)
    profile = None if args.refresh else _load_profile_cache(ticker)
    if profile is None:
        print("  Fetching profile via discovery...")
        profile = discover(ticker)
        _save_profile_cache(ticker, profile)
        print(f"  Profile cached -> {_profile_cache_path(ticker)}")
    else:
        print(f"  Loaded cached profile for {profile.get('name', ticker)}.")

    # Step 2 -- Fisher evidence (cached)
    evidence = None if args.refresh else _load_evidence_cache(ticker)
    if evidence is None:
        print("  Gathering Fisher evidence (Tavily)...")
        evidence = fisher_mod._gather_evidence(profile.get("name", ticker))
        _save_evidence_cache(ticker, evidence)
        print(f"  Evidence cached -> {_evidence_cache_path(ticker)}")
    else:
        print("  Loaded cached Fisher evidence.")

    # Step 3 -- additional selection data (yfinance, fast, no cache needed)
    print("  Fetching additional selection data (yfinance)...")
    extra = sel_mod._fetch_additional_data(ticker)

    # Step 4 -- N Groq-only scoring runs
    print()
    all_runs = []
    for i in range(1, n_runs + 1):
        print(f"  Run {i}/{n_runs}...", end="  ", flush=True)
        result = _run_one(profile, evidence, extra)
        all_runs.append(result)
        print(
            f"BMP={result['bmp_score']}  "
            f"Fisher={result['fisher_total']}  "
            f"Selection={result['selection_score']}  "
            f"Pos={result['risk_position_pct']}%  "
            f"Conviction={result['risk_conviction']}"
        )

    # Step 5 -- analyse + print
    stats = _analyse(all_runs)
    _print_summary(ticker, n_runs, stats)

    # Step 6 -- save results JSON
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"{ticker.replace('.', '_')}_consistency_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"ticker": ticker, "runs": n_runs, "date": today,
             "raw_runs": all_runs, "stats": stats},
            f, indent=2,
        )
    print(f"  Results saved: {out_path}\n")


if __name__ == "__main__":
    main()
