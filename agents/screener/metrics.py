# Derive screener metrics from a raw yfinance payload.
#
# All money is converted to USD so thresholds work across regions. Ratios are
# fractions (0.15 = 15%). Definitions match the single-company pipeline:
#   - ROIC/ROCE: same formula and tax clamp as discovery._roce_roic_yfinance
#   - OEY: agents.context.compute_oey (Seessel EV basis + growth-adjusted hurdle)
#   - quality_score / feroldi_fin_score: the deterministic (no-LLM) items of
#     quality_screen and feroldi, run on a lite profile, as % of available points

from agents.context import compute_oey
from agents.screener.fetch import MINOR_UNITS

# name -> description. Used to validate criteria and for --list-metrics.
METRICS = {
    "market_cap_usd":          "Market capitalisation, USD",
    "enterprise_value_usd":    "Market cap + debt - cash, USD",
    "revenue_usd":             "Latest annual revenue, USD",
    "revenue_cagr":            "Annual revenue CAGR over available history (usually 3y)",
    "revenue_growth_1y":       "Latest annual revenue growth",
    "revenue_growth_q":        "Latest quarter revenue growth, YoY",
    "gross_margin":            "Latest annual gross margin",
    "operating_margin":        "Latest annual operating margin",
    "operating_margin_change": "Operating margin, latest minus oldest year (e.g. 0.03 = +3pp)",
    "net_margin":              "Latest annual net margin",
    "fcf_margin":              "Free cash flow / revenue, latest year",
    "fcf_positive_years":      "Number of years with positive FCF",
    "fcf_yield":               "FCF / market cap",
    "ocf_to_revenue":          "Operating cash flow / revenue",
    "capex_to_revenue":        "Capex / revenue",
    "roic":                    "Return on invested capital, latest year",
    "roic_avg":                "Average ROIC over available history",
    "roic_min":                "Lowest ROIC over available history",
    "roce_avg":                "Average ROCE over available history",
    "roe":                     "Return on equity (Yahoo, TTM)",
    "net_cash_usd":            "Cash - debt, USD (positive = net cash)",
    "net_cash_to_mcap":        "Net cash / market cap",
    "net_debt_to_ebitda":      "(Debt - cash) / EBITDA (negative = net cash)",
    "pe":                      "Trailing P/E",
    "forward_pe":              "Forward P/E",
    "ps":                      "Price / sales (market cap / latest annual revenue)",
    "ev_to_ebit":              "EV / operating income",
    "ev_to_sales":             "EV / revenue",
    "peg":                     "P/E divided by EPS CAGR (in %)",
    "eps_cagr":                "Diluted EPS CAGR over available history",
    "share_dilution":          "Diluted share count CAGR (positive = dilution)",
    "oey":                     "Seessel operating earnings yield on EV (normalised where applicable)",
    "oey_reported":            "Reported operating earnings yield on EV",
    "oey_hurdle":              "OEY hurdle for this company (3.5% elite compounder, else 5%)",
    "oey_passes":              "True if oey >= oey_hurdle (no Atlas price veto)",
    "insider_pct":             "Share of stock held by insiders",
    "week52_change":           "52-week price change",
    "beta":                    "Beta",
    "quality_score":           "Atlas Quality Screen quantitative + valuation points (0-1)",
    "feroldi_fin_score":       "Atlas Feroldi financial items (0-1)",
    "sector":                  "Yahoo sector (text)",
    "industry":                "Yahoo industry (text)",
    "country":                 "Country (text)",
}


def _div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _cagr(newest_first: list) -> float | None:
    vals = [v for v in newest_first if v is not None]
    if len(vals) < 2:
        return None
    newest, oldest = vals[0], vals[-1]
    if oldest <= 0 or newest <= 0:
        return None
    return (newest / oldest) ** (1 / (len(vals) - 1)) - 1


def _trend(newest: float, oldest: float) -> str:
    """Same 2pp tolerance as discovery._trend."""
    diff = newest - oldest
    return "improving" if diff > 0.02 else "declining" if diff < -0.02 else "stable"


def _market_cap(info: dict) -> float | None:
    """Market cap in major currency units. Yahoo quotes LSE prices in pence,
    so cross-check against shares x price and fix a 100x mismatch."""
    mcap = info.get("marketCap")
    shares = info.get("sharesOutstanding")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    divisor = MINOR_UNITS.get(info.get("currency") or "", (None, 1))[1]
    computed = shares * price / divisor if shares and price else None
    if mcap and computed:
        ratio = mcap / computed
        if 50 < ratio < 200:
            mcap /= 100
    return mcap or computed


