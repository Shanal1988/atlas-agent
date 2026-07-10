# Stage 1.5 - Industry & Competitor Analysis
#
# Fetches peer companies, compares quantitative metrics, and synthesises
# industry dynamics via LLM.  Runs after Discovery, before BMP Gate.

import os
import requests
import yfinance as yf
from groq import Groq


# -- Constants -----------------------------------------------------------------

FMP_BASE   = "https://financialmodelingprep.com/stable"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


# -- Shared helpers ------------------------------------------------------------

def _fmp(endpoint: str, params: dict) -> list | None:
    from agents.fmp_client import fmp_get
    return fmp_get(endpoint, params)


def _groq():
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _tavily_content(query: str, max_results: int = 4) -> str:
    from tavily import TavilyClient
    tc = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = tc.search(query=query, max_results=max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results.get("results", [])
    )


def _is_us_listed(ticker: str) -> bool:
    if "." not in ticker and ":" not in ticker:
        return True
    if ":" in ticker:
        return False
    _INTL_SUFFIXES = {
        "L", "AS", "TO", "PA", "DE", "HK", "AX", "BR", "MC", "MI",
        "CO", "ST", "OL", "HE", "SW", "VI", "OTC", "SA", "NS", "BO", "KL", "SI",
    }
    suffix = ticker.rsplit(".", 1)[1].upper()
    return suffix not in _INTL_SUFFIXES


# -- Peer discovery ------------------------------------------------------------

def _business_focus(profile: dict) -> str:
    """Return a short business description for building targeted search queries."""
    desc = (profile.get("description") or "")[:300]
    moat = profile.get("moat") or ""
    industry = profile.get("industry") or ""
    # Prefer description over generic industry label
    if desc and len(desc) > 40:
        return desc
    if moat and len(moat) > 20:
        return f"{moat} {industry}"
    return industry


def _fetch_peers(ticker: str, is_us: bool, company: str = "", profile: dict | None = None) -> list[str]:
    """Get list of peer/competitor tickers (max 6).

    Strategy: always run semantic search (Tavily+Groq) to find true business competitors,
    then merge with FMP/yfinance peers and deduplicate.  FMP's SIC-based peers are often
    too generic (e.g. PYPL/SQ for Wise instead of RELY/WU).
    """
    fmp_peers: list[str] = []
    mkt_cap = (profile or {}).get("market_cap")

    # 1. FMP peers (SIC-code based — useful baseline but may be generic)
    data = _fmp("/peers", {"symbol": ticker})
    if data and isinstance(data, list) and data:
        fmp_peers = data[0].get("peersList", [])[:8]

    # 2. yfinance recommendedSymbols — only trust for US stocks (noisy for international)
    yf_peers: list[str] = []
    if is_us and not fmp_peers:
        try:
            t = yf.Ticker(ticker)
            recs = t.info.get("recommendedSymbols") or []
            yf_peers = [r.get("symbol") for r in recs if r.get("symbol")][:8]
        except Exception:
            pass

    # 3. Semantic search — ALWAYS run to find true business competitors
    #    (e.g. Remitly, Western Union for Wise rather than generic payment co's)
    semantic_peers: list[str] = []
    if company:
        focus = _business_focus(profile or {})
        semantic_peers = _resolve_peers_via_search(company, focus, ticker)

    # 4. Merge: semantic peers first (most accurate), then FMP/yf to fill gaps
    seen: set[str] = set()
    merged: list[str] = []
    for p in semantic_peers + fmp_peers + yf_peers:
        key = p.upper()
        if p and key != ticker.upper() and key not in seen:
            seen.add(key)
            merged.append(p)

    # 5. Drop size mismatches (giants >30x market cap — clearly wrong sector)
    if mkt_cap:
        merged = _filter_size_mismatches(merged, mkt_cap)

    return merged[:6]


def _filter_size_mismatches(peer_tickers: list[str], target_mktcap: float) -> list[str]:
    """Drop peers whose market cap is >30x the target (likely wrong industry matches)."""
    from agents.fmp_client import yf_company_metrics
    filtered = []
    for pticker in peer_tickers:
        try:
            peer_mc = None
            prof = _fmp("/profile", {"symbol": pticker})
            if prof:
                peer_mc = prof[0].get("marketCap")
            else:
                # FMP quota exhausted — try yfinance for market cap
                yf_row = yf_company_metrics(pticker)
                if yf_row:
                    peer_mc = yf_row.get("market_cap")
            if peer_mc and target_mktcap:
                ratio = peer_mc / target_mktcap
                if ratio > 30:
                    print(f"  [Industry] Dropping {pticker} (market cap {ratio:.0f}x target — likely wrong sector)")
                    continue
            filtered.append(pticker)
        except Exception:
            filtered.append(pticker)
    return filtered


