# Hidden Gems Discovery Feature — CLI Implementation Plan

## Context
Atlas Agent currently analyzes one company at a time via `python main.py <company>`. The user wants a **CLI stock discovery tool** to find hidden gems — potential multibaggers or 20%+ CAGR stocks in growing industries across USA, UK, Europe, and India. Run it from the command line, no web/frontend changes needed.

## Usage
```bash
python discover.py                          # defaults: USA, all sectors
python discover.py --regions USA UK India   # multiple regions
python discover.py --sector Technology      # filter by sector
python discover.py --regions India --sector "Consumer Defensive"
```

## Architecture

Single CLI script (`discover.py`) + one new agent module (`agents/discover.py`). Five phases:

```
Phase 1: Tavily web search for trending industries/themes per region
Phase 2: LLM extracts top investment themes from search results
Phase 3: FMP stock-screener per region/exchange (quantitative filter)
Phase 4: Enrich top candidates with ratios (FMP + yfinance fallback)
Phase 5: LLM synthesizes ranked list with per-stock rationale
→ Print formatted results to terminal
→ Optionally save to data/discover/ as JSON
```

## Files to Create

### 1. `agents/discover.py` — Core discovery logic

Reuses patterns from `agents/similar_companies.py` and `agents/discovery.py`.

```python
REGION_EXCHANGES = {
    "USA":    ["NYSE", "NASDAQ"],
    "UK":     ["LSE"],
    "Europe": ["EPA", "ETR", "AMS", "BIT", "BME"],
    "India":  ["NSE", "BSE"],
}

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

DEFAULT_THEMES = [...]  # Fallback if Tavily unavailable
```

**Functions:**

- `_tavily_search(queries: list[str]) -> str` — Tavily web search, wrapped in try/except. If Tavily fails/rate-limited, returns empty string.
- `_extract_themes(trend_content, regions) -> list[dict]` — LLM call with full fallback chain:
  ```python
  try:
      resp = _groq().chat.completions.create(model=GROQ_MODEL, messages=msgs, ...)
      text = resp.choices[0].message.content
  except Exception as e:
      print(f"  [Warning] Groq unavailable ({type(e).__name__}), trying Gemini...")
      from agents.llm_client import gemini_call
      text = gemini_call(msgs, max_tokens=2048, temperature=0.3, stage="discover_themes")
      # gemini_call internally falls back to Claude Haiku if Gemini also fails
  ```
  If all LLMs fail, use `DEFAULT_THEMES`.

- `_screen_region(region, sector) -> list[dict]` — FMP screener via `fmp_get()` (429 retry built in). Params: exchange, mcap $200M-$50B, actively trading, optional sector. If FMP quota exhausted (circuit-breaker), skip region with warning.

- `_enrich_candidates(candidates, limit=40) -> list[dict]` — Fetch `/ratios` per stock via `fmp_get()`. If FMP returns None for a symbol, fall back to `yf_company_metrics(symbol)` from `agents/fmp_client.py` (same pattern as `similar_companies.py:203-237`).

- `_rank_candidates(candidates) -> list[dict]` — Copy scoring logic from `similar_companies.py:110-169`. Score 0-12 based on rev growth, ROIC, ROE, op margin, P/E, mcap.

- `_synthesize_results(candidates, themes) -> list[dict]` — LLM call with same Groq → Gemini → Haiku fallback. Adds per-stock: `rationale` (2-3 sentences), `theme_tag`, `cagr_potential` ("High 20%+", "Moderate 15-20%", "Speculative").

- `_print_results(results, themes)` — Formatted terminal output (matches style of `similar_companies.py:174-198`).

- `run(regions, sector) -> list[dict]` — Main orchestrator calling all above functions in sequence, printing progress at each step.

**Fallback Chain** (matches all existing agents):

| Component | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|-----------|---------|------------|------------|------------|
| LLM | Groq (llama-4-scout-17b) | Gemini 2.5 Flash | Claude Haiku | DEFAULT_THEMES / skip |
| Web Search | Tavily | — | DEFAULT_THEMES | — |
| Stock Data | FMP screener + ratios | yfinance (`yf_company_metrics`) | Skip candidate | — |
| FMP Rate Limit | 429 retry (2s,4s,8s) | Daily quota circuit-breaker | yfinance fallback | — |

### 2. `discover.py` — CLI entry point (root level, next to `main.py`)

```python
import sys, argparse
from dotenv import load_dotenv
load_dotenv()

# UTF-8 stdout fix (same as main.py)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents.discover import run

def main():
    parser = argparse.ArgumentParser(description="Discover hidden gem stocks")
    parser.add_argument("--regions", nargs="+", default=["USA"],
                        choices=["USA", "UK", "Europe", "India"])
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter by sector (e.g. Technology, Healthcare)")
    parser.add_argument("--save", action="store_true",
                        help="Save results to data/discover/")
    args = parser.parse_args()

    results = run(args.regions, args.sector)

    if args.save and results:
        # Save JSON to data/discover/{date}_{regions}.json
        ...

if __name__ == "__main__":
    main()
```

## Key Files to Reuse
- `agents/similar_companies.py` — `_enrich_candidates()` (line 81), `_rank_candidates()` (line 110), `_enrich_peer_tickers()` yfinance fallback (line 203)
- `agents/llm_client.py` — `gemini_call()` as Gemini → Claude Haiku fallback chain
- `agents/fmp_client.py` — `fmp_get()` with 429 retry, `yf_company_metrics()` for yfinance fallback
- `agents/discovery.py` — Groq + Tavily patterns, `_groq()` / `_tavily()` lazy init

## FMP Rate Limits
~42-48 FMP calls per run (2-8 screener + ~40 enrichment). Existing circuit breaker handles quota exhaustion — candidates without enrichment data get yfinance fallback or lower scores.

## Verification
1. `python discover.py` — should print trending themes + ranked stocks for USA
2. `python discover.py --regions India --sector Technology` — India tech stocks
3. `python discover.py --regions USA UK Europe India` — all regions
4. Test with `GROQ_API_KEY` unset → should fall back to Gemini → Haiku
5. Test with `TAVILY_API_KEY` unset → should use default themes and still screen stocks
6. `python discover.py --save` — should save JSON to `data/discover/`
