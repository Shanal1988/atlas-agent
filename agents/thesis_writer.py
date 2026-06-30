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
    try:
        resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        from agents.llm_client import gemini_call
        return gemini_call(messages, max_tokens, temperature, stage="thesis writing")

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
    "BEAR_1: [company-specific risk with a number or named event — e.g. 'Regulatory fine risk: EU DSA could cap interchange fees, compressing Adyen's ~47% EBITDA margin']\n"
    "BEAR_2: [company-specific risk with a number or named event]\n"
    "BEAR_3: [company-specific risk with a number or named event — do NOT use 'could', 'may', or 'might' without a cited data point]\n"
    "THESIS_STATEMENT: [4-6 sentence first-person conviction paragraph]\n"
    "DESTINATION: [1-2 sentences — where will this company be in 10 years? Name the specific market position, scale, or capability that makes this a materially larger and stronger business at its destination. The primary risk is misanalysing this destination.]\n"
    "WATCH_1: [specific measurable watch point with a threshold where possible]\n"
    "WATCH_2: [specific measurable watch point]\n"
    "WATCH_3: [specific measurable watch point]\n"
    "DECISION: [INVEST or WATCHLIST or PASS]\n"
    "DECISION_RATIONALE: [one sentence]\n\n"
    "Valuation guidance for DECISION: the context includes an Intrinsic Value range "
    "from 4 models (Dhandho, Ben Graham, DCF, Expected Returns). "
    "A stock trading at a significant premium to midpoint IV (>50%) warrants WATCHLIST "
    "unless conviction is HIGH and growth clearly exceeds model assumptions — name why. "
    "A stock at a discount to IV strengthens the case for INVEST. "
    "Never choose INVEST without acknowledging whether the price is near, above, or below IV."
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


def _iv_summary_line(valuation_result: dict | None) -> str:
    """One-line IV summary for inclusion in LLM context."""
    if not valuation_result or not valuation_result.get("available"):
        return "Intrinsic Value:   N/A (not computed)"
    dh  = valuation_result.get("dhandho", {})
    dc  = valuation_result.get("dcf", {})
    er  = valuation_result.get("exp_returns") or {}
    mkt = valuation_result.get("mktcap_mn")

    dh_lo = (dh.get("lower")  or {}).get("iv")
    dh_hi = (dh.get("higher") or {}).get("iv")
    dc_iv = dc.get("iv") if dc else None
    er_iv = er.get("iv")

    from agents.valuation import _mn, _prem
    valid = [v for v in [dh_lo, dh_hi, dc_iv, er_iv] if v and v > 0]
    if not valid:
        return "Intrinsic Value:   N/A"
    iv_lo, iv_hi = min(valid), max(valid)
    prem_str = _prem((iv_lo + iv_hi) / 2, mkt)
    return (
        f"Intrinsic Value:   Range {_mn(iv_lo)} - {_mn(iv_hi)}  "
        f"[Dhandho: {_mn(dh_lo)}/{_mn(dh_hi)}, "
        f"DCF: {_mn(dc_iv)}, ExpRet: {_mn(er_iv)}]  "
        f"vs Mkt Cap: {prem_str}"
    )


