# Shared multi-provider LLM client (Groq -> Gemini -> Claude -> OpenAI fallback).
#
# Usage: from agents.llm_client import claude_call
# Called via call_llm() in agents/context.py.

import os

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-3-7-sonnet-20250219")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def claude_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Primary LLM entrypoint. Tries configured free-tier/primary LLMs in order:
    1. Groq (if GROQ_API_KEY is set)
    2. Gemini (if GEMINI_API_KEY is set)
    3. Anthropic Claude (if ANTHROPIC_API_KEY is set)
    4. OpenAI (if OPENAI_API_KEY is set)
    Returns response string, or "" on failure.
    """
    # 1. Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        res = _groq_call(messages, max_tokens, temperature, stage)
        if res:
            return res

    # 2. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        res = _gemini_call(messages, max_tokens, temperature, stage)
        if res:
            return res

    # 3. Anthropic Claude
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        res = _anthropic_call(messages, max_tokens, temperature, stage)
        if res:
            return res

    # 4. OpenAI fallback
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        res = _openai_call(messages, max_tokens, temperature, stage)
        if res:
            return res

    suffix = f" -- {stage} skipped" if stage else ""
    print(f"  [Warning] No working LLM API keys configured (GROQ, GEMINI, ANTHROPIC, OPENAI){suffix}.")
    return ""


def _groq_call(messages: list, max_tokens: int, temperature: float, stage: str) -> str:
    models_to_try = [GROQ_MODEL, "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "groq/compound"]
    models_to_try = list(dict.fromkeys(models_to_try))
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""

    for m in models_to_try:
        try:
            try:
                from groq import Groq
                client = Groq(api_key=key)
                resp = client.chat.completions.create(
                    model=m,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
            except ImportError:
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
                resp = client.chat.completions.create(
                    model=m,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp.choices[0].message.content or ""
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                print(f"  [Warning] Groq model '{m}' rate-limited (429), trying next model...")
                continue
            print(f"  [Warning] Groq model '{m}' unavailable ({type(e).__name__}: {e}), trying next model...")
            continue
    return ""


def _gemini_call(messages: list, max_tokens: int, temperature: float, stage: str) -> str:
    models_to_try = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-2.5-pro"]
    models_to_try = list(dict.fromkeys(models_to_try))
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""

    prompt = ""
    for msg in messages:
        prompt += f"{msg['role'].upper()}: {msg['content']}\n\n"

    for m in models_to_try:
        try:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                )
                if resp.text:
                    return resp.text
            except ImportError:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
                resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    parts = data["candidates"][0]["content"]["parts"]
                    text_parts = [p.get("text", "") for p in parts if "text" in p]
                    res_text = "".join(text_parts)
                    if res_text:
                        return res_text
                elif resp.status_code == 429:
                    print(f"  [Warning] Gemini model '{m}' rate-limited (429), trying next model...")
                    continue
                else:
                    print(f"  [Warning] Gemini HTTP {resp.status_code}: {resp.text[:100]}")
                    continue
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"  [Warning] Gemini model '{m}' rate-limited (429), trying next model...")
                continue
            print(f"  [Warning] Gemini model '{m}' unavailable ({type(e).__name__}: {e}), trying next model...")
            continue
    return ""




def _anthropic_call(messages: list, max_tokens: int, temperature: float, stage: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
        print(f"  [Warning] Claude unavailable ({type(e).__name__}: {e}), trying next provider...")
        return ""


def _openai_call(messages: list, max_tokens: int, temperature: float, stage: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        print(f"  [Warning] OpenAI unavailable ({type(e).__name__}: {e}).")
        return ""

