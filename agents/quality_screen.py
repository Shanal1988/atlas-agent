# Quality Score Screen (user's investing process §13)
#
# Qualitative: 8 measures x 1-5 via one LLM call (wheelhouse/interest scored via
# a neutral general-investor proxy, flagged proxy: true).
# Quantitative + Valuation points: fully deterministic from profile data.
# Glassdoor: no API -> N/A (0, excluded from denominator, listed in data_gaps).
# Non-NA revenue %: no reliable data feed -> LLM estimate flagged method "llm_estimate".

from agents.context import profile_context, call_llm

_SYSTEM = (
    "You are scoring a company on a quality screen. Score each measure 1-5 using "
    "the exact scale given. One short sentence of reasoning each. Be conservative."
)

_PROMPT = """
A1 Addictiveness — how often customers pay: multiple times/week=5, weekly=4, monthly=3, quarterly=2, less often=1.
A2 Virtualness — totally virtual=5, corporate offices only=4, corp+distribution=3, corp+DC+stores=2, full physical chain=1.
A3 CEO — founder who scaled and built a deep bench=5, long-term-minded non-founder=4, great CEO no team=3, distracted founder=2, jerk boss=1.
A4 Moat — high switching costs + widening + network effects=5, loyal following=4, sticky data but switchable=3, some advantage=2, none=1.
A5 Proven globalness — truly global=5, everywhere but China=4, major markets=3, NA or China only=2, US only=1.
A6 Optionality — multiple significant revenue streams + culture to create more=5, multiple streams=4, product+software=3, some ability=2, none=1.
A7 In my wheelhouse — score as a neutral generalist investor: how easy is this business to understand and follow? very easy=5 ... impenetrable=1.
A8 Interesting to follow — score as a neutral generalist investor: how engaging are this company's products/story? fascinating=5 ... dull=1.

Also estimate the percentage of revenue earned OUTSIDE North America (best estimate from what you know of the business; a number 0-100).

Reply in this exact format:
A1: [1-5] One sentence of reasoning.
A2: [1-5] ...
A3: [1-5] ...
A4: [1-5] ...
A5: [1-5] ...
A6: [1-5] ...
A7: [1-5] ...
A8: [1-5] ...
NON_NA_PCT: [number] One sentence on the revenue mix.
"""

_QUAL_LABELS = {
    "A1": "Addictiveness", "A2": "Virtualness", "A3": "CEO", "A4": "Moat",
    "A5": "Proven globalness", "A6": "Optionality",
    "A7": "In my wheelhouse", "A8": "Interesting to follow",
}


def _parse(text: str, keys: list[str]) -> dict:
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
                        score = float(parts[0].rstrip("%"))
                        reasoning = parts[1] if len(parts) > 1 else ""
                    except (ValueError, IndexError):
                        reasoning = rest
                break
        out[key] = (score, reasoning)
    return out


# -- Deterministic quantitative scoring ----------------------------------------

def _quarterly_yoy(profile: dict) -> list[float]:
    """YoY growth for up to the last 4 quarters (needs 8 quarters of revenue)."""
    rq = [r.get("revenue") for r in (profile.get("revenue_quarterly") or [])]
    growths = []
    for i in range(min(4, max(0, len(rq) - 4))):
        cur, prior = rq[i], rq[i + 4]
        if cur and prior and prior > 0:
            growths.append(cur / prior - 1)
    return growths