def _build_context(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   risk_result: dict, valuation_result: dict | None = None,
                   industry_result: dict | None = None,
                   similar_result: list | None = None) -> str:
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
        f"ROCE (avg):        {round(profile.get('roce_avg') * 100, 2)}%  Trend: {profile.get('roce_trend', 'N/A')}"
            if profile.get("roce_avg") is not None else "ROCE:              N/A",
        f"ROIC (avg):        {round(profile.get('roic_avg') * 100, 2)}%  Trend: {profile.get('roic_trend', 'N/A')}"
            if profile.get("roic_avg") is not None else "ROIC:              N/A",
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
        _iv_summary_line(valuation_result),
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

    # Fisher research evidence — gives the writer real sources to cite in bear case bullets
    fisher_evidence = (fisher_result or {}).get("evidence", "")
    if fisher_evidence:
        excerpt = fisher_evidence[:2500]
        if len(fisher_evidence) > 2500:
            excerpt += "\n[... truncated ...]"
        lines += [
            "",
            "=== RESEARCH EVIDENCE (cite specific facts, names, and figures in bear case) ===",
            excerpt,
        ]

    # Recent news — verbatim, so bear case bullets can cite named events and figures
    news_items = [n for n in (profile.get("news") or []) if n and n != "N/A"]
    if news_items:
        lines += ["", "=== RECENT NEWS (use specific named events and figures in bear case) ==="]
        for item in news_items:
            lines.append(f"- {item}")

    # Regulatory alerts — pin any news containing investigation/fine/regulatory keywords
    # so the thesis writer quotes them precisely rather than hedging with 'could'
    _REG_KEYWORDS = ("investigat", "fine", "penalty", "sanction", "regulat",
                     "summons", "prosecutor", "laundering", "compliance")
    reg_alerts = [n for n in news_items
                  if any(kw in n.lower() for kw in _REG_KEYWORDS)]
    if reg_alerts:
        lines += [
            "",
            "=== REGULATORY ALERTS — QUOTE THESE VERBATIM IN BEAR CASE, NO HEDGING ===",
            "INSTRUCTION: For every bear point that touches regulatory risk, you MUST:",
            "  1. Name the specific authority (e.g. Belgian prosecutors / National Bank of Belgium)",
            "  2. State the specific figure (e.g. €500 million in suspicious transactions)",
            "  3. State the specific consequence (e.g. criminal court summons, EU licence referral)",
            "  4. Do NOT use 'could', 'may', or 'might' — these are ACTIVE proceedings, not hypotheticals",
        ]
        for alert in reg_alerts:
            lines.append(f"ALERT: {alert}")

    # Industry analysis context
    if industry_result and industry_result.get("sections"):
        lines += ["", "=== INDUSTRY ANALYSIS ==="]
        for label, content in industry_result["sections"].items():
            if content:
                lines.append(f"{label.replace('_', ' ').title()}: {content}")
        peers = industry_result.get("peers", [])
        if peers:
            lines.append("\nPeer Metrics:")
            for pm in peers[:5]:
                lines.append(
                    f"  {pm.get('ticker', '?')}: MktCap {pm.get('market_cap', 'N/A')}, "
                    f"P/E {pm.get('pe_ratio', 'N/A')}, "
                    f"ROIC {pm.get('roic', 'N/A')}, "
                    f"OpMgn {pm.get('operating_margin', 'N/A')}"
                )

    # Similar companies for investor exploration
    if similar_result:
        lines += ["", "=== SIMILAR COMPANIES (potential multibaggers for exploration) ==="]
        for s in similar_result[:5]:
            lines.append(
                f"  {s.get('ticker', '?')} - {s.get('name', '?')}: "
                f"MktCap {s.get('market_cap', 'N/A')}, "
                f"RevGrowth {s.get('revenue_growth', 'N/A')}, "
                f"ROIC {s.get('roic', 'N/A')}, "
                f"Score {s.get('multibagger_score', 0)}/12"
            )

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
    "BEAR_1", "BEAR_2", "BEAR_3", "THESIS_STATEMENT", "DESTINATION",
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


def _format_valuation_section(valuation_result: dict | None) -> list[str]:
    """Render a compact IV summary block for inclusion in the printed thesis."""
    if not valuation_result or not valuation_result.get("available"):
        return []
    from agents.valuation import _mn, _price
    dh  = valuation_result.get("dhandho", {})
    gm  = valuation_result.get("graham",  {})
    dc  = valuation_result.get("dcf",     {})
    er  = valuation_result.get("exp_returns") or {}
    mkt = valuation_result.get("mktcap_mn")
    shares = valuation_result.get("shares")

    dh_lo = (dh.get("lower")  or {}).get("iv")
    dh_hi = (dh.get("higher") or {}).get("iv")
    dc_iv = dc.get("iv") if dc else None
    er_iv = er.get("iv")
    glo   = gm.get("lower")
    ghi   = gm.get("higher")

    valid = [v for v in [dh_lo, dh_hi, dc_iv, er_iv] if v and v > 0]
    overall = ""
    if valid and mkt:
        iv_lo, iv_hi = min(valid), max(valid)
        mid  = (iv_lo + iv_hi) / 2
        prem = (mkt - mid) / mid * 100
        verdict = "OVERVALUED" if prem > 20 else ("UNDERVALUED" if prem < -20 else "FAIRLY VALUED")
        overall = (f"  IV Range (ex-Graham): {_mn(iv_lo)} - {_mn(iv_hi)}"
                   f"  ->  {abs(prem):.0f}% {'premium' if prem > 0 else 'discount'} ({verdict})")

    lines = [
        "",
        "  --- INTRINSIC VALUE SUMMARY ---",
        f"  {'Method':<22}  {'IV Lower':>12}  {'IV Higher':>12}  {'Price Lo / Hi':>16}",
        f"  {'-'*62}",
    ]
    def row(label, lo, hi):
        lo_s  = _mn(lo) if lo is not None else "N/A"
        hi_s  = _mn(hi) if hi is not None else "  -"
        pr_lo = _price(lo, shares) if lo is not None else "N/A"
        pr_hi = _price(hi, shares) if hi is not None else "  -"
        lines.append(f"  {label:<22}  {lo_s:>12}  {hi_s:>12}  {pr_lo:>8} / {pr_hi:<8}")

    row("Dhandho",          dh_lo, dh_hi)
    row("Ben Graham",       glo,   ghi)
    row("DCF",              dc_iv, None)
    row("Expected Returns", er_iv, None)
    if overall:
        lines += [f"  {'-'*62}", overall]
    return lines


