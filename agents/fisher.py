# Stage 3 - Fisher 15-Point Analysis

import os
from groq import Groq
from tavily import TavilyClient


GROQ_MODEL = "llama-3.3-70b-versatile"

_FISHER_SYSTEM = (
    "You are Philip Fisher reincarnated as an AI equity analyst. "
    "Score each of the 15 Fisher points for this company using: "
    "1 (YES), 0.75 (MOSTLY), 0.5 (PARTIAL), or 0 (NO). "
    "For each point provide: score + one sentence of evidence-based reasoning. "
    "Be honest and rigorous. Partial credit requires real evidence, not assumption. "
    "If evidence is absent, score 0 and say so.\n\n"
    "Reply in this exact format, one point per line, no extra text:\n"
    "P1: [score] Reasoning here.\n"
    "P2: [score] Reasoning here.\n"
    "P3: [score] Reasoning here.\n"
    "P4: [score] Reasoning here.\n"
    "P5: [score] Reasoning here.\n"
    "P6: [score] Reasoning here.\n"
    "P7: [score] Reasoning here.\n"
    "P8: [score] Reasoning here.\n"
    "P9: [score] Reasoning here.\n"
    "P10: [score] Reasoning here.\n"
    "P11: [score] Reasoning here.\n"
    "P12: [score] Reasoning here.\n"
    "P13: [score] Reasoning here.\n"
    "P14: [score] Reasoning here.\n"
    "P15: [score] Reasoning here."
)

_FISHER_QUESTIONS = """
Evaluate the following 15 Fisher points using the company data and search evidence provided.
Valid scores: 1 (YES), 0.75 (MOSTLY), 0.5 (PARTIAL), 0 (NO).

P1  MARKET POTENTIAL:      Does the company have products/services with sufficient market potential for sizable sales increase over several years? (growing TAM, low market penetration, expansion runway)
P2  MANAGEMENT INNOVATION: Is management determined to develop new products/processes to sustain growth when current lines mature? (R&D investment, new product launches, platform expansion)
P3  R&D EFFECTIVENESS:     How effective are R&D efforts relative to company size? (R&D % of revenue, product pipeline, patent activity)
P4  SALES ORGANISATION:    Does the company have an above-average sales organisation? (customer satisfaction signals, sales efficiency, retention)
P5  PROFIT MARGINS:        Does the company have worthwhile profit margins? (operating margin > 20% for software/fintech, consistent or improving)
P6  MARGIN IMPROVEMENT:    What is the company doing to maintain or improve profit margins? (cost optimisation, economies of scale, pricing power)
P7  LABOUR RELATIONS:      Does the company have outstanding labour and personnel relations? (Glassdoor signals, employee retention, compensation)
P8  EXECUTIVE RELATIONS:   Does the company have outstanding executive relations? (compensation in line with industry, low executive turnover, succession planning)
P9  MANAGEMENT DEPTH:      Does the company have depth beyond one key person? (strong second-tier leadership, decentralised decisions, functions without founder dependency)
P10 COST CONTROLS:         How good are cost analysis and accounting controls? (CFO track record, clean audit history, disciplined opex management)
P11 INDUSTRY POSITION:     Are there unique industry aspects that give competitive clues? (industry-specific moat, regulatory advantages, proprietary data)
P12 LONG TERM OUTLOOK:     Does management take a long-range vs short-range profit outlook? (invest through downturns, long-term guidance language, capex for future growth)
P13 DILUTION RISK:         Will future growth require equity financing that cancels stockholder benefit? (FCF self-funding, debt levels, share count trend)
P14 MANAGEMENT TRANSPARENCY: Does management talk freely when things go wrong? (earnings call tone during misses, frank shareholder letters, no pattern of burying bad news)
P15 MANAGEMENT INTEGRITY:  Does the company have management of unquestionable integrity? (no fraud history, no related party scandals, consistent follow-through on commitments)
"""


# -- Tavily helpers ------------------------------------------------------------

def _tavily() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def _search(query: str, max_results: int = 4) -> str:
    results = _tavily().search(query=query, max_results=max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results.get("results", [])
    )


def _gather_evidence(company: str) -> str:
    """Five batched Tavily searches covering all 15 Fisher points."""
    searches = {
        "Market expansion & R&D pipeline (P1-P3)":
            f"{company} market expansion R&D pipeline new products",
        "Employee & customer satisfaction (P4, P7)":
            f"{company} glassdoor reviews employee satisfaction customer NPS",
        "Profit margins & operational efficiency (P5-P6)":
            f"{company} profit margins operating efficiency cost controls",
        "Management team, leadership depth & CFO (P8-P10)":
            f"{company} management team CFO leadership succession",
        "Strategy, dilution, integrity & shareholder letters (P11-P15)":
            f"{company} competitive position long term strategy share dilution management integrity shareholder",
    }

    sections = []
    for label, query in searches.items():
        content = _search(query)
        sections.append(f"=== {label} ===\n{content}")

    return "\n\n".join(sections)


# -- Profile context -----------------------------------------------------------

