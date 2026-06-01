# Stage 2 - BMP Gate

import os
from groq import Groq


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    """Use fine-tuned OpenAI model if OPENAI_FT_BMP_MODEL is set, else Groq."""
    ft_model = os.environ.get("OPENAI_FT_BMP_MODEL")
    if ft_model:
        try:
            from openai import OpenAI
            resp = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model=ft_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  [Warning] OpenAI BMP model failed ({e}), falling back to Groq.")
    try:
        resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}) -- BMP scoring skipped.")
        return ""


GROQ_MODEL = "llama-3.3-70b-versatile"

_BMP_SYSTEM = (
    "You are a disciplined long-term equity analyst using the BMP checklist framework. "
    "Answer each BMP question with YES, PARTIAL, or NO based strictly on the data provided. "
    "Give a single sentence of reasoning for each answer. "
    "Be concise and brutally honest. Do not give benefit of the doubt without evidence."
)

_BMP_QUESTIONS = """
Q1 BUSINESS: Does the company have at least one material business segment — or a credible strategic bet — with meaningful runway in a large, growing market?

STEP 1 — List every material segment. A segment is material if it: (a) represents >10% of revenue, (b) is growing >20% yoy, (c) is an explicitly stated strategic priority, or (d) is a funded optionality bet (moonshot / pre-revenue platform).
For each segment state: estimated market share, TAM size ($B) and direction, moat, and trajectory (accelerating / stable / declining).

STEP 2 — Include optionality / moonshot bets even if pre-revenue. These represent real options on future value. Assess their plausibility (is the company actually spending on them? Is there technical progress?) and flag the TAM if the bet succeeds.

STEP 3 — Assess whether the company is diversifying its revenue mix. A company actively growing new segments (e.g. shifting from ads to cloud + subscriptions) should be rewarded for that trajectory, not penalised for having a mature primary segment.

YES    -- At least one material segment has genuine runway (<15% share in a growing TAM >$20B with a clear moat), OR the company has a credible optionality portfolio that creates a real call option on a large future TAM. Judge the portfolio of businesses, not just the largest segment.
PARTIAL -- The primary segment is mature or highly penetrated, but secondary segments or strategic bets are growing rapidly and de-risking the revenue mix; OR a dominant primary segment has a still-expanding TAM with multi-year runway.
NO     -- All material segments are near-saturation or declining AND no credible optionality exists in the portfolio.

Do NOT score NO simply because the primary segment is large or dominant — dominance in a growing category is a strength, not a weakness.

Q2 MOAT: Does the company have a sustainable competitive advantage?
Criteria: at least one of - switching costs, network effects, cost advantage, intangible assets, efficient scale.
The strongest moat signal is Scale Economics Shared: the company reinvests scale savings back into lower prices or better service for customers, creating a self-reinforcing cycle where growth deepens the moat (e.g. Costco passes buying-club savings to members; Amazon reinvests fulfilment scale into faster/cheaper delivery; AirAsia's scale yields the lowest fares). Score YES if this pattern is clearly present. Score PARTIAL for a conventional cost/network moat without the customer-sharing flywheel.

Q3 MANAGEMENT: Do managers think and act like owners?
Criteria — assess in order:
1. VOTING CONTROL: For companies with dual/multi-class share structures (Class A/B/C or equivalent), founders or insiders with majority voting control ARE owner-aligned even if their economic ownership appears low. A founder holding <5% economic stake but >50% voting power via super-voting shares = PARTIAL minimum.
2. ECONOMIC OWNERSHIP: YES > 15%, PARTIAL 5-15%, NO < 5% — but only use this as the primary criterion if no super-voting structure exists.
3. CAPITAL ALLOCATION: low dilution history, sensible reinvestment, long-term mindset over short-term margin extraction.
Score YES if voting control is strong (founders effectively control the company) AND capital allocation is disciplined. Score PARTIAL if either voting control or ownership is meaningful but not both. Score NO only if economic ownership is negligible AND no voting control AND poor capital allocation track record.

Q4 GROWTH: Has the company grown sales and earnings consistently?
Criteria: revenue CAGR > 10% over 3 years, positive operating cash flow (OCF).

Q5 PRICE SANITY: Is the company's earnings power reasonably priced?
Use Operating Earnings Yield (OEY) = Operating Income x 0.79 / Market Cap x 100.
OEY strips GAAP noise (stock comp, amortisation) to approximate after-tax earnings power.

YES     -- OEY >= 5% (earnings power multiple <= 20x). Clear value or fair entry.
PARTIAL -- OEY 3-5% (20-33x earnings power). Expensive but justifiable if growth is strong.
          Example: OEY = 4.2% -> PARTIAL (borderline expensive, justified by 35% revenue CAGR)
NO      -- OEY < 3% (>33x earnings power). Priced for perfection with limited margin of safety.
NEEDS MANUAL REVIEW -- Operating Income is missing, negative, or not provided. Use Earnings Yield as a proxy if available.

Reply in this exact format. Each answer must be on one line. Do not use curly braces:
Q1: [YES/PARTIAL/NO] One sentence of reasoning here.
Q2: [YES/PARTIAL/NO] One sentence of reasoning here.
Q3: [YES/PARTIAL/NO/NEEDS MANUAL REVIEW] One sentence of reasoning here.
Q4: [YES/PARTIAL/NO] One sentence of reasoning here.
Q5: [YES/PARTIAL/NO/NEEDS MANUAL REVIEW] One sentence of reasoning here.
"""


