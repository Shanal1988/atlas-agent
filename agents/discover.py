# Hidden Gems Discovery — Find potential multibagger stocks across global markets
#
# Five-phase pipeline:
#   1. Tavily web search for trending industries/themes per region
#   2. LLM extracts top investment themes from search results
#   3. FMP stock-screener per region/exchange (quantitative filter)
#   4. Enrich top candidates with ratios (FMP + yfinance fallback)
#   5. LLM synthesizes ranked list with per-stock rationale
#
# Reuses patterns from similar_companies.py, discovery.py, fmp_client.py.

import json
import os

from groq import Groq
from tavily import TavilyClient

from agents.fmp_client import fmp_get
from agents.llm_client import gemini_call


# -- Constants -----------------------------------------------------------------

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

REGION_EXCHANGES = {
    "USA":    ["NYSE", "NASDAQ"],
    "UK":     ["LSE"],
    "Europe": ["EPA", "ETR", "AMS", "BIT", "BME"],
    "India":  ["NSE", "BSE"],
}

DEFAULT_THEMES = [
    {"theme": "AI and Cloud Infrastructure", "regions": ["USA", "Europe"]},
    {"theme": "Electric Vehicles and Battery Technology", "regions": ["USA", "Europe", "India"]},
    {"theme": "Digital Payments and Fintech", "regions": ["USA", "UK", "India"]},
    {"theme": "Cybersecurity", "regions": ["USA", "UK"]},
    {"theme": "Healthcare IT and Diagnostics", "regions": ["USA", "India"]},
    {"theme": "Renewable Energy and Green Hydrogen", "regions": ["India", "Europe"]},
    {"theme": "Semiconductor Equipment and Design", "regions": ["USA", "Europe"]},
    {"theme": "SaaS and Enterprise Software", "regions": ["USA", "UK", "Europe"]},
]


# -- Shared clients (lazy) ----------------------------------------------------

def _groq() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _tavily() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


# -- Formatters (reused from similar_companies.py) -----------------------------

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


# -- Phase 1: Web search for trending themes ----------------------------------

def _tavily_search(queries: list[str]) -> str:
    """Run Tavily searches, return concatenated results. Empty string on failure."""
    try:
        client = _tavily()
        all_content = []
        for q in queries:
            results = client.search(query=q, max_results=5)
            for r in results.get("results", []):
                all_content.append(f"[{r['title']}]\n{r['content']}")
        return "\n\n".join(all_content)
    except Exception as e:
        print(f"  [Warning] Tavily unavailable ({type(e).__name__}) — using default themes.")
        return ""


# -- Phase 2: LLM extracts themes ---------------------------------------------

def _extract_themes(trend_content: str, regions: list[str]) -> list[dict]:
    """LLM call to extract investment themes. Falls back to DEFAULT_THEMES."""
    if not trend_content:
        filtered = [t for t in DEFAULT_THEMES if any(r in t["regions"] for r in regions)]
        return filtered or DEFAULT_THEMES[:5]

    region_str = ", ".join(regions)
    prompt = (
        f"From the search results below, identify 5-8 high-growth investment themes "
        f"relevant to these regions: {region_str}.\n\n"
        "For each theme, provide:\n"
        "- theme: a concise name (3-6 words)\n"
        "- regions: which of the target regions it applies to\n"
        "- why: one sentence on why it's a growth opportunity\n\n"
        "Reply ONLY with valid JSON — an array of objects with keys: theme, regions, why.\n"
        "No markdown fences, no explanation.\n\n"
        f"Search results:\n{trend_content[:8000]}"
    )

    msgs = [{"role": "user", "content": prompt}]
    text = ""
    try:
        resp = _groq().chat.completions.create(
            model=GROQ_MODEL, messages=msgs, max_tokens=2048, temperature=0.3,
        )
        text = resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        text = gemini_call(msgs, max_tokens=2048, temperature=0.3, stage="discover_themes")

    if text:
        try:
            # Strip markdown fences if present
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            themes = json.loads(clean)
            if isinstance(themes, list) and themes:
                return themes[:8]
        except (json.JSONDecodeError, TypeError):
            pass

    # All LLMs failed — use defaults
    print("  [Warning] Could not extract themes from LLM — using defaults.")
    filtered = [t for t in DEFAULT_THEMES if any(r in t["regions"] for r in regions)]
    return filtered or DEFAULT_THEMES[:5]


