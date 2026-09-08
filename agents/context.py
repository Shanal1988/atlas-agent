# Shared profile serialization + operating-earnings-yield (OEY) helpers.
#
# Extracted from agents/bmp_gate.py so that the BMP gate, Munger Four Filters,
# process scoring and risk sizing all use identical numbers. The earning-yield
# >5% price veto (user's investing process §6) lives here.

import os


def call_llm(messages: list, max_tokens: int, temperature: float,
             stage: str = "", model: str | None = None) -> str:
    """Call Claude (only LLM provider). Returns response string or ""."""
    from agents.llm_client import claude_call
    return claude_call(messages, max_tokens, temperature, stage=stage)


def call_llm_with_ft(messages: list, max_tokens: int, temperature: float,
                     stage: str = "", ft_env_var: str = "") -> str:
    """Try a fine-tuned OpenAI model first, then fall back to call_llm()."""
    ft_model = os.environ.get(ft_env_var) if ft_env_var else None
    if ft_model:
        try:
            from openai import OpenAI
            resp = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).chat.completions.create(
                model=ft_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  [Warning] OpenAI FT model failed ({e}), falling back...")
    return call_llm(messages, max_tokens, temperature, stage=stage)

_DIGITAL_MATURE_MARGINS = {
    "internet content & information": 0.38,   # Google, Meta (steady-state digital ad + cloud)
    "internet retail":                0.16,   # Amazon blended retail + AWS + Ads
    "software - application":         0.32,   # Seessel benchmark for scaled SaaS/apps
    "software—application":           0.30,
    "software - infrastructure":      0.36,   # Scaled infrastructure & database software
    "software—infrastructure":        0.34,
    "financial technology":           0.38,   # Adyen, Stripe, PayPal platform scale
    "credit services":                0.36,
    "payments":                       0.38,
    "semiconductors":                 0.32,
    "semiconductor equipment":        0.30,
    "entertainment":                  0.22,   # Netflix, Disney
    "consumer electronics":           0.18,
    "information technology services":0.24,
}
_DIGITAL_SECTORS = frozenset({"Technology", "Communication Services", "Financial Services"})

# Segment-weighted mature margins for multi-business digital leaders.
# Sources: Adam Seessel ('Where the Money Is', 2022), 10-K segment reporting, Damodaran.
# Format: ticker -> [(revenue_share, mature_margin, label), ...]
_SEGMENT_MATURE_MARGINS = {
    # Amazon: 3 distinct businesses (AWS cloud + high-margin ads + scaled retail/logistics)
    "AMZN": [
        (0.16, 0.36, "AWS Cloud"),             # cloud infra at scale; 36% margin
        (0.09, 0.48, "Advertising"),           # ad-tech at scale; 48% margin
        (0.75, 0.07, "Retail & Fulfillment"),  # e-commerce + 3P logistics; 7% structural margin
    ],
    # Alphabet: Search dominance + YouTube + Google Cloud reaching AWS/Azure scale
    "GOOGL": [
        (0.56, 0.46, "Search & Core Ads"),     # near-monopoly ad engine; 46% mature margin
        (0.10, 0.38, "YouTube"),               # ad-supported video at global scale; 38% margin
        (0.13, 0.34, "Google Cloud"),          # cloud enterprise infrastructure; 34% margin
        (0.21, 0.18, "Subs, Devices & Other"), # YouTube Premium, hardware, self-funding bets; 18% margin
    ],
    "GOOG": [
        (0.56, 0.46, "Search & Core Ads"),
        (0.10, 0.38, "YouTube"),
        (0.13, 0.34, "Google Cloud"),
        (0.21, 0.18, "Subs, Devices & Other"),
    ],
    # Meta: core Family of Apps ad machine at maturity; Reality Labs pre-profit phase
    "META": [
        (0.97, 0.50, "Family of Apps"),        # FB/IG/WhatsApp ad engine at maturity; 50% margin
        (0.03, 0.00, "Reality Labs"),          # discretionary AR/VR moonshot; 0% margin
    ],
    # Microsoft: three core cloud and enterprise software pillars
    "MSFT": [
        (0.44, 0.46, "Intelligent Cloud"),        # Azure + server; 46% margin
        (0.33, 0.42, "Productivity & Business"),  # Office 365, LinkedIn, Dynamics; 42% margin
        (0.23, 0.25, "More Personal Computing"),  # Windows, Gaming, Bing; 25% margin
    ],
}


def compute_oey(profile: dict) -> dict:
    """
    Compute reported and Adam Seessel (EV-based + Growth OpEx Normalized)
    Operating Earnings Yield (OEY) following 'Where the Money Is: Value Investing in the Digital Age'.

    Adam Seessel Digital Value Principles:
    1. Capital Basis: Enterprise Value (EV = Market Cap + Debt - Cash) isolates the actual
       operating business price paid by investors, giving full credit for excess cash.
    2. Growth OpEx Normalization: Digital platforms expense long-term growth investments
       (speculative R&D + new cohort customer acquisition S&M) through the P&L under GAAP,
       artificially depressing reported operating earnings. Normalizing for steady-state
       segment margins and growth OpEx reveals true underlying earnings power.
    3. Tax Adjustment: Multiply operating earnings by 0.79 (standard 21% corporate tax rate).
    4. Dynamic Growth Hurdle: A 5% yield (20x EV/NOPAT) is a rare table-pounding bargain for
       a compounder, while 3.5%-5.0% is a fair and attractive price for secular compounders
       growing revenue at >12-15% with high ROE/ROIC.
    """
    revenues   = profile.get("revenues") or []
    market_cap = profile.get("market_cap")
    op_income  = profile.get("operating_income")

    # Enterprise Value resolution
    cash = profile.get("total_cash") or profile.get("cash_and_equivalents") or 0
    debt = profile.get("total_debt") or 0
    ev   = profile.get("enterprise_value")

    if not ev and market_cap:
        ev = max(market_cap + debt - cash, market_cap * 0.5)

    # Denominator: Prefer EV to isolate operating enterprise
    denom = ev if (ev and ev > 0) else market_cap

    # 1. Reported OEY (Market Cap basis & EV basis)
    reported_oey_mktcap = round((op_income * 0.79 / market_cap) * 100, 2) if (op_income and market_cap and market_cap > 0) else None
    reported_oey_ev     = round((op_income * 0.79 / denom) * 100, 2) if (op_income and denom and denom > 0) else None

    # Base reported yield prefers EV per Seessel methodology
    oey = reported_oey_ev if reported_oey_ev is not None else reported_oey_mktcap

    # 2. Seessel Normalized Operating Margin & Yield Derivation
    normalized_oey    = None
    mature_margin_pct = None
    segment_breakdown = None
    industry_lower    = (profile.get("industry") or "").lower()
    sector_val        = profile.get("sector") or ""
    ticker_val        = (profile.get("ticker") or "").upper()

    if ticker_val in _SEGMENT_MATURE_MARGINS:
        segs = _SEGMENT_MATURE_MARGINS[ticker_val]
        mature_margin_pct = round(sum(s * m for s, m, _ in segs), 4)
        segment_breakdown = " + ".join(f"{lbl} ({s:.0%}×{m:.0%})" for s, m, lbl in segs)
    else:
        for key, margin in _DIGITAL_MATURE_MARGINS.items():
            if key in industry_lower:
                mature_margin_pct = margin
                break

    if mature_margin_pct is None and sector_val in _DIGITAL_SECTORS:
        mature_margin_pct = 0.32  # Seessel software/digital baseline

    norm_oey_raw = None
    norm_op_income = None
    derivation_str = ""

    latest_rev = revenues[0].get("revenue") if revenues else None
    if isinstance(latest_rev, (int, float)) and latest_rev > 0 and denom and denom > 0:
        if mature_margin_pct:
            norm_op_income = latest_rev * mature_margin_pct
            # If reported operating income is already higher than baseline, retain reported as floor
            if op_income and op_income > norm_op_income:
                norm_op_income = op_income
            norm_oey_raw = round((norm_op_income * 0.79 / denom) * 100, 2)
            normalized_oey = norm_oey_raw
            derivation_str = (
                f"Seessel steady-state operating margin ({mature_margin_pct:.1%}"
                + (f" across {segment_breakdown}" if segment_breakdown else "")
                + f") on ${latest_rev/1e9:,.1f}B revenue = ${norm_op_income/1e9:,.1f}B Normalized EBIT "
                + f"(${norm_op_income*0.79/1e9:,.1f}B after-tax) on ${denom/1e9:,.1f}B EV"
            )

    # Active OEY choice: Seessel Normalized EV Yield if available, else Reported EV Yield
    active_oey = normalized_oey if normalized_oey is not None else oey

    # 3. Dynamic Price Veto Logic per Seessel
    cagr_raw = profile.get("revenue_cagr") if profile.get("revenue_cagr") is not None else profile.get("revenue_growth_pct")
    cagr = cagr_raw if cagr_raw is not None else 0.0
    roe = profile.get("roe") or 0.0
    is_elite_compounder = (cagr >= 0.12 or roe >= 0.20)

    # Price Veto condition:
    # - For elite compounders (growth >= 12% or ROE >= 20%): hurdle is 3.5% (fair value entry)
    # - For moderate growers: hurdle is 5.0%
    if active_oey is None:
        price_veto = False
    elif is_elite_compounder:
        price_veto = active_oey < 3.5
    else:
        price_veto = active_oey < 5.0

    return {
        "reported_oey":        oey,
        "reported_oey_mktcap": reported_oey_mktcap,
        "reported_oey_ev":     reported_oey_ev,
        "normalized_oey":      normalized_oey,
        "norm_oey_raw":        norm_oey_raw,
        "mature_margin_pct":   mature_margin_pct,
        "segment_breakdown":   segment_breakdown,
        "enterprise_value":    ev,
        "net_cash":            cash - debt if (cash or debt) else None,
        "active_oey":          active_oey,
        "is_elite_compounder": is_elite_compounder,
        "price_veto":          price_veto,
        "derivation":          derivation_str,
    }


def _fmt_big(n) -> str:
    if n is None:
        return "N/A"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n:,.0f}"


