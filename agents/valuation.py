# Stage 7 – Intrinsic Value Analysis
#
# Four models following the user's framework:
#   1. Dhandho          – 3-phase FCF + zero-growth perpetuity + net cash (lower & higher)
#   2. Ben Graham       – Avg_NI × (8.5 + 2G)  (lower & higher growth assumption)
#   3. DCF              – 3-phase FCF + Gordon Growth terminal value + net cash
#   4. Expected Returns – projected NI × exit P/E, discounted back
#
# No LLM calls – pure arithmetic + yfinance.

import yfinance as yf
import pandas as pd


# -- Constants ------------------------------------------------------------------
DISCOUNT_RATE   = 0.10   # used in all models
TERMINAL_GROWTH = 0.03   # DCF Gordon Growth rate only
GRAHAM_PE_ZERO  = 8.5    # Ben Graham's P/E at 0% growth

# Default 3-phase growth schedules  (start_year, end_year, annual_growth)
PHASES_LOWER  = [(1, 3, 0.12), (4, 6, 0.10), (7, 10, 0.08)]
PHASES_HIGHER = [(1, 3, 0.15), (4, 6, 0.12), (7, 10, 0.10)]


# -- Financial company detection -----------------------------------------------
# Mirrored from stock_selection.py; kept here to avoid circular imports.

_FINANCIAL_SECTORS = {"Financial Services", "Real Estate"}
_FINANCIAL_FINTECH_KEYWORDS = {
    "payment", "fintech", "financial technology", "banking",
    "insurance", "credit services", "capital markets", "money transfer",
}


def _is_financial_company(profile: dict) -> bool:
    """Return True if OCF/FCF is likely distorted by customer float or deposits."""
    sector      = (profile.get("sector") or "").strip()
    industry    = (profile.get("industry") or "").lower()
    description = (profile.get("description") or "").lower()
    if sector in _FINANCIAL_SECTORS:
        return True
    return any(kw in f"{industry} {description}" for kw in _FINANCIAL_FINTECH_KEYWORDS)


# -- yfinance helpers -----------------------------------------------------------

def _safe_float(val):
    try:
        return None if val is None or pd.isna(val) else float(val)
    except Exception:
        return None


def _fetch_extra(ticker: str) -> dict:
    """Fetch shares, net cash, net income history, D&A and total capex from yfinance."""
    out = {
        "shares_outstanding": None,
        "net_cash_mn":        None,
        "ni_latest_mn":       None,
        "avg_5yr_ni_mn":      None,
        "ni_cagr_5yr":        None,
        "da_mn":              None,   # Depreciation & Amortisation (cash flow stmt)
        "total_capex_mn":     None,   # Total capital expenditure (absolute value)
    }
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        fin  = t.financials    # rows = metrics, cols = dates newest-first
        bs   = t.balance_sheet
        cf   = t.cashflow

        out["shares_outstanding"] = info.get("sharesOutstanding")

        # Net cash = total cash − total debt
        cash, debt = None, None
        if bs is not None and not bs.empty:
            for k in ("Cash And Cash Equivalents",
                      "Cash Cash Equivalents And Short Term Investments",
                      "Cash And Short Term Investments"):
                if k in bs.index:
                    cash = _safe_float(bs.loc[k].iloc[0])
                    if cash is not None:
                        break
            for k in ("Total Debt", "Long Term Debt"):
                if k in bs.index:
                    debt = _safe_float(bs.loc[k].iloc[0])
                    if debt is not None:
                        break
        if cash is not None:
            out["net_cash_mn"] = (cash - (debt or 0.0)) / 1e6

        # Net income history (newest first, up to 5 years)
        ni_hist = []
        if fin is not None and not fin.empty and "Net Income" in fin.index:
            for col in list(fin.columns)[:5]:
                val = _safe_float(fin.loc["Net Income"][col])
                if val is not None:
                    ni_hist.append(val)

        if ni_hist:
            out["ni_latest_mn"]  = ni_hist[0] / 1e6
            out["avg_5yr_ni_mn"] = (sum(ni_hist) / len(ni_hist)) / 1e6
            if len(ni_hist) >= 5 and ni_hist[-1] and ni_hist[-1] > 0:
                out["ni_cagr_5yr"] = round((ni_hist[0] / ni_hist[-1]) ** (1 / 4) - 1, 4)

        # Operating income + tax data (needed for NOPAT earnings of financial companies)
        if fin is not None and not fin.empty:
            for k in ("Operating Income", "EBIT", "Operating Profit"):
                if k in fin.index:
                    val = _safe_float(fin.loc[k].iloc[0])
                    if val is not None:
                        out["operating_income_mn"] = val / 1e6
                        break

            for k in ("Tax Provision", "Income Tax Expense", "Income Tax"):
                if k in fin.index:
                    val = _safe_float(fin.loc[k].iloc[0])
                    if val is not None and val != 0:
                        out["income_tax_mn"] = abs(val) / 1e6
                        break

            for k in ("Pretax Income", "Income Before Tax", "Pre Tax Income"):
                if k in fin.index:
                    val = _safe_float(fin.loc[k].iloc[0])
                    if val is not None:
                        out["pretax_income_mn"] = val / 1e6
                        break

        # D&A breakdown for maintenance capex estimation.
        # Preferred: fetch physical depreciation and intangible amortisation separately.
        # Physical depreciation is a genuine cash maintenance cost (servers age, trucks wear
        # out, warehouses need upkeep).  Acquired intangible amortisation is mostly non-
        # economic: the underlying assets (customer relationships, brands, technology) are
        # maintained via P&L operating expenses (sales, R&D, marketing), not capex.
        # Fallback: total D&A with a sector-blended adjustment factor (see valuation module).
        if cf is not None and not cf.empty:
            # Try physical depreciation first (separate from intangible amort)
            for k in ("Depreciation", "Depreciation Of PPE",
                      "Depreciation Tangible Assets"):
                if k in cf.index:
                    val = _safe_float(cf.loc[k].iloc[0])
                    if val is not None and val > 0:
                        out["depreciation_mn"] = val / 1e6
                        break

            # Try intangible amortisation separately
            for k in ("Amortization Of Intangibles",
                      "Amortization Of Acquired Intangibles",
                      "Amortization"):
                if k in cf.index:
                    val = _safe_float(cf.loc[k].iloc[0])
                    if val is not None and val > 0:
                        out["amort_intangibles_mn"] = val / 1e6
                        break

            # Total D&A — used when separate lines are unavailable
            for k in (
                "Depreciation Amortization Depletion",
                "Depreciation And Amortization",
                "Reconciled Depreciation",
            ):
                if k in cf.index:
                    val = _safe_float(cf.loc[k].iloc[0])
                    if val is not None and val > 0:
                        out["da_mn"] = val / 1e6
                        break

            # If we got separate components but not the total, derive it
            if out["da_mn"] is None and (out.get("depreciation_mn") or out.get("amort_intangibles_mn")):
                out["da_mn"] = (out.get("depreciation_mn") or 0.0) + (out.get("amort_intangibles_mn") or 0.0)

            # Total capex (yfinance reports as negative; take absolute value)
            for k in ("Capital Expenditure", "Capital Expenditures",
                      "Purchase Of PPE", "Purchase Of Property Plant And Equipment"):
                if k in cf.index:
                    val = _safe_float(cf.loc[k].iloc[0])
                    if val is not None:
                        out["total_capex_mn"] = abs(val) / 1e6
                        break

    except Exception:
        pass
    return out


