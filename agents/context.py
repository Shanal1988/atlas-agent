# Shared profile serialization + operating-earnings-yield (OEY) helpers.
#
# Extracted from agents/bmp_gate.py so that the BMP gate, Munger Four Filters,
# process scoring and risk sizing all use identical numbers. The earning-yield
# >5% price veto (user's investing process §6) lives here.

import os


def call_llm(messages: list, max_tokens: int, temperature: float,
             stage: str = "", model: str | None = None) -> str:
    """Call Gemini (only LLM provider). Returns response string or ""."""
    from agents.llm_client import gemini_call
    return gemini_call(messages, max_tokens, temperature, stage=stage)


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
    "internet content & information": 0.35,   # Google, Meta
    "internet retail":                0.12,   # Amazon blended
    "software - application":         0.25,
    "software—application":           0.25,
    "software - infrastructure":      0.30,
    "software—infrastructure":        0.30,
    "semiconductors":                 0.28,
    "semiconductor equipment":        0.25,
    "entertainment":                  0.18,   # Netflix, Disney
    "consumer electronics":           0.12,
    "information technology services":0.22,
}
_DIGITAL_SECTORS = frozenset({"Technology", "Communication Services"})

# Segment-weighted mature margins for multi-business conglomerates.
# Format: ticker -> [(revenue_share, mature_margin, label), ...]
# Revenue shares are approximate; refresh annually from 10-K segment data.
# Sources: Damodaran sector data, company 10-Ks, sell-side comps.
_SEGMENT_MATURE_MARGINS = {
    # Amazon: FMP misclassifies as "Specialty Retail"; real mix is 3 distinct businesses
    "AMZN": [
        (0.15, 0.35, "AWS"),              # cloud infra; Azure/GCP comp at maturity
        (0.08, 0.45, "Advertising"),      # ad-tech at scale; Meta/Google comp
        (0.77, 0.05, "Retail/Logistics"), # e-commerce + fulfilment; thin structural margin
    ],
    # Alphabet: search dominance + fast-growing cloud suppressed by infra spend
    "GOOGL": [
        (0.56, 0.42, "Search & Ads"),     # near-mature; durable pricing power
        (0.10, 0.35, "YouTube"),          # ad-supported video at scale
        (0.13, 0.28, "Google Cloud"),     # investing heavily; Azure/AWS comp
        (0.21, 0.12, "Other/Bets"),       # subscriptions, hardware, moonshots
    ],
    "GOOG": [                             # same economic exposure, different share class
        (0.56, 0.42, "Search & Ads"),
        (0.10, 0.35, "YouTube"),
        (0.13, 0.28, "Google Cloud"),
        (0.21, 0.12, "Other/Bets"),
    ],
    # Meta: core advertising very high-margin; Reality Labs in heavy pre-profit phase
    "META": [
        (0.97, 0.48, "Family of Apps"),   # FB/IG/WhatsApp ad engine at maturity
        (0.03, 0.00, "Reality Labs"),     # deliberate loss; AR/VR platform bet
    ],
    # Microsoft: three clearly separated segments with different margin profiles
    "MSFT": [
        (0.43, 0.45, "Intelligent Cloud"),        # Azure + server; highest-margin segment
        (0.33, 0.40, "Productivity & Business"),  # Office 365, LinkedIn, Dynamics
        (0.24, 0.22, "More Personal Computing"),  # Windows, Gaming, Bing
    ],
}


