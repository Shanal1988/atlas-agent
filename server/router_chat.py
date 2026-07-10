import json
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from server.models import ChatResponse, ChatSource, ProposedUpdate

router = APIRouter()
THESES_DIR = Path("data/theses")
UPLOADS_DIR = Path("data/uploads")

CHAT_MODEL = "claude-sonnet-4-6"

_WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for real-time information about the company, market conditions, "
        "recent earnings, news, competitor moves, or any topic the user asks about. "
        "Use this when the question requires information more recent than the analysis date."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"}
        },
        "required": ["query"],
    },
}

_UPDATE_THESIS_TOOL = {
    "name": "update_thesis",
    "description": (
        "Propose an update to the investment thesis based on new information in the conversation. "
        "Call this when the discussion reveals something that should change the thesis, a score, "
        "the decision, bull/bear cases, or watch points. The user will review and confirm the change."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "description": "Dot-path to the field being updated, e.g. 'thesis.decision', 'thesis.bull_case', 'bmp.answers.0.rating'",
            },
            "old_value": {"type": "string", "description": "The current value (for display)"},
            "new_value": {"type": "string", "description": "The proposed new value"},
            "reason": {"type": "string", "description": "Why this change is warranted"},
        },
        "required": ["field", "new_value", "reason"],
    },
}