def profile_context(profile: dict) -> str:
    """Serialise the CompanyProfile into a readable block for LLM prompts."""
    revenues = profile.get("revenues") or []
    rev_str = "  |  ".join(
        f"{r.get('year','?')}: {r.get('revenue')}"
        for r in revenues
    ) or "N/A"

    # CAGR is stored as a decimal fraction (e.g. 0.1918 = 19.18%)
    cagr_raw = profile.get("revenue_cagr") if profile.get("revenue_cagr") is not None \
               else profile.get("revenue_growth_pct")
    cagr = round(cagr_raw * 100, 2) if cagr_raw is not None else None

    insider = profile.get("insider_ownership_pct")
    insider_str = f"{insider * 100:.2f}%" if insider is not None else "N/A"

    roe = profile.get("roe")
    roe_str = f"{roe * 100:.2f}%" if roe is not None else "N/A"

    pe = profile.get("pe_ratio")
    earnings_yield = None
    if pe and pe > 0:
        earnings_yield = round((1 / pe) * 100, 2)

    op_income  = profile.get("operating_income")
    op_cf      = profile.get("operating_cash_flow")
    market_cap = profile.get("market_cap")
    fcf        = profile.get("free_cash_flow")

    o = compute_oey(profile)
    oey               = o["reported_oey"]
    normalized_oey    = o["normalized_oey"]
    norm_oey_raw      = o["norm_oey_raw"]
    mature_margin_pct = o["mature_margin_pct"]
    segment_breakdown = o["segment_breakdown"]
    derivation_str    = o.get("derivation", "")

    fcf_yield = None
    if fcf and market_cap and market_cap > 0:
        fcf_yield = round((fcf / market_cap) * 100, 2)

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {market_cap if market_cap else 'N/A'}",
        f"Enterprise Value:  {o.get('enterprise_value') if o.get('enterprise_value') else 'N/A'}",
        f"Current Price:     {profile.get('current_price', 'N/A')}",
        f"P/E Ratio:         {pe if pe else 'N/A'}",
        f"Earnings Yield:    {earnings_yield}%" if earnings_yield else "Earnings Yield:    N/A",
        f"Op. Earnings Yield:{oey}% (Op. Income x 0.79 / EV)" if oey is not None else "Op. Earnings Yield: N/A",
        *(
            [f"Normalized OEY:    {normalized_oey}% [Seessel 'Where the Money Is' — USE THIS for Q5 / F4]\n"
             f"  Derivation:      {derivation_str}"]
            if normalized_oey is not None else
            ["Normalized OEY:    N/A (traditional business or margins not suppressed by reinvestment)"]
        ),
        f"FCF Yield:         {fcf_yield}% (FCF / Mkt Cap)" if fcf_yield is not None else "FCF Yield:          N/A",
        f"Beta:              {profile.get('beta', 'N/A')}",
        f"Revenue (3yr):     {rev_str}",
        f"Revenue CAGR:      {cagr}% (3yr)" if cagr is not None else "Revenue CAGR:      N/A",
        f"Free Cash Flow:    {fcf if fcf is not None else 'N/A'}",
        f"Operating Income:  {op_income if op_income is not None else 'N/A'}",
        f"Op. Cash Flow:     {op_cf if op_cf is not None else 'N/A'}",
        f"ROE:               {roe_str}",
        *(
            [f"ROCE (avg):        {round(profile.get('roce_avg') * 100, 2)}%  Trend: {profile.get('roce_trend', 'N/A')}"]
            if profile.get("roce_avg") is not None else ["ROCE:              N/A"]
        ),
        *(
            [f"ROIC (avg):        {round(profile.get('roic_avg') * 100, 2)}%  Trend: {profile.get('roic_trend', 'N/A')}"]
            if profile.get("roic_avg") is not None else ["ROIC:              N/A"]
        ),
        f"Insider Ownership: {insider_str}",
    ]

    # -- Extended fields (populated by discovery enrichment; all nullable) -----
    gm = profile.get("gross_margin")
    if gm is not None:
        lines.append(f"Gross Margin:      {gm * 100:.1f}%  (Gross Profit: {_fmt_big(profile.get('gross_profit'))})")
    ni = profile.get("net_income")
    if ni is not None:
        lines.append(f"Net Income (TTM):  {_fmt_big(ni)}")
    ni_hist = profile.get("net_income_history") or []
    if ni_hist:
        lines.append("Net Income (5yr):  " + "  |  ".join(
            f"{r.get('year','?')}: {_fmt_big(r.get('net_income'))}" for r in ni_hist))
    eps_hist = profile.get("eps_history") or []
    if eps_hist:
        lines.append("EPS (5yr):         " + "  |  ".join(
            f"{r.get('year','?')}: {r.get('eps')}" for r in eps_hist))
    if profile.get("total_debt") is not None or profile.get("cash_and_equivalents") is not None:
        lines.append(
            f"Total Debt:        {_fmt_big(profile.get('total_debt'))}   "
            f"Cash: {_fmt_big(profile.get('cash_and_equivalents'))}   "
            f"Net Debt: {_fmt_big(profile.get('net_debt'))}"
        )
    dil = profile.get("dilution_cagr")
    if dil is not None:
        lines.append(f"Share Dilution:    {dil * 100:+.2f}%/yr (share count CAGR; negative = buybacks)")
    if profile.get("week52_high") is not None:
        chg = profile.get("week52_change_pct")
        chg_str = f"  52W Change: {chg * 100:+.1f}%" if chg is not None else ""
        lines.append(f"52-Week Range:     {profile.get('week52_low')} – {profile.get('week52_high')}{chg_str}")
    ps = profile.get("ps_ratio")
    if ps is not None:
        lines.append(f"P/S Ratio:         {ps}")
    sm = profile.get("sm_expense")
    if sm is not None:
        gp = profile.get("gross_profit")
        ratio = f"  (S&M / Gross Profit: {sm / gp * 100:.1f}%)" if gp else ""
        lines.append(f"S&M Expense:       {_fmt_big(sm)}{ratio}")
    rq = profile.get("revenue_quarterly") or []
    if rq:
        lines.append("Revenue (last 5Q): " + "  |  ".join(
            f"{r.get('period','?')}: {_fmt_big(r.get('revenue'))}" for r in rq))

    lines += [
        f"Competitive Moat:  {profile.get('moat', 'N/A')}",
        f"Description:       {profile.get('description', 'N/A')}",
        f"Growth Drivers:    {'; '.join(profile.get('growth_drivers', []))}",
        f"Risk Factors:      {'; '.join(profile.get('risk_factors', []))}",
    ]
    return "\n".join(lines)
