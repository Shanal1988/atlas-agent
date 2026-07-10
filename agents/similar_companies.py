# Similar Company Suggestions — Multibagger Screening
#
# Screens for companies in the same sector with multibagger characteristics:
#   - High revenue growth (>15%)
#   - Strong ROIC (>15%)
#   - High ROE (>15%)
#   - Good operating margins (>15%)
#   - Reasonable P/E (not extreme)
#   - Market cap sweet spot ($500M–$50B) for room to grow
#
# Pure quantitative — no LLM calls needed.

import os
import requests


# -- Constants -----------------------------------------------------------------

FMP_BASE = "https://financialmodelingprep.com/stable"


# -- FMP helper ----------------------------------------------------------------

def _fmp(endpoint: str, params: dict) -> list | None:
    from agents.fmp_client import fmp_get
    return fmp_get(endpoint, params)


# -- Formatters ----------------------------------------------------------------

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


# -- Screening -----------------------------------------------------------------

def _screen_candidates(sector: str, industry: str, exclude_ticker: str) -> list[dict]:
    """Screen FMP for potential multibagger candidates in the same sector/industry."""
    # Try industry-specific first for more relevant results
    for search_params in [
        {"industry": industry, "marketCapMoreThan": 500_000_000,
         "marketCapLowerThan": 50_000_000_000, "isActivelyTrading": True, "limit": 30},
        {"sector": sector, "marketCapMoreThan": 500_000_000,
         "marketCapLowerThan": 50_000_000_000, "isActivelyTrading": True, "limit": 30},
        {"sector": sector, "marketCapMoreThan": 200_000_000,
         "marketCapLowerThan": 100_000_000_000, "isActivelyTrading": True, "limit": 30},
    ]:
        results = _fmp("/stock-screener", search_params)
        if results:
            candidates = [
                r for r in results
                if r.get("symbol", "").upper() != exclude_ticker.upper()
            ]
            if candidates:
                return candidates

    return []


def _enrich_candidates(candidates: list[dict], limit: int = 10) -> list[dict]:
    """Fetch ratios for screening candidates."""
    enriched = []
    for c in candidates[:limit]:
        symbol = c.get("symbol")
        try:
            ratios = _fmp("/ratios", {"symbol": symbol, "limit": 1})
            r = ratios[0] if ratios else {}
            enriched.append({
                "ticker":           symbol,
                "name":             c.get("companyName"),
                "market_cap":       c.get("marketCap"),
                "price":            c.get("price"),
                "sector":           c.get("sector"),
                "industry":         c.get("industry"),
                "pe_ratio":         r.get("priceToEarningsRatio"),
                "roe":              r.get("returnOnEquity"),
                "roic":             r.get("returnOnInvestedCapital"),
                "revenue_growth":   r.get("revenueGrowth"),
                "operating_margin": r.get("operatingProfitMargin"),
                "fcf_yield":        r.get("freeCashFlowYield"),
            })
        except Exception:
            continue
    return enriched


# -- Multibagger scoring -------------------------------------------------------