def _run_web_search(query: str) -> tuple[str, list[dict]]:
    """Run Tavily search, return (content_for_claude, sources_list)."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
        result = client.search(query=query, max_results=5)
        sources = []
        snippets = []
        for r in result.get("results", []):
            sources.append({"title": r.get("title", ""), "url": r.get("url", "")})
            snippets.append(f"**{r.get('title', '')}** ({r.get('url', '')})\n{r.get('content', '')}")
        return "\n\n".join(snippets), sources
    except Exception as e:
        return f"Search failed: {e}", []


def _load_upload_context(analysis_id: str) -> str:
    """Load text from uploaded files for this analysis as additional context."""
    upload_dir = UPLOADS_DIR / analysis_id
    if not upload_dir.exists():
        return ""
    texts = []
    for f in upload_dir.iterdir():
        try:
            if f.suffix.lower() == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(str(f))
                text = "\n".join(p.extract_text() or "" for p in reader.pages[:5])
            else:
                text = f.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                texts.append(f"=== {f.name} ===\n{text[:3000]}")
        except Exception:
            continue
    return "\n\n".join(texts)


def _extract_file_text(content: bytes, filename: str) -> str:
    """Return text content of an uploaded file (for inline chat context)."""
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages[:10])[:6000]
        elif suffix in (".xlsx", ".xls"):
            import openpyxl, io
            from server.financial_parser import _FIN_ROW_KEYWORDS
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            relevant, fallback = [], []
            for sheet in wb.worksheets:
                header_added = False
                for row in sheet.iter_rows(values_only=True):
                    r = "\t".join(str(c) if c is not None else "" for c in row).strip()
                    if not r:
                        continue
                    if any(k in r.lower() for k in _FIN_ROW_KEYWORDS):
                        if not header_added:
                            relevant.append(f"=== {sheet.title} ===")
                            header_added = True
                        relevant.append(r)
                    elif len(fallback) < 100:
                        fallback.append(r)
                    if len(relevant) >= 500:
                        break
                if len(relevant) >= 500:
                    break
            rows = relevant if relevant else fallback
            return "\n".join(rows)[:10000]
        else:
            return content.decode("utf-8", errors="replace")[:6000]
    except Exception as e:
        return f"[Could not read file: {e}]"


@router.post("/chat/{analysis_id}", response_model=ChatResponse)
async def chat(
    analysis_id: str,
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    path = THESES_DIR / f"{analysis_id}.json"
    if not path.exists():
        raise HTTPException(404, "Analysis not found")

    data = json.loads(path.read_text(encoding="utf-8"))
    formatted_thesis = data.get("formatted_thesis", "")
    company = data.get("company", "Unknown")
    ticker = data.get("ticker", "")

    if not formatted_thesis:
        raise HTTPException(422, "No formatted thesis available for this analysis")

    # Load any previously uploaded documents
    upload_context = _load_upload_context(analysis_id)
    upload_section = f"\n\n--- UPLOADED DOCUMENTS ---\n{upload_context}" if upload_context else ""

    system_prompt = (
        f"You are Atlas, an AI equity research analyst. You have performed a detailed "
        f"investment analysis of {company} ({ticker}).\n"
        f"Answer follow-up questions based on the analysis below. You can also search the web "
        f"for current information when needed.\n\n"
        f"THESIS UPDATES: Be proactive about keeping the thesis current. When the user:\n"
        f"- shares new information or their own research,\n"
        f"- uploads/attaches a file with relevant data,\n"
        f"- proposes a change or disagrees with part of the analysis,\n"
        f"- or when your web search reveals something material,\n"
        f"then ASK the user whether they'd like the thesis updated, and use the update_thesis "
        f"tool to propose specific section changes (executive_summary, bull_case, bear_case, "
        f"thesis_statement, watch_points, decision, decision_rationale). Propose one update per "
        f"changed section with a clear reason. The user reviews and confirms each change.\n\n"
        f"--- ANALYSIS ---\n{formatted_thesis}"
        f"{upload_section}"
    )

    # Build user message — append file content inline if provided
    user_content = message
    if file and file.filename:
        raw = await file.read()
        # Persist attachment so future chat turns can reference it
        try:
            upload_dir = UPLOADS_DIR / analysis_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / file.filename).write_bytes(raw)
        except Exception:
            pass
        file_text = _extract_file_text(raw, file.filename)
        user_content = (
            f"{message}\n\n"
            f"--- ATTACHED FILE: {file.filename} ---\n"
            f"{file_text}"
        )

    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": user_content}]
    tools = [_WEB_SEARCH_TOOL, _UPDATE_THESIS_TOOL]

    all_sources: list[dict] = []
    proposed_updates: list[dict] = []

    # Agentic loop: allow up to 5 tool calls
    for _ in range(5):
        resp = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=2048,
            temperature=0.3,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )

        # Collect tool use blocks
        tool_uses = [b for b in resp.content if b.type == "tool_use"]

        if not tool_uses:
            # Final answer
            text_blocks = [b for b in resp.content if b.type == "text"]
            answer = text_blocks[0].text if text_blocks else ""
            return ChatResponse(
                answer=answer,
                sources=([ChatSource(**s) for s in all_sources] if all_sources else None),
                proposed_updates=([ProposedUpdate(**u) for u in proposed_updates] if proposed_updates else None),
            )

        # Append assistant message
        messages.append({"role": "assistant", "content": resp.content})

        # Process each tool call
        tool_results = []
        for tool_use in tool_uses:
            if tool_use.name == "web_search":
                query = tool_use.input.get("query", "")
                content, sources = _run_web_search(query)
                all_sources.extend(sources)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": content,
                })
            elif tool_use.name == "update_thesis":
                proposed_updates.append(tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": "Update proposal recorded. The user will be shown this proposal to confirm.",
                })

        messages.append({"role": "user", "content": tool_results})

    # Fallback if loop exhausted
    resp = client.messages.create(
        model=CHAT_MODEL,
        max_tokens=1024,
        temperature=0.3,
        system=system_prompt,
        messages=messages,
    )
    text_blocks = [b for b in resp.content if b.type == "text"]
    answer = text_blocks[0].text if text_blocks else ""
    return ChatResponse(
        answer=answer,
        sources=([ChatSource(**s) for s in all_sources] if all_sources else None),
        proposed_updates=([ProposedUpdate(**u) for u in proposed_updates] if proposed_updates else None),
    )