def _quant_items(profile: dict, gaps: list) -> list[dict]:
    items = []

    def add(key, label, score, points_max, method, reasoning, **kw):
        items.append({"key": key, "label": label, "score": score, "max": points_max,
                      "method": method, "reasoning": reasoning, **kw})

    revs = profile.get("revenues") or []
    rev = revs[0].get("revenue") if revs else None

    # Revenue (TTM) — 5 pts
    if rev is None:
        add("Q1", "Revenue (TTM)", 0, 5, "unavailable", "Revenue unavailable.")
        gaps.append("revenue_ttm")
    else:
        s = 5 if rev >= 5e9 else 3 if rev >= 1e9 else 1
        add("Q1", "Revenue (TTM)", s, 5, "computed", f"Latest annual revenue ${rev/1e9:.1f}B.")

    # Revenue growth, last 4 quarters — 15 pts (12 + 3 accelerating bonus)
    yoy = _quarterly_yoy(profile)
    if len(yoy) >= 2:
        lo = min(yoy)
        s = 12 if lo > 0.50 else 9 if lo > 0.30 else 6 if lo > 0.15 else 3 if lo > 0.08 else 1 if lo > 0 else 0
        accel = yoy[0] > yoy[-1]  # newest first
        if accel:
            s = min(15, s + 3)
        add("Q2", "Revenue growth (last 4Q YoY)", s, 15, "computed",
            f"YoY growth {', '.join(f'{g*100:.0f}%' for g in yoy)}"
            + (" — accelerating (+3)." if accel else "."))
    else:
        cagr = profile.get("revenue_cagr")
        if cagr is None:
            add("Q2", "Revenue growth (last 4Q YoY)", 0, 15, "unavailable",
                "Insufficient quarterly data and no CAGR.")
            gaps.append("revenue_growth_quarters")
        else:
            s = 12 if cagr > 0.50 else 9 if cagr > 0.30 else 6 if cagr > 0.15 else 3 if cagr > 0.08 else 1 if cagr > 0 else 0
            add("Q2", "Revenue growth (last 4Q YoY)", s, 15, "computed",
                f"Quarterly data sparse — 3yr revenue CAGR {cagr*100:.0f}% used as proxy.")

    # Cash/Debt — 5 pts
    cash, debt = profile.get("cash_and_equivalents"), profile.get("total_debt")
    if cash is None or debt is None:
        add("Q3", "Cash/Debt", 0, 5, "unavailable", "Cash or debt unavailable.")
        gaps.append("cash_debt")
    elif debt == 0 and rev and cash > 0.75 * rev:
        add("Q3", "Cash/Debt", 5, 5, "computed", "No debt and cash > 75% of TTM revenue.")
    else:
        ratio = cash / debt if debt > 0 else float("inf")
        s = 4 if ratio > 2.5 else 3 if ratio > 1 else 2 if ratio > 0.5 else 1 if ratio > 0.25 else 0
        add("Q3", "Cash/Debt", s, 5, "computed",
            "No debt but cash below 75% of revenue." if debt == 0 else f"Cash/debt ratio {ratio:.2f}.")

    # OCF / TTM revenue — 5 pts (can go negative)
    ocf = profile.get("operating_cash_flow")
    if ocf is None or not rev:
        add("Q4", "OCF / TTM revenue", 0, 5, "unavailable", "OCF or revenue unavailable.")
        gaps.append("ocf_revenue")
    else:
        r = ocf / rev
        s = 5 if r > 0.30 else 4 if r > 0.15 else 3 if r > 0.10 else 2 if r > 0.05 else 1 if r > 0 else -2 if r < -0.15 else -1
        add("Q4", "OCF / TTM revenue", s, 5, "computed", f"OCF is {r*100:.0f}% of revenue.")

    # Glassdoor — N/A
    add("Q5", "Glassdoor rating", 0, 5, "unavailable", "No Glassdoor API — excluded from denominator.")
    gaps.append("glassdoor")

    # % Operating income — 5 pts
    op = profile.get("operating_income")
    if op is None or not rev:
        add("Q6", "% Operating income (GAAP)", 0, 5, "unavailable", "Operating income unavailable.")
        gaps.append("operating_margin")
    else:
        m = op / rev
        s = 5 if m > 0.05 else 3 if m > 0 else -2 if m < -0.20 else -1 if m < -0.10 else 0
        add("Q6", "% Operating income (GAAP)", s, 5, "computed", f"Operating margin {m*100:.0f}%.")

    return items


