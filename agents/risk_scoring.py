# Stage - Risk Rating ("Crushability") & Position Sizing
#
# User's investing process §11: 25 YES/NO questions; count the NOs — fewer NOs
# = harder to crush = bigger position. 11 questions are deterministic from
# profile data; 14 judgement questions go to one LLM call. Missing/unparseable
# answers become UNKNOWN and are counted as NO (conservative).
#
# Position-size resolution:
#   1. Crushability category range, point picked by conviction
#   2. Capped by stage_cap_pct (Investment Stage framework, §14)
#   3. Anti-Fragile < 7 -> forced to 0%
#   4. OEY < 5% -> price_veto flag (blocks INVEST in thesis; doesn't zero size)

from agents.context import compute_oey


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    from agents.context import call_llm_with_ft
    return call_llm_with_ft(messages, max_tokens, temperature,
                            stage="risk scoring", ft_env_var="OPENAI_FT_RISK_MODEL")


# (name, lo_nos, hi_nos, label, lo_pct, hi_pct) — per the sheet
_CATEGORIES = [
    ("Diamond",      0,  5,   "6-10%", 6.0, 10.0),
    ("Marble",       6,  8,   "3-5%",  3.0,  5.0),
    ("Jawbreaker",   9,  11,  "1-2%",  1.0,  2.0),
    ("Coconut",      12, 14,  "<1%",   0.25, 0.75),
    ("Glass Bottle", 15, 18,  "0%",    0.0,  0.0),
    ("Egg",          19, 999, "0%",    0.0,  0.0),
]

_LLM_QUESTIONS = {
    "L1":  "Recognisable brand — do everyday consumers or enterprise B2B buyers know this company's brand name?",
    "L2":  "Diversified buyer base — no single customer accounts for > 20% of revenue? (Score YES for consumer platforms, digital advertising ecosystems with millions of advertisers, enterprise cloud/SaaS providers with broad customer bases, or companies with no >=20% single customer concentration in filings; score NO only if a single client represents >20% of total revenue).",
    "L3":  "Positive word of mouth — do customers/users actively recommend it or are there enthusiastic fans, power users, or developers? (Score YES for essential consumer products, high-retention software platforms, developer ecosystems, or ubiquitous services with strong brand loyalty; score NO only if product suffers from poor user reputation or high churn).",
    "L4":  "Underdog — is it an agile challenger/disruptor taking share from slower incumbents, OR free of a dominant rival with 10x greater resources? (Score YES for high-growth challengers disrupting large markets, OR established market leaders who ARE the dominant resource holder in their niche; score NO only if the company is a vulnerable small player battling a far better-funded giant).",
    "L5":  "Goliath — is it the entrenched market leader with high structural barriers that protect its core business from upstarts? (Score YES for category leaders, platform monopolies/oligopolies, or businesses with strong network effects/switching costs that prevent upstarts from displacing them; score NO only if the company is a vulnerable incumbent being actively displaced by nimble competitors).",
    "L6":  "Moat — are entry barriers (network effects, switching costs, proprietary data, patents) high enough that direct competitors pose limited threat?",
    "L7":  "Top-3 CXOs — do the top three executives have combined leadership/industry/company tenure over 15 years? (Score YES if senior leadership (CEO, CFO, CTO/CIO/COO) have collectively spent >15 years in senior executive, founder, or industry leadership roles; score NO only if leadership is entirely inexperienced, unstable, or brand-new with high executive turnover).",
    "L8":  "Stock Advisor fit — quality business, proven capital allocation, solid balance sheet, conscious capitalism, and long-term shareholder orientation?",
    "L9":  "Rule Breaker fit — possesses core Rule Breaker traits (top dog/first mover in an important industry, durable competitive advantage, strong past price/operational momentum, visionary leadership, strong brand, or early perceived overvaluation)? (Score YES for innovative market leaders and disruptive growth compounders).",
    "L10": "Fraud-free — no history of material accounting fraud, regulatory deception, or management integrity scandals?",
    "L11": "Want to know more — is this a business an investor would genuinely enjoy studying deeper?",
    "L12": "Company-specific risk #1 — name the single biggest company-specific risk; is the company positioned to survive it? (YES = survivable)",
    "L13": "Company-specific risk #2 — name the second biggest company-specific risk; is the company positioned to survive it? (YES = survivable)",
    "L14": "Macro resilience / Antifragile — can the business withstand or benefit from macro inflation, economic downturns, and market volatility through pricing power, essential utility, or net-cash balance sheets? (Score YES if high gross margins, net cash balance sheet, mission-critical utility, or pricing power allow the company to compound through recessions; score NO only for deeply cyclical, debt-heavy, or commodity-dependent businesses vulnerable to macro collapse).",
}