def _rank_candidates(candidates: list[dict]) -> list[dict]:
    """
    Score and rank candidates by multibagger potential (0-12 points).

    Criteria:
      - Revenue growth >15% (+2), >10% (+1)
      - ROIC >20% (+2), >15% (+1)
      - ROE >20% (+2), >15% (+1)
      - Operating margin >25% (+2), >15% (+1)
      - P/E 0-30 (+2), 0-50 (+1)
      - Market cap $500M-$5B (+2), $5B-$20B (+1)
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
        if 500_000_000 < mc < 5_000_000_000:
            score += 2
        elif 5_000_000_000 < mc < 20_000_000_000:
            score += 1

        c["multibagger_score"] = score

    candidates.sort(key=lambda x: x.get("multibagger_score", 0), reverse=True)
    return candidates


# -- Output printer ------------------------------------------------------------

def _print_suggestions(suggestions: list[dict]) -> None:
    W = 62
    print(f"\n{'=' * W}")
    print("  ATLAS: SIMILAR COMPANIES (Potential Multibaggers)")
    print(f"{'=' * W}")

    if not suggestions:
        print("  No candidates found matching screening criteria.")
        print(f"{'=' * W}\n")
        return

    for i, s in enumerate(suggestions, 1):
        name = (s.get("name") or "")[:30]
        pe_str = f"{s['pe_ratio']:.1f}" if s.get("pe_ratio") else "N/A"
        print(f"\n  {i}. {s['ticker']} — {name}")
        print(f"     Industry:    {s.get('industry', 'N/A')}")
        print(f"     Mkt Cap:     {_fmt_num(s.get('market_cap'))}")
        print(f"     Rev Growth:  {_fmt_pct(s.get('revenue_growth'))}")
        print(f"     ROIC:        {_fmt_pct(s.get('roic'))}")
        print(f"     ROE:         {_fmt_pct(s.get('roe'))}")
        print(f"     Op Margin:   {_fmt_pct(s.get('operating_margin'))}")
        print(f"     P/E:         {pe_str}")
        print(f"     Score:       {s.get('multibagger_score', 0)}/12")

    print(f"\n{'=' * W}\n")


# -- Entry point ---------------------------------------------------------------

def _enrich_peer_tickers(peer_tickers: list[str], exclude_ticker: str) -> list[dict]:
    """Fallback: enrich peer tickers from industry analysis when FMP screener returns nothing."""
    enriched = []
    for symbol in peer_tickers:
        if symbol.upper() == exclude_ticker.upper():
            continue
        try:
            profile = _fmp("/profile", {"symbol": symbol})
            ratios = _fmp("/ratios", {"symbol": symbol, "limit": 1})
            if not profile:
                continue
            p = profile[0]
            r = ratios[0] if ratios else {}
            enriched.append({
                "ticker":           symbol,
                "name":             p.get("companyName"),
                "market_cap":       p.get("marketCap"),
                "price":            p.get("price"),
                "sector":           p.get("sector"),
                "industry":         p.get("industry"),
                "pe_ratio":         r.get("priceToEarningsRatio"),
                "roe":              r.get("returnOnEquity"),
                "roic":             r.get("returnOnInvestedCapital"),
                "revenue_growth":   r.get("revenueGrowth"),
                "operating_margin": r.get("operatingProfitMargin"),
                "fcf_yield":        r.get("freeCashFlowYield"),
            })
        except Exception:
            continue
    return enriched


def run(profile: dict, industry_result: dict | None = None) -> list[dict]:
    """
    Screen for similar companies with multibagger potential.
    Returns top 5 ranked suggestions.
    """
    ticker   = profile.get("ticker", "")
    sector   = profile.get("sector", "")
    industry = profile.get("industry", "")

    if not sector:
        print("\n  [Similar] No sector data — skipping multibagger screening.")
        return []

    print(f"\n  [Similar] Screening for multibagger candidates in {sector}...")

    candidates = _screen_candidates(sector, industry, ticker)
    if candidates:
        print(f"  [Similar] Found {len(candidates)} candidates, enriching top 10...")
        enriched = _enrich_candidates(candidates)
    else:
        # Fallback: reuse peer data from industry analysis (already fetched)
        peer_data = (industry_result or {}).get("peers", [])
        if peer_data:
            print(f"  [Similar] FMP screener empty — using {len(peer_data)} peers from industry analysis...")
            enriched = []
            for pm in peer_data:
                if pm.get("ticker", "").upper() == ticker.upper():
                    continue
                enriched.append({
                    "ticker":           pm.get("ticker"),
                    "name":             pm.get("name"),
                    "market_cap":       pm.get("market_cap"),
                    "price":            pm.get("price"),
                    "sector":           pm.get("sector"),
                    "industry":         pm.get("industry"),
                    "pe_ratio":         pm.get("pe_ratio"),
                    "roe":              pm.get("roe"),
                    "roic":             pm.get("roic"),
                    "revenue_growth":   pm.get("revenue_growth"),
                    "operating_margin": pm.get("operating_margin"),
                    "fcf_yield":        None,
                })
        else:
            print("  [Similar] No candidates found.")
            return []

    if not enriched:
        print("  [Similar] No candidates could be enriched.")
        return []

    ranked = _rank_candidates(enriched)

    top = ranked[:5]
    _print_suggestions(top)
    return top
