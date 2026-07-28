# Unified web search abstraction: Claude web search tool
#
# All agents and server code import web_search() / web_search_content()
# from here instead of calling search APIs directly.

import os


def web_search(query: str, max_results: int = 4) -> list[dict]:
    """Search the web via Claude's built-in web search tool.
    Returns list of {"title": str, "content": str, "url": str}."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            return _claude_search(query, max_results, api_key)
        except Exception as e:
            print(f"  [Warning] Claude web search unavailable ({type(e).__name__}).")

    print("  [Warning] ANTHROPIC_API_KEY not configured for web search.")
    return []


def web_search_content(query: str, max_results: int = 4) -> str:
    """Search and return concatenated content string for LLM prompts."""
    results = web_search(query, max_results)
    return "\n\n".join(
        f"[{r['title']}]\n{r['content']}"
        for r in results
    )


# -- Provider implementation --------------------------------------------------

def _claude_search(query: str, max_results: int, api_key: str) -> list[dict]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
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

    # Extract search results from web_search_tool_result blocks
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

    # Fallback: extract text summary if no structured results
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
