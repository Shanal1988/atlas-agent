# Stage 1 - Company Discovery

import os
import sys
import requests
import yfinance as yf
import pandas as pd
from groq import Groq
from tavily import TavilyClient
from agents.guardrails import check_security_type


# -- Constants -----------------------------------------------------------------

FMP_BASE = "https://financialmodelingprep.com/stable"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Yahoo Finance exchange suffixes that indicate non-US listings -> use yfinance
_INTL_SUFFIXES = {
    "L",   # London Stock Exchange
    "AS",  # Euronext Amsterdam
    "TO",  # Toronto Stock Exchange
    "PA",  # Euronext Paris
    "DE",  # Deutsche Börse (XETRA)
    "HK",  # Hong Kong
    "AX",  # ASX Australia
    "BR",  # Euronext Brussels
    "MC",  # Madrid
    "MI",  # Milan
    "CO",  # Copenhagen
    "ST",  # Stockholm
    "OL",  # Oslo
    "HE",  # Helsinki
    "SW",  # SIX Swiss Exchange
    "VI",  # Vienna
    "OTC", # OTC markets
    "SA",  # São Paulo (B3)
    "NS",  # NSE India
    "BO",  # BSE India
    "KL",  # Kuala Lumpur
    "SI",  # Singapore
}


# -- Shared clients (lazily initialised on first use) -------------------------

def _groq() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])

def _tavily() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


# -- Exchange routing ----------------------------------------------------------

def _is_us_listed(ticker: str) -> bool:
    """True -> use FMP.  False -> use yfinance."""
    if "." not in ticker and ":" not in ticker:
        return True
    if ":" in ticker:
        # e.g. TSE:CSU format -> international
        return False
    suffix = ticker.rsplit(".", 1)[1].upper()
    return suffix not in _INTL_SUFFIXES


# -- Step 1: Ticker resolution -------------------------------------------------

def _resolve_ticker(company_name: str) -> str:
    """
    Tavily search -> Groq extraction.
    Returns ticker with correct exchange suffix (e.g. ADYEN.AS, WISE.L, AAPL).
    """
    print("  [1/3] Resolving ticker...")

    results = _tavily().search(
        query=f"{company_name} stock ticker symbol exchange",
        max_results=5,
    )
    snippets = "\n\n".join(
        f"Title: {r['title']}\n{r['content']}"
        for r in results.get("results", [])
    )

    prompt = (
        f'From the search results below, extract the primary stock ticker symbol for "{company_name}".\n\n'
        "Rules:\n"
        "- US-listed (NYSE/NASDAQ): no suffix, e.g. AAPL, CRWD, GOOGL\n"
        "- London Stock Exchange: .L suffix, e.g. WISE.L\n"
        "- Euronext Amsterdam: .AS suffix, e.g. ADYEN.AS, ASML.AS\n"
        "- Toronto Stock Exchange: .TO suffix or TSE:TICKER format, e.g. SHOP.TO\n"
        "- Other exchanges: use the correct Yahoo Finance suffix\n\n"
        "Reply with ONLY the ticker symbol. Nothing else.\n\n"
        f"Search results:\n{snippets}"
    )

    try:
        response = _groq().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip().upper()
        ticker = raw.split()[0].strip(".,;:()'\"")
    except Exception as e:
        print(f"        -> Groq unavailable ({type(e).__name__}), using input as ticker")
        ticker = company_name.upper().split()[0].strip(".,;:()'\"")
    print(f"        -> {ticker}")
    return ticker


# -- Step 2a: FMP data (US-listed) ---------------------------------------------

def _fmp(endpoint: str, params: dict) -> list | None:
    """Single FMP stable API call. Returns list or None on any error."""
    params["apikey"] = os.environ["FMP_API_KEY"]
    resp = requests.get(f"{FMP_BASE}{endpoint}", params=params, timeout=15)
    if resp.status_code == 401:
        print("  FMP error: Unauthorized -- check FMP_API_KEY in .env")
        sys.exit(1)
    if resp.status_code in (402, 403, 404):
        return None
    resp.raise_for_status()
    data = resp.json()
    return data if data else None