_LLM_LABELS = {
    "L1": "Recognisable brand", "L2": "Diversified buyer base", "L3": "Word of mouth / fans",
    "L4": "Underdog (no bigger rival)", "L5": "Goliath (no upstarts)", "L6": "Moat / entry barriers",
    "L7": "CXO tenure > 15 yrs", "L8": "Stock Advisor fit", "L9": "Rule Breaker fit",
    "L10": "Fraud-free", "L11": "Want to know more", "L12": "Company risk #1 survivable",
    "L13": "Company risk #2 survivable", "L14": "Macro antifragile",
}

_RISK_SYSTEM = (
    "You are a risk analyst running a 25-question 'crushability' checklist for a "
    "long-term investor. Answer each question with YES or NO based on the company data, "
    "business fundamentals, and industry context provided, with one sentence of reasoning. "
    "Be rigorous and objective. Answer YES when the business model and evidence clearly satisfy the criterion. "
    "Answer NO only when the company clearly fails the criterion or exhibits significant risk.\n\n"
    "Reply with one line per question in this exact format, then a final conviction line:\n"
    + "\n".join(f"{k}: [YES/NO] Reasoning." for k in _LLM_QUESTIONS)
    + "\nCONVICTION: [HIGH/MEDIUM/LOW] One sentence overall conviction."
)

_SUMMARY_SYSTEM = (
    "You are a portfolio manager writing a closing investment memo for a "
    "long-term investor. Write exactly one paragraph (4-6 sentences) summarising "
    "the overall investment case and position size rationale. Be specific, "
    "reference actual data provided, and write in a professional fund manager "
    "tone. Do not use bullet points. Do not repeat scores verbatim."
)


# -- Deterministic questions ---------------------------------------------------

def _q(key, label, answer, reasoning):
    return {"key": key, "label": label, "answer": answer,
            "method": "computed", "reasoning": reasoning}


_MAJOR_EXCHANGES = ("NASDAQ", "NYSE", "AMEX", "LONDON", "LSE", "EURONEXT", "XETRA",
                    "TORONTO", "ASX", "SIX", "TSX", "OMX", "OSLO", "AMSTERDAM")