def compute_oey(profile: dict) -> dict:
    """
    Compute reported and (Seessel) normalized operating earnings yield.

    Returns dict:
      reported_oey       -- Op. Income x 0.79 / Mkt Cap, in % (or None)
      normalized_oey     -- active only when materially (>15%) above reported (or None)
      norm_oey_raw       -- always computed when possible, even if not surfaced
      mature_margin_pct  -- blended mature operating margin used (fraction, or None)
      segment_breakdown  -- human-readable segment decomposition (or None)
      active_oey         -- normalized_oey if it fired, else reported_oey (or None)
      price_veto         -- True when active_oey < 5% (process rule: earning yield
                            must exceed 5% before buying); False if OEY unknown
    """
    revenues   = profile.get("revenues") or []
    market_cap = profile.get("market_cap")
    op_income  = profile.get("operating_income")

    oey = None
    if op_income and market_cap and market_cap > 0:
        oey = round((op_income * 0.79 / market_cap) * 100, 2)

    normalized_oey    = None
    mature_margin_pct = None
    segment_breakdown = None
    industry_lower    = (profile.get("industry") or "").lower()
    sector_val        = profile.get("sector") or ""
    ticker_val        = (profile.get("ticker") or "").upper()

    if ticker_val in _SEGMENT_MATURE_MARGINS:
        segs = _SEGMENT_MATURE_MARGINS[ticker_val]
        mature_margin_pct = round(sum(s * m for s, m, _ in segs), 4)
        segment_breakdown = " + ".join(
            f"{lbl} ({s:.0%}×{m:.0%})" for s, m, lbl in segs
        )
    else:
        for key, margin in _DIGITAL_MATURE_MARGINS.items():
            if key in industry_lower:
                mature_margin_pct = margin
                break
    if mature_margin_pct is None and sector_val in _DIGITAL_SECTORS:
        mature_margin_pct = 0.25  # generic tech fallback

    norm_oey_raw = None   # always computed when possible; used even in N/A line
    if mature_margin_pct and revenues and market_cap and market_cap > 0:
        latest_rev = revenues[0].get("revenue") if revenues else None
        if isinstance(latest_rev, (int, float)) and latest_rev > 0:
            norm_op_income = latest_rev * mature_margin_pct
            norm_oey_raw   = round((norm_op_income * 0.79 / market_cap) * 100, 2)
            # Only surface as the active OEY when normalization reveals materially higher earnings power
            if oey is None or norm_oey_raw > oey * 1.15:
                normalized_oey = norm_oey_raw

    active_oey = normalized_oey if normalized_oey is not None else oey

    return {
        "reported_oey":      oey,
        "normalized_oey":    normalized_oey,
        "norm_oey_raw":      norm_oey_raw,
        "mature_margin_pct": mature_margin_pct,
        "segment_breakdown": segment_breakdown,
        "active_oey":        active_oey,
        "price_veto":        active_oey is not None and active_oey < 5.0,
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

    fcf_yield = None
    if fcf and market_cap and market_cap > 0:
        fcf_yield = round((fcf / market_cap) * 100, 2)

    lines = [
        f"Company:           {profile.get('name', 'N/A')}",
        f"Ticker:            {profile.get('ticker', 'N/A')}",
        f"Exchange:          {profile.get('exchange', 'N/A')}",
        f"Sector/Industry:   {profile.get('sector', 'N/A')} / {profile.get('industry', 'N/A')}",
        f"Market Cap:        {market_cap if market_cap else 'N/A'}",
        f"Current Price:     {profile.get('current_price', 'N/A')}",
        f"P/E Ratio:         {pe if pe else 'N/A'}",
        f"Earnings Yield:    {earnings_yield}%" if earnings_yield else "Earnings Yield:    N/A",
        f"Op. Earnings Yield:{oey}% (Op. Income x 0.79 / Mkt Cap)" if oey is not None else "Op. Earnings Yield: N/A",
        *(
            # Normalization fires: show as the active OEY with full segment derivation
            [f"Normalized OEY:    {normalized_oey}% "
             f"({'Segments: ' + segment_breakdown + ' → ' if segment_breakdown else ''}"
             f"{mature_margin_pct:.1%} blended op margin × Rev × 0.79 / Mkt Cap) [Seessel — USE THIS for Q5]"]
            if normalized_oey is not None else
            # Segment data exists but current margins already near mature — show computed OEY for transparency
            [f"Normalized OEY:    N/A — computed {norm_oey_raw}% OEY (mature blended op margin {mature_margin_pct:.1%}: "
             f"{segment_breakdown}) is not materially above reported OEY {oey}%; "
             f"use reported OEY for Q5"]
            if segment_breakdown and norm_oey_raw is not None else
            # No segment data but segment_breakdown set (shouldn't occur) or no data at all
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
