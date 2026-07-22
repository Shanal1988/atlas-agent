# Stage 4 - Stock Selection Checklist

import os
import yfinance as yf
import pandas as pd
from groq import Groq


GROQ_MODEL = "openai/gpt-oss-120b"


def _call_llm(messages: list, max_tokens: int, temperature: float) -> str:
    """Use fine-tuned OpenAI model if OPENAI_FT_SELECTION_MODEL is set, else Groq."""
    ft_model = os.environ.get("OPENAI_FT_SELECTION_MODEL")
    if ft_model:
        try:
            from openai import OpenAI
            resp = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model=ft_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  [Warning] OpenAI Selection model failed ({e}), falling back to Groq.")
    try:
        resp = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        from agents.llm_client import gemini_call
        return gemini_call(messages, max_tokens, temperature, stage="selection")

_SELECTION_SYSTEM = (
    "You are a rigorous long-term equity analyst running a stock selection checklist "
    "for a disciplined value-growth investor. "
    "Score each question YES (1), PARTIAL (0.5), or NO (0). "
    "Use the financial data and computed metrics provided. "
    "Give one sentence of evidence-based reasoning per question. "
    "Flag any question where data is insufficient rather than guessing.\n\n"
    "Reply in this exact format, one question per line, no extra text:\n"
    "Q1: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q2: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q3: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q4: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q5: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q6: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q7: [YES/PARTIAL/NO] Reasoning here.\n"
    "Q8: [YES/PARTIAL/NO] Reasoning here."
)

_CHECKLIST_QUESTIONS = """
Q1 SIMPLICITY:           Can you explain the business model in 2 sentences to a 10-year-old? Score YES if the business is clear and simple with no excessive complexity.
Q2 EARNINGS CONSISTENCY: Has the company grown earnings consistently? Look for EPS/Net Income growth trend, no more than 1-2 loss-making years in available history.
Q3 TEN YEAR DURABILITY:  What is this company's 10-year destination? Apply Nomad's destination analysis: the primary long-term risk is misanalysing where the business is heading, not short-term volatility. Will it be materially larger, stronger-moated, and more valuable? Look for a clear destination (e.g. dominant logistics platform, global software standard), structural tailwinds that compound, and no obvious disruption that diverts the journey.
Q4 BUFFETT DOLLAR TEST:  For every $1 retained, has the company created more than $1 of market value? Use the Buffett Ratio provided. Ratio > 1.0 = YES, 0.5-1.0 = PARTIAL, < 0.5 or negative = NO.
Q5 MOAT DURABILITY:      Does the competitive advantage look durable for the next decade? Look for structural moat - switching costs or network effects that compound over time.
Q6 MANAGEMENT QUALITY:   Do managers think and act like long-term owners — building the moat rather than harvesting it? Look for insider ownership (>15% ideal), buybacks vs dilution, reinvestment into customer value and competitive position over short-term margin extraction, and a demonstrated willingness to sacrifice near-term profits to widen the moat.
Q7 CAPEX INTENSITY:      Is the business asset-light? Use Capex % of Revenue provided. < 5% = YES, 5-15% = PARTIAL, > 15% = NO.
Q8 FREE CASH FLOW:       Does the company generate strong and consistent free cash flow? Look for FCF margin > 15%, FCF growth trend, FCF/Net Income conversion > 0.8.
"""


# -- Financial company detection -----------------------------------------------

_FINANCIAL_SECTORS = {"Financial Services", "Real Estate"}
_FINANCIAL_FINTECH_KEYWORDS = {
    "payment", "fintech", "financial technology", "banking",
    "insurance", "credit services", "capital markets", "money transfer",
}


def _is_financial_company(profile: dict) -> bool:
    """Return True if FCF is likely distorted by customer float or deposits."""
    sector      = (profile.get("sector") or "").strip()
    industry    = (profile.get("industry") or "").lower()
    description = (profile.get("description") or "").lower()

    if sector in _FINANCIAL_SECTORS:
        return True
    # Check industry name AND description — fintech companies often have a generic
    # industry label (e.g. "Information Technology Services") but their description
    # clearly identifies them as payment/fintech businesses
    search_text = f"{industry} {description}"
    if any(kw in search_text for kw in _FINANCIAL_FINTECH_KEYWORDS):
        return True
    return False


# -- yfinance additional data fetch --------------------------------------------

def _safe_float(val) -> float | None:
    try:
        return None if val is None or pd.isna(val) else float(val)
    except Exception:
        return None