def _fetch_fmp_data(ticker: str) -> dict | None:
    """Fetch profile + financials from FMP for US-listed tickers."""
    profile_data = _fmp("/profile", {"symbol": ticker})
    if not profile_data:
        return None
    p = profile_data[0]

    # Income statement -- last 3 fiscal years
    income = _fmp("/income-statement", {"symbol": ticker, "limit": 3}) or []
    revenues = [
        {"year": str(row.get("fiscalYear", "?")), "revenue": row.get("revenue")}
        for row in income
    ]
    operating_income = income[0].get("operatingIncome") if income else None

    # Cash flow -- last year
    cf = _fmp("/cash-flow-statement", {"symbol": ticker, "limit": 1}) or []
    free_cash_flow       = cf[0].get("freeCashFlow")      if cf else None
    operating_cash_flow  = cf[0].get("operatingCashFlow") if cf else None

    # Ratios -- last year
    ratios = _fmp("/ratios", {"symbol": ticker, "limit": 1}) or []
    r = ratios[0] if ratios else {}
    pe = r.get("priceToEarningsRatio")
    roe = r.get("returnOnEquity")

    return {
        "name":                 p.get("companyName"),
        "ticker":               p.get("symbol"),
        "exchange":             p.get("exchange"),
        "sector":               p.get("sector"),
        "industry":             p.get("industry"),
        "market_cap":           p.get("marketCap"),
        "current_price":        p.get("price"),
        "pe_ratio":             round(pe, 2) if pe else None,
        "beta":                 p.get("beta"),
        "revenues":             revenues,
        "free_cash_flow":       free_cash_flow,
        "operating_cash_flow":  operating_cash_flow,
        "operating_income":     operating_income,
        "roe":                  roe,
        "insider_ownership_pct": p.get("insiderOwnership"),
        "data_source":          "FMP",
    }


# -- Step 2a-patch: fill FMP gaps from yfinance --------------------------------

_PATCHABLE = ("revenues", "free_cash_flow", "operating_cash_flow", "operating_income", "roe", "insider_ownership_pct", "pe_ratio")


def _patch_fmp_gaps(data: dict, ticker: str) -> dict:
    """
    Silently fill any None/empty financial fields in FMP data using yfinance.
    Populates data['field_sources'] so the printer can show [FMP] / [yfinance] tags.
    """
    # Mark every patchable field with its current source
    sources = {f: "FMP" for f in _PATCHABLE}

    needs_patch = (
        not data.get("revenues")
        or data.get("free_cash_flow") is None
        or data.get("operating_cash_flow") is None
        or data.get("operating_income") is None
        or data.get("roe") is None
        or data.get("insider_ownership_pct") is None
        or data.get("pe_ratio") is None
    )

    if needs_patch:
        try:
            yf = _fetch_yfinance_data(ticker)
        except Exception:
            yf = None

        if yf:
            if not data.get("revenues") and yf.get("revenues"):
                data["revenues"] = yf["revenues"]
                sources["revenues"] = "yfinance"

            for field in ("free_cash_flow", "operating_cash_flow", "operating_income", "roe", "insider_ownership_pct", "pe_ratio"):
                if data.get(field) is None and yf.get(field) is not None:
                    data[field] = yf[field]
                    sources[field] = "yfinance"

    data["field_sources"] = sources
    return data


# -- Step 2b: yfinance data (international) ------------------------------------

def _safe_int(val) -> int | None:
    try:
        return None if val is None or pd.isna(val) else int(val)
    except Exception:
        return None


