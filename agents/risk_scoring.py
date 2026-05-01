# Stage 5 - Risk Scoring & Position Sizing (Diamond-to-Egg Framework)

import os
from groq import Groq


GROQ_MODEL = "llama-3.3-70b-versatile"


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    """Use fine-tuned OpenAI model if OPENAI_FT_RISK_MODEL is set, else Groq."""
    ft_model = os.environ.get("OPENAI_FT_RISK_MODEL")
    if ft_model:
        try:
            from openai import OpenAI
            resp = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model=ft_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  [Warning] OpenAI Risk model failed ({e}), falling back to Groq.")
    resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
        model=GROQ_MODEL, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content

# (name, lo_nos, hi_nos, label, lo_pct, hi_pct)
_CATEGORIES = [
    ("Diamond", 0,  5,  "6-10%",  6.0,  10.0),
    ("Gold",    6,  8,  "4-6%",   4.0,   6.0),
    ("Silver",  9,  11, "2-4%",   2.0,   4.0),
    ("Bronze",  12, 14, "1-2%",   1.0,   2.0),
    ("Glass",   15, 18, "0.5-1%", 0.5,   1.0),
    ("Egg",     19, 999, "0%",    0.0,   0.0),
]

_RISK_SYSTEM = (
    "You are a risk analyst assessing position sizing for a UK-based "
    "long-term investor. For each of the 5 risk factors provided, "
    "assign a penalty score of 0, 1, or 2. "
    "Base your assessment strictly on the company data provided. "
    "Give one sentence of reasoning per factor. "
    "Be conservative - when in doubt, assign the higher penalty.\n\n"
    "Reply in this exact format, no extra text:\n"
    "R1: [0/1/2] Reasoning.\n"
    "R2: [0/1/2] Reasoning.\n"
    "R3: [0/1/2] Reasoning.\n"
    "R4: [0/1/2] Reasoning.\n"
    "R5: [0/1/2] Reasoning.\n"
    "CONVICTION: [HIGH/MEDIUM/LOW] One sentence overall conviction."
)

_RISK_QUESTIONS = """
R1 VALUATION RISK:      Is the current valuation stretched vs historical averages?
Use P/E ratio context. Penalty: 0 (fair value), 1 (moderately stretched), 2 (significantly stretched).

R2 CONCENTRATION RISK:  Is the company dependent on a single product, customer, or geography for >50% of revenue?
Penalty: 0 (diversified), 1 (moderate concentration), 2 (high concentration).

R3 REGULATORY RISK:     Is the company operating in a heavily regulated sector with active regulatory scrutiny?
Penalty: 0 (low risk), 1 (moderate - some regulatory exposure), 2 (high - active investigations or sector under pressure).

R4 MACRO SENSITIVITY:   How sensitive is the business to economic downturns?
Penalty: 0 (defensive/recession resistant), 1 (moderate cyclicality), 2 (highly cyclical).

R5 CURRENCY RISK:       For UK-based investors holding non-GBP stocks, is there meaningful currency exposure?
Penalty: 0 (GBP or hedged), 1 (single foreign currency exposure), 2 (multiple currency exposure, unhedged).
"""

_SUMMARY_SYSTEM = (
    "You are a portfolio manager writing a closing investment memo for a UK-based long-term investor. "
    "Write exactly one paragraph (4-6 sentences) summarising the overall investment case and "
    "position size rationale. Be specific, reference actual data provided, and write in a "
    "professional fund manager tone. Do not use bullet points. Do not repeat scores verbatim."
)

_RISK_LABELS = {
    "R1": "Valuation Risk",
    "R2": "Concentration Risk",
    "R3": "Regulatory Risk",
    "R4": "Macro Sensitivity",
    "R5": "Currency Risk",
}


# -- NO counters ---------------------------------------------------------------

def _count_nos_bmp(bmp_result: dict) -> tuple[int, list[str]]:
    nos, items = 0, []
    for a in (bmp_result or {}).get("answers", []):
        if a.get("rating", "").upper() == "NO":
            nos += 1
            items.append(f"BMP {a['label']}: NO - {a.get('reasoning', '')}")
    return nos, items


def _count_nos_fisher(fisher_result: dict | None) -> tuple[int, list[str]]:
    if not fisher_result:
        return 0, []
    nos, items = 0, []
    for p in fisher_result.get("points", []):
        if p.get("score", 1.0) == 0.0:
            nos += 1
            items.append(
                f"Fisher {p['key']} {p.get('label','')}: 0 - {p.get('reasoning', '')}"
            )
    return nos, items