def _profile_context(profile: dict) -> str:
    """Serialise the CompanyProfile into a readable block for Groq."""
    revenues = profile.get("revenues") or []
    rev_str = "  |  ".join(
        f"{r.get('year','?')}: {r.get('revenue')}"
        for r in revenues
    ) or "N/A"

    # CAGR is stored as a decimal fraction (e.g. 0.1918 = 19.18%)
    cagr_raw = profile.get("revenue_cagr") if profile.get("revenue_cagr") is not None \
               else profile.get("revenue_growth_pct")
    cagr = round(cagr_raw * 100, 2) if cagr_raw is not None else None

    insider = profile.get("insider_ownership_pct")
    insider_str = f"{insider * 100:.2f}%" if insider is not None else "N/A"

    roe = profile.get("roe")
    roe_str = f"{roe * 100:.2f}%" if roe is not None else "N/A"

    pe = profile.get("pe_ratio")
    earnings_yield = None
    if pe and pe > 0:
        earnings_yield = round((1 / pe) * 100, 2)

    op_income  = profile.get("operating_income")
    op_cf      = profile.get("operating_cash_flow")
    market_cap = profile.get("market_cap")
    fcf        = profile.get("free_cash_flow")

    oey = None
    if op_income and market_cap and market_cap > 0:
        oey = round((op_income * 0.79 / market_cap) * 100, 2)

    fcf_yield = None
    if fcf and market_cap and market_cap > 0:
        fcf_yield = round((fcf / market_cap) * 100, 2)

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {market_cap if market_cap else 'N/A'}",
        f"Current Price:     {profile.get('current_price', 'N/A')}",
        f"P/E Ratio:         {pe if pe else 'N/A'}",
        f"Earnings Yield:    {earnings_yield}%" if earnings_yield else "Earnings Yield:    N/A",
        f"Op. Earnings Yield:{oey}% (Op. Income x 0.79 / Mkt Cap)" if oey is not None else "Op. Earnings Yield: N/A",
        f"FCF Yield:         {fcf_yield}% (FCF / Mkt Cap)" if fcf_yield is not None else "FCF Yield:          N/A",
        f"Beta:              {profile.get('beta', 'N/A')}",
        f"Revenue (3yr):     {rev_str}",
        f"Revenue CAGR:      {cagr}% (3yr)" if cagr is not None else "Revenue CAGR:      N/A",
        f"Free Cash Flow:    {fcf if fcf is not None else 'N/A'}",
        f"Operating Income:  {op_income if op_income is not None else 'N/A'}",
        f"Op. Cash Flow:     {op_cf if op_cf is not None else 'N/A'}",
        f"ROE:               {roe_str}",
        f"Insider Ownership: {insider_str}",
        f"Competitive Moat:  {profile.get('moat', 'N/A')}",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors', []))}",
    ]
    return "\n".join(lines)