def _resolve_peers_via_search(company: str, business_focus: str, ticker: str) -> list[str]:
    """Use Tavily search + Groq to identify competitor tickers when API peers unavailable."""
    import re
    try:
        # Build a targeted query from the business description, not the FMP industry label
        query = f"{company} direct competitors publicly listed companies same business"
        if business_focus and len(business_focus) > 20:
            # Truncate to key phrase for search
            focus_short = business_focus[:120]
            query = f"{company} competitors {focus_short}"

        snippets = _tavily_content(query, max_results=4)

        prompt = (
            f"From the search results below, list the top 5-6 publicly traded DIRECT competitors "
            f"of {company} ({ticker}) — companies in the SAME specific business, not just the same broad sector.\n"
            f"Business context: {business_focus[:200]}\n\n"
            f"Focus on companies that compete head-to-head for the SAME customers in the SAME niche "
            f"(e.g. for a cross-border money transfer company like Wise: Remitly (RELY), Western Union (WU), "
            f"MoneyGram — consumer/SMB money transfer).\n"
            f"EXCLUDE companies in adjacent but different niches: merchant payment processors / acquirers "
            f"(Adyen, Stripe, Square, PayPal merchant services), payroll providers, or broad software companies — "
            f"unless the target company's core business is the same.\n\n"
            f"Return ONLY ticker symbols, one per line. "
            f"Use US tickers (e.g. RELY, WU) or Yahoo Finance format for international "
            f"(e.g. ADYEN.AS, WISE.L). No numbering, no explanations, just the ticker.\n\n"
            f"Example output:\nRELY\nWU\nADYEN.AS\n\n"
            f"Search results:\n{snippets}"
        )
        resp = _groq().chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=100, temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        tickers = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[\d]+[.)]\s*", "", line)
            line = re.sub(r"^[-*•]\s*", "", line)
            token = line.split()[0].strip(".,;:()'\"*-") if line.split() else ""
            token = token.upper()
            if token and 1 <= len(token) <= 10 and token[0].isalpha():
                tickers.append(token)
        return tickers[:6]
    except Exception:
        return []


# -- Peer metrics fetch --------------------------------------------------------

def _fmt_num(n) -> str:
    if n is None:
        return "N/A"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n / 1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n / 1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.0f}M"
    return f"${n:,.0f}"


def _fmt_pct(n) -> str:
    if n is None:
        return "N/A"
    try:
        return f"{float(n) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fetch_peer_metrics(peers: list[str]) -> list[dict]:
    """Fetch key comparison metrics for each peer via FMP, with yfinance fallback
    when FMP is rate-limited (daily quota) or has no data."""
    from agents.fmp_client import yf_company_metrics
    results = []
    for peer in peers:
        try:
            profile = _fmp("/profile", {"symbol": peer})
            if not profile:
                # FMP quota exhausted or no data — fall back to yfinance
                yf_row = yf_company_metrics(peer)
                if yf_row:
                    results.append(yf_row)
                continue
            ratios = _fmp("/ratios", {"symbol": peer, "limit": 1})
            km = _fmp("/key-metrics", {"symbol": peer, "limit": 1})
            growth = _fmp("/financial-growth", {"symbol": peer, "limit": 1})
            p = profile[0]
            r = ratios[0] if ratios else {}
            k = km[0] if km else {}
            g = growth[0] if growth else {}
            row = {
                "ticker":           peer,
                "name":             p.get("companyName"),
                "market_cap":       p.get("marketCap"),
                "pe_ratio":         r.get("priceToEarningsRatio"),
                "roe":              r.get("returnOnEquity") or k.get("returnOnEquity"),
                "roic":             r.get("returnOnInvestedCapital") or k.get("roic"),
                "operating_margin": r.get("operatingProfitMargin"),
                "revenue_growth":   r.get("revenueGrowth") or g.get("revenueGrowth"),
                "price":            p.get("price"),
                "sector":           p.get("sector"),
                "industry":         p.get("industry"),
            }
            # If ratio endpoints were rate-limited, patch gaps from yfinance
            if row["pe_ratio"] is None and row["roe"] is None and row["operating_margin"] is None:
                yf_row = yf_company_metrics(peer)
                if yf_row:
                    for key in ("pe_ratio", "roe", "operating_margin", "revenue_growth"):
                        if row.get(key) is None:
                            row[key] = yf_row.get(key)
            results.append(row)
        except Exception:
            continue
    return results