def _val_items(profile: dict, gaps: list) -> list[dict]:
    items = []

    ps = profile.get("ps_ratio")
    if ps is None:
        items.append({"key": "L1", "label": "P/S (TTM)", "score": 0, "max": 5,
                      "method": "unavailable", "reasoning": "P/S unavailable."})
        gaps.append("ps_ratio")
    else:
        s = 5 if ps < 3 else 4 if ps < 6 else 3 if ps < 9 else 2 if ps < 12 else 1 if ps < 20 else -2 if ps > 40 else -1 if ps > 30 else 0
        items.append({"key": "L1", "label": "P/S (TTM)", "score": s, "max": 5,
                      "method": "computed", "reasoning": f"P/S ratio {ps}."})

    mc = profile.get("market_cap")
    if mc is None:
        items.append({"key": "L2", "label": "Market cap", "score": 0, "max": 5,
                      "method": "unavailable", "reasoning": "Market cap unavailable."})
        gaps.append("market_cap")
    else:
        s = 5 if mc < 3e9 else 4 if mc < 15e9 else 3 if mc < 30e9 else 2 if mc < 60e9 else 1 if mc < 100e9 else 0
        items.append({"key": "L2", "label": "Market cap", "score": s, "max": 5,
                      "method": "computed", "reasoning": f"Market cap ${mc/1e9:.0f}B (smaller = more upside)."})

    chg = profile.get("week52_change_pct")
    if chg is None:
        items.append({"key": "L3", "label": "52W stock growth", "score": 0, "max": 5,
                      "method": "unavailable", "reasoning": "52-week change unavailable."})
        gaps.append("week52_change")
    else:
        c = chg * 100
        s = 5 if c > 60 else 4 if c > 30 else 3 if c > 15 else 1 if c > 5 else -2 if c < -30 else -1 if c < -15 else 0
        items.append({"key": "L3", "label": "52W stock growth", "score": s, "max": 5,
                      "method": "computed", "reasoning": f"52-week change {c:+.0f}%."})
    return items


def run(profile: dict) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"  [Quality Screen] Scoring {company}...")
    gaps: list[str] = []

    context = profile_context(profile)
    raw = call_llm(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": f"Company data:\n{context}\n\n{_PROMPT}"}],
        max_tokens=700, temperature=0.1, stage="Quality Screen")

    keys = list(_QUAL_LABELS.keys()) + ["NON_NA_PCT"]
    parsed = _parse(raw, keys)

    qual_items = []
    for k, label in _QUAL_LABELS.items():
        score, why = parsed[k]
        score = max(1, min(5, round(score))) if score is not None else 1
        item = {"key": k, "label": label, "score": score, "max": 5,
                "method": "llm", "reasoning": why or "No answer parsed — scored 1."}
        if k in ("A7", "A8"):
            item["proxy"] = True   # personal-judgement items scored via neutral proxy
        qual_items.append(item)

    quant_items = _quant_items(profile, gaps)

    # Non-NA revenue % — LLM estimate (flagged)
    nna, nna_why = parsed["NON_NA_PCT"]
    if nna is None:
        quant_items.append({"key": "Q7", "label": "Non-NA revenue %", "score": 0, "max": 5,
                            "method": "unavailable", "reasoning": "No geographic data or estimate."})
        gaps.append("non_na_revenue")
    else:
        nna = max(0.0, min(100.0, nna))
        s = 5 if nna > 50 else 4 if nna > 30 else 3 if nna > 15 else 1 if nna > 5 else 0
        quant_items.append({"key": "Q7", "label": "Non-NA revenue %", "score": s, "max": 5,
                            "method": "llm_estimate", "value": nna,
                            "reasoning": nna_why or f"Estimated {nna:.0f}% of revenue outside North America."})

    val_items = _val_items(profile, gaps)

    qual_total = sum(i["score"] for i in qual_items)
    quant_total = sum(i["score"] for i in quant_items)
    val_total = sum(i["score"] for i in val_items)

    return {
        "qualitative": {"items": qual_items, "total": qual_total, "max": 40},
        "quantitative": {"items": quant_items, "total": quant_total,
                         "max": sum(i["max"] for i in quant_items
                                    if i.get("method") != "unavailable")},
        "valuation": {"items": val_items, "total": val_total, "max": 15},
        "overall": qual_total + quant_total + val_total,
        "data_gaps": sorted(set(gaps)),
    }