def _fetch_additional_data(ticker: str) -> dict:
    """
    Fetch the extra yfinance fields needed for this checklist:
    - Net Income history (earnings consistency + Buffett test)
    - Diluted Average Shares (to compute EPS)
    - Capital Expenditure (capex intensity)
    - Historical market cap ~5yr ago (Buffett test)
    """
    result = {
        "eps_history":          [],   # list of {year, eps}
        "net_income_history":   [],   # list of {year, net_income}
        "capex_latest":         None,
        "revenue_latest":       None,
        "capex_pct":            None,
        "mcap_5yr_ago":         None,
        "buffett_ratio":        None,
        "operating_cash_flow":  None,   # OCF fallback for financial companies
    }

    try:
        t = yf.Ticker(ticker)
        info = t.info
        fin  = t.financials   # rows = metrics, columns = dates newest-first
        cf   = t.cashflow

        # -- Net income and EPS history --
        ni_row  = "Net Income"
        eps_row = "Diluted Average Shares"   # yfinance mis-labels this as Diluted EPS

        if ni_row in fin.index and eps_row in fin.index:
            ni_series    = fin.loc[ni_row]
            shares_series = fin.loc[eps_row]
            for col in fin.columns:
                ni     = _safe_float(ni_series.get(col))
                shares = _safe_float(shares_series.get(col))
                year   = str(col.year)
                result["net_income_history"].append({"year": year, "net_income": ni})
                if ni is not None and shares and shares > 0:
                    result["eps_history"].append({"year": year, "eps": round(ni / shares, 4)})

        elif ni_row in fin.index:
            for col in fin.columns:
                ni = _safe_float(fin.loc[ni_row].get(col))
                result["net_income_history"].append({"year": str(col.year), "net_income": ni})

        # -- Capex and revenue for capex % --
        capex_keys = ["Capital Expenditure"]
        rev_keys   = ["Total Revenue"]
        capex = None
        rev   = None

        for k in capex_keys:
            if k in cf.index:
                capex = _safe_float(cf.loc[k].iloc[0])
                break

        for k in rev_keys:
            if k in fin.index:
                rev = _safe_float(fin.loc[k].iloc[0])
                break

        result["capex_latest"]  = capex
        result["revenue_latest"] = rev

        if capex is not None and rev and rev > 0:
            result["capex_pct"] = round(abs(capex) / rev * 100, 2)

        # -- Operating Cash Flow (Q8 substitute for financial companies) --
        ocf_keys = ["Operating Cash Flow",
                    "Cash Flow From Continuing Operating Activities"]
        for k in ocf_keys:
            if k in cf.index:
                result["operating_cash_flow"] = _safe_float(cf.loc[k].iloc[0])
                break

        # -- Buffett Dollar Test: ΔMarketCap / cumulative retained earnings --
        # Use 5-year price history to estimate market cap at start of window
        hist   = t.history(period="5y")
        shares_out = info.get("sharesOutstanding")
        mcap_now   = info.get("marketCap")

        if not hist.empty and shares_out and mcap_now:
            price_5yr_ago     = float(hist["Close"].iloc[0])
            result["mcap_5yr_ago"] = price_5yr_ago * shares_out
            delta_mcap        = mcap_now - result["mcap_5yr_ago"]

            # Cumulative retained earnings = sum of net income over available years
            # (approximation: no dividends found for these companies)
            ni_values = [
                r["net_income"] for r in result["net_income_history"]
                if r["net_income"] is not None and r["net_income"] > 0
            ]
            cumulative_retained = sum(ni_values) if ni_values else None

            if cumulative_retained and cumulative_retained > 0:
                result["buffett_ratio"] = round(delta_mcap / cumulative_retained, 2)

    except Exception:
        pass  # return whatever was populated; Groq will flag missing data

    return result


# -- Context builder -----------------------------------------------------------

