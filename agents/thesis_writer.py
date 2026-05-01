# Stage 6 - Investment Thesis Writer

import os
import json
from datetime import date
from pathlib import Path
from groq import Groq


GROQ_MODEL = "llama-3.3-70b-versatile"


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    """Use fine-tuned OpenAI model if OPENAI_FT_THESIS_MODEL is set, else Groq."""
    ft_model = os.environ.get("OPENAI_FT_THESIS_MODEL")
    if ft_model:
        try:
            from openai import OpenAI
            resp = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model=ft_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  [Warning] OpenAI Thesis model failed ({e}), falling back to Groq.")
    resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
        model=GROQ_MODEL, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content

_FINANCIAL_FINTECH_KEYWORDS = {
    "payment", "fintech", "financial technology", "banking",
    "insurance", "credit services", "capital markets", "money transfer",
}


_FINANCIAL_SECTORS = {"Financial Services", "Real Estate"}


def _is_financial_company(profile: dict) -> bool:
    sector      = (profile.get("sector") or "").strip()
    industry    = (profile.get("industry") or "").lower()
    description = (profile.get("description") or "").lower()
    if sector in _FINANCIAL_SECTORS:
        return True
    return any(kw in f"{industry} {description}" for kw in _FINANCIAL_FINTECH_KEYWORDS)


# -- Groq system prompt --------------------------------------------------------

_THESIS_SYSTEM = (
    "You are a senior equity research analyst writing a formal investment thesis "
    "for a UK-based long-term investor with a 5-10 year horizon. "
    "Use the company data, framework scores, and risk analysis provided. "
    "Be specific and evidence-based — reference actual metrics. "
    "Do not use vague language without citing data. "
    "Write the THESIS_STATEMENT in first person as if the investor wrote it. "
    "The DECISION must be exactly one of: INVEST, WATCHLIST, or PASS.\n\n"
    "Reply using EXACTLY these labels in order. "
    "Each label starts a new line. No text outside labelled sections:\n"
    "EXECUTIVE_SUMMARY: [3-4 sentence paragraph]\n"
    "BULL_1: [specific bullet — strongest reason to own over 5-10 years]\n"
    "BULL_2: [specific bullet]\n"
    "BULL_3: [specific bullet]\n"
    "BEAR_1: [specific bullet — most credible reason investment could fail]\n"
    "BEAR_2: [specific bullet]\n"
    "BEAR_3: [specific bullet]\n"
    "THESIS_STATEMENT: [4-6 sentence first-person conviction paragraph]\n"
    "WATCH_1: [specific measurable watch point with a threshold where possible]\n"
    "WATCH_2: [specific measurable watch point]\n"
    "WATCH_3: [specific measurable watch point]\n"
    "DECISION: [INVEST or WATCHLIST or PASS]\n"
    "DECISION_RATIONALE: [one sentence]"
)


# -- Context builder -----------------------------------------------------------

def _collect_no_items(bmp_result: dict, fisher_result: dict | None,
                      selection_result: dict | None) -> list[str]:
    items = []
    for a in (bmp_result or {}).get("answers", []):
        if a.get("rating", "").upper() == "NO":
            items.append(f"BMP {a['label']}: NO — {a.get('reasoning', '')}")
    for p in (fisher_result or {}).get("points", []):
        if p.get("score", 1.0) == 0.0:
            items.append(
                f"Fisher {p['key']} {p.get('label', '')}: 0 — {p.get('reasoning', '')}"
            )
    for a in (selection_result or {}).get("answers", []):
        if a.get("rating", "").upper() == "NO":
            items.append(
                f"Selection {a['key']} {a.get('label', '')}: NO — {a.get('reasoning', '')}"
            )
    return items