def _fetch_yfinance_data(ticker: str) -> dict | None:
    """Fetch profile + financials from yfinance for international tickers."""
    t = yf.Ticker(ticker)
    info = t.info

    if not info or not any(info.get(k) for k in ("currentPrice", "regularMarketPrice", "marketCap")):
        return None

    # Revenue -- last 3 annual periods (columns = dates, newest first)
    revenues = []
    try:
        fin = t.financials
        if fin is not None and not fin.empty and "Total Revenue" in fin.index:
            rev_row = fin.loc["Total Revenue"]
            for col in list(rev_row.index)[:3]:
                revenues.append({
                    "year": str(col.year),
                    "revenue": _safe_int(rev_row[col]),
                })
    except Exception:
        pass

    # Operating Cash Flow and Free Cash Flow -- most recent annual
    operating_cash_flow = None
    free_cash_flow = None
    try:
        cf = t.cashflow
        if cf is not None and not cf.empty:
            if "Operating Cash Flow" in cf.index:
                vals = cf.loc["Operating Cash Flow"].dropna()
                if len(vals):
                    operating_cash_flow = _safe_int(vals.iloc[0])
            if "Free Cash Flow" in cf.index:
                vals = cf.loc["Free Cash Flow"].dropna()
                if len(vals):
                    free_cash_flow = _safe_int(vals.iloc[0])
            if free_cash_flow is None and operating_cash_flow is not None:
                cap = cf.loc["Capital Expenditure"].iloc[0] if "Capital Expenditure" in cf.index else None
                if cap is not None:
                    free_cash_flow = _safe_int(operating_cash_flow + cap)  # capex stored as negative
    except Exception:
        pass

    # Operating income -- most recent annual
    operating_income = None
    try:
        fin = t.financials
        if fin is not None and not fin.empty:
            for row_name in ("Operating Income", "EBIT", "Total Operating Income As Reported"):
                if row_name in fin.index:
                    vals = fin.loc[row_name].dropna()
                    if len(vals):
                        operating_income = _safe_int(vals.iloc[0])
                    break
    except Exception:
        pass

    pe  = info.get("trailingPE")
    roe = info.get("returnOnEquity")

    return {
        "name":                 info.get("longName") or info.get("shortName"),
        "ticker":               ticker,
        "exchange":             info.get("fullExchangeName") or info.get("exchange"),
        "sector":               info.get("sector"),
        "industry":             info.get("industry"),
        "market_cap":           info.get("marketCap"),
        "current_price":        info.get("currentPrice") or info.get("regularMarketPrice"),
        "pe_ratio":             round(pe, 2) if pe else None,
        "beta":                 info.get("beta"),
        "revenues":             revenues,
        "free_cash_flow":       free_cash_flow,
        "operating_cash_flow":  operating_cash_flow,
        "operating_income":     operating_income,
        "roe":                  roe,
        "insider_ownership_pct": info.get("heldPercentInsiders"),
        "data_source":          "yfinance",
    }


# -- Revenue CAGR --------------------------------------------------------------

def _revenue_cagr(revenues: list) -> float | None:
    """
    revenues is sorted newest-first.
    CAGR = (newest / oldest)^(1/n) - 1
    """
    valid = [r for r in revenues if r.get("revenue")]
    if len(valid) < 2:
        return None
    newest = valid[0]["revenue"]
    oldest = valid[-1]["revenue"]
    n = len(valid) - 1
    if oldest <= 0:
        return None
    return round((newest / oldest) ** (1 / n) - 1, 4)


# -- Step 3: Qualitative analysis ----------------------------------------------

_ANALYST_SYSTEM = (
    "You are an equity research analyst. Based on the search results provided, "
    "extract and summarise:\n"
    "1. A 2-3 sentence plain English description of what the company does\n"
    "2. Primary competitive moat (one of: switching costs, network effects, "
    "cost advantage, intangible assets, efficient scale)\n"
    "3. Top 2 growth drivers (one sentence each)\n"
    "4. Top 2 risk factors (one sentence each)\n"
    "5. Most significant recent news in last 90 days (2-3 bullet points)\n"
    "Be concise and factual. No waffle.\n\n"
    "Reply in this exact format:\n"
    "DESCRIPTION: <text>\n"
    "MOAT: <one of the five options>\n"
    "GROWTH_1: <text>\n"
    "GROWTH_2: <text>\n"
    "RISK_1: <text>\n"
    "RISK_2: <text>\n"
    "NEWS_1: <text>\n"
    "NEWS_2: <text>\n"
    "NEWS_3: <text>"
)