def _deterministic_questions(profile: dict) -> list[dict]:
    qs = []
    ni = profile.get("net_income")
    fcf = profile.get("free_cash_flow")
    cagr = profile.get("revenue_cagr")
    cash = profile.get("cash_and_equivalents")
    roe = profile.get("roe")
    mc = profile.get("market_cap")
    beta = profile.get("beta")
    pe = profile.get("pe_ratio")
    insider = profile.get("insider_ownership_pct")

    # D1 Profitable last 12 months
    if ni is None:
        qs.append(_q("D1", "Profitable (TTM)", "UNKNOWN", "Net income unavailable."))
    else:
        qs.append(_q("D1", "Profitable (TTM)", "YES" if ni > 0 else "NO",
                     f"TTM net income {'positive' if ni > 0 else 'negative'} (${ni/1e9:.2f}B)."))

    # D2 FCF-positive last 12 months
    if fcf is None:
        qs.append(_q("D2", "FCF-positive (TTM)", "UNKNOWN", "Free cash flow unavailable."))
    else:
        qs.append(_q("D2", "FCF-positive (TTM)", "YES" if fcf > 0 else "NO",
                     f"Free cash flow ${fcf/1e9:.2f}B."))

    # D3 Sales growth 10-40% over last 3 years (>41% = NO, too hot)
    if cagr is None:
        qs.append(_q("D3", "Sales growth 10-40% (3yr)", "UNKNOWN", "Revenue CAGR unavailable."))
    elif 0.10 <= cagr <= 0.40:
        qs.append(_q("D3", "Sales growth 10-40% (3yr)", "YES", f"3yr revenue CAGR {cagr*100:.1f}%."))
    elif cagr > 0.40:
        qs.append(_q("D3", "Sales growth 10-40% (3yr)", "NO",
                     f"CAGR {cagr*100:.1f}% > 41% — growth too hot to sustain."))
    else:
        qs.append(_q("D3", "Sales growth 10-40% (3yr)", "NO", f"CAGR {cagr*100:.1f}% below 10%."))

    # D4 Can operate 3 years without external funds
    if fcf is not None and fcf > 0:
        qs.append(_q("D4", "3-yr self-funding", "YES", "Self-funding: positive free cash flow."))
    elif fcf is not None and cash is not None:
        ok = cash > 3 * abs(fcf)
        qs.append(_q("D4", "3-yr self-funding", "YES" if ok else "NO",
                     f"Cash ${cash/1e9:.1f}B vs 3yr burn ${3*abs(fcf)/1e9:.1f}B."))
    else:
        qs.append(_q("D4", "3-yr self-funding", "UNKNOWN", "Cash/FCF data unavailable."))

    # D5 High disclosure standard
    exchange = (profile.get("exchange") or "").upper()
    if any(x in exchange for x in _MAJOR_EXCHANGES):
        qs.append(_q("D5", "High disclosure standard", "YES",
                     f"Listed on a major regulated exchange ({profile.get('exchange')})."))
    else:
        qs.append(_q("D5", "High disclosure standard", "UNKNOWN",
                     f"Exchange '{profile.get('exchange')}' disclosure regime not verified."))

    # D6 Transparency (financials & insider ownership easy to find)
    if (profile.get("revenues") and profile.get("operating_cash_flow") is not None
            and insider is not None):
        qs.append(_q("D6", "Transparency", "YES", "Financials and insider ownership readily available."))
    else:
        qs.append(_q("D6", "Transparency", "NO", "Key financials or ownership data hard to obtain."))

    # D7 Well-managed: ROE >= 15% most recent FY
    if roe is None:
        qs.append(_q("D7", "ROE >= 15%", "UNKNOWN", "ROE unavailable."))
    else:
        qs.append(_q("D7", "ROE >= 15%", "YES" if roe >= 0.15 else "NO", f"ROE {roe*100:.1f}%."))

    # D8 Market cap > $500M
    if mc is None:
        qs.append(_q("D8", "Market cap > $500M", "UNKNOWN", "Market cap unavailable."))
    else:
        qs.append(_q("D8", "Market cap > $500M", "YES" if mc > 5e8 else "NO",
                     f"Market cap ${mc/1e9:.1f}B."))

    # D9 Beta < 1.3
    if beta is None:
        qs.append(_q("D9", "Beta < 1.3", "UNKNOWN", "Beta unavailable."))
    else:
        qs.append(_q("D9", "Beta < 1.3", "YES" if beta < 1.3 else "NO", f"Beta {beta}."))

    # D10 Positive P/E < 30
    if pe is None:
        qs.append(_q("D10", "Positive P/E < 30", "UNKNOWN", "P/E unavailable."))
    else:
        qs.append(_q("D10", "Positive P/E < 30", "YES" if 0 < pe < 30 else "NO", f"P/E {pe}."))

    # D11 Key insider owns > 5%
    if insider is None:
        qs.append(_q("D11", "Insider ownership > 5%", "UNKNOWN", "Insider ownership unavailable."))
    else:
        qs.append(_q("D11", "Insider ownership > 5%", "YES" if insider > 0.05 else "NO",
                     f"Insiders own {insider*100:.1f}%."))
    return qs


# -- LLM questions -------------------------------------------------------------

def _parse_llm_questions(text: str) -> tuple[list[dict], str]:
    qs = []
    for key, label in _LLM_LABELS.items():
        answer, reasoning = "UNKNOWN", "No answer parsed — counted as NO (conservative)."
        for line in (text or "").splitlines():
            s = line.strip()
            if s.startswith(f"{key}:"):
                rest = s.split(":", 1)[1].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        answer = rest[1:close].strip().upper()
                        reasoning = rest[close + 1:].strip()
                else:
                    parts = rest.split(None, 1)
                    answer = parts[0].rstrip(".").upper()
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        if answer not in ("YES", "NO"):
            answer = "UNKNOWN"
        qs.append({"key": key, "label": label, "answer": answer,
                   "method": "llm", "reasoning": reasoning})

    conviction = "MEDIUM"
    for line in (text or "").splitlines():
        s = line.strip()
        if s.upper().startswith("CONVICTION:"):
            rest = s[len("CONVICTION:"):].strip()
            if rest.startswith("["):
                close = rest.find("]")
                if close != -1:
                    conviction = rest[1:close].strip().upper()
            elif rest:
                conviction = rest.split()[0].upper().rstrip(".")
            break
    if conviction not in ("HIGH", "MEDIUM", "LOW"):
        conviction = "MEDIUM"
    return qs, conviction