# -- Effective tax rate ---------------------------------------------------------

def _effective_tax_rate(extra: dict) -> float:
    """
    Derive effective tax rate from income_tax / pretax_income.
    Clamped to [0.10, 0.40]. Defaults to 0.25 (global average) if unavailable.
    """
    tax    = extra.get("income_tax_mn")
    pretax = extra.get("pretax_income_mn")
    if tax is not None and pretax and pretax > 0:
        return max(0.10, min(0.40, tax / pretax))
    return 0.25


# -- Capex-heavy detection ------------------------------------------------------

def _capex_heavy_mode(fcf_abs, ocf_abs) -> bool:
    """
    Return True when FCF is severely depressed by growth capex.
    Threshold: FCF < 40% of OCF — company is in a heavy reinvestment cycle.
    Using FCF as base would dramatically understate earnings power; OCF is
    the better proxy for 'cash generated before growth reinvestment'.
    """
    if not fcf_abs or not ocf_abs or ocf_abs <= 0:
        return False
    return (fcf_abs / ocf_abs) < 0.40


# -- Owner Earnings derivation --------------------------------------------------
#
# Framework: Buffett (1986 BRK letter), Mauboussin/Peddireddy (Columbia 2020),
#            Mark Leonard (CSU annual letters), Aswath Damodaran (NYU).
#
# Owner Earnings = OCF - Maintenance Capex
#
# D&A has two economically distinct components:
#
#  1. Physical PP&E depreciation  ->  100% real maintenance cash cost.
#     Servers age, warehouses need upkeep, delivery trucks wear out.
#     Mauboussin (2020): actual replacement cost ~100-125% of book depreciation
#     in inflationary periods; we use 100% as a conservative base.
#
#  2. Amortisation of acquired intangibles  ->  MOSTLY non-economic.
#     The underlying assets are maintained via P&L operating expenses, not capex:
#       - Customer relationships: maintained via sales & marketing opex
#       - Technology / IP: maintained via R&D opex
#       - Brand / trademarks: don't wear out (perpetual useful life economically)
#       - Non-compete agreements: expire at zero renewal cost
#     Mark Leonard (CSU letters): adds back virtually ALL acquired intangible
#       amortisation -- VMS software customer lifetimes (~25 yrs) >> GAAP useful
#       life (8-10 yrs); assets perpetually renewed via maintenance contracts.
#     Buffett (1986): "add back most of the amortisation charges reported."
#     S&P 500 (2023): intangible amort = single largest non-GAAP add-back category.
#
# Growth capex = Total Capex - Maintenance Capex.  Deliberately NOT deducted:
# it creates incremental future cash flows, already captured by the positive
# growth rates in the 3-phase DCF / Dhandho projections.
#
# Implementation priority:
#   Level 1  separate physical depreciation + intangible amortisation available
#            -> maint = depreciation + amort * _AMORT_CASH_FACTOR[sector]
#   Level 2  only total D&A available
#            -> maint = da * _DA_BLENDED_FACTOR[sector]
#   Level 3  no D&A data at all  ->  fall back to raw OCF (flagged in output)

