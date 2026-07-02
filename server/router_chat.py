import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from server.models import ChatRequest, ChatResponse
from agents.llm_client import _claude_call

router = APIRouter()
THESES_DIR = Path("data/theses")

CHAT_MODEL = "claude-sonnet-4-6"


@router.post("/chat/{analysis_id}", response_model=ChatResponse)
def chat(analysis_id: str, req: ChatRequest):
    path = THESES_DIR / f"{analysis_id}.json"
    if not path.exists():
        raise HTTPException(404, "Analysis not found")

    data = json.loads(path.read_text(encoding="utf-8"))
    formatted_thesis = data.get("formatted_thesis", "")
    company = data.get("company", "Unknown")
    ticker = data.get("ticker", "")

    if not formatted_thesis:
        raise HTTPException(422, "No formatted thesis available for this analysis")

    system_prompt = (
        f"You are Atlas, an AI equity research analyst. You have performed a detailed "
        f"investment analysis of {company} ({ticker}).\n"
        f"Answer follow-up questions based strictly on this analysis. Be concise and direct.\n\n"
        f"--- ANALYSIS ---\n{formatted_thesis}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message},
    ]

    import anthropic
    api_key = __import__("os").environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=CHAT_MODEL,
        max_tokens=1024,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": req.message}],
    )
    answer = resp.content[0].text or ""
    return ChatResponse(answer=answer)
