# Financial Freedom Planner — Portfolio tracking, scenario modelling, AI review
#
# Tracks holdings, calculates live portfolio value in GBP, models CAGR scenarios
# to reach a target (default £3M), and provides AI-powered portfolio review.

import json
import os
from datetime import datetime

import yfinance as yf

from agents.llm_client import gemini_call

try:
    from groq import Groq
except ImportError:
    Groq = None


# -- Constants -----------------------------------------------------------------

PORTFOLIO_PATH = os.path.join("data", "portfolio", "portfolio.json")

GROQ_MODEL = "qwen/qwen3.6-27b"

DEFAULT_PORTFOLIO = {
    "owner": "",
    "target_value": 3_000_000,
    "target_age": 50,
    "current_age": 38,
    "currency": "GBP",
    "monthly_contribution": 1000,
    "last_updated": "",
    "holdings": [],
    "contributions": [],
}

# Currencies that trade in minor units (pence, cents) on their exchange
GBX_EXCHANGES = {"LSE", "LON"}


# -- Lazy LLM client ----------------------------------------------------------

def _groq():
    return Groq(api_key=os.environ["GROQ_API_KEY"])


# -- Portfolio CRUD ------------------------------------------------------------

def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_PATH):
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_PORTFOLIO)


def save_portfolio(data: dict) -> None:
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(PORTFOLIO_PATH), exist_ok=True)
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def add_holding(ticker: str, shares: float, avg_price: float,
                account: str = "ISA", notes: str = "") -> dict:
    portfolio = load_portfolio()
    ticker = ticker.upper()

    # Fetch name from yfinance
    name = ticker
    try:
        info = yf.Ticker(ticker).info or {}
        name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        pass

    # Check if holding already exists — update it
    for h in portfolio["holdings"]:
        if h["ticker"] == ticker:
            # Average up/down
            old_total = h["shares"] * h["avg_price"]
            new_total = shares * avg_price
            h["shares"] += shares
            h["avg_price"] = (old_total + new_total) / h["shares"] if h["shares"] else avg_price
            h["notes"] = notes or h["notes"]
            print(f"  Updated {ticker}: now {h['shares']} shares @ {h['avg_price']:.2f} avg")
            save_portfolio(portfolio)
            return portfolio

    # Determine currency from ticker suffix
    currency = "GBP" if ticker.endswith(".L") else "USD"
    if any(ticker.endswith(s) for s in [".PA", ".DE", ".AS", ".MI", ".MC", ".BR"]):
        currency = "EUR"
    elif any(ticker.endswith(s) for s in [".NS", ".BO"]):
        currency = "INR"

    portfolio["holdings"].append({
        "ticker": ticker,
        "name": name,
        "shares": shares,
        "avg_price": avg_price,
        "currency": currency,
        "account": account,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "notes": notes,
    })
    print(f"  Added {ticker} ({name}): {shares} shares @ {avg_price}")
    save_portfolio(portfolio)
    return portfolio


def remove_holding(ticker: str) -> dict:
    portfolio = load_portfolio()
    ticker = ticker.upper()
    before = len(portfolio["holdings"])
    portfolio["holdings"] = [h for h in portfolio["holdings"] if h["ticker"] != ticker]
    if len(portfolio["holdings"]) < before:
        print(f"  Removed {ticker}")
        save_portfolio(portfolio)
    else:
        print(f"  {ticker} not found in portfolio")
    return portfolio


# -- Live Prices & FX ---------------------------------------------------------

def _get_fx_rate(pair: str) -> float:
    """Get FX rate e.g. 'GBPUSD=X' returns how many USD per 1 GBP."""
    try:
        info = yf.Ticker(pair).info or {}
        return info.get("regularMarketPrice") or info.get("previousClose") or 1.0
    except Exception:
        return 1.0


