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


# -- yfinance helpers -----------------------------------------------------------

def _safe_float(val):
    try:
        return None if val is None or pd.isna(val) else float(val)
    except Exception:
        return None


def _fetch_extra(ticker: str) -> dict:
    """Fetch shares outstanding, net cash, and net income history from yfinance."""
    out = {
        "shares_outstanding": None,
        "net_cash_mn":        None,
        "ni_latest_mn":       None,
        "avg_5yr_ni_mn":      None,
        "ni_cagr_5yr":        None,
    }
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        fin  = t.financials    # rows = metrics, cols = dates newest-first
        bs   = t.balance_sheet

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

    except Exception:
        pass
    return out


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
    is_ch      = r.get("is_capex_heavy", False)

    print(f"\n{'=' * W}")
    print("  ATLAS: INTRINSIC VALUE ANALYSIS")
    print(f"{'=' * W}")
    print(f"  Company:         {profile.get('name', 'N/A')}")
    if is_ch:
        print(f"  Base {cf_label}:        {_mn(base_mn)}  |  Net Cash: {_mn(r.get('net_cash_mn'))}")
        print(f"  [Capex-heavy mode: FCF ({_mn(fcf_mn_ref)}) < 40% of OCF — using OCF as earnings-power base]")
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

    # Detect capex-heavy reinvestment cycle — switch base to OCF
    is_capex_heavy = _capex_heavy_mode(fcf_abs, ocf_abs)

    if is_capex_heavy:
        base_abs   = ocf_abs
        base_label = "OCF"
    elif fcf_abs and fcf_abs > 0:
        base_abs   = fcf_abs
        base_label = "FCF"
    elif ocf_abs and ocf_abs > 0:
        # FCF zero/negative but OCF available — use OCF as fallback
        base_abs   = ocf_abs
        base_label = "OCF"
        is_capex_heavy = True
    else:
        print(f"\n  [Valuation] FCF/OCF not available for {company} -- skipping.")
        return {"available": False}

    if is_capex_heavy:
        print(f"\n  [Valuation] Capex-heavy mode: FCF ({fcf_abs/1e9:.1f}B) < 40% of OCF "
              f"({ocf_abs/1e9:.1f}B) — using OCF as earnings-power base.")

    print(f"\n  [Valuation] Fetching supplementary data for {company}...")
    extra = _fetch_extra(ticker)

    base_mn     = base_abs / 1e6
    fcf_mn      = fcf_abs / 1e6 if fcf_abs else None
    ocf_mn      = ocf_abs / 1e6 if ocf_abs else None
    mktcap_mn   = mktcap / 1e6 if mktcap else None
    net_cash_mn = extra.get("net_cash_mn") or 0.0
    shares      = extra.get("shares_outstanding")
    ni_mn       = extra.get("ni_latest_mn")
    avg_ni_mn   = extra.get("avg_5yr_ni_mn")
    ni_cagr     = extra.get("ni_cagr_5yr")

    print("  [Valuation] Computing Dhandho / Ben Graham / DCF / Expected Returns...")

    dh_lower  = _dhandho(base_mn, net_cash_mn, PHASES_LOWER)
    dh_higher = _dhandho(base_mn, net_cash_mn, PHASES_HIGHER)

    lo_g, hi_g    = _graham_growth_rates(rev_cagr, ni_cagr)
    graham_lower  = _ben_graham(avg_ni_mn, lo_g)  if avg_ni_mn else None
    graham_higher = _ben_graham(avg_ni_mn, hi_g)  if avg_ni_mn else None

    dcf_result  = _dcf(base_mn, net_cash_mn, PHASES_LOWER)
    exp_returns = _expected_returns(ni_mn, ni_cagr, pe)

    result = {
        "available":       True,
        "base_mn":         base_mn,
        "base_label":      base_label,
        "is_capex_heavy":  is_capex_heavy,
        "fcf_mn":          fcf_mn,
        "ocf_mn":          ocf_mn,
        "net_cash_mn":     net_cash_mn,
        "shares":          shares,
        "mktcap_mn":       mktcap_mn,
        "dhandho":         {"lower": dh_lower, "higher": dh_higher},
        "graham":          {
            "lower":         graham_lower,
            "higher":        graham_higher,
            "lo_rate":       lo_g,
            "hi_rate":       hi_g,
            "avg_5yr_ni_mn": avg_ni_mn,
        },
        "dcf":             dcf_result,
        "exp_returns":     exp_returns,
        "phases_lower":    PHASES_LOWER,
        "phases_higher":   PHASES_HIGHER,
    }

    _print_valuation(profile, result)
    return result
