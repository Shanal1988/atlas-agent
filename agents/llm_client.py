# Shared LLM client: Claude only.
#
# Usage: from agents.llm_client import claude_call
# Called via call_llm() in agents/context.py.

import os

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def claude_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Call Claude via the Anthropic SDK.
    Handles system message extraction (Anthropic expects it as a separate param).
    Returns the response string, or "" on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        suffix = f" -- {stage} skipped" if stage else ""
        print(f"  [Warning] ANTHROPIC_API_KEY not set{suffix}.")
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

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
