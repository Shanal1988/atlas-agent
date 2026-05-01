"""
Fine-Tuning Prep — Scoring Calibration

Reads all data/theses/*.json files and extracts message-format training pairs
for three stages: BMP, Selection, and Risk. No Groq or API calls are made —
all data is reconstructed from the saved thesis JSON.

Output files:
    fine_tuning/training_data/bmp_training.jsonl
    fine_tuning/training_data/selection_training.jsonl
    fine_tuning/training_data/risk_training.jsonl

Each line is one JSON object with the OpenAI fine-tuning messages format:
    {"messages": [{"role": "system", ...}, {"role": "user", ...},
                  {"role": "assistant", ...}]}

When to run:
    50+  theses -> fine-tune BMP, Selection, Risk
    100+ theses -> Fisher also (requires fisher_evidence saved in thesis JSON)

Usage:
    python fine_tuning/prepare_scoring_data.py
    python fine_tuning/prepare_scoring_data.py --min-theses 10   # lower threshold for testing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.bmp_gate as bmp_mod
import agents.stock_selection as sel_mod
import agents.risk_scoring as risk_mod

_THESES_DIR  = Path(__file__).parent.parent / "data" / "theses"
_OUTPUT_DIR  = Path(__file__).parent / "training_data"
_MIN_THESES  = 50   # default minimum before recommending fine-tuning


# -- Context reconstructors ----------------------------------------------------
# These rebuild the user message sent to Groq from the fields stored in the
# thesis JSON. Fields not saved (revenues list, current_price, beta) are marked N/A.

def _bmp_context(profile: dict) -> str:
    """Reconstruct BMP profile context from saved thesis profile dict."""
    pe       = profile.get("pe_ratio")
    roe      = profile.get("roe")
    insider  = profile.get("insider_ownership_pct")
    cagr_raw = profile.get("revenue_cagr")
    cagr     = round(cagr_raw * 100, 2) if cagr_raw is not None else None
    earnings_yield = round((1 / pe) * 100, 2) if pe and pe > 0 else None

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        "Current Price:     N/A (not stored in thesis JSON)",
        f"P/E Ratio:         {pe if pe else 'N/A'}",
        f"Earnings Yield:    {earnings_yield}%" if earnings_yield else "Earnings Yield:    N/A",
        "Beta:              N/A (not stored in thesis JSON)",
    ]

    # Use saved revenues list if present (thesis_writer saves it from v1.1+)
    revenues = profile.get("revenues") or []
    if revenues:
        rev_str = "  |  ".join(
            f"{r.get('year','?')}: {r.get('revenue')}" for r in revenues
        )
        lines.append(f"Revenue (3yr):     {rev_str}")
    else:
        lines.append("Revenue (3yr):     N/A (not stored in thesis JSON)")

    lines += [
        f"Revenue CAGR:      {cagr}% (3yr)" if cagr is not None else "Revenue CAGR:      N/A",
        f"Free Cash Flow:    {profile.get('free_cash_flow', 'N/A')}",
        f"ROE:               {round(roe * 100, 2)}%" if roe else "ROE:               N/A",
        f"Insider Ownership: {round(insider * 100, 2)}%" if insider else "Insider Ownership: N/A",
        f"Competitive Moat:  {profile.get('moat', 'N/A')}",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers') or [])}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors') or [])}",
    ]
    return "\n".join(lines)


def _selection_context(profile: dict, selection: dict) -> str:
    """
    Reconstruct Selection context. Computed metrics (Buffett ratio, capex %,
    net income history) were not stored in early thesis JSONs and default to N/A.
    Quality improves as thesis_writer saves more fields.
    """
    revenues = profile.get("revenues") or []
    rev_str  = "  |  ".join(
        f"{r.get('year','?')}: {r.get('revenue')}" for r in revenues
    ) or "N/A"

    cagr_raw = profile.get("revenue_cagr")
    cagr     = f"{round(cagr_raw * 100, 2)}%" if cagr_raw is not None else "N/A"
    roe      = profile.get("roe")
    insider  = profile.get("insider_ownership_pct")
    fcf      = profile.get("free_cash_flow")

    # Grab Buffett ratio and capex % if they were stored (v1.1+)
    buffett_ratio = selection.get("buffett_ratio")
    capex_pct     = selection.get("capex_pct")

    lines = [
        f"Company:             {profile.get('name', 'N/A')}",
        f"Sector/Industry:     {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Description:         {profile.get('description', 'N/A')}",
        f"Market Cap:          {profile.get('market_cap', 'N/A')}",
        f"P/E Ratio:           {profile.get('pe_ratio', 'N/A')}",
        f"Revenue (3yr):       {rev_str}",
        f"Revenue CAGR:        {cagr}",
        "Net Income history:  N/A (not stored in thesis JSON)",
        "EPS history:         N/A (not stored in thesis JSON)",
        f"Free Cash Flow:      {fcf or 'N/A'}",
        f"ROE:                 {round(roe * 100, 2)}%" if roe else "ROE:                 N/A",
        f"Insider Ownership:   {round(insider * 100, 2)}%" if insider else "Insider Ownership:   N/A",
        f"Moat:                {profile.get('moat', 'N/A')}",
        f"Growth Drivers:      {'; '.join(profile.get('growth_drivers') or [])}",
        f"Risk Factors:        {'; '.join(profile.get('risk_factors') or [])}",
        "--- Computed Metrics ---",
        f"Capex % of Revenue:  {capex_pct}%" if capex_pct is not None else "Capex % of Revenue:  N/A",
        f"Buffett Ratio:       {buffett_ratio}" if buffett_ratio is not None
            else "Buffett Ratio:       N/A (not stored in thesis JSON)",
    ]
    return "\n".join(lines)


def _risk_context(profile: dict, bmp: dict, fisher: dict | None,
                  selection: dict | None) -> str:
    """Reconstruct Risk context. All inputs are fully available in thesis JSON."""
    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    cagr    = profile.get("revenue_cagr")

    # Reconstruct NO items exactly as risk_scoring._count_nos_* does
    nos_bmp,  items_bmp  = risk_mod._count_nos_bmp(bmp)
    nos_fish, items_fish = risk_mod._count_nos_fisher(fisher)
    nos_sel,  items_sel  = risk_mod._count_nos_selection(selection)
    no_items = items_bmp + items_fish + items_sel

    return risk_mod._build_context(profile, bmp, fisher, selection, no_items)


# -- Assistant turn builders ---------------------------------------------------

def _bmp_assistant(answers: list[dict]) -> str:
    return "\n".join(
        f"{a['label']}: [{a['rating']}] {a['reasoning']}"
        for a in answers
    )


def _selection_assistant(answers: list[dict]) -> str:
    return "\n".join(
        f"{a['key']}: [{a['rating']}] {a['reasoning']}"
        for a in answers
    )


def _risk_assistant(factors: list[dict], conviction: str) -> str:
    lines = [
        f"{f['key']}: [{f['penalty']}] {f['reasoning']}"
        for f in factors
    ]
    lines.append(f"CONVICTION: [{conviction}] Overall conviction assessment.")
    return "\n".join(lines)


# -- JSONL writer --------------------------------------------------------------

def _make_example(system: str, user: str, assistant: str) -> str:
    obj = {
        "messages": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }
    return json.dumps(obj, ensure_ascii=False)


# -- Main extraction -----------------------------------------------------------

def extract(theses: list[dict]) -> dict[str, list[str]]:
    """
    Returns dict of stage -> list of JSONL lines.
    """
    bmp_lines = []
    sel_lines = []
    risk_lines = []

    for t in theses:
        profile   = t.get("profile", {})
        scores    = t.get("scores", {})
        bmp       = scores.get("bmp", {})
        fisher    = scores.get("fisher") or None
        selection = scores.get("selection") or None
        risk      = scores.get("risk", {})

        # Normalise fisher/selection to None if they have no data
        if fisher and not fisher.get("points"):
            fisher = None
        if selection and not selection.get("answers"):
            selection = None

        # -- BMP --
        if bmp.get("answers"):
            ctx = _bmp_context(profile)
            usr = (
                f"Company data:\n{ctx}\n\n"
                f"Answer the following BMP checklist questions:\n{bmp_mod._BMP_QUESTIONS}"
            )
            ast = _bmp_assistant(bmp["answers"])
            bmp_lines.append(_make_example(bmp_mod._BMP_SYSTEM, usr, ast))

        # -- Selection --
        if selection and selection.get("answers"):
            ctx = _selection_context(profile, selection)
            usr = (
                f"Company data and computed metrics:\n{ctx}\n\n"
                f"Score these 8 checklist questions:\n{sel_mod._CHECKLIST_QUESTIONS}"
            )
            ast = _selection_assistant(selection["answers"])
            sel_lines.append(_make_example(sel_mod._SELECTION_SYSTEM, usr, ast))

        # -- Risk --
        if risk.get("factors") and risk.get("conviction"):
            ctx = _risk_context(profile, bmp, fisher, selection)
            usr = (
                f"Company data and prior stage results:\n{ctx}\n\n"
                f"Assess these 5 risk factors:\n{risk_mod._RISK_QUESTIONS}"
            )
            ast = _risk_assistant(risk["factors"], risk["conviction"])
            risk_lines.append(_make_example(risk_mod._RISK_SYSTEM, usr, ast))

    return {"bmp": bmp_lines, "selection": sel_lines, "risk": risk_lines}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract scoring training data from thesis JSONs")
    parser.add_argument("--min-theses", type=int, default=_MIN_THESES,
                        help=f"Warn if fewer than N theses found (default: {_MIN_THESES})")
    args = parser.parse_args()

    theses = []
    for p in sorted(_THESES_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            theses.append(json.load(f))

    if not theses:
        print("No thesis files found. Run the pipeline on some companies first.")
        sys.exit(1)

    n = len(theses)
    print(f"\nFound {n} thesis file(s).")
    if n < args.min_theses:
        print(f"  Warning: {n} < {args.min_theses} examples. Fine-tuning with this few examples "
              f"may not improve quality. Recommend accumulating {args.min_theses}+ theses first.")
        print("  Continuing anyway — output is valid for inspection and testing.")

    data = extract(theses)

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    for stage, lines in data.items():
        if not lines:
            print(f"  {stage}: 0 examples — skipped (no {stage} data in theses)")
            continue
        out_path = _OUTPUT_DIR / f"{stage}_training.jsonl"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  {stage}: {len(lines)} example(s) -> {out_path}")
        total += len(lines)

    print(f"\n  Total: {total} training example(s) across {len(data)} stages.")

    # Fisher note
    fisher_examples = sum(
        1 for t in theses
        if t.get("scores", {}).get("fisher_evidence")
    )
    if fisher_examples == 0:
        print("\n  Note: Fisher training data requires fisher_evidence saved in thesis JSON.")
        print("  This is saved from the next pipeline run onwards. Accumulate 100+ theses")
        print("  with evidence saved, then add a --stage fisher option to this script.")
    print()


if __name__ == "__main__":
    main()