# -- Phase 3: Discover candidate tickers via Tavily + LLM ---------------------
# FMP /stock-screener is not available on all plans, so we use web search +
# LLM to discover specific ticker symbols, then enrich via /profile + /ratios.

def _discover_tickers(region: str, sector: str | None, themes: list[dict]) -> list[dict]:
    """Use Tavily + LLM to discover hidden gem tickers for a region."""
    sector_str = f" in the {sector} sector" if sector else ""
    theme_names = [t.get("theme", "") for t in themes if region in t.get("regions", [region])]
    theme_hint = f" Focus on themes: {', '.join(theme_names[:4])}." if theme_names else ""

    queries = [
        f"best hidden gem stocks {region}{sector_str} 2025 2026 small mid cap multibagger",
        f"undervalued growth stocks {region}{sector_str} high ROIC revenue growth",
    ]

    search_content = _tavily_search(queries)
    if not search_content:
        return []

    prompt = (
        f"From the search results below, extract 15-25 specific stock ticker symbols "
        f"of hidden gem / high-growth companies in {region}{sector_str}.{theme_hint}\n\n"
        "Requirements:\n"
        "- Small to mid cap ($200M - $50B market cap)\n"
        "- High revenue growth or strong competitive position\n"
        "- Include the stock exchange suffix for non-US tickers "
        "(e.g. .L for London, .NS for NSE India, .BO for BSE India, "
        ".PA for Paris, .DE for Frankfurt, .AS for Amsterdam, .MI for Milan, .MC for Madrid)\n"
        "- US tickers need no suffix (e.g. CRWD, AXON)\n\n"
        "Reply ONLY with valid JSON — an array of objects with keys: "
        "ticker, name, region.\n"
        "No markdown fences, no explanation.\n\n"
        f"Search results:\n{search_content[:8000]}"
    )

    msgs = [{"role": "user", "content": prompt}]
    text = ""
    try:
        resp = _groq().chat.completions.create(
            model=GROQ_MODEL, messages=msgs, max_tokens=2048, temperature=0.3,
        )
        text = resp.choices[0].message.content
    except Exception as e:
        print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
        text = gemini_call(msgs, max_tokens=2048, temperature=0.3, stage="discover_tickers")

    if text:
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            tickers = json.loads(clean)
            if isinstance(tickers, list):
                for t in tickers:
                    t["_region"] = region
                return tickers[:25]
        except (json.JSONDecodeError, TypeError):
            pass

    return []


# -- Phase 4: Enrich candidates with profile + ratios -------------------------