# What % of acquired intangible amortisation represents a genuine recurring cash cost?
# Low in all sectors because the underlying assets are maintained via OPEX, not capex.
# Sources: CSU letters (~0%), Buffett ("add back most"), Damodaran (non-economic),
#          Calcbench 2023: intangible amort is the largest single non-GAAP add-back.
_AMORT_CASH_FACTOR: dict = {
    "Technology":              0.08,  # SaaS/software acquirers: customer rel via sales opex
    "Communication Services":  0.12,  # Mix of physical infra + media/content IP
    "Consumer Cyclical":       0.15,  # Some franchise/brand value maintained via marketing
    "Consumer Defensive":      0.15,  # Brand-heavy but renewal is via marketing, not capex
    "Healthcare":              0.18,  # Pharma/device IP has partial R&D renewal cost
    "Industrials":             0.15,  # Process patents maintained via R&D opex
    "Financial Services":      0.08,  # Mostly customer-list/software amort
    "Utilities":               0.20,  # Regulatory asset rights have some renewal cost
    "Energy":                  0.15,  # Exploration licences have some renewal cost
    "Real Estate":             0.12,  # Lease intangibles
    "Basic Materials":         0.15,
    "default":                 0.15,
}

# Blended factor applied to TOTAL D&A when physical/intangible can't be separated.
# Derived from typical sector-average split between physical depreciation (100% real)
# and intangible amortisation (see _AMORT_CASH_FACTOR above), weighted by composition.
# Mauboussin (2020): software-heavy / M&A-intensive sectors have far lower real
# maintenance % than capital-intensive physical businesses.
_DA_BLENDED_FACTOR: dict = {
    # ~50% physical, ~50% intangible amort: 50%*1.0 + 50%*0.08 = 54% -> 55%
    "Technology":              0.55,
    # ~65% physical, ~35% intangible: 65%*1.0 + 35%*0.12 = 69%
    "Communication Services":  0.69,
    # ~85% physical (warehouses/vehicles/servers), ~15% intangible: 87%
    "Consumer Cyclical":       0.87,
    # ~80% physical, ~20% intangible: 83%
    "Consumer Defensive":      0.83,
    # ~60% physical equipment/facilities, ~40% pharma/device IP: 67%
    "Healthcare":              0.67,
    # ~85% physical machinery, ~15% process IP: 87%
    "Industrials":             0.87,
    # ~40% physical systems, ~60% software/customer-list amort: 45%
    "Financial Services":      0.45,
    # ~90% physical infrastructure (wires, pipes, plant): 92%
    "Utilities":               0.92,
    # ~85% physical wells/pipelines/equipment: 87%
    "Energy":                  0.87,
    # ~90% physical buildings: 91%
    "Real Estate":             0.91,
    # ~88% physical plant and mining assets: 89%
    "Basic Materials":         0.89,
    # Conservative default
    "default":                 0.70,
}


def _compute_owner_earnings(
    ocf_mn: float,
    da_mn: float | None,
    total_capex_mn: float | None,
    fcf_mn: float,
    sector: str = "",
    depreciation_mn: float | None = None,
    amort_intangibles_mn: float | None = None,
) -> dict:
    """
    Derive Owner Earnings = OCF - Maintenance Capex.

    Priority:
      1. Separate depreciation + intangible amortisation available -> two-component method
      2. Total D&A only                                            -> sector-blended factor
      3. Neither available                                         -> raw OCF with warning

    Returns dict: owner_earnings_mn, maint_capex_mn, growth_capex_mn, method.
    """
    maint: float | None = None
    method: str = ""

    if depreciation_mn and amort_intangibles_mn:
        # Level 1: most accurate -- both physical depreciation and intangible amort known
        amort_factor = _AMORT_CASH_FACTOR.get(sector, _AMORT_CASH_FACTOR["default"])
        maint  = depreciation_mn + amort_intangibles_mn * amort_factor
        method = (
            f"Depr {_mn(depreciation_mn)} + "
            f"Intangible Amort {_mn(amort_intangibles_mn)} x {amort_factor:.0%} "
            f"[{sector or 'default'} sector]"
        )

    elif depreciation_mn and depreciation_mn > 0:
        # Level 1.5: only physical depreciation known; use it directly.
        # D&A = depreciation means yfinance found the separate "Depreciation" row,
        # implying intangible amortisation is negligible or already included.
        maint  = depreciation_mn
        method = f"Physical depreciation {_mn(depreciation_mn)} (100% real maintenance cost)"

    elif da_mn and da_mn > 0:
        # Level 2: sector-blended factor on total D&A
        factor = _DA_BLENDED_FACTOR.get(sector, _DA_BLENDED_FACTOR["default"])
        amort_real_pct = int(_AMORT_CASH_FACTOR.get(sector, 0.15) * 100)
        method = (
            f"D&A {_mn(da_mn)} x {factor:.0%} "
            f"[{sector or 'default'}: physical depr 100% real, "
            f"intangible amort ~{amort_real_pct}% real]"
        )
        maint = da_mn * factor

    if maint is not None:
        # Cap: maintenance cannot exceed total capex actually spent
        if total_capex_mn and total_capex_mn > 0:
            maint = min(maint, total_capex_mn)
        oe     = ocf_mn - maint
        growth = (total_capex_mn - maint) if total_capex_mn else None
        # Floor: owner earnings >= reported FCF (most conservative real bound)
        oe = max(oe, fcf_mn)
        return {
            "owner_earnings_mn": oe,
            "maint_capex_mn":    maint,
            "growth_capex_mn":   growth,
            "method":            method,
        }

    # Level 3: no D&A data
    return {
        "owner_earnings_mn": ocf_mn,
        "maint_capex_mn":    None,
        "growth_capex_mn":   None,
        "method":            "OCF (D&A unavailable - maintenance capex not deducted)",
    }