def _count_nos_selection(selection_result: dict | None) -> tuple[int, list[str]]:
    if not selection_result:
        return 0, []
    nos, items = 0, []
    for a in selection_result.get("answers", []):
        if a.get("rating", "").upper() == "NO":
            nos += 1
            items.append(
                f"Selection {a['key']} {a.get('label','')}: NO - {a.get('reasoning', '')}"
            )
    return nos, items


# -- Category lookup -----------------------------------------------------------

def _get_category(total_nos: int) -> tuple[str, str, float, float]:
    for name, lo, hi, label, lo_pct, hi_pct in _CATEGORIES:
        if lo <= total_nos <= hi:
            return name, label, lo_pct, hi_pct
    return "Egg", "0%", 0.0, 0.0


def _position_size(category: str, lo_pct: float, hi_pct: float,
                   conviction: str) -> float:
    if category == "Egg":
        return 0.0
    if conviction == "HIGH":
        return hi_pct
    if conviction == "LOW":
        return lo_pct
    return round((lo_pct + hi_pct) / 2, 1)  # MEDIUM = midpoint


# -- Context builder -----------------------------------------------------------

def _build_context(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   no_items: list[str]) -> str:
    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    cagr    = profile.get("revenue_cagr")

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        f"P/E Ratio:         {profile.get('pe_ratio', 'N/A')}",
        f"Revenue CAGR:      {round(cagr * 100, 2)}%" if cagr is not None else "Revenue CAGR:      N/A",
        f"ROE:               {round(roe * 100, 2)}%" if roe else "ROE:               N/A",
        f"Insider Ownership: {round(insider * 100, 2)}%" if insider else "Insider Ownership: N/A",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors', []))}",
        "",
        f"BMP Score:         {bmp_result.get('score', 0)}/5   Verdict: {bmp_result.get('verdict', 'N/A')}",
    ]

    if fisher_result:
        lines.append(
            f"Fisher Score:      {fisher_result.get('total', 0)}/15  "
            f"Rating: {fisher_result.get('rating', 'N/A')}"
        )
    else:
        lines.append("Fisher Score:      N/A (not run)")

    if selection_result:
        lines.append(
            f"Selection Score:   {selection_result.get('score', 0)}/8   "
            f"Verdict: {selection_result.get('verdict', 'N/A')}"
        )
    else:
        lines.append("Selection Score:   N/A (not run)")

    if no_items:
        lines += ["", "--- Areas scoring NO / 0 ---"]
        lines.extend(no_items)

    return "\n".join(lines)


# -- Groq calls ----------------------------------------------------------------

