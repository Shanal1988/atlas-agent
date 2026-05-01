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
    resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
        model=GROQ_MODEL, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content


GROQ_MODEL = "llama-3.3-70b-versatile"

_BMP_SYSTEM = (
    "You are a disciplined long-term equity analyst using the BMP checklist framework. "
    "Answer each BMP question with YES, PARTIAL, or NO based strictly on the data provided. "
    "Give a single sentence of reasoning for each answer. "
    "Be concise and brutally honest. Do not give benefit of the doubt without evidence."
)

_BMP_QUESTIONS = """
Q1 BUSINESS: Does the company have a low market share of a large and growing market with an identifiable competitive advantage?
Criteria: market share < 30%, growing TAM, clear moat identified. If market share is unknown, infer from sector context and company size vs TAM.

Q2 MOAT: Does the company have a sustainable competitive advantage?
Criteria: at least one of - switching costs, network effects, cost advantage, intangible assets, efficient scale.

Q3 MANAGEMENT: Do managers think and act like owners?
Criteria: insider ownership > 5%, low dilution history, sensible capital allocation.

Q4 GROWTH: Has the company grown sales and earnings consistently?
Criteria: revenue CAGR > 10% over 3 years, positive free cash flow.

Q5 PRICE SANITY: Can you arrive at a reasonable earnings yield > 5%?
Criteria: earnings yield = (1 / P/E) * 100. If P/E is missing or negative, reply NEEDS MANUAL REVIEW.

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

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        f"Current Price:     {profile.get('current_price', 'N/A')}",
        f"P/E Ratio:         {pe if pe else 'N/A'}",
        f"Earnings Yield:    {earnings_yield}%" if earnings_yield else "Earnings Yield:    N/A",
        f"Beta:              {profile.get('beta', 'N/A')}",
        f"Revenue (3yr):     {rev_str}",
        f"Revenue CAGR:      {cagr}% (3yr)" if cagr is not None else "Revenue CAGR:      N/A",
        f"Free Cash Flow:    {profile.get('free_cash_flow', 'N/A')}",
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

    return {"answers": answers, "score": score, "verdict": verdict}