def _tavily_content(query: str, max_results: int = 4) -> str:
    """Return concatenated content snippets from a Tavily search."""
    results = _tavily().search(query=query, max_results=max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results.get("results", [])
    )


def _fetch_qualitative(company_name: str, ticker: str) -> dict:
    """Four Tavily searches -> Groq synthesis."""
    searches = [
        f"{company_name} competitive moat analysis",
        f"{company_name} growth drivers 2025",
        f"{company_name} risk factors investors",
        f"{company_name} news last 90 days",
    ]
    combined = "\n\n===\n\n".join(_tavily_content(q) for q in searches)

    user_msg = (
        f"Company: {company_name} (ticker: {ticker})\n\n"
        f"Search results:\n{combined}"
    )

    try:
        response = _groq().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _ANALYST_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        text = response.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}) -- qualitative analysis skipped.")
        return {
            "description":    "N/A",
            "moat":           "N/A",
            "growth_drivers": ["N/A", "N/A"],
            "risk_factors":   ["N/A", "N/A"],
            "news":           ["N/A", "N/A", "N/A"],
        }

    def extract(label: str) -> str:
        for line in text.splitlines():
            if line.startswith(f"{label}:"):
                return line[len(label) + 1:].strip()
        return "N/A"

    return {
        "description":   extract("DESCRIPTION"),
        "moat":          extract("MOAT"),
        "growth_drivers": [extract("GROWTH_1"), extract("GROWTH_2")],
        "risk_factors":   [extract("RISK_1"),   extract("RISK_2")],
        "news":          [extract("NEWS_1"),    extract("NEWS_2"),    extract("NEWS_3")],
    }


# -- Output formatting ---------------------------------------------------------

def _fmt_num(n) -> str:
    if n is None:
        return "N/A"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"
    if abs(n) >= 1_000_000_000:
        return f"${n / 1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"${n / 1_000_000:.2f}M"
    return f"${n:,.0f}"


