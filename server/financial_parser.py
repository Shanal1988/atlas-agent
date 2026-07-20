"""
Financial data parser and seeder for Atlas Agent.

Provides utilities to:
- Seed financial statements from FMP API
- Extract data from existing analysis JSON
- Parse Excel/CSV files
- Parse PDF financial statements via LLM
- Fetch and extract data from URLs
- Merge financial data dicts
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

FMP_BASE = "https://financialmodelingprep.com/stable"

# Canonical line item keys for each statement
INCOME_KEYS = [
    "revenue", "cost_of_revenue", "gross_profit", "operating_expenses",
    "operating_income", "interest_expense", "income_before_tax",
    "income_tax_expense", "net_income", "eps_basic", "eps_diluted",
]
BALANCE_KEYS = [
    "cash_and_equivalents", "total_current_assets", "total_assets",
    "total_current_liabilities", "total_debt", "total_liabilities",
    "total_equity", "shares_outstanding",
]
CASHFLOW_KEYS = [
    "operating_cash_flow", "capital_expenditures", "free_cash_flow",
    "dividends_paid", "share_buybacks",
]

# FMP field name mapping → our canonical keys
_FMP_INCOME_MAP = {
    "revenue": "revenue",
    "costOfRevenue": "cost_of_revenue",
    "grossProfit": "gross_profit",
    "operatingExpenses": "operating_expenses",
    "operatingIncome": "operating_income",
    "interestExpense": "interest_expense",
    "incomeBeforeTax": "income_before_tax",
    "incomeTaxExpense": "income_tax_expense",
    "netIncome": "net_income",
    "eps": "eps_basic",
    "epsdiluted": "eps_diluted",
}
_FMP_BALANCE_MAP = {
    "cashAndCashEquivalents": "cash_and_equivalents",
    "totalCurrentAssets": "total_current_assets",
    "totalAssets": "total_assets",
    "totalCurrentLiabilities": "total_current_liabilities",
    "totalDebt": "total_debt",
    "totalLiabilities": "total_liabilities",
    "totalStockholdersEquity": "total_equity",
    "sharesOutstanding": "shares_outstanding",
    "commonStock": "shares_outstanding",  # fallback, only used if sharesOutstanding is missing
}
_FMP_CF_MAP = {
    "operatingCashFlow": "operating_cash_flow",
    "capitalExpenditure": "capital_expenditures",
    "freeCashFlow": "free_cash_flow",
    "dividendsPaid": "dividends_paid",
    "commonStockRepurchased": "share_buybacks",
}


def _fmp(endpoint: str, params: dict) -> list | None:
    """Single FMP API call with 429 retry. Returns list or None on error."""
    from agents.fmp_client import fmp_get
    return fmp_get(endpoint, params)


def _empty_statement(keys: list[str], years: list[str]) -> dict:
    return {k: {y: None for y in years} for k in keys}


def _blank_financials(analysis_id: str, ticker: str, company: str) -> dict:
    return {
        "analysis_id": analysis_id,
        "ticker": ticker,
        "company": company,
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "years": [],
        "income_statement": {k: {} for k in INCOME_KEYS},
        "balance_sheet": {k: {} for k in BALANCE_KEYS},
        "cash_flow": {k: {} for k in CASHFLOW_KEYS},
        "uploads": [],
    }


def seed_from_fmp(ticker: str, years: int = 5) -> dict:
    """Fetch FMP financial statements and return in our schema format."""
    result: dict[str, dict] = {
        "income_statement": {k: {} for k in INCOME_KEYS},
        "balance_sheet": {k: {} for k in BALANCE_KEYS},
        "cash_flow": {k: {} for k in CASHFLOW_KEYS},
    }
    seen_years: set[str] = set()

    income_rows = _fmp("/income-statement", {"symbol": ticker, "limit": years}) or []
    for row in income_rows:
        yr = str(row.get("calendarYear") or row.get("fiscalYear") or "")
        if not yr:
            continue
        seen_years.add(yr)
        for fmp_key, our_key in _FMP_INCOME_MAP.items():
            val = row.get(fmp_key)
            if val is not None:
                result["income_statement"][our_key][yr] = val

    balance_rows = _fmp("/balance-sheet-statement", {"symbol": ticker, "limit": years}) or []
    for row in balance_rows:
        yr = str(row.get("calendarYear") or row.get("fiscalYear") or "")
        if not yr:
            continue
        seen_years.add(yr)
        for fmp_key, our_key in _FMP_BALANCE_MAP.items():
            val = row.get(fmp_key)
            if val is not None and result["balance_sheet"].get(our_key, {}).get(yr) is None:
                result["balance_sheet"].setdefault(our_key, {})[yr] = val

    cf_rows = _fmp("/cash-flow-statement", {"symbol": ticker, "limit": years}) or []
    for row in cf_rows:
        yr = str(row.get("calendarYear") or row.get("fiscalYear") or "")
        if not yr:
            continue
        seen_years.add(yr)
        for fmp_key, our_key in _FMP_CF_MAP.items():
            val = row.get(fmp_key)
            if val is not None:
                result["cash_flow"][our_key][yr] = val

    result["years"] = sorted(seen_years, reverse=True)
    return result


# yfinance row label → our canonical keys
_YF_INCOME_MAP = {
    "Total Revenue": "revenue",
    "Cost Of Revenue": "cost_of_revenue",
    "Gross Profit": "gross_profit",
    "Operating Expense": "operating_expenses",
    "Operating Income": "operating_income",
    "Interest Expense": "interest_expense",
    "Pretax Income": "income_before_tax",
    "Tax Provision": "income_tax_expense",
    "Net Income": "net_income",
    "Basic EPS": "eps_basic",
    "Diluted EPS": "eps_diluted",
}
_YF_BALANCE_MAP = {
    "Cash And Cash Equivalents": "cash_and_equivalents",
    "Current Assets": "total_current_assets",
    "Total Assets": "total_assets",
    "Current Liabilities": "total_current_liabilities",
    "Total Debt": "total_debt",
    "Total Liabilities Net Minority Interest": "total_liabilities",
    "Stockholders Equity": "total_equity",
    "Ordinary Shares Number": "shares_outstanding",
}
_YF_CF_MAP = {
    "Operating Cash Flow": "operating_cash_flow",
    "Capital Expenditure": "capital_expenditures",
    "Free Cash Flow": "free_cash_flow",
    "Cash Dividends Paid": "dividends_paid",
    "Repurchase Of Capital Stock": "share_buybacks",
}


def seed_from_yfinance(ticker: str) -> dict:
    """
    Fallback: fetch financial statements from yfinance when FMP is
    rate-limited (daily quota) or has no data for the ticker.
    """
    result: dict[str, dict] = {
        "income_statement": {k: {} for k in INCOME_KEYS},
        "balance_sheet": {k: {} for k in BALANCE_KEYS},
        "cash_flow": {k: {} for k in CASHFLOW_KEYS},
        "years": [],
    }
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        seen_years: set[str] = set()

        for df, mapping, section in (
            (t.income_stmt, _YF_INCOME_MAP, "income_statement"),
            (t.balance_sheet, _YF_BALANCE_MAP, "balance_sheet"),
            (t.cashflow, _YF_CF_MAP, "cash_flow"),
        ):
            if df is None or df.empty:
                continue
            for yf_label, our_key in mapping.items():
                if yf_label not in df.index:
                    continue
                for col in df.columns:
                    yr = str(getattr(col, "year", col))[:4]
                    val = df.loc[yf_label, col]
                    if val is not None and val == val:  # not NaN
                        result[section][our_key][yr] = float(val)
                        seen_years.add(yr)

        result["years"] = sorted(seen_years, reverse=True)
    except Exception:
        pass
    return result


def seed_from_analysis(analysis_json: dict) -> dict:
    """Extract financial data from existing analysis JSON into our schema."""
    result: dict[str, dict] = {
        "income_statement": {k: {} for k in INCOME_KEYS},
        "balance_sheet": {k: {} for k in BALANCE_KEYS},
        "cash_flow": {k: {} for k in CASHFLOW_KEYS},
    }
    seen_years: set[str] = set()

    profile = analysis_json.get("profile", {})

    # Revenue history
    for rev_entry in profile.get("revenues", []):
        yr = str(rev_entry.get("year", ""))
        val = rev_entry.get("revenue")
        if yr and val is not None:
            result["income_statement"]["revenue"][yr] = val
            seen_years.add(yr)

    # Current year estimates from profile (use analysis date as year)
    analysis_date = analysis_json.get("date", "")
    yr = analysis_date[:4] if analysis_date else ""

    if yr:
        seen_years.add(yr)
        if profile.get("operating_income"):
            result["income_statement"]["operating_income"][yr] = profile["operating_income"]
        if profile.get("free_cash_flow"):
            result["cash_flow"]["free_cash_flow"][yr] = profile["free_cash_flow"]
        if profile.get("operating_cash_flow"):
            result["cash_flow"]["operating_cash_flow"][yr] = profile["operating_cash_flow"]

    result["years"] = sorted(seen_years, reverse=True)
    return result


def merge_financials(existing: dict, new_data: dict) -> dict:
    """
    Merge new_data into existing. New non-null values overwrite existing nulls.
    New years are added. New non-null values always overwrite (user intent).
    """
    merged = existing.copy()

    # Merge years list
    existing_years = set(existing.get("years", []))
    new_years = set(new_data.get("years", []))
    merged["years"] = sorted(existing_years | new_years, reverse=True)

    for stmt in ("income_statement", "balance_sheet", "cash_flow"):
        if stmt not in new_data:
            continue
        if stmt not in merged:
            merged[stmt] = {}
        for key, year_dict in new_data[stmt].items():
            if key not in merged[stmt]:
                merged[stmt][key] = {}
            for yr, val in year_dict.items():
                if val is not None:
                    merged[stmt][key][yr] = val

    merged["last_modified"] = datetime.now(timezone.utc).isoformat()
    return merged


# Keywords indicating a row contains financial statement data — used to filter
# large freeform analyst workbooks down to the relevant statement rows.
_FIN_ROW_KEYWORDS = (
    "revenue", "income", "profit", "loss", "ebitda", "ebit", "margin",
    "cost of", "expense", "tax", "eps", "asset", "liabilit", "equity",
    "debt", "cash", "capex", "capital expenditure", "share", "dividend",
    "buyback", "operating", "free cash", "balance sheet", "statement",
    "gross", "net inc", "depreciation", "amortisation", "amortization",
)


def parse_excel(file_path: Path) -> dict:
    """
    Parse an Excel or CSV file and extract financial data using LLM.
    Filters large freeform workbooks down to rows containing financial
    keywords so the statements aren't lost outside the LLM context window.
    Returns partial financials dict (only years/statement keys found).
    """
    content = ""
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".csv":
            content = file_path.read_text(encoding="utf-8", errors="replace")[:14000]
        else:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            relevant: list[str] = []
            fallback: list[str] = []
            for sheet in wb.worksheets:
                header_added = False
                for row in sheet.iter_rows(values_only=True):
                    row_str = "\t".join(str(c) if c is not None else "" for c in row).strip()
                    if not row_str:
                        continue
                    low = row_str.lower()
                    if any(k in low for k in _FIN_ROW_KEYWORDS):
                        if not header_added:
                            relevant.append(f"=== Sheet: {sheet.title} ===")
                            header_added = True
                        relevant.append(row_str)
                    elif len(fallback) < 300:
                        fallback.append(row_str)
                    if len(relevant) >= 800:
                        break
                if len(relevant) >= 800:
                    break
            rows = relevant if relevant else fallback[:500]
            content = "\n".join(rows)[:14000]
    except Exception as e:
        return {"error": str(e), "years": [], "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    if not content.strip():
        return {"error": "No readable content found in file", "years": [],
                "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    return _llm_extract_financials(content)


def parse_pdf_financials(file_path: Path) -> dict:
    """
    Extract text from PDF and use LLM to parse financial statements.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        pages_text = []
        for page in reader.pages[:20]:  # limit to first 20 pages
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text)
        content = "\n\n".join(pages_text)[:8000]  # limit chars
    except Exception as e:
        return {"error": str(e), "years": [], "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    return _llm_extract_financials(content)


def extract_from_url(url: str) -> dict:
    """
    Fetch URL content via Tavily extract (or requests fallback) and use LLM to parse.
    """
    content = ""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
        result = client.extract(urls=[url])
        if result and result.get("results"):
            content = result["results"][0].get("raw_content", "")[:8000]
    except Exception:
        pass

    if not content:
        try:
            from bs4 import BeautifulSoup
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            content = soup.get_text(separator="\n", strip=True)[:8000]
        except Exception as e:
            return {"error": str(e), "years": [], "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    return _llm_extract_financials(content)


def _llm_extract_financials(content: str) -> dict:
    """
    Use Claude/Groq to extract financial statement data from raw text.
    Returns partial financials dict.
    """
    schema_example = json.dumps({
        "years": ["2024", "2023"],
        "income_statement": {
            "revenue": {"2024": 100000000, "2023": 90000000},
            "net_income": {"2024": 15000000, "2023": 12000000},
        },
        "balance_sheet": {
            "total_assets": {"2024": 500000000},
        },
        "cash_flow": {
            "free_cash_flow": {"2024": 20000000},
        },
    }, indent=2)

    prompt = f"""Extract financial statement data from the text below.

Return ONLY valid JSON matching this structure (include only fields you find):
{schema_example}

Available income_statement keys: {INCOME_KEYS}
Available balance_sheet keys: {BALANCE_KEYS}
Available cash_flow keys: {CASHFLOW_KEYS}

Rules:
- All monetary values must be raw numbers (not in millions/billions notation)
- If values are in millions (e.g. "£ million", "Mn", "GBP Mn"), multiply by 1,000,000
- If values are in billions, multiply by 1,000,000,000
- Use 4-digit year strings as keys (e.g. "2024"). Fiscal year dates like "31/3/2025" → "2025"
- Skip forecast/estimate columns (marked with 'e' like "FY26e" or "2026e")
- Ignore spreadsheet errors like #DIV/0!, #REF!
- Return null for values you cannot find
- Return ONLY the JSON object, no explanation

Text:
{content[:14000]}"""

    import anthropic
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Extract JSON from response
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        pass

    # Groq fallback
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e), "years": [], "income_statement": {}, "balance_sheet": {}, "cash_flow": {}}
