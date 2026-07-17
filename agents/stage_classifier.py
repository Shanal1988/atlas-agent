# Investment Stage Framework (§14) + Lynch six categories.
#
# Deterministic pre-classification narrows the candidate stage window from
# profitability + growth + margin trend; one small LLM call picks the exact
# stage and Lynch category within that window. Lookup tables map the stage to
# allocation guidance and a hard position-size cap used by risk sizing.

from agents.context import profile_context, call_llm

STAGES = {
    1:  {"label": "Business formation",   "risk": "Max",       "profits": "No",    "return_potential": "200x+",   "do_invest": "No"},
    2:  {"label": "Product development",  "risk": "Max",       "profits": "No",    "return_potential": "200x+",   "do_invest": "No"},
    3:  {"label": "Product launch",       "risk": "Very high", "profits": "No",    "return_potential": "100x+",   "do_invest": "No"},
    4:  {"label": "Product-market fit?",  "risk": "Very high", "profits": "No",    "return_potential": "50x+",    "do_invest": "No"},
    5:  {"label": "Huge revenue growth",  "risk": "High",      "profits": "No",    "return_potential": "20x+",    "do_invest": "<1%"},
    6:  {"label": "Reinvestment",         "risk": "Med-high",  "profits": "No",    "return_potential": "20x+",    "do_invest": "<1%"},
    7:  {"label": "Margin expansion",     "risk": "Medium",    "profits": "Close", "return_potential": "10x+",    "do_invest": "1-2%"},
    8:  {"label": "Reach profitability",  "risk": "Med-low",   "profits": "Yes",   "return_potential": "10x+",    "do_invest": "2-4%"},
    9:  {"label": "Huge profit growth",   "risk": "Med-low",   "profits": "Yes",   "return_potential": "10x+",    "do_invest": "2-4%"},
    10: {"label": "Market maturity",      "risk": "Low",       "profits": "Yes",   "return_potential": "2x SPY",  "do_invest": "4-10%"},
    11: {"label": "Dividend/buyback",     "risk": "Low",       "profits": "Yes",   "return_potential": "1.5x SPY","do_invest": "Start to exit"},
    12: {"label": "Dividend aristocrat",  "risk": "Low",       "profits": "Yes",   "return_potential": "1.25x SPY","do_invest": "Exit"},
}

# Hard cap on new-position size by stage (% of portfolio)
STAGE_CAP_PCT = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 2, 8: 4, 9: 4, 10: 10, 11: 2, 12: 0}

LYNCH = {
    "FAST GROWER": {"risk": "High", "gain": "High", "allocation": "30-40%",
                    "attributes": "20-25% earnings growth"},
    "SLOW GROWER": {"risk": "Low", "gain": "Low", "allocation": "5-10%",
                    "attributes": "Generous, regular dividend"},
    "STALWART":    {"risk": "Low", "gain": "Medium", "allocation": "10-20%",
                    "attributes": "10-12% earnings growth"},
    "CYCLICAL":    {"risk": "Low", "gain": "High", "allocation": "10-20%",
                    "attributes": "Expand, contract, expand again"},
    "TURNAROUND":  {"risk": "High", "gain": "High", "allocation": "Rest",
                    "attributes": "Plan is working, well managed"},
    "ASSET PLAY":  {"risk": "Low", "gain": "High", "allocation": "5-10%",
                    "attributes": "Valuable assets"},
}


def _candidate_window(profile: dict) -> tuple[int, int, str]:
    """Deterministic pre-classification -> (lo_stage, hi_stage, rationale)."""
    ni = profile.get("net_income")
    revs = profile.get("revenues") or []
    rev = revs[0].get("revenue") if revs else None
    op = profile.get("operating_income")
    cagr = profile.get("revenue_cagr") or 0
    profitable = (ni is not None and ni > 0) or (ni is None and op is not None and op > 0)
    near_breakeven = (op is not None and rev and abs(op / rev) < 0.05)

    if not rev:
        return 1, 4, "No meaningful revenue — pre-revenue stages."
    if not profitable and near_breakeven:
        return 7, 8, "Near breakeven operating margin."
    if not profitable:
        return (5, 6, f"Unprofitable, revenue growing {cagr*100:.0f}%/yr.") if cagr > 0.20 \
            else (4, 7, f"Unprofitable with modest growth ({cagr*100:.0f}%/yr).")
    if cagr > 0.20:
        return 8, 9, f"Profitable and growing fast ({cagr*100:.0f}%/yr)."
    if cagr > 0.05:
        return 9, 11, f"Profitable, moderate growth ({cagr*100:.0f}%/yr)."
    return 10, 12, f"Profitable, slow growth ({cagr*100:.0f}%/yr) — mature."


def run(profile: dict) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    lo, hi, rationale = _candidate_window(profile)
    print(f"  [Stage] Pre-classified {company} to stages {lo}-{hi} ({rationale})")

    window = "\n".join(f"{n}. {STAGES[n]['label']} (risk {STAGES[n]['risk']}, "
                       f"profits: {STAGES[n]['profits']})" for n in range(lo, hi + 1))
    lynch_opts = ", ".join(LYNCH.keys())

    raw = call_llm(
        [{"role": "system", "content":
            "You classify companies by investment stage and Peter Lynch category. "
            "Answer strictly in the requested format."},
         {"role": "user", "content":
            f"Company data:\n{profile_context(profile)}\n\n"
            f"Pre-classification: {rationale}\n"
            f"Pick the single best stage from this window ONLY:\n{window}\n\n"
            f"Then pick the single best Lynch category from: {lynch_opts}\n\n"
            "Reply in this exact format:\n"
            "STAGE: <number>\n"
            "LYNCH: <category>\n"
            "REASON: <one sentence>"}],
        max_tokens=150, temperature=0.1, stage="Stage Classifier")

    stage_n, lynch, reason = None, None, ""
    for line in (raw or "").splitlines():
        s = line.strip()
        if s.upper().startswith("STAGE:"):
            try:
                stage_n = int("".join(ch for ch in s.split(":", 1)[1] if ch.isdigit()))
            except ValueError:
                pass
        elif s.upper().startswith("LYNCH:"):
            lynch = s.split(":", 1)[1].strip().upper().rstrip(".")
            if lynch.endswith("S") and lynch[:-1] in LYNCH:   # "STALWARTS" -> "STALWART"
                lynch = lynch[:-1]
        elif s.upper().startswith("REASON:"):
            reason = s.split(":", 1)[1].strip()

    if stage_n is None or not (lo <= stage_n <= hi):
        stage_n = (lo + hi) // 2
        reason = (reason + " " if reason else "") + "[Stage defaulted to window midpoint]"
    if lynch not in LYNCH:
        lynch = "FAST GROWER" if (profile.get("revenue_cagr") or 0) > 0.15 else "STALWART"

    info = STAGES[stage_n]
    lynch_info = LYNCH[lynch]
    return {
        "stage_number": stage_n,
        "stage_label": info["label"],
        "risk": info["risk"],
        "profits": info["profits"],
        "return_potential": info["return_potential"],
        "allocation_guidance": info["do_invest"],
        "do_invest": info["do_invest"] not in ("No", "Exit"),
        "stage_cap_pct": STAGE_CAP_PCT[stage_n],
        "lynch_category": lynch.title(),
        "lynch_allocation": lynch_info["allocation"],
        "lynch_attributes": lynch_info["attributes"],
        "window": [lo, hi],
        "pre_classification": rationale,
        "reasoning": reason,
    }