def _fmt_pct(n) -> str:
    if n is None:
        return "N/A"
    try:
        return f"{float(n) * 100:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _print_profile(p: dict) -> None:
    W = 44
    sources = p.get("field_sources", {})

    def tag(field: str) -> str:
        src = sources.get(field)
        return f" [{src}]" if src else ""

    revenues = p.get("revenues") or []
    cagr     = _revenue_cagr(revenues)
    rev_line = "  ->  ".join(
        f"{_fmt_num(r.get('revenue'))} ({r.get('year','?')})"
        for r in revenues
    ) or "N/A"

    print(f"\n{'=' * W}")
    print(f"  ATLAS: COMPANY DISCOVERY  [{p.get('data_source','?')}]")
    print(f"{'=' * W}")
    print(f"  Company      : {p.get('name') or 'N/A'}")
    print(f"  Ticker       : {p.get('ticker') or 'N/A'}")
    print(f"  Exchange     : {p.get('exchange') or 'N/A'}")
    sector   = p.get("sector")   or "N/A"
    industry = p.get("industry") or "N/A"
    print(f"  Sector / Industry : {sector} / {industry}")

    print(f"\n  {'-' * (W - 2)}")
    print("  --- FINANCIALS ---")
    print(f"  {'-' * (W - 2)}")
    print(f"  Market Cap    : {_fmt_num(p.get('market_cap'))}")
    print(f"  Current Price : {_fmt_num(p.get('current_price'))}")
    print(f"  P/E Ratio     : {p.get('pe_ratio') or 'N/A'}{tag('pe_ratio')}")
    print(f"  Beta          : {p.get('beta') or 'N/A'}")
    print(f"  Revenue (3yr) : {rev_line}{tag('revenues')}")
    print(f"  Revenue CAGR  : {_fmt_pct(cagr) if cagr is not None else 'N/A'}{tag('revenues')}")
    print(f"  Free Cash Flow: {_fmt_num(p.get('free_cash_flow'))}{tag('free_cash_flow')}")
    print(f"  Op. Cash Flow : {_fmt_num(p.get('operating_cash_flow'))}{tag('operating_cash_flow')}")
    print(f"  Op. Income    : {_fmt_num(p.get('operating_income'))}{tag('operating_income')}")
    print(f"  ROE           : {_fmt_pct(p.get('roe'))}{tag('roe')}")
    insider = p.get("insider_ownership_pct")
    print(f"  Insider Own.  : {_fmt_pct(insider) if insider is not None else 'N/A'}{tag('insider_ownership_pct')}")

    print(f"\n  {'-' * (W - 2)}")
    print("  --- QUALITATIVE ---")
    print(f"  {'-' * (W - 2)}")
    print(f"  What they do  : {p.get('description', 'N/A')}")
    print(f"  Primary Moat  : {p.get('moat', 'N/A')}")
    drivers = p.get("growth_drivers", ["N/A", "N/A"])
    risks   = p.get("risk_factors",   ["N/A", "N/A"])
    print(f"  Growth Driver 1 : {drivers[0]}")
    print(f"  Growth Driver 2 : {drivers[1]}")
    print(f"  Risk Factor 1   : {risks[0]}")
    print(f"  Risk Factor 2   : {risks[1]}")

    print(f"\n  {'-' * (W - 2)}")
    print("  --- RECENT NEWS ---")
    print(f"  {'-' * (W - 2)}")
    for item in p.get("news", []):
        if item and item != "N/A":
            print(f"  * {item}")

    print(f"\n{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(company_name: str) -> dict:
    print(f"\nAtlas initialised for: {company_name}")

    # Step 1 -- ticker resolution
    ticker = _resolve_ticker(company_name)

    # Normalise US-listed tickers: BRK.B -> BRK-B (dot = share class, not exchange suffix)
    if _is_us_listed(ticker) and "." in ticker:
        ticker = ticker.replace(".", "-")
        print(f"        -> Normalised to {ticker}")

    # Step 1b -- security type check (Guardrail 1: fatal)
    try:
        _info = yf.Ticker(ticker).info
        error = check_security_type(ticker, _info)
        if error:
            print(f"\n{error}")
            sys.exit(1)
    except SystemExit:
        raise
    except Exception:
        pass  # if yfinance can't return info, let the pipeline continue

    # Step 2 -- financial data
    print(f"  [2/3] Fetching financial data for {ticker}...")
    financial_data = None

    if _is_us_listed(ticker):
        print("        -> Source: FMP (US-listed)")
        financial_data = _fetch_fmp_data(ticker)
        if financial_data:
            financial_data = _patch_fmp_gaps(financial_data, ticker)
        else:
            print("        FMP returned no data -- falling back to yfinance")
            financial_data = _fetch_yfinance_data(ticker)
            if financial_data:
                financial_data["field_sources"] = {f: "yfinance" for f in _PATCHABLE}
    else:
        print("        -> Source: yfinance (international)")
        financial_data = _fetch_yfinance_data(ticker)
        if financial_data:
            financial_data["field_sources"] = {f: "yfinance" for f in _PATCHABLE}
        else:
            print("        yfinance returned no data -- trying FMP")
            financial_data = _fetch_fmp_data(ticker)
            if financial_data:
                financial_data = _patch_fmp_gaps(financial_data, ticker)

    if not financial_data:
        print(f"\n  Could not retrieve financial data for '{ticker}' from any source.")
        sys.exit(1)

    # Step 3 -- qualitative analysis
    print("  [3/3] Fetching qualitative analysis (Tavily + Groq)...")
    qualitative = _fetch_qualitative(company_name, ticker)

    profile = {**financial_data, **qualitative}
    # Compute and store CAGR so downstream stages (e.g. BMP gate) can read it
    profile["revenue_cagr"] = _revenue_cagr(profile.get("revenues") or [])
    _print_profile(profile)

    # Auto-index any documents for this ticker (RAG — no-op if libs not installed)
    try:
        from agents.rag import auto_index
        auto_index(
            profile.get("ticker", ""),
            f"{profile.get('sector', '')} {profile.get('industry', '')}",
        )
    except Exception:
        pass

    return profile