def _format_thesis(profile: dict, bmp_result: dict,
                   fisher_result: dict | None, selection_result: dict | None,
                   risk_result: dict, sections: dict, today_str: str,
                   valuation_result: dict | None = None,
                   industry_result: dict | None = None,
                   similar_result: list | None = None) -> str:
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
    ]
    lines += _format_valuation_section(valuation_result)
    lines += [
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
        f"  ROCE (avg):        {round(profile.get('roce_avg') * 100, 2)}%  ({profile.get('roce_trend', 'N/A')})"
            if profile.get("roce_avg") is not None else "  ROCE:              N/A",
        f"  ROIC (avg):        {round(profile.get('roic_avg') * 100, 2)}%  ({profile.get('roic_trend', 'N/A')})"
            if profile.get("roic_avg") is not None else "  ROIC:              N/A",
        f"  Insider Ownership: {round(insider * 100, 2)}%" if insider
            else "  Insider Ownership: N/A",
        f"  P/E Ratio:         {profile.get('pe_ratio', 'N/A')}",
        "",
        "  --- THESIS STATEMENT ---",
        _wrap(sections["THESIS_STATEMENT"]),
        "",
        "  --- 10-YEAR DESTINATION ---",
        _wrap(sections["DESTINATION"]),
        "",
        "  --- WATCH POINTS ---",
        f"  1. {sections['WATCH_1']}",
        f"  2. {sections['WATCH_2']}",
        f"  3. {sections['WATCH_3']}",
        "",
        "  --- DECISION ---",
        f"  {sections['DECISION']}",
        f"  {sections['DECISION_RATIONALE']}",
    ]

    # Industry analysis section
    if industry_result and industry_result.get("sections"):
        lines += [
            "",
            "  --- INDUSTRY CONTEXT ---",
        ]
        ind_sections = industry_result["sections"]
        for label in ("INDUSTRY_OVERVIEW", "MARKET_STRUCTURE", "COMPETITIVE_POSITION"):
            val = ind_sections.get(label, "")
            if val:
                display = label.replace("_", " ").title()
                lines.append(f"  {display}: {val}")

    # Similar companies section
    if similar_result:
        lines += [
            "",
            "  --- SIMILAR COMPANIES (Potential Multibaggers) ---",
        ]
        for i, s in enumerate(similar_result[:5], 1):
            name = (s.get("name") or "")[:25]
            mc = s.get("market_cap")
            mc_str = _fmt_mcap(mc) if mc else "N/A"
            rg = s.get("revenue_growth")
            rg_str = f"{rg * 100:.1f}%" if rg is not None else "N/A"
            roic = s.get("roic")
            roic_str = f"{roic * 100:.1f}%" if roic is not None else "N/A"
            pe = s.get("pe_ratio")
            pe_str = f"{pe:.1f}" if pe is not None else "N/A"
            score = s.get("multibagger_score", 0)
            lines.append(
                f"  {i}. {s.get('ticker', '?')} - {name}  |  "
                f"MktCap: {mc_str}  RevGrowth: {rg_str}  "
                f"ROIC: {roic_str}  P/E: {pe_str}  "
                f"Score: {score}/12"
            )

    lines += ["", f"{'=' * W}"]
    return "\n".join(lines)