def _score_risk_factors(context: str) -> str:
    user_msg = (
        f"Company data and prior stage results:\n{context}\n\n"
        f"Assess these 5 risk factors:\n{_RISK_QUESTIONS}"
    )
    return _call_llm(
        messages=[
            {"role": "system", "content": _RISK_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=512,
        temperature=0.1,
    )


def _get_summary(context: str, risk_lines: list[str], category: str,
                 alloc_label: str, conviction: str, position_pct: float) -> str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    user_msg = (
        f"Company data:\n{context}\n\n"
        f"Risk factor assessments:\n" + "\n".join(risk_lines) + "\n\n"
        f"Final outcome: {category} category, conviction {conviction}, "
        f"recommended position size {position_pct}% (range: {alloc_label}).\n\n"
        "Write the 4-6 sentence investment memo paragraph."
    )
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=350,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


# -- Parser --------------------------------------------------------------------

def _parse_risk_factors(text: str) -> tuple[list[dict], str]:
    factors = []
    for key, label in _RISK_LABELS.items():
        penalty   = 0
        reasoning = "No response parsed."
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                rest = stripped[len(key) + 1:].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        try:
                            penalty = int(rest[1:close].strip())
                        except ValueError:
                            penalty = 0
                        reasoning = rest[close + 1:].strip()
                else:
                    parts = rest.split(None, 1)
                    try:
                        penalty = int(parts[0])
                    except (ValueError, IndexError):
                        penalty = 0
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        factors.append({"key": key, "label": label, "penalty": penalty,
                        "reasoning": reasoning})

    # Parse conviction line
    conviction = "MEDIUM"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("CONVICTION:"):
            rest = stripped[len("CONVICTION:"):].strip()
            if rest.startswith("["):
                close = rest.find("]")
                if close != -1:
                    conviction = rest[1:close].strip().upper()
            else:
                conviction = rest.split()[0].upper().rstrip(".")
            break

    if conviction not in ("HIGH", "MEDIUM", "LOW"):
        conviction = "MEDIUM"

    return factors, conviction


# -- Output --------------------------------------------------------------------

def _print_results(profile: dict,
                   bmp_result: dict, fisher_result: dict | None,
                   selection_result: dict | None,
                   nos_bmp: int, nos_fisher: int, nos_selection: int,
                   factors: list[dict], total_penalty: int, adjusted_nos: int,
                   category: str, alloc_label: str,
                   conviction: str, position_pct: float,
                   summary: str) -> None:
    W    = 52
    name = profile.get("name", "N/A")

    bmp_score       = bmp_result.get("score", 0)
    fisher_score    = fisher_result.get("total", "N/A") if fisher_result else "N/A"
    selection_score = selection_result.get("score", "N/A") if selection_result else "N/A"

    print(f"\n{'=' * W}")
    print("  ATLAS: RISK SCORING & POSITION SIZING")
    print(f"{'=' * W}")
    print(f"  Company: {name}")
    print()

    print("  --- SCORE SUMMARY ---")
    print(f"  BMP Gate:        {bmp_score}/5    ({nos_bmp} NOs)")
    if fisher_result:
        print(f"  Fisher Analysis: {fisher_score}/15   ({nos_fisher} NOs)")
    else:
        print(f"  Fisher Analysis: N/A          (not run)")
    if selection_result:
        print(f"  Stock Selection: {selection_score}/8    ({nos_selection} NOs)")
    else:
        print(f"  Stock Selection: N/A          (not run)")
    base_nos = nos_bmp + nos_fisher + nos_selection
    print(f"  Base NO Count:   {base_nos}")
    print()

    print("  --- RISK FACTORS ---")
    for f in factors:
        label_col = f"{f['label']}:"
        print(f"  {label_col:<22} [{f['penalty']}]  {f['reasoning']}")
    print(f"  Risk Penalty:          +{total_penalty} NOs")
    print()

    print("  --- FINAL ASSESSMENT ---")
    print(f"  Adjusted NO Count: {adjusted_nos}")
    print(f"  Risk Category:     {category}")
    print(f"  Conviction Level:  {conviction}")
    if category == "Egg":
        print(f"  Position Size:     0% - do not invest")
    else:
        print(f"  Position Size:     {position_pct}% of portfolio  (range: {alloc_label})")
    print()

    print("  --- RECOMMENDATION ---")
    # Word-wrap the summary at ~72 chars for clean terminal output
    words = summary.split()
    line, lines = [], []
    for w in words:
        if sum(len(x) + 1 for x in line) + len(w) > 70:
            lines.append("  " + " ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append("  " + " ".join(line))
    print("\n".join(lines))

    print(f"\n{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(profile: dict, bmp_result: dict,
        fisher_result: dict | None, selection_result: dict | None) -> dict:
    """
    Run Diamond-to-Egg risk scoring and position sizing.
    Always runs regardless of BMP verdict.
    """
    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"\n  [Risk] Scoring risk factors for {company}...")

    nos_bmp,       items_bmp       = _count_nos_bmp(bmp_result)
    nos_fisher,    items_fisher    = _count_nos_fisher(fisher_result)
    nos_selection, items_selection = _count_nos_selection(selection_result)

    base_nos  = nos_bmp + nos_fisher + nos_selection
    no_items  = items_bmp + items_fisher + items_selection

    context = _build_context(profile, bmp_result, fisher_result,
                             selection_result, no_items)

    raw      = _score_risk_factors(context)
    factors, conviction = _parse_risk_factors(raw)

    total_penalty = sum(f["penalty"] for f in factors)
    adjusted_nos  = base_nos + total_penalty

    category, alloc_label, lo_pct, hi_pct = _get_category(adjusted_nos)
    position_pct = _position_size(category, lo_pct, hi_pct, conviction)

    risk_lines = [
        f"{f['label']}: [{f['penalty']}] {f['reasoning']}" for f in factors
    ]

    print(f"  [Risk] Writing investment memo...")
    summary = _get_summary(context, risk_lines, category, alloc_label,
                           conviction, position_pct)

    _print_results(
        profile, bmp_result, fisher_result, selection_result,
        nos_bmp, nos_fisher, nos_selection,
        factors, total_penalty, adjusted_nos,
        category, alloc_label, conviction, position_pct, summary,
    )

    return {
        "factors":       factors,
        "total_penalty": total_penalty,
        "base_nos":      base_nos,
        "adjusted_nos":  adjusted_nos,
        "category":      category,
        "alloc_label":   alloc_label,
        "conviction":    conviction,
        "position_pct":  position_pct,
        "summary":       summary,
    }
