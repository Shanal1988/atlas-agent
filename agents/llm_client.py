# Shared LLM client: Gemini only.
#
# Usage: from agents.llm_client import gemini_call
# Called via call_llm() in agents/context.py.

import os

GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def gemini_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Call Gemini via its OpenAI-compatible REST endpoint.
    Returns the response string, or "" on failure.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        suffix = f" -- {stage} skipped" if stage else ""
        print(f"  [Warning] GEMINI_API_KEY not set{suffix}.")
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
        # Gemini 2.5 Flash thinking tokens count against max_tokens.
        # Thinking typically consumes 500-2000 tokens before any output is emitted,
        # so callers that pass small budgets (e.g. 16 for ticker, 512 for BMP)
        # get truncated. Use 8192 as the floor to cover thinking + full output.
        effective_tokens = max(max_tokens, 8192)
        resp = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=messages,
            max_tokens=effective_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        suffix = f" -- {stage} skipped" if stage else ""
        print(f"  [Warning] Gemini unavailable ({type(e).__name__}){suffix}.")
        return ""
