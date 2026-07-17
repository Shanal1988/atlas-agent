# Stage - Munger Four Filters (first gate of the user's investing process, §5)
#
# F1 understand / F2 moat / F3 management are judgement calls -> one LLM call.
# F4 price is computed deterministically from the shared OEY helper:
#   active OEY >= 5% -> YES, 3-5% -> TBC, < 3% -> NO, unknown -> TBC.
# The pipeline does not hard-stop on a failed filter; the verdict feeds the
# thesis decision.

from agents.context import profile_context, compute_oey, call_llm

_SYSTEM = (
    "You are Charlie Munger applying your Four Filters to an investment idea. "
    "Answer each filter with YES, TBC, or NO based strictly on the data provided. "
    "TBC means 'to be confirmed' — plausible but not yet proven. "
    "Give a single sentence of reasoning for each. Be concise and brutally honest."
)

_QUESTIONS = """
F1 UNDERSTAND: Is this a business an intelligent generalist can understand — clear products,
clear customers, clear reason people pay? (A simple description and an identifiable revenue
model = YES. Opaque, highly technical or shifting business models = TBC or NO.)

F2 MOAT: Does the business have sustainable competitive advantages producing long-term
favourable economics? (Durable moat with evidence — switching costs, network effects,
cost advantage, brand/intangibles — plus healthy returns on capital = YES. Some advantage
but unproven durability = TBC. No identifiable advantage = NO.)

F3 MANAGEMENT: Is management able AND trustworthy — do they act like owners? (Founder-led or
high insider ownership with a sound capital-allocation record = YES. Competent but ordinary
agent-managers = TBC. Promotional, diluting, or misaligned management = NO.)

Reply in this exact format. Each answer on one line. Do not use curly braces:
F1: [YES/TBC/NO] One sentence of reasoning here.
F2: [YES/TBC/NO] One sentence of reasoning here.
F3: [YES/TBC/NO] One sentence of reasoning here.
"""

_LABELS = {
    "F1": "Do I understand the business?",
    "F2": "Sustainable competitive advantages?",
    "F3": "Able and trustworthy management?",
    "F4": "Price with a margin of safety?",
}


def _parse(text: str) -> dict:
    out = {}
    for key in ("F1", "F2", "F3"):
        rating, reasoning = "TBC", "No answer parsed — treated as to-be-confirmed."
        for line in (text or "").splitlines():
            if line.strip().startswith(f"{key}:"):
                rest = line.split(":", 1)[1].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        rating = rest[1:close].strip().upper()
                        reasoning = rest[close + 1:].strip()
                else:
                    parts = rest.split(None, 1)
                    rating = parts[0].rstrip(".").upper()
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        if rating not in ("YES", "TBC", "NO"):
            rating = "TBC"
        out[key] = (rating, reasoning)
    return out


def _price_filter(oey: dict) -> tuple[str, str]:
    active = oey.get("active_oey")
    which = "normalized" if oey.get("normalized_oey") is not None else "reported"
    if active is None:
        return "TBC", "Operating earnings yield unavailable — price cannot be assessed yet."
    if active >= 5.0:
        return "YES", f"{which.capitalize()} operating earnings yield of {active}% clears the 5% hurdle."
    if active >= 3.0:
        return "TBC", f"{which.capitalize()} OEY of {active}% is below the 5% hurdle — wait for Mr. Market."
    return "NO", f"{which.capitalize()} OEY of {active}% is priced for perfection (<3%)."


def _verdict(filters: list[dict]) -> str:
    ratings = [f["rating"] for f in filters]
    yes = ratings.count("YES")
    if yes == 4:
        return "ALL FOUR FILTERS PASSED"
    if "NO" not in ratings:
        tbc = [f["key"] for f in filters if f["rating"] == "TBC"]
        return f"PROVISIONAL PASS — {', '.join(tbc)} to be confirmed"
    failed = [f["key"] for f in filters if f["rating"] == "NO"]
    return f"FAILS FILTER {', '.join(failed)} — Munger would pass on this idea"


def run(profile: dict) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"\n  [Munger] Applying the Four Filters to {company}...")

    context = profile_context(profile)
    raw = call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Company data:\n{context}\n\n{_QUESTIONS}"},
        ],
        max_tokens=300, temperature=0.1, stage="Munger",
    )
    parsed = _parse(raw)
    oey = compute_oey(profile)
    f4_rating, f4_reason = _price_filter(oey)

    filters = [
        {"key": k, "label": _LABELS[k], "rating": parsed[k][0],
         "reasoning": parsed[k][1], "method": "llm"}
        for k in ("F1", "F2", "F3")
    ]
    filters.append({"key": "F4", "label": _LABELS["F4"], "rating": f4_rating,
                    "reasoning": f4_reason, "method": "computed"})

    pass_count = sum(1 for f in filters if f["rating"] == "YES")
    verdict = _verdict(filters)

    W = 44
    print(f"\n{'=' * W}")
    print("  ATLAS: MUNGER FOUR FILTERS")
    print(f"{'=' * W}")
    print(f"  Company: {company}")
    print()
    for f in filters:
        print(f"  {f['key']} {f['label']}: [{f['rating']}]")
        print(f"     {f['reasoning']}")
        print()
    print(f"  PASSED:  {pass_count} / 4")
    print(f"  VERDICT: {verdict}")
    print(f"{'=' * W}\n")

    return {"filters": filters, "pass_count": pass_count, "verdict": verdict}
