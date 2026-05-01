"""
Fine-Tuning Prep — Thesis Style

Generates message-format training pairs for the thesis writer stage.
Input:  structured context block (same format as sent to Groq in thesis_writer)
Output: formatted thesis sections (executive summary, bull/bear case, etc.)

Workflow:
  1. Run this script — it generates draft training data from stored theses.
  2. Review the output in fine_tuning/training_data/style_training.jsonl.
  3. (Optional) Copy the JSON objects you want to improve into
     data/style_examples/edited/ as individual .json files, then edit the
     "assistant" content to reflect a higher-quality thesis style.
  4. Re-run this script — it uses your edited files where available and falls
     back to the unedited originals for the rest.
  5. Once satisfied, run: python fine_tuning/train_style_model.py

Usage:
    python fine_tuning/prepare_style_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.thesis_writer as tw_mod

_THESES_DIR  = Path(__file__).parent.parent / "data" / "theses"
_EDITED_DIR  = Path(__file__).parent.parent / "data" / "style_examples" / "edited"
_OUTPUT_DIR  = Path(__file__).parent / "training_data"


# -- Context reconstructor -----------------------------------------------------

def _reconstruct_context(t: dict) -> str:
    """
    Rebuild the context block originally sent to thesis_writer's Groq call.
    Uses the same field layout as thesis_writer._build_context().
    """
    profile   = t.get("profile", {})
    scores    = t.get("scores", {})
    bmp       = scores.get("bmp", {})
    fisher    = scores.get("fisher") or None
    selection = scores.get("selection") or None
    risk      = scores.get("risk", {})

    if fisher and not fisher.get("points"):
        fisher = None
    if selection and not selection.get("answers"):
        selection = None

    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    cagr    = profile.get("revenue_cagr")
    fcf     = profile.get("free_cash_flow")
    revenues = profile.get("revenues") or []

    # FCF margin
    is_fin = tw_mod._is_financial_company(profile)
    if fcf is not None and revenues:
        latest_rev = revenues[0].get("revenue") if revenues else None
        if latest_rev and latest_rev > 0:
            fcf_margin_str = (
                "Unreliable - financial company float distortion"
                if is_fin
                else f"{round(fcf / latest_rev * 100, 2)}%"
            )
        else:
            fcf_margin_str = "N/A"
    else:
        fcf_margin_str = "N/A"

    lines = [
        "=== COMPANY DATA ===",
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        f"P/E Ratio:         {profile.get('pe_ratio', 'N/A')}",
        f"Revenue CAGR:      {round(cagr * 100, 2)}%" if cagr is not None else "Revenue CAGR:      N/A",
        f"FCF Margin:        {fcf_margin_str}",
        f"ROE:               {round(roe * 100, 2)}%" if roe else "ROE:               N/A",
        f"Insider Ownership: {round(insider * 100, 2)}%" if insider else "Insider Ownership: N/A",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Moat:              {profile.get('moat', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers') or [])}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors') or [])}",
        "",
        "=== FRAMEWORK SCORES ===",
        f"BMP Gate:          {bmp.get('score', 0)}/5   — {bmp.get('verdict', 'N/A')}",
    ]

    if fisher:
        lines.append(
            f"Fisher Analysis:   {fisher.get('total', 0)}/15  — {fisher.get('rating', 'N/A')}"
        )
    else:
        lines.append("Fisher Analysis:   N/A (not run)")

    if selection:
        lines.append(
            f"Stock Selection:   {selection.get('score', 0)}/8   — {selection.get('verdict', 'N/A')}"
        )
    else:
        lines.append("Stock Selection:   N/A (not run)")

    lines += [
        f"Risk Category:     {risk.get('category', 'N/A')} ({risk.get('alloc_label', 'N/A')})",
        f"Conviction:        {risk.get('conviction', 'N/A')}",
        f"Position Size:     {risk.get('position_pct', 0)}%",
        "",
        "=== STRENGTHS ===",
    ]

    for p in (fisher or {}).get("points", []):
        if p.get("score", 0) >= 0.75:
            lines.append(f"Fisher {p['key']} {p.get('label', '')} [{p['score']}]: {p.get('reasoning', '')}")
    for a in (selection or {}).get("answers", []):
        if a.get("rating", "").upper() == "YES":
            lines.append(f"Selection {a['key']} {a.get('label', '')}: YES — {a.get('reasoning', '')}")

    lines += ["", "=== WEAKNESSES ==="]
    for a in bmp.get("answers", []):
        if a.get("rating", "").upper() == "NO":
            lines.append(f"BMP {a['label']}: NO — {a.get('reasoning', '')}")
    for p in (fisher or {}).get("points", []):
        if p.get("score", 1.0) == 0.0:
            lines.append(f"Fisher {p['key']} {p.get('label', '')}: 0 — {p.get('reasoning', '')}")
    for a in (selection or {}).get("answers", []):
        if a.get("rating", "").upper() == "NO":
            lines.append(f"Selection {a['key']} {a.get('label', '')}: NO — {a.get('reasoning', '')}")

    lines += ["", "=== RISK FACTOR PENALTIES ==="]
    for f in risk.get("factors", []):
        lines.append(f"{f['label']}: [{f['penalty']}] {f['reasoning']}")
    lines += [
        f"Total risk penalty: +{risk.get('total_penalty', 0)} NOs",
        f"Adjusted NO count:  {risk.get('adjusted_nos', 0)}",
    ]

    return "\n".join(lines)


# -- Assistant turn builder ----------------------------------------------------

def _thesis_assistant(sections: dict) -> str:
    """Format stored thesis sections as the model's expected output."""
    parts = [
        f"EXECUTIVE_SUMMARY: {sections.get('executive_summary', '')}",
        f"BULL_1: {sections.get('bull_case', ['', '', ''])[0]}",
        f"BULL_2: {sections.get('bull_case', ['', '', ''])[1]}",
        f"BULL_3: {sections.get('bull_case', ['', '', ''])[2]}",
        f"BEAR_1: {sections.get('bear_case', ['', '', ''])[0]}",
        f"BEAR_2: {sections.get('bear_case', ['', '', ''])[1]}",
        f"BEAR_3: {sections.get('bear_case', ['', '', ''])[2]}",
        f"THESIS_STATEMENT: {sections.get('thesis_statement', '')}",
        f"WATCH_1: {sections.get('watch_points', ['', '', ''])[0]}",
        f"WATCH_2: {sections.get('watch_points', ['', '', ''])[1]}",
        f"WATCH_3: {sections.get('watch_points', ['', '', ''])[2]}",
        f"DECISION: {sections.get('decision', 'WATCHLIST')}",
        f"DECISION_RATIONALE: {sections.get('decision_rationale', '')}",
    ]
    return "\n".join(parts)


