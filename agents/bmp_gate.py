# Stage 2 - BMP Gate

from agents.context import profile_context as _profile_context, compute_oey


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    from agents.context import call_llm_with_ft
    return call_llm_with_ft(messages, max_tokens, temperature,
                            stage="BMP", ft_env_var="OPENAI_FT_BMP_MODEL")

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
