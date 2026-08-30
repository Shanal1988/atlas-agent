# Shared multi-provider LLM client (Groq -> Gemini -> OpenRouter fallback).
#
# Usage: from agents.llm_client import claude_call
# Called via call_llm() in agents/context.py.

import os

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")


def claude_call(
    messages:    list,
    max_tokens:  int,
    temperature: float,
    stage:       str = "",
) -> str:
    """
    Primary LLM entrypoint. Tries configured free-tier LLMs in order:
    1. Groq (if GROQ_API_KEY is set)
    2. Gemini (if GEMINI_API_KEY is set)
    3. OpenRouter free tier (if OPENROUTER_API_KEY is set)
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

    # 3. OpenRouter free tier (replaces Anthropic + OpenAI)
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        res = _openrouter_call(messages, max_tokens, temperature, stage)
        if res:
            return res

    suffix = f" -- {stage} skipped" if stage else ""
    print(f"  [Warning] No working LLM API keys configured (GROQ, GEMINI, OPENROUTER){suffix}.")
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


def _openrouter_call(messages: list, max_tokens: int, temperature: float, stage: str) -> str:
    """
    OpenRouter free-tier fallback. Uses the OpenAI-compatible API at
    https://openrouter.ai/api/v1 with free models. Cycles through models
    on rate-limit (429) or error, just like the Groq/Gemini providers.
    """
    models_to_try = [
        OPENROUTER_MODEL,
        "deepseek/deepseek-r1-0528:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "meta-llama/llama-4-maverick:free",
        "qwen/qwen3-235b-a22b:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]
    # Deduplicate while preserving order
    models_to_try = list(dict.fromkeys(models_to_try))

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return ""

    for m in models_to_try:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/Shanal1988/atlas-agent",
                    "X-Title": "Atlas Agent",
                },
            )
            resp = client.chat.completions.create(
                model=m,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = resp.choices[0].message.content or ""
            if content:
                return content
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower() or "quota" in err.lower():
                print(f"  [Warning] OpenRouter model '{m}' rate-limited (429), trying next model...")
                continue
            print(f"  [Warning] OpenRouter model '{m}' unavailable ({type(e).__name__}: {e}), trying next model...")
            continue
    return ""


