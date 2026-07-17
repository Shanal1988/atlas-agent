# Feroldi Quality Score (user's investing process §9) + Anti-Fragile Score (§10)
#
# Deterministic policy: every quantifiable item is computed in Python from the
# profile; only judgement items go to the LLM, split into three calls
# (A: Moat+Potential, B: Customers/Company/Management/Stock, C: Gauntlet).
#
# Normalization: the sheet's raw section maxima sum to 110 (Moat's six raw items
# sum to 75 and are scaled ×30/75). Unavailable items (e.g. Glassdoor — no API)
# score 0, are subtracted from the effective denominator and listed in
# data_gaps. Pre-Gauntlet is reported /100; total = pre_gauntlet + gauntlet
# (Gauntlet floor −54).
#
# Anti-Fragile (−7..17) is derived from Feroldi items + profile — no extra LLM
# call. Bands: <7 IGNORE · 7–12 INVESTABLE · ≥12 FANTASTIC.

from agents.context import profile_context, call_llm

_MOAT_RAW_MAX = 75          # M1..M6 raw maxima sum
_MOAT_SCALED_MAX = 30       # sheet's "Moat (0–~30 combined)"

_SYSTEM = (
    "You are Brian Feroldi scoring a company on your Quality Score framework. "
    "Score each item within its stated range based strictly on the data provided. "
    "Give one short sentence of reasoning per item. Be conservative: no credit without evidence."
)

_PROMPT_A = """
Score these MOAT and POTENTIAL items. Ranges are hard limits.

M1 (0-15) Network effect / product ecosystem: None=0-2, Weak=3-8, Strong=9-15.
M2 (0-15) Switching costs: None=0-2, Weak=3-8, Strong=9-15.
M3 (0-15) Durable cost advantage (scale, distribution, physical locations, vertical integration): None=0-2, Weak=3-8, Strong=9-15.
M4 (0-15) Intangibles (premium brand, patents, trade secrets, licenses): None=0-2, Weak=3-8, Strong=9-15.
M5 (0-10) Counter-positioning (incumbents harmed by copying the model): None=0, Some=1-5, Strong=6-10.
M6 (0-5) Moat direction: Narrowing=0-1, Stable=2-3, Widening=4-5.
P1 (0-7) Optionality: None=0, Within current industry=1-4, Into new industries=5-7.
P2 (0-4) Organic growth runway: ~GDP=0-1, 2-3x GDP=2-3, 15%+ sustained=4.
P3 (0-3) Top dog & first mover in an important emerging industry, and/or disruptor: No=0, Partly=1-2, Clearly=3.
P4 (0-4) Operating leverage ahead: Negative=0, None=1, Modest=2-3, Tons=4.

Reply in this exact format, one line each, integer scores in brackets:
M1: [score] One sentence of reasoning.
M2: [score] ...
M3: [score] ...
M4: [score] ...
M5: [score] ...
M6: [score] ...
P1: [score] ...
P2: [score] ...
P3: [score] ...
P4: [score] ...
"""

_PROMPT_B_ITEMS = {
    "C1": ("C1 (0-5) Customer dependence: Highly cyclical=0-1, Moderate=2-3, Recession-proof=4-5.", 5),
    "K1": ("K1 (0-5) Recurring revenue: None=0-1, Some=2-3, Tons (subscriptions/contracts/consumables)=4-5.", 5),
    "K2": ("K2 (0-5) Pricing power: None=0-1, Some=2-3, Tons=4-5.", 5),
    "G1": ("G1 (0-4) Soul in the game: Hired-gun CEO=0-1, Long-tenured CEO=2, Family-run=3, Founder-led=4.", 4),
    "G2": ("G2 (0-3) Mission statement: none/generic=0, simple=1, +inspirational=2, +optionable=3.", 3),
    "S1": ("S1 (0-4) 5-yr stock performance vs S&P 500 (or since IPO): underperform=0-1, beat=2, +50% over index=3, +100% over index=4.", 4),
    "S2": ("S2 (0-3) Shareholder-friendly actions (buybacks below value, rising dividend, debt paydown): none=0, some=1-2, consistent=3.", 3),
    "S3": ("S3 (0-4) Beats expectations: routinely misses=0, mixed=1-2, consistently beats=3-4.", 4),
    "C0": ("C0 (0-5) Customer acquisition cost (S&M as % of gross profit): Expensive >75%=0-1, Normal 25-75%=2-3, Word of mouth <10%=4-5.", 5),
}