def _build_context(profile: dict, extra: dict) -> str:
    revenues = profile.get("revenues") or []
    rev_str  = "  |  ".join(
        f"{r.get('year','?')}: {r.get('revenue')}" for r in revenues
    ) or "N/A"

    cagr_raw = profile.get("revenue_cagr") if profile.get("revenue_cagr") is not None \
               else profile.get("revenue_growth_pct")
    cagr     = f"{round(cagr_raw * 100, 2)}%" if cagr_raw is not None else "N/A"

    roe     = profile.get("roe")
    insider = profile.get("insider_ownership_pct")
    fcf     = profile.get("free_cash_flow")
    ni_hist = extra.get("net_income_history", [])
    eps_hist = extra.get("eps_history", [])

    # EPS summary line (newest first)
    eps_str = "  |  ".join(
        f"{e['year']}: {e['eps']:.4f}" for e in eps_hist[:5]
    ) or "N/A (computed from Net Income / Diluted Shares)"

    # Net Income summary
    ni_str = "  |  ".join(
        f"{n['year']}: {n['net_income']}" for n in ni_hist[:5]
        if n["net_income"] is not None
    ) or "N/A"

    capex_pct     = extra.get("capex_pct")
    buffett_ratio = extra.get("buffett_ratio")
    is_fin        = _is_financial_company(profile)
    ocf           = extra.get("operating_cash_flow")

    latest_rev = revenues[0].get("revenue") if revenues else None

    if is_fin:
        # FCF is distorted by customer float — use OCF as Q8 substitute
        fcf_display  = f"Unreliable - financial company float distortion (raw: {fcf})"
        fcf_margin_line = "FCF Margin:          N/A (FCF unreliable - see OCF Margin below)"
        fcf_ni_line     = "FCF / Net Income:    N/A (FCF unreliable)"

        ocf_margin = None
        if ocf is not None and latest_rev and latest_rev > 0:
            ocf_margin = round(ocf / latest_rev * 100, 2)

        ocf_ni_ratio = None
        if ni_hist and ocf is not None:
            latest_ni = ni_hist[0].get("net_income")
            if latest_ni and latest_ni > 0:
                ocf_ni_ratio = round(ocf / latest_ni, 2)

        ocf_line         = f"Operating Cash Flow: {ocf} [Q8 substitute for FCF]" if ocf is not None \
                           else "Operating Cash Flow: N/A"
        ocf_margin_line  = f"OCF Margin (Q8):     {ocf_margin}%" if ocf_margin is not None \
                           else "OCF Margin (Q8):     N/A"
        ocf_ni_line_str  = f"OCF / Net Income:    {ocf_ni_ratio}" if ocf_ni_ratio is not None \
                           else "OCF / Net Income:    N/A"
        fin_note = (
            "NOTE (Q8):           FCF is unreliable for this company due to financial company "
            "float/deposit distortion. Score Q8 using OCF Margin and OCF/Net Income instead. "
            "OCF margin > 15% = YES, 5-15% = PARTIAL, < 5% = NO."
        )
    else:
        fcf_margin = None
        if fcf is not None and latest_rev and latest_rev > 0:
            fcf_margin = round(fcf / latest_rev * 100, 2)

        fcf_ni_ratio = None
        if ni_hist and fcf is not None:
            latest_ni = ni_hist[0].get("net_income")
            if latest_ni and latest_ni > 0:
                fcf_ni_ratio = round(fcf / latest_ni, 2)

        fcf_display      = str(fcf) if fcf is not None else "N/A"
        fcf_margin_line  = f"FCF Margin:          {fcf_margin}%" if fcf_margin is not None \
                           else "FCF Margin:          N/A"
        fcf_ni_line      = f"FCF / Net Income:    {fcf_ni_ratio}" if fcf_ni_ratio is not None \
                           else "FCF / Net Income:    N/A"

    lines = [
        f"Company:             {profile.get('name', 'N/A')}",
        f"Sector/Industry:     {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Description:         {profile.get('description', 'N/A')}",
        f"Market Cap:          {profile.get('market_cap', 'N/A')}",
        f"P/E Ratio:           {profile.get('pe_ratio', 'N/A')}",
        f"Revenue (3yr):       {rev_str}",
        f"Revenue CAGR:        {cagr}",
        f"Net Income history:  {ni_str}",
        f"EPS history:         {eps_str}",
        f"Free Cash Flow:      {fcf_display}",
        fcf_margin_line,
        fcf_ni_line,
        f"ROE:                 {round(roe * 100, 2)}%" if roe else "ROE:                 N/A",
        f"Insider Ownership:   {round(insider * 100, 2)}%" if insider else "Insider Ownership:   N/A",
        f"Moat:                {profile.get('moat', 'N/A')}",
        f"Growth Drivers:      {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:        {'; '.join(profile.get('risk_factors', []))}",
        f"--- Computed Metrics ---",
        f"Capex % of Revenue:  {capex_pct}%" if capex_pct is not None else "Capex % of Revenue:  N/A",
        f"Buffett Ratio:       {buffett_ratio} (delta market cap / cumulative retained earnings over ~5yr)"
            if buffett_ratio is not None else "Buffett Ratio:       N/A (insufficient history)",
        f"ROCE (avg):          {round(profile.get('roce_avg') * 100, 2)}%  Trend: {profile.get('roce_trend', 'N/A')}"
            if profile.get("roce_avg") is not None else "ROCE:                N/A",
        f"ROIC (avg):          {round(profile.get('roic_avg') * 100, 2)}%  Trend: {profile.get('roic_trend', 'N/A')}"
            if profile.get("roic_avg") is not None else "ROIC:                N/A",
    ]

    if is_fin:
        lines += [ocf_line, ocf_margin_line, ocf_ni_line_str, fin_note]

    return "\n".join(lines)


