# Unified web search abstraction: Exa -> Tavily
#
# All agents and server code import web_search() / web_search_content()
# from here instead of calling search APIs directly.

import os


def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Search the web via Exa -> Tavily fallback chain.
    Returns list of {"title": str, "content": str, "url": str}."""

    exa_key = os.environ.get("EXA_API_KEY")
    if exa_key:
        try:
            return _exa_search(query, max_results, exa_key)
        except Exception as e:
            print(f"  [Warning] Exa unavailable ({type(e).__name__}), trying Tavily...")

    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        try:
            return _tavily_search(query, max_results, tavily_key)
        except Exception as e:
            print(f"  [Warning] Tavily unavailable ({type(e).__name__}).")

    print("  [Warning] No search API keys configured.")
    return []


def web_search_content(query: str, max_results: int = 4) -> str:
    """Search and return concatenated content string for LLM prompts."""
    results = web_search(query, max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results
    )


# -- Provider implementations -------------------------------------------------

def _exa_search(query: str, max_results: int, api_key: str) -> list[dict]:
    from exa_py import Exa
    exa = Exa(api_key=api_key)
    results = exa.search_and_contents(query, num_results=max_results, text=True)
    return [
        {"title": r.title or "", "content": r.text or "", "url": r.url or ""}
        for r in results.results[:max_results]
    ]


def _tavily_search(query: str, max_results: int, api_key: str) -> list[dict]:
    from tavily import TavilyClient
    client = TavilyClient(api_key=api_key)
    results = client.search(query=query, max_results=max_results)
    return [
        {"title": r.get("title", ""), "content": r.get("content", ""),
         "url": r.get("url", "")}
        for r in results.get("results", [])[:max_results]
    ]