def _parse_answers(text: str) -> list[dict]:
    """
    Parse Groq response into a list of 5 answer dicts.
    Each dict: {label, rating, reasoning}
    """
    labels = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    answers = []

    for label in labels:
        rating = "N/A"
        reasoning = ""
        for line in text.splitlines():
            if line.strip().startswith(f"{label}:"):
                rest = line.split(":", 1)[1].strip()
                # Extract bracketed rating
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        rating = rest[1:close].strip()
                        reasoning = rest[close + 1:].strip()
                    else:
                        reasoning = rest
                else:
                    # No brackets — first word is rating
                    parts = rest.split(None, 1)
                    rating = parts[0].rstrip(".")
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        # Normalise split "NEEDS" + "MANUAL REVIEW ..." that some models emit
        if rating.upper() == "NEEDS" and reasoning.upper().startswith("MANUAL REVIEW"):
            rating = "NEEDS MANUAL REVIEW"
            reasoning = reasoning[len("MANUAL REVIEW"):].strip()

        answers.append({"label": label, "rating": rating, "reasoning": reasoning})

    return answers


def _score(answers: list[dict]) -> float:
    """YES=1, PARTIAL=0.5, everything else=0."""
    total = 0.0
    for a in answers:
        r = a["rating"].upper()
        if r == "YES":
            total += 1.0
        elif r == "PARTIAL":
            total += 0.5
    return total


def _verdict(score: float) -> str:
    if score >= 4.0:
        return "PROCEED TO FISHER ANALYSIS"
    if score >= 3.0:
        return "WATCHLIST - monitor and revisit"
    return "REJECT - not a long-term prospect"


def _print_gate(profile: dict, answers: list[dict], score: float, verdict: str) -> None:
    W = 44
    q_labels = {
        "Q1": "BUSINESS  ",
        "Q2": "MOAT      ",
        "Q3": "MANAGEMENT",
        "Q4": "GROWTH    ",
        "Q5": "PRICE     ",
    }

    print(f"\n{'=' * W}")
    print("  ATLAS: BMP GATE")
    print(f"{'=' * W}")
    print(f"  Company: {profile.get('name', 'N/A')}")
    print()

    for a in answers:
        label_str = q_labels.get(a["label"], a["label"])
        rating    = a["rating"].upper()
        reasoning = a["reasoning"]
        print(f"  {a['label']} {label_str}: [{rating}]")
        print(f"           {reasoning}")
        print()

    print(f"  SCORE:   {score} / 5")
    print(f"  VERDICT: {verdict}")
    print(f"{'=' * W}\n")


def run(profile: dict) -> dict:
    """
    Run the BMP gate against a CompanyProfile dict.
    Returns a result dict with keys: answers, score, verdict.
    """
    context = _profile_context(profile)
    user_msg = (
        f"Company data:\n{context}\n\n"
        f"Answer the following BMP checklist questions:\n{_BMP_QUESTIONS}"
    )

    raw = _call_llm(
        messages=[
            {"role": "system", "content": _BMP_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    answers = _parse_answers(raw)
    score   = _score(answers)
    verdict = _verdict(score)

    _print_gate(profile, answers, score, verdict)

    from agents.judge import audit_score_justification, print_judge
    judge_r = audit_score_justification("BMP", context, answers)
    print_judge(judge_r, profile.get("name", ""))

    return {"answers": answers, "score": score, "verdict": verdict, "judge": judge_r}