def _roic_series(annual: list) -> tuple[list, list]:
    roic, roce = [], []
    for r in annual:
        ebit = r.get("operating_income")
        if ebit is None:
            continue
        tax_rate = 0.25
        if r.get("tax") is not None and r.get("pretax") and r["pretax"] > 0:
            tax_rate = max(0.10, min(0.40, abs(r["tax"]) / r["pretax"]))
        if r.get("total_assets") and r.get("current_liabilities") is not None:
            roce.append(_div(ebit, r["total_assets"] - r["current_liabilities"]))
        if r.get("equity") is not None and r.get("total_debt") is not None:
            invested = r["equity"] + r["total_debt"] - (r.get("cash") or 0)
            roic.append(_div(ebit * (1 - tax_rate), invested) if invested > 0 else None)
    return [v for v in roic if v is not None], [v for v in roce if v is not None]


def _points_pct(items: list[dict]) -> float | None:
    avail = [i for i in items if i.get("method") != "unavailable"]
    max_pts = sum(i.get("max", 0) for i in avail)
    if not max_pts:
        return None
    return max(0.0, sum(i.get("score", 0) for i in avail) / max_pts)


def derive(payload: dict, usd_rate) -> dict:
    """Flat metrics row for one ticker. `usd_rate(currency)` returns USD per unit."""
    info = payload.get("info") or {}
    annual = payload.get("annual") or []
    latest = annual[0] if annual else {}

    mkt_ccy = info.get("currency")
    fin_ccy = info.get("financialCurrency") or MINOR_UNITS.get(mkt_ccy or "", (mkt_ccy,))[0]
    fx_m, fx_f = usd_rate(mkt_ccy), usd_rate(fin_ccy)

    def usd(v):  # statement currency -> USD
        return v * fx_f if v is not None and fx_f else None

    mcap = _market_cap(info)
    mcap_usd = mcap * fx_m if mcap and fx_m else None

    revs = [r.get("revenue") for r in annual]
    rev = latest.get("revenue")
    rev_usd = usd(rev)

    # Growth
    qrevs = [q.get("revenue") for q in payload.get("quarterly_revenue") or []]
    q_yoy = [qrevs[i] / qrevs[i + 4] - 1 for i in range(max(0, len(qrevs) - 4))
             if qrevs[i] and qrevs[i + 4] and qrevs[i + 4] > 0]
    growth_q = q_yoy[0] if q_yoy else info.get("revenueGrowth")

    # Margins
    op_margins = [_div(r.get("operating_income"), r.get("revenue")) for r in annual]
    op_margins = [m for m in op_margins if m is not None]
    gross_margin = _div(latest.get("gross_profit"), rev)
    if gross_margin is None:
        gross_margin = info.get("grossMargins")

    # Cash flow
    def fcf_of(r):
        if r.get("free_cash_flow") is not None:
            return r["free_cash_flow"]
        if r.get("operating_cash_flow") is not None and r.get("capex") is not None:
            return r["operating_cash_flow"] - abs(r["capex"])
        return None
    fcfs = [fcf_of(r) for r in annual]
    fcf = fcfs[0] if fcfs else None
    if fcf is None and info.get("freeCashflow") is not None:
        fcf = info["freeCashflow"]
    ocf = latest.get("operating_cash_flow", info.get("operatingCashflow"))

    # Returns on capital
    roic_hist, roce_hist = _roic_series(annual)

    # Balance sheet
    cash = latest.get("cash", info.get("totalCash"))
    debt = latest.get("total_debt", info.get("totalDebt"))
    net_cash = cash - debt if cash is not None and debt is not None else None
    ebitda = info.get("ebitda")
    ev_usd = mcap_usd + usd(-net_cash) if mcap_usd is not None and net_cash is not None and fx_f else mcap_usd

    # Per-share
    eps_cagr = _cagr([r.get("eps") for r in annual])
    pe = info.get("trailingPE")
    shares_cagr = _cagr([r.get("shares") for r in annual])

    m = {
        "ticker":   payload.get("symbol"),
        "name":     info.get("longName") or info.get("shortName"),
        "sector":   info.get("sector"),
        "industry": info.get("industry"),
        "country":  info.get("country"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": mkt_ccy,
        "quote_type": info.get("quoteType"),
        "years_of_data": len(annual),

        "market_cap_usd":       mcap_usd,
        "enterprise_value_usd": ev_usd,
        "revenue_usd":          rev_usd,
        "revenue_cagr":         _cagr(revs),
        "revenue_growth_1y":    _div(revs[0], revs[1]) - 1 if len(revs) > 1 and _div(revs[0], revs[1]) else None,
        "revenue_growth_q":     growth_q,
        "gross_margin":         gross_margin,
        "operating_margin":     op_margins[0] if op_margins else info.get("operatingMargins"),
        "operating_margin_change": op_margins[0] - op_margins[-1] if len(op_margins) > 1 else None,
        "net_margin":           _div(latest.get("net_income"), rev),
        "fcf_margin":           _div(fcf, rev),
        "fcf_positive_years":   sum(1 for f in fcfs if f is not None and f > 0) if fcfs else None,
        "fcf_yield":            _div(usd(fcf), mcap_usd),
        "ocf_to_revenue":       _div(ocf, rev),
        "capex_to_revenue":     _div(abs(latest["capex"]), rev) if latest.get("capex") is not None else None,
        "roic":                 roic_hist[0] if roic_hist else None,
        "roic_avg":             sum(roic_hist) / len(roic_hist) if roic_hist else None,
        "roic_min":             min(roic_hist) if roic_hist else None,
        "roce_avg":             sum(roce_hist) / len(roce_hist) if roce_hist else None,
        "roe":                  info.get("returnOnEquity"),
        "net_cash_usd":         usd(net_cash),
        "net_cash_to_mcap":     _div(usd(net_cash), mcap_usd),
        "net_debt_to_ebitda":   _div(-net_cash, ebitda) if net_cash is not None and ebitda and ebitda > 0 else None,
        "pe":                   pe,
        "forward_pe":           info.get("forwardPE"),
        "ps":                   _div(mcap_usd, rev_usd),
        "ev_to_ebit":           _div(ev_usd, usd(latest.get("operating_income"))),
        "ev_to_sales":          _div(ev_usd, rev_usd),
        "peg":                  pe / (eps_cagr * 100) if pe and pe > 0 and eps_cagr and eps_cagr > 0 else None,
        "eps_cagr":             eps_cagr,
        "share_dilution":       shares_cagr,
        "insider_pct":          info.get("heldPercentInsiders"),
        "week52_change":        info.get("52WeekChange"),
        "beta":                 info.get("beta"),
    }

    # Lite profile in the shape discovery.run() produces, so Atlas's own
    # deterministic scorers run unchanged on screener data.
    profile = {
        "ticker": m["ticker"], "name": m["name"], "sector": m["sector"], "industry": m["industry"],
        "market_cap": mcap_usd, "enterprise_value": ev_usd,
        "revenues": [{"year": r["year"], "revenue": usd(r.get("revenue"))} for r in annual],
        "revenue_quarterly": [{"period": q["period"], "revenue": usd(q.get("revenue"))}
                              for q in payload.get("quarterly_revenue") or []],
        "revenue_cagr": m["revenue_cagr"],
        "cash_and_equivalents": usd(cash), "total_cash": usd(cash), "total_debt": usd(debt),
        "net_debt": usd(-net_cash) if net_cash is not None else None,
        "operating_cash_flow": usd(ocf), "operating_income": usd(latest.get("operating_income")),
        "free_cash_flow": usd(fcf), "net_income": usd(latest.get("net_income")),
        "net_income_history": [{"year": r["year"], "net_income": r.get("net_income")} for r in annual],
        "eps_history": [{"year": r["year"], "eps": r.get("eps")} for r in annual],
        "gross_margin": gross_margin, "roe": m["roe"],
        "roic_avg": m["roic_avg"], "roce_avg": m["roce_avg"],
        "roic_trend": _trend(roic_hist[0], roic_hist[-1]) if len(roic_hist) > 1 else None,
        "ps_ratio": round(m["ps"], 2) if m["ps"] else None,
        "week52_change_pct": m["week52_change"],
        "insider_ownership_pct": m["insider_pct"],
        "dilution_cagr": shares_cagr,
    }

    if mcap_usd and rev_usd:
        oey = compute_oey(profile)
        active = oey.get("active_oey")
        m["oey"] = active / 100 if active is not None else None
        m["oey_reported"] = oey["reported_oey_ev"] / 100 if oey.get("reported_oey_ev") is not None else None
        m["oey_hurdle"] = 0.035 if oey.get("is_elite_compounder") else 0.05
        m["oey_passes"] = (m["oey"] >= m["oey_hurdle"]) if m["oey"] is not None else None
    else:
        m.update({"oey": None, "oey_reported": None, "oey_hurdle": None, "oey_passes": None})

    from agents.quality_screen import _quant_items, _val_items
    from agents.feroldi import _fin_items
    m["quality_score"] = _points_pct(_quant_items(profile, []) + _val_items(profile, []))
    m["feroldi_fin_score"] = _points_pct(_fin_items(profile, []))

    m["data_gaps"] = [k for k in METRICS if m.get(k) is None]
    return m