# -- Groq scoring --------------------------------------------------------------

def _score_with_groq(context: str) -> str:
    user_msg = (
        f"Company data and computed metrics:\n{context}\n\n"
        f"Score these 8 checklist questions:\n{_CHECKLIST_QUESTIONS}"
    )
    return _call_llm(
        messages=[
            {"role": "system", "content": _SELECTION_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=768,
        temperature=0.1,
    )


# -- Parser --------------------------------------------------------------------

_Q_LABELS = {
    "Q1": "Simplicity",
    "Q2": "Earnings Consistency",
    "Q3": "Ten Year Durability",
    "Q4": "Buffett Dollar Test",
    "Q5": "Moat Durability",
    "Q6": "Management Quality",
    "Q7": "Capex Intensity",
    "Q8": "Free Cash Flow",
}


def _parse_answers(text: str) -> list[dict]:
    answers = []
    for key, label in _Q_LABELS.items():
        rating    = "N/A"
        reasoning = ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                rest = stripped[len(key) + 1:].strip()
                if rest.startswith("["):
                    close = rest.find("]")
                    if close != -1:
                        rating    = rest[1:close].strip().upper()
                        reasoning = rest[close + 1:].strip()
                else:
                    parts  = rest.split(None, 1)
                    rating = parts[0].upper().rstrip(".")
                    reasoning = parts[1] if len(parts) > 1 else ""
                break
        answers.append({"key": key, "label": label, "rating": rating, "reasoning": reasoning})
    return answers


def _score(answers: list[dict]) -> float:
    total = 0.0
    for a in answers:
        r = a["rating"]
        if r == "YES":
            total += 1.0
        elif r == "PARTIAL":
            total += 0.5
    return total


def _verdict(score: float) -> str:
    if score >= 7:
        return "STRONG BUY candidate"
    if score >= 5:
        return "BUY with monitoring"
    if score >= 3:
        return "WATCHLIST only"
    return "AVOID"


# -- Output --------------------------------------------------------------------

def _print_results(profile: dict, answers: list[dict], score: float,
                   extra: dict) -> None:
    W    = 48
    name = profile.get("name", "N/A")

    capex_pct     = extra.get("capex_pct")
    buffett_ratio = extra.get("buffett_ratio")
    is_fin        = _is_financial_company(profile)
    ocf           = extra.get("operating_cash_flow")

    print(f"\n{'=' * W}")
    print("  ATLAS: STOCK SELECTION CHECKLIST")
    print(f"{'=' * W}")
    print(f"  Company: {name}")
    print()

    for a in answers:
        label_col = f"{a['key']} {a['label']}:"
        suffix = ""
        if a["key"] == "Q4" and buffett_ratio is not None:
            suffix = f"  (ratio: {buffett_ratio})"
        if a["key"] == "Q7" and capex_pct is not None:
            suffix = f"  (capex %: {capex_pct}%)"
        if a["key"] == "Q8" and is_fin:
            suffix = f"  (scored on OCF: {ocf})"
        print(f"  {label_col:<28} [{a['rating']:<7}]  {a['reasoning']}{suffix}")

    if is_fin:
        print()
        print("  [FCF adjusted for financial company characteristics]")

    verdict = _verdict(score)
    print()
    print(f"  SELECTION SCORE:   {score} / 8")
    print(f"  SELECTION VERDICT: {verdict}")
    print(f"{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(profile: dict, bmp_verdict: str) -> dict | None:
    """
    Run the 8-question Stock Selection Checklist.
    Skips if BMP verdict is REJECT.
    Returns result dict or None if skipped.
    """
    if bmp_verdict.upper().startswith("REJECT"):
        print(f"\n  [Selection] BMP verdict is REJECT — running full checklist to capture complete business picture.")

    ticker  = profile.get("ticker", "")
    company = profile.get("name") or ticker
    print(f"\n  [Selection] Fetching additional data for {company}...")

    extra   = _fetch_additional_data(ticker)
    context = _build_context(profile, extra)

    print("  [Selection] Scoring checklist via Groq...")
    raw     = _score_with_groq(context)

    answers = _parse_answers(raw)
    score   = _score(answers)

    _print_results(profile, answers, score, extra)

    from agents.judge import audit_score_justification, print_judge
    judge_r = audit_score_justification("SELECTION", context, answers)
    print_judge(judge_r, company)

    return {
        "answers": answers,
        "score":   score,
        "verdict": _verdict(score),
        "judge":   judge_r,
    }
