# Ten Vital Signs (user's investing process §12) — score 0 / 0.5 / 1 each.
#
# One LLM call for the 10 judgement items + two closing free-text questions.
# Deterministic floor: V1 (balance sheet) capped at 0.5 when net debt > 0.

from agents.context import profile_context, call_llm
import logging
logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a quality-growth investor running your Ten Vital Signs checklist. "
    "Score each vital sign 0 (fails), 0.5 (partial), or 1 (clearly passes) based "
    "strictly on the data provided. One short sentence of reasoning each. "
    "Be conservative — no credit without evidence."
)

_PROMPT = """
V1 Strong balance sheet, preferably net cash? (net cash vs net debt, debt trend, interest coverage, could cash cover expenses in a zero-revenue stress test)
V2 Organic revenue growth powered by a large market / long-term tailwinds? (TAM, secular themes, reinvestment at high returns)
V3 Rising or stable margins, gross and operating? (pricing power, operating leverage, mix — not growth-at-any-cost)
V4 High/increasing ROIC with growing earnings and FCF? (moat protected and new moats built)
V5 Exceptional CEO and leadership team? (founder, inside ownership, long-term orientation, culture)
V6 Recurring revenue and/or pricing power? (contracts, subscriptions, consumables, habits, mission-critical)
V7 Medium (or lower) risk profile? (debt, cyclicality, concentration, disruption, regulation, earnings quality)
V8 Executing well — strong business momentum? (growth maintained/accelerating, taking share, rising margins)
V9 Mission beyond maximizing profits? (solving an important problem, stakeholder win-wins)
V10 Multi-bagger potential? (innovation, optionality, first mover in an emerging frontier, saves customers time/money)

After the 10 scores, answer the two closing questions in one sentence each.

Reply in this exact format:
V1: [0/0.5/1] One sentence of reasoning.
V2: [0/0.5/1] ...
V3: [0/0.5/1] ...
V4: [0/0.5/1] ...
V5: [0/0.5/1] ...
V6: [0/0.5/1] ...
V7: [0/0.5/1] ...
V8: [0/0.5/1] ...
V9: [0/0.5/1] ...
V10: [0/0.5/1] ...
SANE_VALUATION: Is the stock selling at a sane valuation? One sentence.
OPPORTUNITY_COST: What is the opportunity cost vs adding to existing holdings? One sentence.
"""

_LABELS = {
    "V1": "Strong balance sheet (net cash)",
    "V2": "Organic growth, large market/tailwinds",
    "V3": "Rising or stable margins",
    "V4": "High/increasing ROIC, growing FCF",
    "V5": "Exceptional CEO and leadership",
    "V6": "Recurring revenue / pricing power",
    "V7": "Medium (or lower) risk profile",
    "V8": "Executing well (momentum)",
    "V9": "Mission beyond profits",
    "V10": "Multi-bagger potential",
}


def _valuation_summary(valuation: dict | None) -> str:
    if not valuation or valuation.get("available") is False:
        return "Intrinsic value models: unavailable."
    lines = []
    mktcap = valuation.get("mktcap_mn")
    if mktcap:
        lines.append(f"Market cap: ${mktcap:,.0f}M")
    for name, key in (("Dhandho IV", "dhandho"), ("Graham IV", "graham")):
        d = valuation.get(key) or {}
        lo, hi = d.get("lower"), d.get("higher")
        # Dhandho lower/higher are dicts with an "iv" key; Graham's are numbers
        if isinstance(lo, dict):
            lo = lo.get("iv")
        if isinstance(hi, dict):
            hi = hi.get("iv")
        if lo and hi:
            lines.append(f"{name}: ${lo:,.0f}M – ${hi:,.0f}M")
    dcf = valuation.get("dcf") or {}
    if dcf.get("iv"):
        lines.append(f"DCF IV: ${dcf['iv']:,.0f}M")
    return "Intrinsic value models:\n" + "\n".join(lines) if lines else "Intrinsic value models: unavailable."


def run(profile: dict, bmp_result: dict | None, fisher_result: dict | None,
        valuation_result: dict | None) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    logger.info(f"  [Vital Signs] Scoring 10 vital signs for {company}...")

    context = profile_context(profile)
    extra = []
    if bmp_result:
        extra.append(f"BMP checklist score: {bmp_result.get('score')} / 5 ({bmp_result.get('verdict')})")
    if fisher_result:
        extra.append(f"Fisher 15-point score: {fisher_result.get('total')} / 15 ({fisher_result.get('rating')})")
    extra.append(_valuation_summary(valuation_result))

    raw = call_llm(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": f"Company data:\n{context}\n\n"
                                     f"Prior pipeline signals:\n" + "\n".join(extra)
                                     + f"\n\n{_PROMPT}"}],
        max_tokens=700, temperature=0.1, stage="Vital Signs")

    items = []
    for i in range(1, 11):
        key = f"V{i}"
        score, reasoning = 0.0, "No answer parsed — scored 0."
        for line in (raw or "").splitlines():
            s = line.strip()
            if s.startswith(f"{key}:"):
                rest = s.split(":", 1)[1].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        try:
                            score = float(rest[1:close].strip())
                        except ValueError:
                            score = 0.0
                        reasoning = rest[close + 1:].strip()
                else:
                    parts = rest.split(None, 1)
                    try:
                        score = float(parts[0])
                        reasoning = parts[1] if len(parts) > 1 else ""
                    except (ValueError, IndexError):
                        reasoning = rest
                break
        score = min((0.0, 0.5, 1.0), key=lambda a: abs(a - score))
        items.append({"key": key, "label": _LABELS[key], "score": score, "reasoning": reasoning})

    # Deterministic floor: V1 capped at 0.5 when carrying net debt
    net_debt = profile.get("net_debt")
    if net_debt is not None and net_debt > 0 and items[0]["score"] > 0.5:
        items[0]["score"] = 0.5
        items[0]["reasoning"] += " [Floor: net debt > 0 caps V1 at 0.5]"

    def closing(label: str) -> str:
        for line in (raw or "").splitlines():
            if line.strip().startswith(f"{label}:"):
                return line.split(":", 1)[1].strip()
        return "N/A"

    total = round(sum(i["score"] for i in items), 1)
    result = {
        "items": items, "total": total, "max": 10,
        "closing": {
            "sane_valuation": closing("SANE_VALUATION"),
            "opportunity_cost": closing("OPPORTUNITY_COST"),
        },
    }
    return result