# -- NOPAT-based Owner Earnings for financial / fintech companies ---------------
#
# Problem: payment processors, fintechs, and banks report OCF that is severely
# distorted by changes in customer balances (float).
#
#   Example — Wise FY2025:
#     Reported OCF    = £4.5B
#     Operating Income = £558M
#     Gap (£3.9B)     = customer deposits flowing through working capital —
#                       these funds belong to customers, not shareholders.
#
# Solution: start from Operating Income (EBIT), which is computed ABOVE the
# working capital / float line.  Float changes never reach Operating Income;
# only fee revenues and FX-spread income minus operating costs are captured.
#
# Formula (Damodaran FCFF / McKinsey approach):
#   NOPAT               = Operating Income × (1 − effective tax rate)
#   + D&A (maintenance) ← add back non-cash charge already deducted in EBIT
#   − Maintenance Capex ← subtract real cash replacement cost
#   = Adjusted Owner Earnings
#
# For asset-light fintechs: D&A ≈ Maintenance Capex → Adj OE ≈ NOPAT
#
# Net cash treatment: balance sheet cash for payment companies includes
# segregated customer funds (asset offset by customer balance liabilities).
# We set net_cash = 0 conservatively so float does not inflate IV.
#
# References: Damodaran (FCFF for financial firms, NYU), Koller/Goedhart/Wessels
# (McKinsey Valuation 7e ch.9), Penman (Financial Statement Analysis).


def _compute_nopat_owner_earnings(
    op_income_mn: float,
    tax_rate: float,
    da_mn: float | None,
    total_capex_mn: float | None,
    sector: str = "",
    depreciation_mn: float | None = None,
    amort_intangibles_mn: float | None = None,
) -> dict:
    """
    Float-adjusted Owner Earnings for financial/fintech companies.
    Returns: nopat_owner_earnings_mn, nopat_mn, tax_rate, maint_capex_mn, method.
    """
    nopat = op_income_mn * (1 - tax_rate)

    # Estimate maintenance D&A — same 3-tier priority as _compute_owner_earnings
    maint_da: float | None = None
    da_method = ""

    if depreciation_mn and amort_intangibles_mn:
        amort_factor = _AMORT_CASH_FACTOR.get(sector, _AMORT_CASH_FACTOR["default"])
        maint_da  = depreciation_mn + amort_intangibles_mn * amort_factor
        da_method = (
            f"Depr {_mn(depreciation_mn)} + "
            f"Intangible Amort {_mn(amort_intangibles_mn)} × {amort_factor:.0%} "
            f"[{sector or 'default'} sector]"
        )
    elif depreciation_mn and depreciation_mn > 0:
        maint_da  = depreciation_mn
        da_method = f"Physical depreciation {_mn(depreciation_mn)} (100% real)"
    elif da_mn and da_mn > 0:
        factor    = _DA_BLENDED_FACTOR.get(sector, _DA_BLENDED_FACTOR["default"])
        maint_da  = da_mn * factor
        da_method = f"D&A {_mn(da_mn)} × {factor:.0%} [{sector or 'default'} blended]"

    if maint_da is not None:
        # Actual maintenance capex is the lesser of estimated D&A and reported capex
        maint_capex = maint_da
        if total_capex_mn and total_capex_mn > 0:
            maint_capex = min(maint_da, total_capex_mn)
        # NOPAT + D&A (add back non-cash) − Maintenance Capex (real cash cost)
        # Both sides are roughly equal for asset-light companies → ≈ NOPAT
        oe     = nopat + maint_da - maint_capex
        method = (
            f"NOPAT {_mn(nopat)} "
            f"(OpIncome {_mn(op_income_mn)} × {1 - tax_rate:.0%} after-tax, "
            f"tax rate {tax_rate:.0%}) "
            f"+ D&A {_mn(maint_da)} − Maint. Capex {_mn(maint_capex)} "
            f"[{da_method}]"
        )
    else:
        oe          = nopat
        maint_capex = None
        method      = (
            f"NOPAT {_mn(nopat)} "
            f"(OpIncome {_mn(op_income_mn)} × {1 - tax_rate:.0%} after-tax, "
            f"tax rate {tax_rate:.0%}) "
            f"[D&A unavailable — no maintenance capex adjustment]"
        )

    return {
        "nopat_owner_earnings_mn": oe,
        "nopat_mn":                nopat,
        "tax_rate":                tax_rate,
        "maint_da_mn":             maint_da,
        "maint_capex_mn":          maint_capex,
        "method":                  method,
    }


# -- Cash flow projection -------------------------------------------------------

def _project_fcf(base_mn: float, phases: list) -> list[float]:
    """Return list of FCFs for years 1-10 applying 3-phase growth rates."""
    fcfs, curr = [], base_mn
    for yr in range(1, 11):
        for s, e, r in phases:
            if s <= yr <= e:
                curr = curr * (1 + r)
                break
        fcfs.append(curr)
    return fcfs


# -- Model 1: Dhandho -----------------------------------------------------------

