# Shared LLM fallback chain: Groq (in each agent) -> Gemini -> Claude Haiku
#
# Usage: from agents.llm_client import gemini_call
# Called by each agent after Groq fails to avoid silent blank output.

import os

GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

CLAUDE_MODEL    = os.environ.get("CLAUDE_FALLBACK_MODEL", "claude-haiku-4-5-20251001")

_SESSION_TOKEN_FILE = "/home/claude/.claude/remote/.session_ingress_token"


def _make_anthropic_client():
    """Return an Anthropic client using API key or session Bearer token."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        return anthropic.Anthropic(api_key=api_key)
    try:
        with open(_SESSION_TOKEN_FILE) as f:
            token = f.read().strip()
        if token:
            return anthropic.Anthropic(auth_token=token)
    except Exception:
        pass
    return None


def _claude_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Call Claude Haiku via the Anthropic SDK.
    Handles system message extraction (Anthropic expects it as a separate param).
    Returns the response string, or "" on any failure.
    """
    try:
        import anthropic
        client = _make_anthropic_client()
        if client is None:
            suffix = f" -- {stage} skipped" if stage else ""
            print(f"  [Warning] No Anthropic credentials available{suffix}.")
            return ""

        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        kwargs = dict(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=user_messages,
        )
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        return resp.content[0].text or ""
    except Exception as e:
        suffix = f" -- {stage} skipped" if stage else ""
        print(f"  [Warning] Claude unavailable ({type(e).__name__}){suffix}.")
        return ""


def gemini_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Call Gemini via its OpenAI-compatible REST endpoint.
    Falls back to Claude Haiku if Gemini is unavailable or rate-limited.
    Returns the response string, or "" if all fallbacks fail.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        suffix = f" -- trying Claude..." if stage else "trying Claude..."
        print(f"  [Warning] GEMINI_API_KEY not set -- {suffix}")
        return _claude_call(messages, max_tokens, temperature, stage)
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
        print(f"  [Warning] Gemini unavailable ({type(e).__name__}), trying Claude...")
        return _claude_call(messages, max_tokens, temperature, stage)