def _profile_context(profile: dict) -> str:
    revenues = profile.get("revenues") or []
    rev_str = "  |  ".join(
        f"{r.get('year','?')}: {r.get('revenue')}" for r in revenues
    ) or "N/A"

    cagr_raw = profile.get("revenue_cagr") if profile.get("revenue_cagr") is not None \
               else profile.get("revenue_growth_pct")
    cagr = f"{round(cagr_raw * 100, 2)}% (3yr)" if cagr_raw is not None else "N/A"

    roe = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    pe = profile.get("pe_ratio")
    fcf = profile.get("free_cash_flow")

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        f"Current Price:     {profile.get('current_price', 'N/A')}",
        f"P/E Ratio:         {pe or 'N/A'}",
        f"Beta:              {profile.get('beta', 'N/A')}",
        f"Revenue (3yr):     {rev_str}",
        f"Revenue CAGR:      {cagr}",
        f"Free Cash Flow:    {fcf or 'N/A'}",
        f"ROE:               {round(roe * 100, 2)}%" if roe else "ROE:               N/A",
        f"Insider Ownership: {round(insider * 100, 2)}%" if insider else "Insider Ownership: N/A",
        f"Moat:              {profile.get('moat', 'N/A')}",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors', []))}",
        f"Recent News:       {'; '.join(n for n in profile.get('news', []) if n and n != 'N/A')}",
    ]
    return "\n".join(lines)


# -- Groq scoring --------------------------------------------------------------

def _score_with_groq(company: str, profile_ctx: str, evidence: str) -> str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    user_msg = (
        f"Company financial data:\n{profile_ctx}\n\n"
        f"Research evidence:\n{evidence}\n\n"
        f"Fisher 15-point questions:\n{_FISHER_QUESTIONS}"
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _FISHER_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content


# -- Parser --------------------------------------------------------------------

_POINT_LABELS = {
    "P1":  "Market Potential",
    "P2":  "Management Innovation",
    "P3":  "R&D Effectiveness",
    "P4":  "Sales Organisation",
    "P5":  "Profit Margins",
    "P6":  "Margin Improvement",
    "P7":  "Labour Relations",
    "P8":  "Executive Relations",
    "P9":  "Management Depth",
    "P10": "Cost Controls",
    "P11": "Industry Position",
    "P12": "Long Term Outlook",
    "P13": "Dilution Risk",
    "P14": "Management Transparency",
    "P15": "Management Integrity",
}

_VALID_SCORES = {1.0, 0.75, 0.5, 0.0}


def _parse_scores(text: str) -> list[dict]:
    points = []
    for key in _POINT_LABELS:
        score = 0.0
        reasoning = "No response parsed."
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}:") or stripped.startswith(f"{key} "):
                rest = stripped[len(key):].lstrip(": ").strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        raw_score = rest[1:close].strip()
                        reasoning = rest[close + 1:].strip()
                        try:
                            parsed = float(raw_score)
                            score = parsed if parsed in _VALID_SCORES else round(parsed * 2) / 2
                        except ValueError:
                            score = 0.0
                else:
                    parts = rest.split(None, 1)
                    try:
                        score = float(parts[0])
                    except (ValueError, IndexError):
                        score = 0.0
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        points.append({
            "key":       key,
            "label":     _POINT_LABELS[key],
            "score":     score,
            "reasoning": reasoning,
        })
    return points


def _fisher_rating(total: float) -> str:
    if total >= 12:
        return "EXCEPTIONAL - high conviction candidate"
    if total >= 9:
        return "STRONG - worth deep analysis"
    if total >= 6:
        return "AVERAGE - proceed with caution"
    return "WEAK - does not meet Fisher standard"


# -- Output --------------------------------------------------------------------

def _print_fisher(profile: dict, points: list[dict], total: float) -> None:
    W = 48
    name = profile.get("name", "N/A")
    rating = _fisher_rating(total)

    print(f"\n{'=' * W}")
    print("  ATLAS: FISHER 15-POINT ANALYSIS")
    print(f"{'=' * W}")
    print(f"  Company: {name}")
    print()

    for pt in points:
        label_col = f"Point {pt['key'][1:]:>2} - {pt['label']}:"
        print(f"  {label_col:<32} [{pt['score']}]  {pt['reasoning']}")

    print()
    print(f"  FISHER SCORE:  {total} / 15")
    print(f"  FISHER RATING: {rating}")
    print(f"{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(profile: dict, bmp_verdict: str) -> dict | None:
    """
    Run Fisher 15-point analysis.
    Skips if BMP verdict is REJECT.
    Returns dict with points, total, rating — or None if skipped.
    """
    verdict_upper = bmp_verdict.upper()
    if verdict_upper.startswith("REJECT"):
        print("\nBMP Gate verdict: REJECT. Fisher analysis not warranted.")
        return None

    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"\n  [Fisher] Gathering evidence for {company}...")

    profile_ctx = _profile_context(profile)
    evidence    = _gather_evidence(company)

    print("  [Fisher] Scoring 15 points via Groq...")
    raw = _score_with_groq(company, profile_ctx, evidence)

    points = _parse_scores(raw)
    total  = round(sum(pt["score"] for pt in points), 2)
    rating = _fisher_rating(total)

    _print_fisher(profile, points, total)

    return {"points": points, "total": total, "rating": rating}