def _dhandho(base_mn: float, net_cash_mn: float, phases: list) -> dict:
    """
    IV = Σ PV(FCF_t, t=1..10)
       + PV of terminal value  (zero-growth perpetuity: FCF_10 / r)
       + net cash              (already at present value)
    """
    fcfs   = _project_fcf(base_mn, phases)
    rows, pv_sum = [], 0.0
    for i, fcf in enumerate(fcfs, 1):
        pv = fcf / (1 + DISCOUNT_RATE) ** i
        rows.append({"year": i, "fcf": fcf, "pv": pv})
        pv_sum += pv
    tv    = fcfs[-1] / DISCOUNT_RATE                   # perpetuity at 0% growth
    pv_tv = tv / (1 + DISCOUNT_RATE) ** 10
    iv    = pv_sum + pv_tv + net_cash_mn
    return {"rows": rows, "pv_sum": pv_sum, "pv_tv": pv_tv,
            "net_cash": net_cash_mn, "iv": iv}


# -- Model 2: Ben Graham --------------------------------------------------------

def _graham_growth_rates(rev_cagr: float | None,
                         ni_cagr_5yr: float | None) -> tuple[float, float]:
    """
    Derive lower/higher growth rates in percentage points for the Graham formula.
    Uses NI CAGR if available, else revenue CAGR.
    Lower = 50% of base CAGR.  Higher = 80% of base CAGR.
    Clamped to [-10, 25] pct points.
    """
    base = (ni_cagr_5yr if ni_cagr_5yr is not None else rev_cagr or 0.08) * 100
    base = max(-10.0, min(30.0, base))
    lower  = round(base * 0.5, 1)
    higher = round(base * 0.8, 1)
    return lower, higher


def _ben_graham(avg_5yr_ni_mn: float, growth_pct: float) -> float:
    """
    Graham original formula applied to aggregate net income.
    Value (Mn) = Avg_5yr_NI_Mn × (8.5 + 2 × G)
    where G is in percentage points  (e.g. 9.6, not 0.096).
    Result can be negative for negative or very low G.
    """
    return avg_5yr_ni_mn * (GRAHAM_PE_ZERO + 2 * growth_pct)


# -- Model 3: DCF ---------------------------------------------------------------

def _dcf(base_mn: float, net_cash_mn: float, phases: list) -> dict:
    """
    Standard DCF with Gordon Growth Model terminal value.
    TV = FCF_10 × (1 + g) / (r − g)
    IV = Σ PV(FCF_t) + PV(TV) + net cash
    """
    fcfs   = _project_fcf(base_mn, phases)
    rows, pv_sum = [], 0.0
    for i, fcf in enumerate(fcfs, 1):
        pv = fcf / (1 + DISCOUNT_RATE) ** i
        rows.append({"year": i, "fcf": fcf, "pv": pv})
        pv_sum += pv
    tv    = fcfs[-1] * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    pv_tv = tv / (1 + DISCOUNT_RATE) ** 10
    iv    = pv_sum + pv_tv + net_cash_mn
    return {"rows": rows, "pv_sum": pv_sum, "pv_tv": pv_tv,
            "net_cash": net_cash_mn, "iv": iv}


# -- Model 4: Expected Returns --------------------------------------------------

def _expected_returns(ni_mn: float | None, ni_cagr: float | None,
                      current_pe: float | None) -> dict | None:
    """
    1. Project net income 10 years forward at NI CAGR
    2. Apply exit P/E = max(current_P/E × 0.5, 15x)
    3. Discount implied market cap back at DISCOUNT_RATE
    """
    if not ni_mn or not ni_cagr or not current_pe:
        return None
    projected_ni  = ni_mn * (1 + ni_cagr) ** 10
    exit_pe       = max(current_pe * 0.5, 15.0)
    projected_cap = projected_ni * exit_pe
    iv            = projected_cap / (1 + DISCOUNT_RATE) ** 10
    return {
        "ni_cagr_pct":   round(ni_cagr * 100, 2),
        "projected_ni":  projected_ni,
        "exit_pe":       exit_pe,
        "projected_cap": projected_cap,
        "iv":            iv,
    }


# -- Formatters -----------------------------------------------------------------

def _mn(v: float | None) -> str:
    """Format a value in millions, auto-scaling to B or T."""
    if v is None:
        return "N/A"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}{v / 1_000_000:,.2f}T"
    if v >= 1_000:
        return f"{sign}{v / 1_000:,.1f}B"
    return f"{sign}{v:,.0f}M"


def _price(iv_mn: float | None, shares: float | None) -> str:
    """Compute implied share price from aggregate IV in millions."""
    if iv_mn is None or not shares or shares == 0:
        return "N/A"
    p = (iv_mn * 1e6) / shares
    return f"{p:,.0f}" if p >= 0 else f"({abs(p):,.0f})"


def _prem(iv_mn: float | None, mktcap_mn: float | None) -> str:
    if not iv_mn or iv_mn <= 0 or not mktcap_mn or mktcap_mn <= 0:
        return "N/A"
    diff = (mktcap_mn - iv_mn) / iv_mn * 100
    return f"{abs(diff):.0f}% {'premium' if diff > 0 else 'discount'}"


# -- Printer --------------------------------------------------------------------

def _phases_str(phases: list) -> str:
    return "  |  ".join(f"Yr {s}-{e}: {int(r*100)}%" for s, e, r in phases)


def _print_dhandho_block(label: str, phases: list, res: dict, shares: float | None,
                         cf_label: str = "FCF") -> None:
    print(f"\n  {label}  ({_phases_str(phases)})")
    print(f"  {'Year':<8} {cf_label+' (Mn)':>12}  {'PV of CF (Mn)':>15}")
    print(f"  {'0 Net Cash':<8} {'':>12}  {res['net_cash']:>15,.0f}")
    for row in res["rows"]:
        print(f"  {row['year']:<8} {row['fcf']:>12,.0f}  {row['pv']:>15,.0f}")
    print(f"  {'':-<38}")
    print(f"  {'Sum PV CFs':<24}  {res['pv_sum']:>15,.0f}")
    print(f"  {'PV Terminal Value':<24}  {res['pv_tv']:>15,.0f}")
    print(f"  {'Net Cash':<24}  {res['net_cash']:>15,.0f}")
    print(f"  {'IV Total':<24}  {res['iv']:>15,.0f}")
    print(f"  -> IV: {_mn(res['iv'])}  |  Per Share: {_price(res['iv'], shares)}")