_PROMPT_C = """
Score these GAUNTLET penalty items. Each score must be EXACTLY one of the allowed values
(0 means no penalty). Negative numbers are penalties.

X1 (-10 or 0) Accounting irregularities (restatements, auditor changes, SEC inquiries).
X2 (-5/-3/0) Customer concentration: one customer >20% of revenue or AR=-5, one or a few >10%=-3, none=0.
X3 (-5/-3/0) Industry disruption: actively being disrupted=-5, plausible disruption=-3, none=0.
X4 (-5/-3/0) Outside forces dependence (commodity prices, interest rates, own stock price, economy): high=-5, moderate=-3, low=0.
X5 (-5/-3/0) Big market loser: lost >50% vs S&P over 5 yrs / since IPO=-5, meaningful underperformance=-3, no=0.
X6 (-5 or 0) Binary event pending (patent cliff, legal ruling, regulatory decision).
X7 (-4/-2/0) Extreme dilution: >5% annual share growth=-4, 3-5%=-2, <3%=0.
X8 (-4/-2/0) Growth by acquisition: exclusively=-4, partially=-2, organic=0.
X9 (-3 or 0) Complicated financials (hard to follow, heavy adjustments).
X10 (-3 or 0) Antitrust concerns.
X11 (-3/-2/0) Headquarters country risk: high=-3, medium=-2, low=0.
X12 (-2/-1/0) Currency risk: >75% revenue in foreign currencies=-2, >50%=-1, <50%=0.

Reply in this exact format, one line each:
X1: [score] One sentence of reasoning.
X2: [score] ...
X3: [score] ...
X4: [score] ...
X5: [score] ...
X6: [score] ...
X7: [score] ...
X8: [score] ...
X9: [score] ...
X10: [score] ...
X11: [score] ...
X12: [score] ...
"""

_GAUNTLET_ALLOWED = {
    "X1": (-10, 0), "X2": (-5, -3, 0), "X3": (-5, -3, 0), "X4": (-5, -3, 0),
    "X5": (-5, -3, 0), "X6": (-5, 0), "X7": (-4, -2, 0), "X8": (-4, -2, 0),
    "X9": (-3, 0), "X10": (-3, 0), "X11": (-3, -2, 0), "X12": (-2, -1, 0),
}

_GAUNTLET_LABELS = {
    "X1": "Accounting irregularities", "X2": "Customer concentration",
    "X3": "Industry disruption", "X4": "Outside forces",
    "X5": "Big market loser", "X6": "Binary event",
    "X7": "Extreme dilution", "X8": "Growth by acquisition",
    "X9": "Complicated financials", "X10": "Antitrust concerns",
    "X11": "HQ country risk", "X12": "Currency risk",
}


def _parse_lines(text: str, keys: list[str]) -> dict:
    """Parse 'KEY: [n] reasoning' lines. Returns {key: (score_float_or_None, reasoning)}."""
    out = {}
    for key in keys:
        score, reasoning = None, ""
        for line in (text or "").splitlines():
            s = line.strip()
            if s.startswith(f"{key}:"):
                rest = s.split(":", 1)[1].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        try:
                            score = float(rest[1:close].strip().rstrip("%"))
                        except ValueError:
                            score = None
                        reasoning = rest[close + 1:].strip()
                else:
                    parts = rest.split(None, 1)
                    try:
                        score = float(parts[0])
                        reasoning = parts[1] if len(parts) > 1 else ""
                    except (ValueError, IndexError):
                        reasoning = rest
                break
        out[key] = (score, reasoning)
    return out


def _clamp(score, lo, hi, default=0):
    if score is None:
        return default
    return max(lo, min(hi, score))


def _snap_allowed(score, allowed):
    """Snap a penalty to the nearest allowed value; missing -> 0 (no penalty)."""
    if score is None:
        return 0
    return min(allowed, key=lambda a: abs(a - score))


# -- Deterministic items -------------------------------------------------------