# -- Category / sizing ---------------------------------------------------------

def _get_category(no_count: int) -> tuple[str, str, float, float]:
    for name, lo, hi, label, lo_pct, hi_pct in _CATEGORIES:
        if lo <= no_count <= hi:
            return name, label, lo_pct, hi_pct
    return "Egg", "0%", 0.0, 0.0


def _position_size(category: str, lo_pct: float, hi_pct: float, conviction: str) -> float:
    if category in ("Glass Bottle", "Egg"):
        return 0.0
    if conviction == "HIGH":
        return hi_pct
    if conviction == "LOW":
        return lo_pct
    return round((lo_pct + hi_pct) / 2, 2)


# -- Context / memo ------------------------------------------------------------

def _build_context(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   process_result: dict | None) -> str:
    from agents.context import profile_context
    lines = [profile_context(profile), ""]
    lines.append(f"BMP Score:         {bmp_result.get('score', 0)}/5   Verdict: {bmp_result.get('verdict', 'N/A')}")
    if fisher_result:
        lines.append(f"Fisher Score:      {fisher_result.get('total', 0)}/15  Rating: {fisher_result.get('rating', 'N/A')}")
        # Append relevant Fisher points for leadership, sales, and moats
        for p in (fisher_result.get("points") or []):
            if p.get("key") in ("P4", "P7", "P8", "P9", "P11", "P14", "P15"):
                lines.append(f"  Fisher {p['key']} {p.get('label')}: [{p.get('score')}] {p.get('reasoning')}")
    if selection_result:
        lines.append(f"Selection Score:   {selection_result.get('score', 0)}/8   Verdict: {selection_result.get('verdict', 'N/A')}")
        for a in (selection_result.get("answers") or []):
            if a.get("key") in ("Q1", "Q3", "Q5", "Q7"):
                lines.append(f"  Selection {a['key']} {a.get('label')}: [{a.get('rating')}] {a.get('reasoning')}")
    if process_result:
        st = process_result.get("stage") or {}
        lines.append(f"Stage:             {st.get('stage_number')} - {st.get('stage_label')}")
    return "\n".join(lines)


def _get_summary(context: str, question_lines: list[str], category: str,
                 alloc_label: str, conviction: str, position_pct: float) -> str:
    user_msg = (
        f"Company data:\n{context}\n\n"
        f"Crushability answers (NOs and UNKNOWNs shown):\n" + "\n".join(question_lines) + "\n\n"
        f"Final outcome: {category} category, conviction {conviction}, "
        f"recommended position size {position_pct}% (range: {alloc_label}).\n\n"
        "Write the 4-6 sentence investment memo paragraph."
    )
    try:
        return _call_llm(
            [{"role": "system", "content": _SUMMARY_SYSTEM},
             {"role": "user", "content": user_msg}],
            max_tokens=350, temperature=0.2).strip()
    except Exception as e:
        print(f"  [Warning] Memo unavailable ({type(e).__name__}).")
        return "Investment memo unavailable."


# -- Output --------------------------------------------------------------------