# -- Qualitative industry research --------------------------------------------

def _fetch_industry_qualitative(industry: str, sector: str, company: str, profile: dict | None = None) -> str:
    """Two Tavily searches for industry context, using actual business description if available."""
    # Use specific business description for better search results
    focus = _business_focus(profile or {}) if profile else industry
    if not focus or len(focus) < 10:
        focus = industry

    # Build a short search phrase from the business description
    if profile and profile.get("description") and len(profile["description"]) > 40:
        # Extract a key phrase: company name + core business
        desc_short = profile["description"][:150]
        searches = [
            f"{company} market size growth trends 2025 2026",
            f"{desc_short} competitive landscape market structure",
        ]
    else:
        searches = [
            f"{focus} market size growth trends 2025 2026",
            f"{focus} competitive landscape market structure barriers to entry",
        ]
    try:
        combined = "\n\n===\n\n".join(_tavily_content(q) for q in searches)
        return combined
    except Exception:
        return ""


# -- LLM synthesis -------------------------------------------------------------

_INDUSTRY_SYSTEM = (
    "You are an industry research analyst. Based on the company data, peer comparison metrics, "
    "and industry research provided, deliver a structured industry analysis.\n\n"
    "IMPORTANT: Use the 'Business Focus' field (derived from the company description) to define "
    "the industry — NOT the generic 'Sector' label which may be inaccurate. For example, if the "
    "company does cross-border money transfers, the industry is 'cross-border payments / remittance', "
    "not 'Information Technology Services'.\n\n"
    "Reply using EXACTLY these labels, each on a new line:\n"
    "INDUSTRY_OVERVIEW: [2-3 sentences on industry size, growth rate, and stage — name the specific industry from the business description]\n"
    "MARKET_STRUCTURE: [oligopoly/fragmented/consolidating/etc. with 1-2 sentence explanation]\n"
    "COMPETITIVE_POSITION: [where does the target company rank among peers, 1-2 sentences]\n"
    "KEY_DYNAMICS: [2-3 most important competitive dynamics or trends, one sentence each]\n"
    "PEER_COMPARISON: [which peers are the strongest threats and why, 2-3 sentences]\n"
    "MOAT_VS_PEERS: [how does the target company's moat compare to its peers, 1-2 sentences]"
)


def _synthesise(profile: dict, peer_metrics: list[dict], qualitative: str) -> dict:
    """LLM call to synthesise industry analysis sections."""
    # Build peer comparison text
    peer_lines = []
    for pm in peer_metrics:
        peer_lines.append(
            f"  {pm['ticker']:<8} {(pm.get('name') or '')[:25]:<26} "
            f"MktCap: {_fmt_num(pm.get('market_cap'))}  "
            f"P/E: {pm.get('pe_ratio', 'N/A')}  "
            f"ROE: {_fmt_pct(pm.get('roe'))}  "
            f"ROIC: {_fmt_pct(pm.get('roic'))}  "
            f"OpMargin: {_fmt_pct(pm.get('operating_margin'))}  "
            f"RevGrowth: {_fmt_pct(pm.get('revenue_growth'))}"
        )

    # Derive real business focus from description; fall back to industry label only if needed
    business_focus = _business_focus(profile)

    context = (
        f"=== TARGET COMPANY ===\n"
        f"Company:        {profile.get('name', 'N/A')}\n"
        f"Ticker:         {profile.get('ticker', 'N/A')}\n"
        f"Business Focus: {business_focus}\n"
        f"Market Cap:     {_fmt_num(profile.get('market_cap'))}\n"
        f"ROE:           {_fmt_pct(profile.get('roe'))}\n"
        f"ROCE (avg):    {_fmt_pct(profile.get('roce_avg'))}\n"
        f"ROIC (avg):    {_fmt_pct(profile.get('roic_avg'))}\n"
        f"Moat:          {profile.get('moat', 'N/A')}\n"
        f"Description:   {profile.get('description', 'N/A')}\n"
        f"\n=== PEER METRICS ===\n"
        + ("\n".join(peer_lines) if peer_lines else "  No peer data available.")
        + f"\n\n=== INDUSTRY RESEARCH ===\n{qualitative[:3000]}"
    )

    messages = [
        {"role": "system", "content": _INDUSTRY_SYSTEM},
        {"role": "user",   "content": context},
    ]
    try:
        resp = _groq().chat.completions.create(
            model=GROQ_MODEL, messages=messages, max_tokens=1024, temperature=0.2,
        )
        text = resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        from agents.llm_client import gemini_call
        text = gemini_call(messages, max_tokens=1024, temperature=0.2,
                           stage="industry analysis")

    if not text:
        return {label: "N/A" for label in _SECTION_LABELS}

    return _parse_sections(text)