def _fin_items(profile: dict, gaps: list) -> list[dict]:
    items = []
    net_debt = profile.get("net_debt")
    fcf = profile.get("free_cash_flow")

    # Financial resilience 0-5 (Fragile / Average / Fortress)
    if net_debt is None and fcf is None:
        items.append({"key": "F1", "label": "Financial resilience", "score": 0, "max": 5,
                      "method": "unavailable", "reasoning": "Debt/cash/FCF data unavailable."})
        gaps.append("financial_resilience")
    else:
        if net_debt is not None and net_debt <= 0 and (fcf or 0) > 0:
            s, why = 5, "Net cash with positive free cash flow — fortress."
        elif net_debt is not None and net_debt <= 0:
            s, why = 4, "Net cash balance sheet."
        elif (fcf or 0) > 0 and net_debt is not None and net_debt < 3 * fcf:
            s, why = 3, f"Net debt under 3x FCF ({net_debt/fcf:.1f}x)."
        elif (fcf or 0) > 0:
            s, why = 2, "FCF-positive but carrying meaningful net debt."
        else:
            s, why = 1, "Net debt with weak or negative free cash flow."
        items.append({"key": "F1", "label": "Financial resilience", "score": s, "max": 5,
                      "method": "computed", "reasoning": why})

    # Gross margin 0-3
    gm = profile.get("gross_margin")
    if gm is None:
        items.append({"key": "F2", "label": "Gross margin", "score": 0, "max": 3,
                      "method": "unavailable", "reasoning": "Gross margin unavailable."})
        gaps.append("gross_margin")
    else:
        s = 3 if gm > 0.80 else 2 if gm >= 0.50 else 1
        items.append({"key": "F2", "label": "Gross margin", "score": s, "max": 3,
                      "method": "computed", "reasoning": f"Gross margin {gm*100:.0f}%."})

    # Returns on capital 0-3 (+1 if rising, capped)
    roc = profile.get("roic_avg") if profile.get("roic_avg") is not None else profile.get("roce_avg")
    trend = profile.get("roic_trend") or profile.get("roce_trend")
    if roc is None:
        items.append({"key": "F3", "label": "Returns on capital", "score": 0, "max": 3,
                      "method": "unavailable", "reasoning": "ROIC/ROCE unavailable."})
        gaps.append("returns_on_capital")
    else:
        s = 2 if roc >= 0.15 else 1 if roc >= 0.08 else 0
        if trend == "improving":
            s = min(3, s + 1)
        items.append({"key": "F3", "label": "Returns on capital", "score": s, "max": 3,
                      "method": "computed",
                      "reasoning": f"Avg ROIC/ROCE {roc*100:.1f}%, trend {trend or 'n/a'}."})

    # FCF 0-3 (negative / positive / positive & growing)
    ni_hist = [r.get("net_income") for r in (profile.get("net_income_history") or [])
               if r.get("net_income") is not None]
    growing = len(ni_hist) >= 2 and ni_hist[0] > ni_hist[-1]
    if fcf is None:
        items.append({"key": "F4", "label": "Free cash flow", "score": 0, "max": 3,
                      "method": "unavailable", "reasoning": "FCF unavailable."})
        gaps.append("fcf")
    elif fcf <= 0:
        items.append({"key": "F4", "label": "Free cash flow", "score": 0, "max": 3,
                      "method": "computed", "reasoning": "Negative free cash flow."})
    else:
        s = 3 if growing else 2
        items.append({"key": "F4", "label": "Free cash flow", "score": s, "max": 3,
                      "method": "computed",
                      "reasoning": "Positive and growing (earnings trend proxy)." if growing
                                   else "Positive free cash flow."})

    # EPS 0-3
    eps_hist = [r.get("eps") for r in (profile.get("eps_history") or []) if r.get("eps") is not None]
    if not eps_hist:
        ni = profile.get("net_income")
        if ni is None:
            items.append({"key": "F5", "label": "EPS", "score": 0, "max": 3,
                          "method": "unavailable", "reasoning": "EPS unavailable."})
            gaps.append("eps")
        else:
            s = 2 if ni > 0 else 0
            items.append({"key": "F5", "label": "EPS", "score": s, "max": 3,
                          "method": "computed", "reasoning": "Net income sign used as EPS proxy."})
    else:
        if eps_hist[0] <= 0:
            s, why = 0, f"Latest EPS {eps_hist[0]} is negative."
        elif len(eps_hist) >= 2 and eps_hist[0] > eps_hist[-1]:
            s, why = 3, f"EPS positive and growing ({eps_hist[-1]} → {eps_hist[0]})."
        else:
            s, why = 2, f"EPS positive ({eps_hist[0]})."
        items.append({"key": "F5", "label": "EPS", "score": s, "max": 3,
                      "method": "computed", "reasoning": why})
    return items


