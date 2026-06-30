# Stage 2 - BMP Gate

import os
from groq import Groq

_DIGITAL_MATURE_MARGINS = {
    "internet content & information": 0.35,   # Google, Meta
    "internet retail":                0.12,   # Amazon blended
    "software - application":         0.25,
    "software—application":           0.25,
    "software - infrastructure":      0.30,
    "software—infrastructure":        0.30,
    "semiconductors":                 0.28,
    "semiconductor equipment":        0.25,
    "entertainment":                  0.18,   # Netflix, Disney
    "consumer electronics":           0.12,
    "information technology services":0.22,
}
_DIGITAL_SECTORS = frozenset({"Technology", "Communication Services"})

# Segment-weighted mature margins for multi-business conglomerates.
# Format: ticker -> [(revenue_share, mature_margin, label), ...]
# Revenue shares are approximate; refresh annually from 10-K segment data.
# Sources: Damodaran sector data, company 10-Ks, sell-side comps.
_SEGMENT_MATURE_MARGINS = {
    # Amazon: FMP misclassifies as "Specialty Retail"; real mix is 3 distinct businesses
    "AMZN": [
        (0.15, 0.35, "AWS"),              # cloud infra; Azure/GCP comp at maturity
        (0.08, 0.45, "Advertising"),      # ad-tech at scale; Meta/Google comp
        (0.77, 0.05, "Retail/Logistics"), # e-commerce + fulfilment; thin structural margin
    ],
    # Alphabet: search dominance + fast-growing cloud suppressed by infra spend
    "GOOGL": [
        (0.56, 0.42, "Search & Ads"),     # near-mature; durable pricing power
        (0.10, 0.35, "YouTube"),          # ad-supported video at scale
        (0.13, 0.28, "Google Cloud"),     # investing heavily; Azure/AWS comp
        (0.21, 0.12, "Other/Bets"),       # subscriptions, hardware, moonshots
    ],
    "GOOG": [                             # same economic exposure, different share class
        (0.56, 0.42, "Search & Ads"),
        (0.10, 0.35, "YouTube"),
        (0.13, 0.28, "Google Cloud"),
        (0.21, 0.12, "Other/Bets"),
    ],
    # Meta: core advertising very high-margin; Reality Labs in heavy pre-profit phase
    "META": [
        (0.97, 0.48, "Family of Apps"),   # FB/IG/WhatsApp ad engine at maturity
        (0.03, 0.00, "Reality Labs"),     # deliberate loss; AR/VR platform bet
    ],
    # Microsoft: three clearly separated segments with different margin profiles
    "MSFT": [
        (0.43, 0.45, "Intelligent Cloud"),        # Azure + server; highest-margin segment
        (0.33, 0.40, "Productivity & Business"),  # Office 365, LinkedIn, Dynamics
        (0.24, 0.22, "More Personal Computing"),  # Windows, Gaming, Bing
    ],
}


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
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        from agents.llm_client import gemini_call
        return gemini_call(messages, max_tokens, temperature, stage="BMP")


GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

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

STEP 1 — Reported OEY = Operating Income × 0.79 / Market Cap × 100.
Strips GAAP noise (stock comp, amortisation) to approximate after-tax earnings power.
Use this for traditional businesses (industrials, consumer, financial, etc.).

STEP 2 — Normalized OEY (digital/tech companies only, Seessel "Where the Money Is"):
If Normalized OEY is provided in the data, use it instead for companies suppressing margins
via heavy growth reinvestment in R&D, S&M, or infrastructure build-out.
Formula: Revenue × Sector Mature Operating Margin × 0.79 / Market Cap.
Logic: a company with 60%+ gross margins but <10% operating margin is almost certainly
reinvesting, not structurally unprofitable. At maturity, margins revert to sector norms.
→ Use Normalized OEY when it is provided AND materially higher than Reported OEY.
→ State which OEY you are using in your reasoning.