def _enrich_candidates(candidates: list[dict], limit: int = 40) -> list[dict]:
    """Enrich candidates with financial metrics via yfinance."""
    import yfinance as yf

    enriched = []
    seen = set()
    for c in candidates[:limit]:
        symbol = c.get("ticker", "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        try:
            info = yf.Ticker(symbol).info or {}
            if not info.get("marketCap") and not info.get("longName"):
                continue
            enriched.append({
                "ticker":           symbol,
                "name":             info.get("longName") or info.get("shortName") or c.get("name"),
                "market_cap":       info.get("marketCap"),
                "price":            info.get("currentPrice") or info.get("regularMarketPrice"),
                "sector":           info.get("sector"),
                "industry":         info.get("industry"),
                "region":           c.get("_region"),
                "exchange":         info.get("fullExchangeName") or info.get("exchange", ""),
                "pe_ratio":         info.get("trailingPE"),
                "roe":              info.get("returnOnEquity"),
                "roic":             None,
                "revenue_growth":   info.get("revenueGrowth"),
                "operating_margin": info.get("operatingMargins"),
                "fcf_yield":        None,
            })
        except Exception:
            continue
    return enriched


# -- Phase 4b: Score and rank (from similar_companies.py) ----------------------

def _rank_candidates(candidates: list[dict]) -> list[dict]:
    """
    Score and rank candidates by multibagger potential (0-12 points).

    Criteria:
      - Revenue growth >15% (+2), >10% (+1)
      - ROIC >20% (+2), >15% (+1)
      - ROE >20% (+2), >15% (+1)
      - Operating margin >25% (+2), >15% (+1)
      - P/E 0-30 (+2), 0-50 (+1)
      - Market cap $200M-$5B (+2), $5B-$20B (+1)
    """
    for c in candidates:
        score = 0

        rg = c.get("revenue_growth")
        if rg is not None:
            if rg > 0.15:
                score += 2
            elif rg > 0.10:
                score += 1

        roic = c.get("roic")
        if roic is not None:
            if roic > 0.20:
                score += 2
            elif roic > 0.15:
                score += 1

        roe = c.get("roe")
        if roe is not None:
            if roe > 0.20:
                score += 2
            elif roe > 0.15:
                score += 1

        om = c.get("operating_margin")
        if om is not None:
            if om > 0.25:
                score += 2
            elif om > 0.15:
                score += 1

        pe = c.get("pe_ratio")
        if pe is not None and pe > 0:
            if pe < 30:
                score += 2
            elif pe < 50:
                score += 1

        mc = c.get("market_cap") or 0
        if 200_000_000 < mc < 5_000_000_000:
            score += 2
        elif 5_000_000_000 < mc < 20_000_000_000:
            score += 1

        c["multibagger_score"] = score

    candidates.sort(key=lambda x: x.get("multibagger_score", 0), reverse=True)
    return candidates


# -- Phase 5: LLM synthesis with rationale -------------------------------------

def _synthesize_results(candidates: list[dict], themes: list[dict]) -> list[dict]:
    """LLM adds per-stock rationale, theme tag, and CAGR potential."""
    if not candidates:
        return []

    top = candidates[:20]
    theme_names = [t.get("theme", "") for t in themes]

    stocks_json = json.dumps([
        {
            "ticker": c["ticker"],
            "name": c.get("name"),
            "sector": c.get("sector"),
            "industry": c.get("industry"),
            "region": c.get("region"),
            "market_cap": c.get("market_cap"),
            "revenue_growth": c.get("revenue_growth"),
            "roic": c.get("roic"),
            "roe": c.get("roe"),
            "operating_margin": c.get("operating_margin"),
            "pe_ratio": c.get("pe_ratio"),
            "score": c.get("multibagger_score"),
        }
        for c in top
    ], indent=2)

    prompt = (
        "You are an equity research analyst screening for hidden gem stocks — "
        "potential multibaggers or 20%+ CAGR opportunities.\n\n"
        f"Investment themes to consider: {json.dumps(theme_names)}\n\n"
        f"Candidate stocks (pre-screened and scored):\n{stocks_json}\n\n"
        "For each stock, provide:\n"
        "- ticker: the stock ticker\n"
        "- rationale: 2-3 sentences on why this is a hidden gem\n"
        "- theme_tag: which investment theme it best fits\n"
        "- cagr_potential: one of 'High 20%+', 'Moderate 15-20%', 'Speculative'\n\n"
        "Rank the top 15 by conviction. Reply ONLY with valid JSON — an array of objects.\n"
        "No markdown fences, no explanation."
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
        text = gemini_call(msgs, max_tokens=4096, temperature=0.3, stage="discover_synthesis")

    if text:
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            synthesis = json.loads(clean)
            if isinstance(synthesis, list):
                # Merge LLM rationale back into candidate data
                synth_by_ticker = {s["ticker"]: s for s in synthesis if "ticker" in s}
                for c in top:
                    s = synth_by_ticker.get(c["ticker"], {})
                    c["rationale"] = s.get("rationale", "")
                    c["theme_tag"] = s.get("theme_tag", "")
                    c["cagr_potential"] = s.get("cagr_potential", "")
                # Re-order by LLM conviction ranking
                llm_order = [s["ticker"] for s in synthesis if "ticker" in s]
                ordered = []
                for ticker in llm_order:
                    match = next((c for c in top if c["ticker"] == ticker), None)
                    if match:
                        ordered.append(match)
                # Append any candidates not in LLM output
                seen = set(llm_order)
                for c in top:
                    if c["ticker"] not in seen:
                        ordered.append(c)
                return ordered[:15]
        except (json.JSONDecodeError, TypeError):
            pass

    # LLM synthesis failed — return scored candidates without rationale
    print("  [Warning] LLM synthesis failed — returning scored results without rationale.")
    return top[:15]


# -- Output printer ------------------------------------------------------------

def _print_results(results: list[dict], themes: list[dict]) -> None:
    W = 72
    print(f"\n{'=' * W}")
    print("  ATLAS: HIDDEN GEMS DISCOVERY")
    print(f"{'=' * W}")

    if themes:
        print(f"\n  {'~' * (W - 4)}")
        print("  TRENDING THEMES:")
        for i, t in enumerate(themes, 1):
            theme_name = t.get("theme", "N/A")
            raw_regions = t.get("regions", [])
            regions = ", ".join(raw_regions) if isinstance(raw_regions, list) else str(raw_regions)
            why = t.get("why", "")
            print(f"  {i}. {theme_name} ({regions})")
            if why:
                print(f"     {why}")
        print(f"  {'~' * (W - 4)}")

    if not results:
        print("\n  No hidden gem candidates found matching criteria.")
        print(f"\n{'=' * W}\n")
        return

    print(f"\n  TOP {len(results)} HIDDEN GEM CANDIDATES:")
    print(f"  {'-' * (W - 4)}")

    for i, s in enumerate(results, 1):
        name = (s.get("name") or "")[:35]
        pe_str = f"{s['pe_ratio']:.1f}" if s.get("pe_ratio") else "N/A"
        region = s.get("region", "")
        exchange = s.get("exchange", "")

        print(f"\n  {i}. {s['ticker']} — {name}")
        print(f"     Region:      {region} ({exchange})")
        print(f"     Sector:      {s.get('sector', 'N/A')} / {s.get('industry', 'N/A')}")
        print(f"     Mkt Cap:     {_fmt_num(s.get('market_cap'))}")
        print(f"     Rev Growth:  {_fmt_pct(s.get('revenue_growth'))}")
        print(f"     ROIC:        {_fmt_pct(s.get('roic'))}")
        print(f"     ROE:         {_fmt_pct(s.get('roe'))}")
        print(f"     Op Margin:   {_fmt_pct(s.get('operating_margin'))}")
        print(f"     P/E:         {pe_str}")
        print(f"     Score:       {s.get('multibagger_score', 0)}/12")

        if s.get("cagr_potential"):
            print(f"     CAGR Est:    {s['cagr_potential']}")
        if s.get("theme_tag"):
            print(f"     Theme:       {s['theme_tag']}")
        if s.get("rationale"):
            print(f"     Rationale:   {s['rationale']}")

    print(f"\n{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def run(regions: list[str], sector: str | None = None) -> list[dict]:
    """Main orchestrator for hidden gems discovery."""
    region_str = ", ".join(regions)
    sector_str = sector or "all sectors"
    print(f"\nAtlas Hidden Gems Discovery")
    print(f"  Regions: {region_str}")
    print(f"  Sector:  {sector_str}")

    # Phase 1: Web search for trending themes
    print(f"\n  [1/5] Searching for trending investment themes...")
    queries = [
        f"best growth industries {region_str} 2025 2026 investing",
        f"emerging market trends {region_str} high growth sectors",
        f"hidden gem stocks multibagger opportunities {region_str}",
    ]
    trend_content = _tavily_search(queries)

    # Phase 2: Extract themes
    print(f"  [2/5] Extracting investment themes...")
    themes = _extract_themes(trend_content, regions)
    print(f"        -> Found {len(themes)} themes")
    for t in themes:
        print(f"           - {t.get('theme', 'N/A')}")

    # Phase 3: Discover candidate tickers per region
    print(f"\n  [3/5] Discovering candidate stocks across {len(regions)} region(s)...")
    all_candidates = []
    for region in regions:
        print(f"        -> Searching {region}...", end="")
        candidates = _discover_tickers(region, sector, themes)
        print(f" {len(candidates)} tickers found")
        all_candidates.extend(candidates)

    if not all_candidates:
        print("  [Warning] No candidate tickers found.")
        _print_results([], themes)
        return []

    print(f"        -> Total: {len(all_candidates)} tickers across all regions")

    # Phase 4: Enrich and rank
    enrich_limit = min(len(all_candidates), 40)
    print(f"\n  [4/5] Enriching top {enrich_limit} candidates with financial ratios...")
    enriched = _enrich_candidates(all_candidates, limit=enrich_limit)
    print(f"        -> Enriched {len(enriched)} candidates")

    if not enriched:
        print("  [Warning] Could not enrich any candidates.")
        _print_results([], themes)
        return []

    ranked = _rank_candidates(enriched)
    top_scored = [c for c in ranked if c.get("multibagger_score", 0) >= 3]
    if len(top_scored) < 5:
        top_scored = ranked[:20]
    print(f"        -> {len(top_scored)} candidates scored 3+ out of 12")

    # Phase 5: LLM synthesis
    print(f"\n  [5/5] Synthesizing results with AI analysis...")
    results = _synthesize_results(top_scored, themes)
    print(f"        -> Final list: {len(results)} hidden gems")

    _print_results(results, themes)
    return results