def get_live_prices(tickers: list[str]) -> dict:
    """Fetch current prices for all tickers. Returns {ticker: {price, currency, ...}}."""
    prices = {}
    # Pre-fetch FX rates we might need
    fx_cache = {}

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            currency = info.get("currency", "USD")

            # GBX → GBP conversion (LSE stocks trade in pence)
            if currency == "GBp" or currency == "GBX":
                price = (price or 0) / 100.0
                currency = "GBP"

            prices[ticker] = {
                "price": price,
                "currency": currency,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "roe": info.get("returnOnEquity"),
                "revenue_growth": info.get("revenueGrowth"),
                "day_change_pct": info.get("regularMarketChangePercent"),
            }
        except Exception:
            prices[ticker] = {"price": None, "currency": "USD", "name": ticker}

    return prices


def _to_gbp(amount: float, currency: str, fx_cache: dict) -> float:
    """Convert an amount to GBP."""
    if currency == "GBP":
        return amount
    pair = f"GBP{currency}=X"
    if pair not in fx_cache:
        fx_cache[pair] = _get_fx_rate(pair)
    rate = fx_cache[pair]
    return amount / rate if rate else amount


def value_portfolio(portfolio: dict, prices: dict) -> dict:
    """Calculate portfolio valuation in GBP."""
    fx_cache = {}
    holdings_valued = []
    total_value_gbp = 0.0
    total_cost_gbp = 0.0

    for h in portfolio["holdings"]:
        ticker = h["ticker"]
        p = prices.get(ticker, {})
        current_price = p.get("price")
        price_currency = p.get("currency", h.get("currency", "USD"))

        if current_price is None:
            holdings_valued.append({**h, "current_price": None, "value_gbp": 0,
                                     "cost_gbp": 0, "gain_gbp": 0, "gain_pct": 0})
            continue

        value_local = h["shares"] * current_price
        cost_local = h["shares"] * h["avg_price"]

        value_gbp = _to_gbp(value_local, price_currency, fx_cache)
        cost_gbp = _to_gbp(cost_local, h.get("currency", price_currency), fx_cache)

        gain_gbp = value_gbp - cost_gbp
        gain_pct = (gain_gbp / cost_gbp * 100) if cost_gbp else 0

        total_value_gbp += value_gbp
        total_cost_gbp += cost_gbp

        holdings_valued.append({
            **h,
            "current_price": current_price,
            "price_currency": price_currency,
            "value_gbp": value_gbp,
            "cost_gbp": cost_gbp,
            "gain_gbp": gain_gbp,
            "gain_pct": gain_pct,
            "sector": p.get("sector"),
            "pe_ratio": p.get("pe_ratio"),
            "roe": p.get("roe"),
            "revenue_growth": p.get("revenue_growth"),
        })

    # Calculate weights
    for h in holdings_valued:
        h["weight_pct"] = (h["value_gbp"] / total_value_gbp * 100) if total_value_gbp else 0

    total_gain_gbp = total_value_gbp - total_cost_gbp
    total_gain_pct = (total_gain_gbp / total_cost_gbp * 100) if total_cost_gbp else 0

    return {
        "holdings": holdings_valued,
        "total_value_gbp": total_value_gbp,
        "total_cost_gbp": total_cost_gbp,
        "total_gain_gbp": total_gain_gbp,
        "total_gain_pct": total_gain_pct,
    }


# -- Scenario Modelling --------------------------------------------------------

def _future_value(pv: float, annual_contrib: float, rate: float, years: int) -> float:
    """FV with annual compounding and annual contributions."""
    if rate == 0:
        return pv + annual_contrib * years
    fv_lump = pv * (1 + rate) ** years
    fv_annuity = annual_contrib * ((1 + rate) ** years - 1) / rate
    return fv_lump + fv_annuity