_SECTION_LABELS = [
    "INDUSTRY_OVERVIEW", "MARKET_STRUCTURE", "COMPETITIVE_POSITION",
    "KEY_DYNAMICS", "PEER_COMPARISON", "MOAT_VS_PEERS",
]


def _parse_sections(text: str) -> dict:
    result = {label: "" for label in _SECTION_LABELS}
    current_label = None
    buffer = []

    for line in text.splitlines():
        matched = False
        for label in _SECTION_LABELS:
            if line.strip().startswith(f"{label}:"):
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

    return result


# -- Output printer ------------------------------------------------------------

def _print_industry(profile: dict, peer_metrics: list[dict], sections: dict) -> None:
    W = 62
    print(f"\n{'=' * W}")
    print("  ATLAS: INDUSTRY & COMPETITOR ANALYSIS")
    print(f"{'=' * W}")
    print(f"  Company:  {profile.get('name', 'N/A')}")
    print(f"  Industry: {profile.get('industry', 'N/A')}")
    print(f"  Sector:   {profile.get('sector', 'N/A')}")

    if peer_metrics:
        print(f"\n  {'-' * (W - 2)}")
        print("  --- PEER COMPARISON ---")
        print(f"  {'-' * (W - 2)}")
        header = f"  {'Ticker':<8} {'Name':<22} {'Mkt Cap':>10} {'P/E':>7} {'ROE':>7} {'ROIC':>7} {'OpMgn':>7}"
        print(header)
        print(f"  {'-' * (W - 2)}")
        for pm in peer_metrics:
            name = (pm.get("name") or "")[:20]
            pe = f"{pm['pe_ratio']:.1f}" if pm.get("pe_ratio") else "N/A"
            roe = _fmt_pct(pm.get("roe"))
            roic = _fmt_pct(pm.get("roic"))
            opm = _fmt_pct(pm.get("operating_margin"))
            print(f"  {pm['ticker']:<8} {name:<22} {_fmt_num(pm.get('market_cap')):>10} "
                  f"{pe:>7} {roe:>7} {roic:>7} {opm:>7}")

    print(f"\n  {'-' * (W - 2)}")
    print("  --- INDUSTRY DYNAMICS ---")
    print(f"  {'-' * (W - 2)}")
    for label in _SECTION_LABELS:
        val = sections.get(label, "N/A")
        display_label = label.replace("_", " ").title()
        print(f"  {display_label}:")
        # Wrap long text
        words = val.split()
        line = "    "
        for w in words:
            if len(line) + len(w) + 1 > W:
                print(line)
                line = "    " + w
            else:
                line += " " + w if len(line) > 4 else w
        if line.strip():
            print(line)
        print()

    print(f"{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(profile: dict) -> dict:
    """
    Run industry & competitor analysis.
    Returns dict with peers, sections, peer_tickers.
    """
    ticker  = profile.get("ticker", "")
    company = profile.get("name") or ticker
    industry = profile.get("industry", "")
    sector   = profile.get("sector", "")

    print(f"\n  [Industry] Analysing industry for {company}...")

    is_us = _is_us_listed(ticker)
    peers = _fetch_peers(ticker, is_us, company, profile)
    print(f"  [Industry] Found {len(peers)} peers: {', '.join(peers)}")

    peer_metrics = _fetch_peer_metrics(peers) if peers else []
    print(f"  [Industry] Fetched metrics for {len(peer_metrics)} peers.")

    qualitative = _fetch_industry_qualitative(industry, sector, company, profile)
    print("  [Industry] Synthesising industry analysis...")

    sections = _synthesise(profile, peer_metrics, qualitative)

    _print_industry(profile, peer_metrics, sections)

    return {
        "peers":        peer_metrics,
        "sections":     sections,
        "peer_tickers": peers,
    }