def _print_dcf_block(res: dict, phases: list, shares: float | None,
                     cf_label: str = "FCF") -> None:
    print(f"  Growth: {_phases_str(phases)}  |  Terminal: {int(TERMINAL_GROWTH*100)}%")
    print(f"  {'Year':<8} {cf_label+' (Mn)':>12}  {'PV of CF (Mn)':>15}")
    for row in res["rows"]:
        print(f"  {row['year']:<8} {row['fcf']:>12,.0f}  {row['pv']:>15,.0f}")
    print(f"  {'':-<38}")
    print(f"  {'Sum PV CFs':<24}  {res['pv_sum']:>15,.0f}")
    print(f"  {'PV Terminal Value':<24}  {res['pv_tv']:>15,.0f}")
    print(f"  {'Net Cash':<24}  {res['net_cash']:>15,.0f}")
    print(f"  {'IV Total':<24}  {res['iv']:>15,.0f}")
    print(f"  -> IV: {_mn(res['iv'])}  |  Per Share: {_price(res['iv'], shares)}")


def _print_valuation(profile: dict, r: dict) -> None:
    W      = 62
    shares = r.get("shares")
    mktcap = r.get("mktcap_mn")
    dh     = r.get("dhandho", {})
    gm     = r.get("graham", {})
    dc     = r.get("dcf", {})
    er     = r.get("exp_returns")

    cf_label   = r.get("base_label", "FCF")
    base_mn    = r.get("base_mn")
    fcf_mn_ref = r.get("fcf_mn")
    is_fin     = r.get("is_financial", False)
    is_ch      = r.get("is_capex_heavy", False)

    print(f"\n{'=' * W}")
    print("  ATLAS: INTRINSIC VALUE ANALYSIS")
    print(f"{'=' * W}")
    print(f"  Company:         {profile.get('name', 'N/A')}")
    if is_fin:
        nopat_method = r.get("nopat_method", "")
        op_income_mn = r.get("op_income_mn")
        nopat_mn     = r.get("nopat_mn")
        ocf_mn_ref   = r.get("ocf_mn")
        print(f"  Base {cf_label}:   {_mn(base_mn)}  |  Net Cash: {_mn(r.get('net_cash_mn'))} "
              f"(customer float zeroed)")
        print(f"  Derivation:      Op. Income {_mn(op_income_mn)} → "
              f"NOPAT {_mn(nopat_mn)} (after-tax)")
        print(f"  [OCF {_mn(ocf_mn_ref)} excluded — distorted by customer float/deposits]")
        if nopat_method:
            print(f"  Method:          {nopat_method}")
    elif is_ch:
        oe_method    = r.get("oe_method", "")
        maint_mn     = r.get("maint_capex_mn")
        growth_mn    = r.get("growth_capex_mn")
        ocf_mn_ref   = r.get("ocf_mn")
        print(f"  Base {cf_label}:  {_mn(base_mn)}  |  Net Cash: {_mn(r.get('net_cash_mn'))}")
        print(f"  Derivation:      OCF {_mn(ocf_mn_ref)} - Maint. Capex {_mn(maint_mn)}"
              f" = Owner Earnings {_mn(base_mn)}")
        maint_method = r.get("oe_method", "")
        if maint_method:
            print(f"  Maint. method:   {maint_method}")
        if growth_mn is not None:
            print(f"  Growth Capex:    {_mn(growth_mn)} excluded"
                  f" (creates future cash flows, captured in growth rates)")
        if not maint_mn:
            print(f"  [D&A unavailable — using raw OCF; maintenance capex not deducted]")
        print(f"  [FCF {_mn(fcf_mn_ref)} suppressed by growth capex reinvestment cycle]")
    else:
        print(f"  Base {cf_label}:        {_mn(base_mn)}  |  Net Cash: {_mn(r.get('net_cash_mn'))}")
    print(f"  Discount Rate:   {int(DISCOUNT_RATE*100)}%  |  Terminal Growth (DCF): {int(TERMINAL_GROWTH*100)}%")
    print(f"  Current Mkt Cap: {_mn(mktcap)}  |  Share Price: {profile.get('current_price', 'N/A')}")

    # -- Dhandho --
    print(f"\n  {'-' * (W-2)}")
    print("  METHOD 1: DHANDHO")
    print(f"  {'-' * (W-2)}")
    if dh:
        _print_dhandho_block("Lower Range",  PHASES_LOWER,  dh["lower"],  shares, cf_label)
        _print_dhandho_block("Higher Range", PHASES_HIGHER, dh["higher"], shares, cf_label)

    # -- Ben Graham --
    print(f"\n  {'-' * (W-2)}")
    print("  METHOD 2: BEN GRAHAM  (original: Value = Avg_NI x (8.5 + 2G))")
    print(f"  {'-' * (W-2)}")
    avg_ni = gm.get("avg_5yr_ni_mn")
    lo_r, hi_r = gm.get("lo_rate", "N/A"), gm.get("hi_rate", "N/A")
    glo, ghi   = gm.get("lower"), gm.get("higher")
    print(f"  Avg 5-Yr Net Income: {_mn(avg_ni)}")
    print(f"  Lower  (G = {lo_r}%): IV = {_mn(glo)}  |  Per Share: {_price(glo, shares)}")
    print(f"  Higher (G = {hi_r}%): IV = {_mn(ghi)}  |  Per Share: {_price(ghi, shares)}")
    if glo is not None and glo < 0:
        print("  [Note: negative IV signals company fails Graham test at this growth rate]")

    # -- DCF --
    print(f"\n  {'-' * (W-2)}")
    print("  METHOD 3: DISCOUNTED CASH FLOW")
    print(f"  {'-' * (W-2)}")
    if dc:
        _print_dcf_block(dc, PHASES_LOWER, shares, cf_label)

    # -- Expected Returns --
    print(f"\n  {'-' * (W-2)}")
    print("  METHOD 4: EXPECTED RETURNS MODEL")
    print(f"  {'-' * (W-2)}")
    if er:
        print(f"  NI CAGR (5yr):       {er['ni_cagr_pct']}%")
        print(f"  Projected NI (10yr): {_mn(er['projected_ni'])}")
        print(f"  Exit P/E:            {er['exit_pe']:.1f}x  (50% of current P/E, min 15x)")
        print(f"  Projected Mkt Cap:   {_mn(er['projected_cap'])}")
        print(f"  Discounted IV:       {_mn(er['iv'])}  |  Per Share: {_price(er['iv'], shares)}")
    else:
        print("  N/A (insufficient NI or P/E data)")

    # -- Summary --
    print(f"\n  {'=' * (W-2)}")
    print("  INTRINSIC VALUE SUMMARY")
    print(f"  {'=' * (W-2)}")
    hdr = f"  {'Method':<22}  {'IV Lower':>12}  {'IV Higher':>12}  {'Price Lo / Hi':>16}"
    print(hdr)
    print(f"  {'-' * (W-2)}")

    def _row(label, lo, hi):
        lo_s  = _mn(lo) if lo is not None else "N/A"
        hi_s  = _mn(hi) if hi is not None else "  -"
        pr_lo = _price(lo, shares) if lo is not None else "N/A"
        pr_hi = _price(hi, shares) if hi is not None else "  -"
        print(f"  {label:<22}  {lo_s:>12}  {hi_s:>12}  {pr_lo:>8} / {pr_hi:<8}")

    _row("Dhandho",          dh.get("lower", {}).get("iv"),  dh.get("higher", {}).get("iv"))
    _row("Ben Graham",       glo, ghi)
    _row("DCF",              dc.get("iv") if dc else None, None)
    _row("Expected Returns", er.get("iv") if er else None, None)

    print(f"  {'-' * (W-2)}")
    print(f"  Current Market Cap:  {_mn(mktcap)}")
    print(f"  Current Share Price: {profile.get('current_price', 'N/A')}")
    print()

    # Overall assessment — exclude negative Graham values from range
    dh_lo = dh.get("lower", {}).get("iv")
    dh_hi = dh.get("higher", {}).get("iv")
    dc_iv = dc.get("iv") if dc else None
    er_iv = er.get("iv") if er else None
    valid = [v for v in [dh_lo, dh_hi, dc_iv, er_iv] if v is not None and v > 0]
    if valid and mktcap:
        iv_low, iv_high = min(valid), max(valid)
        mid = (iv_low + iv_high) / 2
        prem = (mktcap - mid) / mid * 100
        verdict = "OVERVALUED" if prem > 20 else ("UNDERVALUED" if prem < -20 else "FAIRLY VALUED")
        print(f"  IV Range (ex-Graham): {_mn(iv_low)}  -  {_mn(iv_high)}")
        print(f"  vs Current Mkt Cap:   {abs(prem):.0f}% {'premium' if prem > 0 else 'discount'} -> {verdict}")

    print(f"\n{'=' * W}\n")