def _required_cagr(pv: float, annual_contrib: float, target: float,
                   years: int) -> float:
    """Binary search for the CAGR needed to reach target."""
    lo, hi = 0.0, 2.0  # 0% to 200%
    for _ in range(100):
        mid = (lo + hi) / 2
        fv = _future_value(pv, annual_contrib, mid, years)
        if fv < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def model_scenarios(current_value: float, monthly: float, years: int,
                    target: float) -> dict:
    """Model CAGR scenarios and find the required rate."""
    annual_contrib = monthly * 12
    cagr_levels = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

    scenarios = []
    for rate in cagr_levels:
        projections = {}
        for y in [1, 3, 5, 8, 10, 12, years]:
            if y <= years:
                projections[y] = _future_value(current_value, annual_contrib, rate, y)
        hits_target = projections.get(years, 0) >= target
        scenarios.append({
            "cagr": rate,
            "projections": projections,
            "final_value": projections.get(years, 0),
            "hits_target": hits_target,
        })

    req_cagr = _required_cagr(current_value, annual_contrib, target, years)

    # Year-by-year for required CAGR
    year_by_year = []
    for y in range(1, years + 1):
        fv = _future_value(current_value, annual_contrib, req_cagr, y)
        year_by_year.append({"year": y, "age": 38 + (years - years) + y, "value": fv})

    return {
        "current_value": current_value,
        "monthly": monthly,
        "annual": annual_contrib,
        "years": years,
        "target": target,
        "scenarios": scenarios,
        "required_cagr": req_cagr,
        "year_by_year": year_by_year,
    }


# -- AI Portfolio Review -------------------------------------------------------

def review_portfolio(portfolio: dict, valuation: dict) -> str:
    """LLM-powered portfolio review with actionable suggestions."""
    holdings_summary = []
    for h in valuation["holdings"]:
        holdings_summary.append({
            "ticker": h["ticker"],
            "name": h.get("name"),
            "sector": h.get("sector"),
            "weight_pct": round(h.get("weight_pct", 0), 1),
            "gain_pct": round(h.get("gain_pct", 0), 1),
            "pe_ratio": h.get("pe_ratio"),
            "roe": h.get("roe"),
            "revenue_growth": h.get("revenue_growth"),
            "value_gbp": round(h.get("value_gbp", 0)),
        })

    target = portfolio.get("target_value", 3_000_000)
    years = portfolio.get("target_age", 50) - portfolio.get("current_age", 38)
    total_val = valuation["total_value_gbp"]
    monthly = portfolio.get("monthly_contribution", 1000)
    req_cagr = _required_cagr(total_val, monthly * 12, target, years)

    prompt = (
        "You are a portfolio strategist helping an investor reach financial freedom.\n\n"
        f"Goal: £{target:,.0f} in {years} years (requires ~{req_cagr*100:.0f}% CAGR)\n"
        f"Current portfolio value: £{total_val:,.0f}\n"
        f"Monthly contribution: £{monthly:,.0f}\n"
        f"Account: Stocks & Shares ISA (tax-free gains)\n"
        f"Strategy: Long-term quality investor, buys quality companies, willing to take profits and redeploy\n\n"
        f"Holdings:\n{json.dumps(holdings_summary, indent=2)}\n\n"
        "Provide a structured portfolio review covering:\n"
        "1. **Portfolio Health**: concentration risk, sector/geographic diversification\n"
        "2. **Individual Stock Quality**: flag any concerns (high P/E, negative growth, etc.)\n"
        "3. **Goal Alignment**: is the portfolio positioned for the required CAGR?\n"
        "4. **Actionable Suggestions**: specific changes to improve chances of hitting the target\n"
        "   - What to consider selling/trimming\n"
        "   - What types of stocks to add (sectors, regions, themes)\n"
        "   - Optimal allocation between growth stocks vs index funds\n"
        "5. **Monthly Deployment**: how to best deploy the £{monthly}/month contributions\n\n"
        "Be direct and specific. Give actual allocation percentages and actionable steps."
    )

    msgs = [{"role": "user", "content": prompt}]
    text = ""
    try:
        resp = _groq().chat.completions.create(
            model=GROQ_MODEL, messages=msgs, max_tokens=4096, temperature=0.3,
        )
        text = resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        text = gemini_call(msgs, max_tokens=4096, temperature=0.3, stage="freedom_review")

    return text or "  [Error] Could not generate portfolio review."