# -- Load edited overrides -----------------------------------------------------

def _load_edited() -> dict[str, dict]:
    """
    Load manually edited thesis sections from data/style_examples/edited/.
    Files are named {TICKER}_{date}.json and match thesis JSON structure.
    Returns a dict keyed by (ticker, date) tuple.
    """
    edited: dict[str, dict] = {}
    if not _EDITED_DIR.exists():
        return edited
    for p in sorted(_EDITED_DIR.glob("*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            key = f"{data.get('ticker', '')}_{data.get('date', '')}"
            edited[key] = data
        except Exception:
            pass
    return edited


# -- Main ----------------------------------------------------------------------

def main() -> None:
    theses = []
    for p in sorted(_THESES_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            theses.append(json.load(f))

    if not theses:
        print("No thesis files found. Run the pipeline on some companies first.")
        sys.exit(1)

    edited = _load_edited()
    if edited:
        print(f"  Found {len(edited)} edited thesis/theses in data/style_examples/edited/")

    lines = []
    for t in theses:
        ticker = t.get("ticker", "")
        dt     = t.get("date", "")
        key    = f"{ticker}_{dt}"

        # Use edited version if available, else use stored sections
        source = edited.get(key, t)
        sections = source.get("thesis", {})
        if not sections:
            continue

        ctx = _reconstruct_context(t)
        usr = ctx  # thesis writer receives the context as the user message
        ast = _thesis_assistant(sections)

        obj = {
            "messages": [
                {"role": "system",    "content": tw_mod._THESIS_SYSTEM},
                {"role": "user",      "content": usr},
                {"role": "assistant", "content": ast},
            ]
        }
        tag = " (edited)" if key in edited else ""
        print(f"  {ticker} {dt}{tag}")
        lines.append(json.dumps(obj, ensure_ascii=False))

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / "style_training.jsonl"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n  {len(lines)} example(s) -> {out_path}")
    print()
    if edited:
        print("  Tip: place additional edited thesis JSONs in data/style_examples/edited/")
        print("       to improve coverage. Recommend 20+ high-quality examples.")
    else:
        print("  Tip: to improve style quality, copy thesis JSONs to")
        print("       data/style_examples/edited/, edit the 'thesis' sections,")
        print("       then re-run this script.")
    print()


if __name__ == "__main__":
    main()