# -- Entry point ----------------------------------------------------------------

def run(profile: dict) -> dict:
    """
    Compute intrinsic value using 4 models.
    Returns a result dict; always runs regardless of BMP verdict.
    """
    ticker   = profile.get("ticker", "")
    company  = profile.get("name") or ticker
    fcf_abs  = profile.get("free_cash_flow")
    ocf_abs  = profile.get("operating_cash_flow")
    mktcap   = profile.get("market_cap")
    pe       = profile.get("pe_ratio")
    rev_cagr = profile.get("revenue_cagr")

    # Detect financial company (OCF/FCF distorted by customer float or deposits)
    is_financial = _is_financial_company(profile)

    # Detect capex-heavy reinvestment cycle (non-financial only)
    is_capex_heavy = (not is_financial) and _capex_heavy_mode(fcf_abs, ocf_abs)

    if not (fcf_abs and fcf_abs > 0) and not (ocf_abs and ocf_abs > 0):
        op_income_abs = profile.get("operating_income")
        if not (is_financial and op_income_abs and op_income_abs > 0):
            print(f"\n  [Valuation] FCF/OCF not available for {company} -- skipping.")
            return {"available": False}

    print(f"\n  [Valuation] Fetching supplementary data for {company}...")
    extra = _fetch_extra(ticker)

    fcf_mn    = fcf_abs / 1e6 if fcf_abs else None
    ocf_mn    = ocf_abs / 1e6 if ocf_abs else None
    mktcap_mn = mktcap / 1e6 if mktcap else None
    # Financial companies: zero out net cash — balance sheet cash includes segregated
    # customer funds that are offset by customer balance liabilities, not shareholder value.
    net_cash_mn = 0.0 if is_financial else (extra.get("net_cash_mn") or 0.0)
    shares      = extra.get("shares_outstanding")
    ni_mn       = extra.get("ni_latest_mn")
    avg_ni_mn   = extra.get("avg_5yr_ni_mn")
    ni_cagr     = extra.get("ni_cagr_5yr")

    # Path 1: Financial company — use NOPAT-based Owner Earnings to strip out float distortion
    nopat_info: dict = {}
    oe_info: dict = {}

    if is_financial:
        op_income_abs = profile.get("operating_income")
        if op_income_abs and op_income_abs > 0:
            op_income_mn = op_income_abs / 1e6
            tax_rate     = _effective_tax_rate(extra)
            nopat_info   = _compute_nopat_owner_earnings(
                op_income_mn=op_income_mn,
                tax_rate=tax_rate,
                da_mn=extra.get("da_mn"),
                total_capex_mn=extra.get("total_capex_mn"),
                sector=profile.get("sector", ""),
                depreciation_mn=extra.get("depreciation_mn"),
                amort_intangibles_mn=extra.get("amort_intangibles_mn"),
            )
            base_mn    = nopat_info["nopat_owner_earnings_mn"]
            base_label = "NOPAT OE"
            print(f"\n  [Valuation] Financial company detected — OCF {_mn(ocf_mn)} "
                  f"distorted by customer float.")
            print(f"  [Valuation] Using NOPAT-based Owner Earnings: {nopat_info['method']}")
        else:
            print(f"\n  [Valuation] Financial company — Operating Income unavailable; "
                  f"falling back to OCF (results will be distorted).")
            base_mn    = ocf_mn
            base_label = "OCF"

    # Path 2: Capex-heavy reinvestment cycle — derive Owner Earnings from OCF
    elif is_capex_heavy and ocf_mn:
        oe_info = _compute_owner_earnings(
            ocf_mn=ocf_mn,
            da_mn=extra.get("da_mn"),
            total_capex_mn=extra.get("total_capex_mn"),
            fcf_mn=fcf_mn or 0.0,
            sector=profile.get("sector", ""),
            depreciation_mn=extra.get("depreciation_mn"),
            amort_intangibles_mn=extra.get("amort_intangibles_mn"),
        )
        base_mn    = oe_info["owner_earnings_mn"]
        base_label = "Owner Earnings"
        print(f"\n  [Valuation] Capex-heavy mode detected "
              f"(FCF {_mn(fcf_mn)} = {fcf_abs/ocf_abs*100:.0f}% of OCF {_mn(ocf_mn)}).")
        print(f"  [Valuation] Maint. capex: {oe_info['method']}")
        print(f"  [Valuation] OCF {_mn(ocf_mn)} - Maint. Capex {_mn(oe_info.get('maint_capex_mn'))}"
              f" = Owner Earnings {_mn(base_mn)}")
    elif fcf_abs and fcf_abs > 0:
        base_mn    = fcf_mn
        base_label = "FCF"
    else:
        # FCF zero/negative, no capex-heavy signal — use OCF as last resort
        base_mn    = ocf_mn
        base_label = "OCF"

    print("  [Valuation] Computing Dhandho / Ben Graham / DCF / Expected Returns...")

    dh_lower  = _dhandho(base_mn, net_cash_mn, PHASES_LOWER)
    dh_higher = _dhandho(base_mn, net_cash_mn, PHASES_HIGHER)

    lo_g, hi_g    = _graham_growth_rates(rev_cagr, ni_cagr)
    graham_lower  = _ben_graham(avg_ni_mn, lo_g)  if avg_ni_mn else None
    graham_higher = _ben_graham(avg_ni_mn, hi_g)  if avg_ni_mn else None

    dcf_result  = _dcf(base_mn, net_cash_mn, PHASES_LOWER)
    exp_returns = _expected_returns(ni_mn, ni_cagr, pe)

    result = {
        "available":        True,
        "base_mn":          base_mn,
        "base_label":       base_label,
        "is_financial":     is_financial,
        "is_capex_heavy":   is_capex_heavy,
        "fcf_mn":           fcf_mn,
        "ocf_mn":           ocf_mn,
        "op_income_mn":     profile.get("operating_income", 0) / 1e6 if profile.get("operating_income") else None,
        "nopat_mn":         nopat_info.get("nopat_mn"),
        "nopat_method":     nopat_info.get("method", ""),
        "maint_capex_mn":   nopat_info.get("maint_capex_mn") or oe_info.get("maint_capex_mn"),
        "growth_capex_mn":  oe_info.get("growth_capex_mn"),
        "oe_method":        oe_info.get("method", ""),
        "net_cash_mn":      net_cash_mn,
        "shares":           shares,
        "mktcap_mn":        mktcap_mn,
        "dhandho":          {"lower": dh_lower, "higher": dh_higher},
        "graham":           {
            "lower":         graham_lower,
            "higher":        graham_higher,
            "lo_rate":       lo_g,
            "hi_rate":       hi_g,
            "avg_5yr_ni_mn": avg_ni_mn,
        },
        "dcf":              dcf_result,
        "exp_returns":      exp_returns,
        "phases_lower":     PHASES_LOWER,
        "phases_higher":    PHASES_HIGHER,
    }

    _print_valuation(profile, result)
    return result