# -- Display -------------------------------------------------------------------

def _fmt_gbp(n: float) -> str:
    if abs(n) >= 1e6:
        return f"£{n/1e6:,.2f}M"
    return f"£{n:,.0f}"


def _progress_bar(pct: float, width: int = 20) -> str:
    filled = int(width * min(pct, 1.0))
    return "█" * filled + "░" * (width - filled)


def print_status(portfolio: dict, valuation: dict, scenarios: dict) -> None:
    W = 72
    target = portfolio.get("target_value", 3_000_000)
    years = scenarios["years"]
    total = valuation["total_value_gbp"]
    progress = total / target if target else 0
    monthly = portfolio.get("monthly_contribution", 1000)

    print(f"\n{'=' * W}")
    print(f"  ATLAS: FINANCIAL FREEDOM TRACKER")
    print(f"  Target: £{target:,.0f} by age {portfolio.get('target_age', 50)} "
          f"({years} years remaining)")
    print(f"{'=' * W}")

    # Summary
    print(f"\n  PORTFOLIO SUMMARY")
    print(f"  {'-' * (W - 4)}")
    print(f"  Total Value:   {_fmt_gbp(total):>12}     "
          f"Progress: {_progress_bar(progress)} {progress*100:.1f}%")
    gain = valuation["total_gain_gbp"]
    gain_pct = valuation["total_gain_pct"]
    sign = "+" if gain >= 0 else ""
    print(f"  Total Cost:    {_fmt_gbp(valuation['total_cost_gbp']):>12}     "
          f"Gain:     {_fmt_gbp(gain)} ({sign}{gain_pct:.1f}%)")
    print(f"  Monthly:       {'£{:,.0f}/mo'.format(monthly):>12}     "
          f"ISA Allowance: £20,000/yr")
    print(f"  {'-' * (W - 4)}")

    # Holdings
    if valuation["holdings"]:
        print(f"\n  HOLDINGS")
        print(f"  {'-' * (W - 4)}")
        print(f"  {'Ticker':<10} {'Name':<22} {'Shares':>7} {'Avg':>8} "
              f"{'Now':>8} {'Gain%':>7} {'Weight':>7}")
        print(f"  {'-' * (W - 4)}")
        for h in sorted(valuation["holdings"], key=lambda x: x.get("value_gbp", 0), reverse=True):
            name = (h.get("name") or "")[:21]
            avg_str = f"{h['avg_price']:.2f}"
            now_str = f"{h['current_price']:.2f}" if h.get("current_price") else "N/A"
            gain_str = f"{h['gain_pct']:+.1f}%" if h.get("current_price") else "N/A"
            wt_str = f"{h['weight_pct']:.1f}%"
            print(f"  {h['ticker']:<10} {name:<22} {h['shares']:>7.0f} "
                  f"{avg_str:>8} {now_str:>8} {gain_str:>7} {wt_str:>7}")
        print(f"  {'-' * (W - 4)}")

    # Scenarios
    print(f"\n  SCENARIO PROJECTIONS ({years} years, £{monthly:,.0f}/mo)")
    print(f"  {'-' * (W - 4)}")
    print(f"  {'CAGR':>6}   {'Year 3':>10}   {'Year 5':>10}   "
          f"{'Year 10':>10}   {'Year 12':>10}   {'Hits?':>6}")
    print(f"  {'-' * (W - 4)}")
    for s in scenarios["scenarios"]:
        cagr_str = f"{s['cagr']*100:.0f}%"
        y3 = _fmt_gbp(s["projections"].get(3, 0))
        y5 = _fmt_gbp(s["projections"].get(5, 0))
        y10 = _fmt_gbp(s["projections"].get(10, 0))
        y12 = _fmt_gbp(s["projections"].get(years, 0))
        hit = "YES" if s["hits_target"] else "NO"
        print(f"  {cagr_str:>6}   {y3:>10}   {y5:>10}   {y10:>10}   {y12:>10}   {hit:>6}")
    print(f"  {'-' * (W - 4)}")
    req = scenarios["required_cagr"]
    print(f"\n  Required CAGR to reach £{target:,.0f}: {req*100:.1f}%")
    if req > 0.30:
        print(f"  Strategy: Concentrated quality stocks + multibaggers needed")
    elif req > 0.20:
        print(f"  Strategy: Aggressive growth stock picking required")
    elif req > 0.15:
        print(f"  Strategy: Quality growth stocks with some index core")
    else:
        print(f"  Strategy: Achievable with disciplined index + quality picks")

    print(f"\n{'=' * W}\n")