def _collect_strengths(fisher_result: dict | None,
                       selection_result: dict | None) -> list[str]:
    """Top-scoring Fisher points and YES selection answers for bull case context."""
    items = []
    for p in (fisher_result or {}).get("points", []):
        if p.get("score", 0.0) >= 0.75:
            items.append(
                f"Fisher {p['key']} {p.get('label', '')} [{p['score']}]: "
                f"{p.get('reasoning', '')}"
            )
    for a in (selection_result or {}).get("answers", []):
        if a.get("rating", "").upper() == "YES":
            items.append(
                f"Selection {a['key']} {a.get('label', '')}: YES — "
                f"{a.get('reasoning', '')}"
            )
    return items


def _build_context(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   risk_result: dict) -> str:
    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    cagr    = profile.get("revenue_cagr")
    fcf     = profile.get("free_cash_flow")
    revenues = profile.get("revenues") or []
    is_fin  = _is_financial_company(profile)

    # FCF margin
    fcf_margin_str = "N/A"
    if fcf is not None and revenues:
        latest_rev = revenues[0].get("revenue")
        if latest_rev and latest_rev > 0:
            if is_fin:
                fcf_margin_str = "Unreliable - financial company float distortion"
            else:
                fcf_margin_str = f"{round(fcf / latest_rev * 100, 2)}%"

    no_items   = _collect_no_items(bmp_result, fisher_result, selection_result)
    strengths  = _collect_strengths(fisher_result, selection_result)
    risk_factors = risk_result.get("factors", [])

    lines = [
        "=== COMPANY DATA ===",
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {profile.get('market_cap', 'N/A')}",
        f"P/E Ratio:         {profile.get('pe_ratio', 'N/A')}",
        f"Revenue CAGR:      {round(cagr * 100, 2)}%" if cagr is not None else "Revenue CAGR:      N/A",
        f"FCF Margin:        {fcf_margin_str}",
        f"ROE:               {round(roe * 100, 2)}%" if roe else "ROE:               N/A",
        f"Insider Ownership: {round(insider * 100, 2)}%" if insider else "Insider Ownership: N/A",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Moat:              {profile.get('moat', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors', []))}",
        "",
        "=== FRAMEWORK SCORES ===",
        f"BMP Gate:          {bmp_result.get('score', 0)}/5   — {bmp_result.get('verdict', 'N/A')}",
    ]

    if fisher_result:
        lines.append(
            f"Fisher Analysis:   {fisher_result.get('total', 0)}/15  — "
            f"{fisher_result.get('rating', 'N/A')}"
        )
    else:
        lines.append("Fisher Analysis:   N/A (not run)")

    if selection_result:
        lines.append(
            f"Stock Selection:   {selection_result.get('score', 0)}/8   — "
            f"{selection_result.get('verdict', 'N/A')}"
        )
    else:
        lines.append("Stock Selection:   N/A (not run)")

    lines += [
        f"Risk Category:     {risk_result.get('category', 'N/A')} "
        f"({risk_result.get('alloc_label', 'N/A')})",
        f"Conviction:        {risk_result.get('conviction', 'N/A')}",
        f"Position Size:     {risk_result.get('position_pct', 0)}%",
        "",
        "=== STRENGTHS (evidence for bull case) ===",
    ]
    lines.extend(strengths[:10])  # cap to avoid context bloat

    lines += ["", "=== WEAKNESSES / NO SCORES (evidence for bear case) ==="]
    if no_items:
        lines.extend(no_items)
    else:
        lines.append("None — all questions scored YES or PARTIAL.")

    lines += ["", "=== RISK FACTOR PENALTIES ==="]
    for f in risk_factors:
        lines.append(f"{f['label']}: [{f['penalty']}] {f['reasoning']}")

    lines += [
        "",
        f"Total risk penalty: +{risk_result.get('total_penalty', 0)} NOs",
        f"Adjusted NO count:  {risk_result.get('adjusted_nos', 0)}",
    ]

    return "\n".join(lines)


# -- Groq call -----------------------------------------------------------------

def _write_thesis_sections(context: str) -> str:
    return _call_llm(
        messages=[
            {"role": "system", "content": _THESIS_SYSTEM},
            {"role": "user",   "content": context},
        ],
        max_tokens=1500,
        temperature=0.15,
    )


# -- Parser --------------------------------------------------------------------

_SECTION_LABELS = [
    "EXECUTIVE_SUMMARY", "BULL_1", "BULL_2", "BULL_3",
    "BEAR_1", "BEAR_2", "BEAR_3", "THESIS_STATEMENT",
    "WATCH_1", "WATCH_2", "WATCH_3", "DECISION", "DECISION_RATIONALE",
]


def _parse_sections(text: str) -> dict:
    result = {label: "" for label in _SECTION_LABELS}
    current_label = None
    buffer: list[str] = []

    for line in text.splitlines():
        matched = False
        for label in _SECTION_LABELS:
            if line.strip().startswith(f"{label}:"):
                # flush previous
                if current_label:
                    result[current_label] = " ".join(buffer).strip()
                current_label = label
                rest = line.strip()[len(label) + 1:].strip()
                buffer = [rest] if rest else []
                matched = True
                break
        if not matched and current_label:
            stripped = line.strip()
            if stripped:
                buffer.append(stripped)

    if current_label:
        result[current_label] = " ".join(buffer).strip()

    # Strip leading markdown bullet chars Groq sometimes adds to bullet sections
    bullet_keys = {"BULL_1", "BULL_2", "BULL_3", "BEAR_1", "BEAR_2", "BEAR_3",
                   "WATCH_1", "WATCH_2", "WATCH_3"}
    for k in bullet_keys:
        result[k] = result[k].lstrip("*-• ").strip()

    # Normalise decision
    result["DECISION"] = result["DECISION"].upper().strip().rstrip(".")
    if result["DECISION"] not in ("INVEST", "WATCHLIST", "PASS"):
        result["DECISION"] = "WATCHLIST"

    return result


# -- Formatter -----------------------------------------------------------------

def _wrap(text: str, width: int = 72, indent: str = "  ") -> str:
    """Simple word-wrap for terminal output."""
    words = text.split()
    lines, line = [], []
    for w in words:
        if sum(len(x) + 1 for x in line) + len(w) > width:
            lines.append(indent + " ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(indent + " ".join(line))
    return "\n".join(lines)


def _fmt_mcap(val) -> str:
    """Format a market cap value: pass through strings, humanise raw numbers."""
    if val is None:
        return "N/A"
    if isinstance(val, str):
        return val
    try:
        v = float(val)
        if v >= 1e12:
            return f"${v / 1e12:.2f}T"
        if v >= 1e9:
            return f"${v / 1e9:.2f}B"
        if v >= 1e6:
            return f"${v / 1e6:.2f}M"
        return f"${v:,.0f}"
    except (TypeError, ValueError):
        return str(val)


def _format_thesis(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   risk_result: dict, sections: dict, today_str: str) -> str:
    name    = profile.get("name", "N/A")
    ticker  = profile.get("ticker", "N/A")
    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    cagr    = profile.get("revenue_cagr")
    fcf     = profile.get("free_cash_flow")
    revenues = profile.get("revenues") or []
    is_fin  = _is_financial_company(profile)

    # FCF margin display
    fcf_margin_display = "N/A"
    if fcf is not None and revenues:
        latest_rev = revenues[0].get("revenue")
        if latest_rev and latest_rev > 0:
            if is_fin:
                fcf_margin_display = "N/A  [unreliable - financial company float]"
            else:
                fcf_margin_display = f"{round(fcf / latest_rev * 100, 2)}%"

    bmp_score  = bmp_result.get("score", 0)
    bmp_ver    = bmp_result.get("verdict", "N/A")
    fish_score = fisher_result.get("total", "N/A") if fisher_result else "N/A"
    fish_rat   = fisher_result.get("rating", "N/A") if fisher_result else "N/A"
    sel_score  = selection_result.get("score", "N/A") if selection_result else "N/A"
    sel_ver    = selection_result.get("verdict", "N/A") if selection_result else "N/A"
    category   = risk_result.get("category", "N/A")
    pos_pct    = risk_result.get("position_pct", 0)
    conviction = risk_result.get("conviction", "N/A")

    W = 48
    lines = [
        f"{'=' * W}",
        "  ATLAS: INVESTMENT THESIS",
        f"{'=' * W}",
        f"  Company:  {name} ({ticker})",
        f"  Date:     {today_str}",
        f"  Analyst:  Atlas v1.0",
        "",
        "  --- EXECUTIVE SUMMARY ---",
        _wrap(sections["EXECUTIVE_SUMMARY"]),
        "",
        "  --- INVESTMENT SCORES ---",
        f"  BMP Gate:        {bmp_score}/5  - {bmp_ver}",
        f"  Fisher Analysis: {fish_score}/15 - {fish_rat}" if fisher_result
            else "  Fisher Analysis: N/A - not run",
        f"  Stock Selection: {sel_score}/8  - {sel_ver}" if selection_result
            else "  Stock Selection: N/A - not run",
        f"  Risk Category:   {category} - Position Size: {pos_pct}%",
        f"  Conviction:      {conviction}",
        "",
        "  --- THE BULL CASE ---",
        f"  * {sections['BULL_1']}",
        f"  * {sections['BULL_2']}",
        f"  * {sections['BULL_3']}",
        "",
        "  --- THE BEAR CASE ---",
        f"  * {sections['BEAR_1']}",
        f"  * {sections['BEAR_2']}",
        f"  * {sections['BEAR_3']}",
        "",
        "  --- KEY METRICS SNAPSHOT ---",
        f"  Market Cap:        {_fmt_mcap(profile.get('market_cap'))}",
        f"  Revenue CAGR:      {round(cagr * 100, 2)}%" if cagr is not None
            else "  Revenue CAGR:      N/A",
        f"  FCF Margin:        {fcf_margin_display}",
        f"  ROE:               {round(roe * 100, 2)}%" if roe else "  ROE:               N/A",
        f"  Insider Ownership: {round(insider * 100, 2)}%" if insider
            else "  Insider Ownership: N/A",
        f"  P/E Ratio:         {profile.get('pe_ratio', 'N/A')}",
        "",
        "  --- THESIS STATEMENT ---",
        _wrap(sections["THESIS_STATEMENT"]),
        "",
        "  --- WATCH POINTS ---",
        f"  1. {sections['WATCH_1']}",
        f"  2. {sections['WATCH_2']}",
        f"  3. {sections['WATCH_3']}",
        "",
        "  --- DECISION ---",
        f"  {sections['DECISION']}",
        f"  {sections['DECISION_RATIONALE']}",
        "",
        f"{'=' * W}",
    ]
    return "\n".join(lines)


# -- Storage -------------------------------------------------------------------

def _save(ticker: str, today_str: str, profile: dict, bmp_result: dict,
          fisher_result: dict | None, selection_result: dict | None,
          risk_result: dict, sections: dict, formatted: str) -> tuple[str, str]:
    Path("data/theses").mkdir(parents=True, exist_ok=True)

    safe_ticker = ticker.replace(".", "_")
    base        = f"data/theses/{safe_ticker}_{today_str}"
    json_path   = base + ".json"
    txt_path    = base + ".txt"

    payload = {
        "company":   profile.get("name", "N/A"),
        "ticker":    ticker,
        "date":      today_str,
        "analyst":   "Atlas v1.0",
        "profile": {
            "name":                 profile.get("name"),
            "ticker":               profile.get("ticker"),
            "exchange":             profile.get("exchange"),
            "sector":               profile.get("sector"),
            "industry":             profile.get("industry"),
            "market_cap":           profile.get("market_cap"),
            "current_price":        profile.get("current_price"),
            "pe_ratio":             profile.get("pe_ratio"),
            "revenue_cagr":         profile.get("revenue_cagr"),
            "revenues":             profile.get("revenues"),
            "free_cash_flow":       profile.get("free_cash_flow"),
            "roe":                  profile.get("roe"),
            "insider_ownership_pct": profile.get("insider_ownership_pct"),
            "description":          profile.get("description"),
            "moat":                 profile.get("moat"),
            "growth_drivers":       profile.get("growth_drivers"),
            "risk_factors":         profile.get("risk_factors"),
        },
        "scores": {
            "bmp": {
                "score":   bmp_result.get("score"),
                "verdict": bmp_result.get("verdict"),
                "answers": bmp_result.get("answers", []),
            },
            "fisher": {
                "total":    fisher_result.get("total") if fisher_result else None,
                "rating":   fisher_result.get("rating") if fisher_result else None,
                "points":   fisher_result.get("points", []) if fisher_result else [],
                "evidence": fisher_result.get("evidence") if fisher_result else None,
            },
            "selection": {
                "score":   selection_result.get("score") if selection_result else None,
                "verdict": selection_result.get("verdict") if selection_result else None,
                "answers": selection_result.get("answers", []) if selection_result else [],
            },
            "risk": {
                "category":      risk_result.get("category"),
                "alloc_label":   risk_result.get("alloc_label"),
                "conviction":    risk_result.get("conviction"),
                "position_pct":  risk_result.get("position_pct"),
                "base_nos":      risk_result.get("base_nos"),
                "total_penalty": risk_result.get("total_penalty"),
                "adjusted_nos":  risk_result.get("adjusted_nos"),
                "factors":       risk_result.get("factors", []),
                "summary":       risk_result.get("summary"),
            },
        },
        "thesis": {
            "executive_summary":   sections["EXECUTIVE_SUMMARY"],
            "bull_case":           [sections["BULL_1"], sections["BULL_2"], sections["BULL_3"]],
            "bear_case":           [sections["BEAR_1"], sections["BEAR_2"], sections["BEAR_3"]],
            "thesis_statement":    sections["THESIS_STATEMENT"],
            "watch_points":        [sections["WATCH_1"], sections["WATCH_2"], sections["WATCH_3"]],
            "decision":            sections["DECISION"],
            "decision_rationale":  sections["DECISION_RATIONALE"],
        },
        "formatted_thesis": formatted,
    }

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)

    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write(formatted)

    return json_path, txt_path


# -- Entry point ---------------------------------------------------------------

def run(profile: dict, bmp_result: dict,
        fisher_result: dict | None, selection_result: dict | None,
        risk_result: dict) -> dict:
    """
    Write and save the investment thesis.
    Always runs regardless of prior stage verdicts.
    """
    company    = profile.get("name") or profile.get("ticker", "Unknown")
    ticker     = profile.get("ticker", "UNKNOWN")
    today_str  = date.today().isoformat()

    print(f"\n  [Thesis] Writing investment thesis for {company}...")

    context  = _build_context(
        profile, bmp_result, fisher_result, selection_result, risk_result
    )
    raw      = _write_thesis_sections(context)
    sections = _parse_sections(raw)

    formatted = _format_thesis(
        profile, bmp_result, fisher_result, selection_result,
        risk_result, sections, today_str,
    )

    print(formatted)

    json_path, txt_path = _save(
        ticker, today_str, profile, bmp_result, fisher_result,
        selection_result, risk_result, sections, formatted,
    )

    print(f"  [Thesis] Saved: {json_path}")
    print(f"  [Thesis] Saved: {txt_path}\n")

    return {
        "sections":  sections,
        "decision":  sections["DECISION"],
        "json_path": json_path,
        "txt_path":  txt_path,
    }