# -- Storage -------------------------------------------------------------------

def _save(ticker: str, today_str: str, profile: dict, bmp_result: dict,
          fisher_result: dict | None, selection_result: dict | None,
          risk_result: dict, sections: dict, formatted: str,
          judge_flags: dict | None = None,
          valuation_result: dict | None = None,
          industry_result: dict | None = None,
          similar_result: list | None = None) -> tuple[str, str]:
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
            "operating_cash_flow":  profile.get("operating_cash_flow"),
            "operating_income":     profile.get("operating_income"),
            "roe":                  profile.get("roe"),
            "roce_avg":             profile.get("roce_avg"),
            "roic_avg":             profile.get("roic_avg"),
            "roce_trend":           profile.get("roce_trend"),
            "roic_trend":           profile.get("roic_trend"),
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
                "penalty_floors": risk_result.get("penalty_floors", []),
            },
        },
        "judge_flags": judge_flags or {},
        "valuation": valuation_result if valuation_result and valuation_result.get("available") else None,
        "industry_analysis": industry_result if industry_result else None,
        "similar_companies": similar_result if similar_result else None,
        "thesis": {
            "executive_summary":   sections["EXECUTIVE_SUMMARY"],
            "bull_case":           [sections["BULL_1"], sections["BULL_2"], sections["BULL_3"]],
            "bear_case":           [sections["BEAR_1"], sections["BEAR_2"], sections["BEAR_3"]],
            "thesis_statement":    sections["THESIS_STATEMENT"],
            "destination":         sections["DESTINATION"],
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
        risk_result: dict, valuation_result: dict | None = None,
        industry_result: dict | None = None,
        similar_result: list | None = None) -> dict:
    """
    Write and save the investment thesis.
    Always runs regardless of prior stage verdicts.
    """
    company    = profile.get("name") or profile.get("ticker", "Unknown")
    ticker     = profile.get("ticker", "UNKNOWN")
    today_str  = date.today().isoformat()

    print(f"\n  [Thesis] Writing investment thesis for {company}...")

    context  = _build_context(
        profile, bmp_result, fisher_result, selection_result, risk_result,
        valuation_result, industry_result, similar_result,
    )
    raw      = _write_thesis_sections(context)
    sections = _parse_sections(raw)

    formatted = _format_thesis(
        profile, bmp_result, fisher_result, selection_result,
        risk_result, sections, today_str, valuation_result,
        industry_result, similar_result,
    )

    print(formatted)

    from agents.judge import check_bull_bear_balance, check_thesis_coherence, print_judge

    bear_r = check_bull_bear_balance(
        company, [sections["BEAR_1"], sections["BEAR_2"], sections["BEAR_3"]]
    )
    print_judge(bear_r, company)

    coherence_r = check_thesis_coherence(
        company, sections["DECISION"],
        bmp_result, fisher_result, selection_result, risk_result,
        valuation_result,
    )
    print_judge(coherence_r, company)

    # Option #8 -- collect all judge flags for audit trail in JSON
    judge_flags: dict = {}
    if bmp_result.get("judge"):
        judge_flags["score_justification_bmp"] = bmp_result["judge"].asdict()
    if fisher_result and fisher_result.get("judge"):
        judge_flags["score_justification_fisher"] = fisher_result["judge"].asdict()
    if selection_result and selection_result.get("judge"):
        judge_flags["score_justification_selection"] = selection_result["judge"].asdict()
    if risk_result.get("judge"):
        judge_flags["cross_stage_consistency"] = risk_result["judge"].asdict()
    judge_flags["bull_bear_balance"]  = bear_r.asdict()
    judge_flags["thesis_coherence"]   = coherence_r.asdict()

    json_path, txt_path = _save(
        ticker, today_str, profile, bmp_result, fisher_result,
        selection_result, risk_result, sections, formatted, judge_flags,
        valuation_result, industry_result, similar_result,
    )

    print(f"  [Thesis] Saved: {json_path}")
    print(f"  [Thesis] Saved: {txt_path}\n")

    return {
        "sections":  sections,
        "decision":  sections["DECISION"],
        "json_path": json_path,
        "txt_path":  txt_path,
    }