def _print_results(profile: dict, questions: list[dict], no_count: int,
                   unknown_count: int, category: str, alloc_label: str,
                   conviction: str, sizing: dict, summary: str) -> None:
    W = 52
    print(f"\n{'=' * W}")
    print("  ATLAS: CRUSHABILITY RISK RATING")
    print(f"{'=' * W}")
    print(f"  Company: {profile.get('name', 'N/A')}")
    print()
    print("  --- 25 QUESTIONS (NO/UNKNOWN shown in full) ---")
    for q in questions:
        mark = {"YES": "Y", "NO": "N", "UNKNOWN": "?"}[q["answer"]]
        if q["answer"] == "YES":
            print(f"  [{mark}] {q['label']}")
        else:
            print(f"  [{mark}] {q['label']}: {q['reasoning']}")
    print()
    print(f"  NO count:          {no_count}  (incl. {unknown_count} UNKNOWN counted as NO)")
    print(f"  Crushable like a:  {category}  (max position {alloc_label})")
    print(f"  Conviction:        {conviction}")
    print()
    print("  --- POSITION SIZING ---")
    print(f"  Crushability size: {sizing['crushability_pct']}%")
    if sizing.get("stage_cap_pct") is not None:
        print(f"  Stage cap:         {sizing['stage_cap_pct']}%")
    print(f"  FINAL SIZE:        {sizing['final_pct']}% of portfolio")
    for note in sizing.get("notes", []):
        print(f"  ! {note}")
    print()
    print("  --- RECOMMENDATION ---")
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
        fisher_result: dict | None, selection_result: dict | None,
        process_result: dict | None = None) -> dict:
    """
    Run the 25-question Crushability risk rating and position sizing.
    Always runs regardless of BMP verdict.
    """
    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"\n  [Risk] Running 25-question Crushability checklist for {company}...")

    det_questions = _deterministic_questions(profile)
    context = _build_context(profile, bmp_result, fisher_result,
                             selection_result, process_result)

    raw = _call_llm(
        [{"role": "system", "content": _RISK_SYSTEM},
         {"role": "user", "content":
             f"Company data and prior stage results:\n{context}\n\n"
             "Answer these 14 judgement questions:\n"
             + "\n".join(f"{k}: {q}" for k, q in _LLM_QUESTIONS.items())}],
        max_tokens=1800, temperature=0.1)
    llm_questions, conviction = _parse_llm_questions(raw)

    questions = det_questions + llm_questions
    no_count = sum(1 for q in questions if q["answer"] in ("NO", "UNKNOWN"))
    unknown_count = sum(1 for q in questions if q["answer"] == "UNKNOWN")

    category, alloc_label, lo_pct, hi_pct = _get_category(no_count)
    crushability_pct = _position_size(category, lo_pct, hi_pct, conviction)

    # -- Position-size resolution against the process frameworks
    oey = compute_oey(profile)
    price_veto = oey["price_veto"]
    sizing_notes: list[str] = []
    final_pct = crushability_pct
    ps = (process_result or {}).get("position_sizing") or {}

    stage_cap = ps.get("stage_cap_pct")
    if stage_cap is not None and final_pct > stage_cap:
        sizing_notes.append(f"Capped at {stage_cap}% by Investment Stage framework "
                            f"(crushability suggested {crushability_pct}%).")
        final_pct = stage_cap
    if price_veto:
        hurdle_str = "3.5%" if oey.get("is_elite_compounder") else "5%"
        sizing_notes.append(f"Price veto: operating earnings yield {oey['active_oey']}% "
                            f"< {hurdle_str} — do not buy until Mr. Market offers a better price.")
    final_pct = round(final_pct, 2)

    sizing = {"crushability_pct": crushability_pct, "stage_cap_pct": stage_cap,
              "final_pct": final_pct, "notes": sizing_notes}

    question_lines = [f"{q['label']}: {q['answer']} - {q['reasoning']}"
                      for q in questions if q["answer"] in ("NO", "UNKNOWN")]

    print(f"  [Risk] Writing investment memo...")
    summary = _get_summary(context, question_lines, category, alloc_label,
                           conviction, final_pct)

    _print_results(profile, questions, no_count, unknown_count,
                   category, alloc_label, conviction, sizing, summary)

    # Backfill final numbers into the process scoring synthesis
    if process_result is not None and "position_sizing" in process_result:
        process_result["position_sizing"]["crushability_pct"] = crushability_pct
        process_result["position_sizing"]["final_pct"] = final_pct
        process_result["position_sizing"]["notes"] = list(
            dict.fromkeys(process_result["position_sizing"].get("notes", []) + sizing_notes))

    result = {
        "questions":      questions,
        "no_count":       no_count,
        "unknown_count":  unknown_count,
        "category":       category,
        "alloc_label":    alloc_label,
        "conviction":     conviction,
        "position_pct":   final_pct,
        "crushability_pct": crushability_pct,
        "stage_cap_pct":  stage_cap,
        "price_veto":     price_veto,
        "sizing_notes":   sizing_notes,
        "summary":        summary,
        # legacy-compatible fields (old schema used adjusted_nos/base_nos/factors)
        "adjusted_nos":   no_count,
        "base_nos":       no_count,
        "total_penalty":  0,
        "factors":        [],
    }

    from agents.judge import check_cross_stage_consistency, audit_score_justification, print_judge
    judge_just = audit_score_justification("RISK", context, questions)
    print_judge(judge_just, company)
    judge_r = check_cross_stage_consistency(fisher_result, selection_result, result)
    print_judge(judge_r, company)
    result["judge"] = judge_r
    result["judge_justification"] = judge_just

    return result