def _inside_ownership(profile: dict, gaps: list) -> dict:
    pct = profile.get("insider_ownership_pct")
    if pct is None:
        gaps.append("inside_ownership")
        return {"key": "G3", "label": "Inside ownership", "score": 0, "max": 3,
                "method": "unavailable", "reasoning": "Insider ownership unavailable."}
    s = 3 if pct >= 0.08 else 2 if pct >= 0.04 else 1 if pct >= 0.01 else 0
    return {"key": "G3", "label": "Inside ownership", "score": s, "max": 3,
            "method": "computed", "reasoning": f"Insiders own {pct*100:.1f}%."}


def _acquisition_cost(profile: dict) -> dict | None:
    sm, gp = profile.get("sm_expense"), profile.get("gross_profit")
    if not sm or not gp or gp <= 0:
        return None
    ratio = sm / gp
    s = 5 if ratio < 0.10 else 4 if ratio < 0.25 else 3 if ratio < 0.50 else 2 if ratio < 0.75 else 1
    return {"key": "C0", "label": "Customer acquisition cost", "score": s, "max": 5,
            "method": "computed", "reasoning": f"S&M is {ratio*100:.0f}% of gross profit."}


def _dilution_penalty(profile: dict) -> dict | None:
    dil = profile.get("dilution_cagr")
    if dil is None:
        return None
    s = -4 if dil > 0.05 else -2 if dil >= 0.03 else 0
    return {"key": "X7", "label": _GAUNTLET_LABELS["X7"], "score": s,
            "method": "computed", "reasoning": f"Share count CAGR {dil*100:+.1f}%/yr."}


# -- Anti-Fragile derivation (§10) ---------------------------------------------

def derive_antifragile(feroldi: dict, profile: dict) -> dict:
    by_key = {}
    for sec in feroldi["sections"]:
        for it in sec["items"]:
            by_key[it["key"]] = it

    def raw(key, default=0):
        it = by_key.get(key)
        return it["score"] if it and it.get("method") != "unavailable" else default

    items = []

    mission_pts = {0: -1, 1: 0, 2: 1, 3: 2}.get(round(raw("G2")), 0)
    items.append({"key": "mission", "label": "Mission statement", "points": mission_pts,
                  "min": -1, "max": 2, "source": "feroldi:G2",
                  "reasoning": by_key.get("G2", {}).get("reasoning", "")})

    moat_pts = 0
    for mk in ("M1", "M2", "M3", "M4"):
        v = raw(mk)
        moat_pts += 2 if v >= 10 else 1 if v >= 5 else 0
    items.append({"key": "moat", "label": "Moat pillars (4 x 0-2)", "points": moat_pts,
                  "min": 0, "max": 8, "source": "feroldi:M1-M4",
                  "reasoning": f"{moat_pts}/8 from network, switching, cost, intangibles."})

    p1 = raw("P1")
    opt_pts = 3 if p1 >= 5 else 2 if p1 >= 3 else 1
    items.append({"key": "optionality", "label": "Optionality", "points": opt_pts,
                  "min": 1, "max": 3, "source": "feroldi:P1",
                  "reasoning": by_key.get("P1", {}).get("reasoning", "")})

    net_debt, fcf = profile.get("net_debt"), profile.get("free_cash_flow")
    if net_debt is not None and net_debt <= 0 and (fcf or 0) > 0:
        ff_pts, ff_why = 1, "Net cash and positive FCF."
    elif net_debt is not None and net_debt > 0 and (fcf or 0) <= 0:
        ff_pts, ff_why = -1, "Net debt with weak/negative FCF."
    else:
        ff_pts, ff_why = 0, "Mixed cash/debt/FCF picture."
    items.append({"key": "fortitude", "label": "Cash, debt, free cash flow", "points": ff_pts,
                  "min": -1, "max": 1, "source": "computed", "reasoning": ff_why})

    x2 = next((g["score"] for g in feroldi["gauntlet_items"] if g["key"] == "X2"), 0)
    conc_pts = -3 if x2 <= -5 else -2 if x2 <= -3 else 0
    items.append({"key": "concentration", "label": "Concentration", "points": conc_pts,
                  "min": -3, "max": 0, "source": "feroldi:X2",
                  "reasoning": next((g["reasoning"] for g in feroldi["gauntlet_items"]
                                     if g["key"] == "X2"), "")})

    items.append({"key": "glassdoor", "label": "Glassdoor", "points": 0,
                  "min": -1, "max": 1, "source": "unavailable",
                  "reasoning": "No Glassdoor API — scored neutral 0."})

    founder_pts = 1 if raw("G1") >= 3 else 0
    items.append({"key": "founder", "label": "Founder involved", "points": founder_pts,
                  "min": 0, "max": 1, "source": "feroldi:G1",
                  "reasoning": by_key.get("G1", {}).get("reasoning", "")})

    pct = profile.get("insider_ownership_pct")
    own_pts = 0 if pct is None else (1 if pct > 0.08 else -1 if pct < 0.04 else 0)
    items.append({"key": "ownership", "label": "Insider ownership", "points": own_pts,
                  "min": -1, "max": 1, "source": "computed",
                  "reasoning": f"Insiders own {pct*100:.1f}%." if pct is not None
                               else "Ownership unavailable — neutral."})

    total = sum(i["points"] for i in items)
    band = "FANTASTIC" if total >= 12 else "INVESTABLE" if total >= 7 else "IGNORE"
    return {"items": items, "total": total, "band": band}