Thresholds (apply to whichever OEY is relevant):
YES     -- OEY >= 5%.  Clear value or fair entry.
PARTIAL -- OEY 3-5%.  Expensive but justifiable if growth is strong.
NO      -- OEY < 3%.  Priced for perfection, limited margin of safety.
NEEDS MANUAL REVIEW -- Operating Income missing, negative, or unavailable.

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

    # Seessel normalized OEY
    normalized_oey    = None
    mature_margin_pct = None
    segment_breakdown = None           # human-readable segment decomposition
    industry_lower    = (profile.get("industry") or "").lower()
    sector_val        = profile.get("sector") or ""
    ticker_val        = (profile.get("ticker") or "").upper()

    if ticker_val in _SEGMENT_MATURE_MARGINS:
        segs = _SEGMENT_MATURE_MARGINS[ticker_val]
        mature_margin_pct = round(sum(s * m for s, m, _ in segs), 4)
        segment_breakdown = " + ".join(
            f"{lbl} ({s:.0%}×{m:.0%})" for s, m, lbl in segs
        )
    else:
        for key, margin in _DIGITAL_MATURE_MARGINS.items():
            if key in industry_lower:
                mature_margin_pct = margin
                break
    if mature_margin_pct is None and sector_val in _DIGITAL_SECTORS:
        mature_margin_pct = 0.25  # generic tech fallback

    norm_oey_raw = None   # always computed when possible; used even in N/A line
    if mature_margin_pct and revenues and market_cap and market_cap > 0:
        latest_rev = revenues[0].get("revenue") if revenues else None
        if isinstance(latest_rev, (int, float)) and latest_rev > 0:
            norm_op_income = latest_rev * mature_margin_pct
            norm_oey_raw   = round((norm_op_income * 0.79 / market_cap) * 100, 2)
            # Only surface as the active OEY when normalization reveals materially higher earnings power
            if oey is None or norm_oey_raw > oey * 1.15:
                normalized_oey = norm_oey_raw

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
        *(
            # Normalization fires: show as the active OEY with full segment derivation
            [f"Normalized OEY:    {normalized_oey}% "
             f"({'Segments: ' + segment_breakdown + ' → ' if segment_breakdown else ''}"
             f"{mature_margin_pct:.1%} blended op margin × Rev × 0.79 / Mkt Cap) [Seessel — USE THIS for Q5]"]
            if normalized_oey is not None else
            # Segment data exists but current margins already near mature — show computed OEY for transparency
            [f"Normalized OEY:    N/A — computed {norm_oey_raw}% OEY (mature blended op margin {mature_margin_pct:.1%}: "
             f"{segment_breakdown}) is not materially above reported OEY {oey}%; "
             f"use reported OEY for Q5"]
            if segment_breakdown and norm_oey_raw is not None else
            # No segment data but segment_breakdown set (shouldn't occur) or no data at all
            ["Normalized OEY:    N/A (traditional business or margins not suppressed by reinvestment)"]
        ),
        f"FCF Yield:         {fcf_yield}% (FCF / Mkt Cap)" if fcf_yield is not None else "FCF Yield:          N/A",
        f"Beta:              {profile.get('beta', 'N/A')}",
        f"Revenue (3yr):     {rev_str}",
        f"Revenue CAGR:      {cagr}% (3yr)" if cagr is not None else "Revenue CAGR:      N/A",
        f"Free Cash Flow:    {fcf if fcf is not None else 'N/A'}",
        f"Operating Income:  {op_income if op_income is not None else 'N/A'}",
        f"Op. Cash Flow:     {op_cf if op_cf is not None else 'N/A'}",
        f"ROE:               {roe_str}",
        *(
            [f"ROCE (avg):        {round(profile.get('roce_avg') * 100, 2)}%  Trend: {profile.get('roce_trend', 'N/A')}"]
            if profile.get("roce_avg") is not None else ["ROCE:              N/A"]
        ),
        *(
            [f"ROIC (avg):        {round(profile.get('roic_avg') * 100, 2)}%  Trend: {profile.get('roic_trend', 'N/A')}"]
            if profile.get("roic_avg") is not None else ["ROIC:              N/A"]
        ),
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