def print_plan(portfolio: dict, valuation: dict, scenarios: dict) -> None:
    """Detailed year-by-year projection."""
    W = 72
    target = portfolio.get("target_value", 3_000_000)
    years = scenarios["years"]
    req = scenarios["required_cagr"]
    current_age = portfolio.get("current_age", 38)

    print(f"\n{'=' * W}")
    print(f"  ATLAS: YEAR-BY-YEAR FINANCIAL FREEDOM PLAN")
    print(f"  Required CAGR: {req*100:.1f}%")
    print(f"{'=' * W}")

    print(f"\n  {'Year':>6}  {'Age':>5}  {'Portfolio Value':>16}  "
          f"{'Annual Contrib':>15}  {'Growth':>12}")
    print(f"  {'-' * (W - 4)}")

    monthly = portfolio.get("monthly_contribution", 1000)
    annual = monthly * 12
    prev_val = valuation["total_value_gbp"]

    for y in range(1, years + 1):
        fv = _future_value(valuation["total_value_gbp"], annual, req, y)
        growth = fv - prev_val - annual
        age = current_age + y
        milestone = ""
        if y == years:
            milestone = " *** TARGET ***"
        elif fv >= target * 0.5 and _future_value(valuation["total_value_gbp"], annual, req, y - 1) < target * 0.5:
            milestone = " (halfway!)"
        print(f"  {y:>6}  {age:>5}  {_fmt_gbp(fv):>16}  "
              f"{'£{:,.0f}'.format(annual):>15}  {_fmt_gbp(growth):>12}"
              f"{milestone}")
        prev_val = fv

    final = _future_value(valuation["total_value_gbp"], annual, req, years)
    total_contrib = valuation["total_value_gbp"] + annual * years
    total_growth = final - total_contrib

    print(f"  {'-' * (W - 4)}")
    print(f"\n  Starting Capital:    {_fmt_gbp(valuation['total_value_gbp'])}")
    print(f"  Total Contributions: {_fmt_gbp(annual * years)}")
    print(f"  Total Growth:        {_fmt_gbp(total_growth)}")
    print(f"  Final Value:         {_fmt_gbp(final)}")
    print(f"\n{'=' * W}\n")


def configure(target: int = None, target_age: int = None,
              current_age: int = None, monthly: int = None) -> dict:
    """Update portfolio configuration."""
    portfolio = load_portfolio()
    if target is not None:
        portfolio["target_value"] = target
    if target_age is not None:
        portfolio["target_age"] = target_age
    if current_age is not None:
        portfolio["current_age"] = current_age
    if monthly is not None:
        portfolio["monthly_contribution"] = monthly
    save_portfolio(portfolio)
    print(f"  Config updated:")
    print(f"    Target:     £{portfolio['target_value']:,.0f}")
    print(f"    Target age: {portfolio['target_age']}")
    print(f"    Current age: {portfolio['current_age']}")
    print(f"    Monthly:    £{portfolio['monthly_contribution']:,.0f}")
    return portfolio
