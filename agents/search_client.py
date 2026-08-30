# Unified web search abstraction: DuckDuckGo -> Tavily -> Claude Web Search tool
#
# All agents and server code import web_search() / web_search_content()
# from here instead of calling search APIs directly.

import os


def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Search the web via available providers in order:
    1. DuckDuckGo (free, zero API key)
    2. Tavily Search API (if TAVILY_API_KEY set)
    3. Claude Web Search Tool (if ANTHROPIC_API_KEY set)
    Returns list of {"title": str, "content": str, "url": str}.
    """
    # 1. Try DuckDuckGo
    ddg_res = _ddg_search(query, max_results)
    if ddg_res:
        return ddg_res

    # 2. Try Tavily
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        tav_res = _tavily_search(query, max_results, tavily_key)
        if tav_res:
            return tav_res

    # 3. Try Claude Web Search
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            return _claude_search(query, max_results, anthropic_key)
        except Exception as e:
            print(f"  [Warning] Claude web search unavailable ({type(e).__name__}: {e}).")

    print("  [Warning] No web search providers succeeded.")
    return []


def web_search_content(query: str, max_results: int = 4) -> str:
    """Search and return concatenated content string for LLM prompts."""
    results = web_search(query, max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results
    )


# -- Provider implementations --------------------------------------------------

def _ddg_search(query: str, max_results: int) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("body", ""),
                    "url": r.get("href", ""),
                })
        return results
    except Exception:
        # Fallback to simple requests if package not installed or fails
        try:
            import requests
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=10,
            )
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for a in soup.find_all("a", class_="result__snippet", limit=max_results):
                    results.append({
                        "title": a.get_text(strip=True),
                        "content": a.get_text(strip=True),
                        "url": a.get("href", ""),
                    })
                if results:
                    return results
        except Exception:
            pass
    return []


def _tavily_search(query: str, max_results: int, api_key: str) -> list[dict]:
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        res = client.search(query=query, max_results=max_results)
        results = []
        for r in res.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "url": r.get("url", ""),
            })
        return results
    except Exception as e:
        print(f"  [Warning] Tavily search failed ({e}).")
        return []


def _claude_search(query: str, max_results: int, api_key: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-3-7-sonnet-20250219"),
        max_tokens=1024,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_results,
        }],
        messages=[{
            "role": "user",
            "content": f"Search the web for: {query}\n\nReturn the key findings.",
        }],
    )

    results = []
    for block in resp.content:
        if block.type == "web_search_tool_result":
            content = block.content if isinstance(block.content, list) else []
            for item in content:
                if hasattr(item, "url"):
                    results.append({
                        "title": getattr(item, "title", ""),
                        "content": getattr(item, "text", "") or "",
                        "url": item.url,
                    })

    if not results:
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                results.append({
                    "title": "Search Summary",
                    "content": block.text,
                    "url": "",
                })
                break

    return results[:max_results]