# -- Entry point ---------------------------------------------------------------

def _band(total: float) -> str:
    if total >= 80:
        return "EXCEPTIONAL"
    if total >= 65:
        return "HIGH QUALITY"
    if total >= 50:
        return "AVERAGE"
    return "BELOW THE BAR"


def run(profile: dict) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    context = profile_context(profile)
    gaps: list[str] = []

    # -- Deterministic
    fin_items = _fin_items(profile, gaps)
    g3 = _inside_ownership(profile, gaps)
    c0 = _acquisition_cost(profile)

    # -- LLM call A: Moat + Potential
    print(f"  [Feroldi] Scoring Moat + Potential for {company}...")
    raw_a = call_llm(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": f"Company data:\n{context}\n\n{_PROMPT_A}"}],
        max_tokens=800, temperature=0.1, stage="Feroldi A")
    keys_a = ["M1", "M2", "M3", "M4", "M5", "M6", "P1", "P2", "P3", "P4"]
    parsed_a = _parse_lines(raw_a, keys_a)
    max_a = {"M1": 15, "M2": 15, "M3": 15, "M4": 15, "M5": 10, "M6": 5,
             "P1": 7, "P2": 4, "P3": 3, "P4": 4}
    labels_a = {"M1": "Network effect / ecosystem", "M2": "Switching costs",
                "M3": "Durable cost advantage", "M4": "Intangibles",
                "M5": "Counter-positioning", "M6": "Moat direction",
                "P1": "Optionality", "P2": "Organic growth runway",
                "P3": "Top dog & first mover", "P4": "Operating leverage ahead"}
    items_a = {}
    for k in keys_a:
        score, why = parsed_a[k]
        items_a[k] = {"key": k, "label": labels_a[k],
                      "score": _clamp(score, 0, max_a[k]), "max": max_a[k],
                      "method": "llm", "reasoning": why or "No answer parsed — scored 0."}

    # -- LLM call B: Customers / Company / Management / Stock judgement items
    print(f"  [Feroldi] Scoring Customers / Company / Management / Stock...")
    keys_b = ["C1", "K1", "K2", "G1", "G2", "S1", "S2", "S3"]
    if c0 is None:
        keys_b.append("C0")
    prompt_b = ("Score these items. Ranges are hard limits.\n\n"
                + "\n".join(_PROMPT_B_ITEMS[k][0] for k in keys_b)
                + "\n\nReply in this exact format, one line each, integer scores in brackets:\n"
                + "\n".join(f"{k}: [score] One sentence of reasoning." for k in keys_b))
    raw_b = call_llm(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": f"Company data:\n{context}\n\n{prompt_b}"}],
        max_tokens=700, temperature=0.1, stage="Feroldi B")
    parsed_b = _parse_lines(raw_b, keys_b)
    labels_b = {"C1": "Customer dependence", "K1": "Recurring revenue", "K2": "Pricing power",
                "G1": "Soul in the game", "G2": "Mission statement",
                "S1": "5-yr performance vs S&P", "S2": "Shareholder-friendly actions",
                "S3": "Beats expectations", "C0": "Customer acquisition cost"}
    items_b = {}
    for k in keys_b:
        score, why = parsed_b[k]
        mx = _PROMPT_B_ITEMS[k][1]
        items_b[k] = {"key": k, "label": labels_b[k],
                      "score": _clamp(score, 0, mx), "max": mx,
                      "method": "llm", "reasoning": why or "No answer parsed — scored 0."}
    if c0 is not None:
        items_b["C0"] = c0

    # -- LLM call C: Gauntlet
    print(f"  [Feroldi] Running the Gauntlet...")
    raw_c = call_llm(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": f"Company data:\n{context}\n\n{_PROMPT_C}"}],
        max_tokens=800, temperature=0.1, stage="Feroldi Gauntlet")
    keys_c = list(_GAUNTLET_ALLOWED.keys())
    parsed_c = _parse_lines(raw_c, keys_c)
    gauntlet_items = []
    for k in keys_c:
        score, why = parsed_c[k]
        item = {"key": k, "label": _GAUNTLET_LABELS[k],
                "score": _snap_allowed(score, _GAUNTLET_ALLOWED[k]),
                "method": "llm", "reasoning": why or "No answer parsed — no penalty applied."}
        gauntlet_items.append(item)
    # Deterministic override: extreme dilution from share-count CAGR
    x7 = _dilution_penalty(profile)
    if x7 is not None:
        gauntlet_items = [x7 if g["key"] == "X7" else g for g in gauntlet_items]

    # -- Assemble sections (moat scaled 75 -> 30)
    moat_raw = sum(items_a[k]["score"] for k in ("M1", "M2", "M3", "M4", "M5", "M6"))
    moat_scaled = round(moat_raw * _MOAT_SCALED_MAX / _MOAT_RAW_MAX, 1)

    glassdoor = {"key": "G4", "label": "Glassdoor ratings", "score": 0, "max": 4,
                 "method": "unavailable", "reasoning": "No Glassdoor API — excluded from denominator."}
    gaps.append("glassdoor")

    sections = [
        {"key": "financials", "label": "Financials", "max": 17, "items": fin_items},
        {"key": "moat", "label": "Moat", "max": _MOAT_SCALED_MAX,
         "items": [items_a[k] for k in ("M1", "M2", "M3", "M4", "M5", "M6")],
         "raw_max": _MOAT_RAW_MAX, "raw_score": moat_raw},
        {"key": "potential", "label": "Potential", "max": 18,
         "items": [items_a[k] for k in ("P1", "P2", "P3", "P4")]},
        {"key": "customers", "label": "Customers", "max": 10,
         "items": [items_b["C0"], items_b["C1"]]},
        {"key": "company", "label": "Company-specific", "max": 10,
         "items": [items_b["K1"], items_b["K2"]]},
        {"key": "management", "label": "Management & Culture", "max": 14,
         "items": [items_b["G1"], g3, glassdoor, items_b["G2"]]},
        {"key": "stock", "label": "Stock", "max": 11,
         "items": [items_b["S1"], items_b["S2"], items_b["S3"]]},
    ]
    for sec in sections:
        if sec["key"] == "moat":
            sec["score"] = moat_scaled
        else:
            sec["score"] = round(sum(i["score"] for i in sec["items"]), 1)

    unavailable_max = sum(
        i["max"] for sec in sections for i in sec["items"]
        if i.get("method") == "unavailable" and sec["key"] != "moat"
    )
    max_effective = 110 - unavailable_max
    raw_total = sum(sec["score"] for sec in sections)
    pre_gauntlet = round(raw_total * 100 / max_effective, 1) if max_effective else 0.0
    gauntlet = sum(g["score"] for g in gauntlet_items)
    total = round(pre_gauntlet + gauntlet, 1)

    feroldi = {
        "sections": sections,
        "pre_gauntlet": pre_gauntlet,
        "pre_gauntlet_raw": round(raw_total, 1),
        "max_effective": max_effective,
        "gauntlet_items": gauntlet_items,
        "gauntlet": gauntlet,
        "total": total,
        "max": 100,
        "band": _band(total),
        "data_gaps": sorted(set(gaps)),
    }
    antifragile = derive_antifragile(feroldi, profile)
    return feroldi, antifragile
