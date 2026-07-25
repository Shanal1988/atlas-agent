import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from server.models import ChatResponse, ChatSource, ProposedUpdate
from server.router_overrides import _overrides_path, OVERRIDES_DIR

router = APIRouter()
THESES_DIR = Path("data/theses")
UPLOADS_DIR = Path("data/uploads")
CHATS_DIR = Path("data/chats")

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
        "Propose or apply an update to the investment thesis based on new information in the "
        "conversation. Call this when the discussion reveals something that should change the "
        "thesis, a score, the decision, bull/bear cases, or watch points. With apply=false the "
        "update is only proposed for the user to review; with apply=true it is applied immediately."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "description": (
                    "Dot-path to the field being updated. Thesis sections MUST use the 'thesis.' prefix: "
                    "'thesis.executive_summary', 'thesis.bull_case', 'thesis.bear_case', 'thesis.thesis_statement', "
                    "'thesis.destination', 'thesis.watch_points', 'thesis.decision', 'thesis.decision_rationale', "
                    "'thesis.short_term_outlook', 'thesis.short_term_catalysts', 'thesis.short_term_risks', "
                    "'thesis.medium_term_outlook', 'thesis.medium_term_milestones'. "
                    "Score changes use 'bmp.answers.<idx>.rating' (value YES/PARTIAL/NO, idx 0-4) or "
                    "'fisher.points.<idx>.score' (value 0, 0.5, 0.75 or 1.0, idx 0-14). "
                    "Intrinsic-value figures in the valuation table use 'valuation.dhandho.lower.iv', "
                    "'valuation.dhandho.higher.iv', 'valuation.graham.lower', 'valuation.graham.higher', "
                    "'valuation.dcf.iv' or 'valuation.exp_returns.iv' — new_value MUST be the TOTAL "
                    "intrinsic value in MILLIONS of the reporting currency (e.g. '85000' for 85bn), "
                    "NOT a per-share figure. "
                    "No other fields exist — do not invent field names."
                ),
            },
            "old_value": {"type": "string", "description": "The current value (for display)"},
            "new_value": {"type": "string", "description": "The proposed new value"},
            "reason": {"type": "string", "description": "Why this change is warranted"},
            "apply": {
                "type": "boolean",
                "description": (
                    "Set to true ONLY when the user has explicitly confirmed in this conversation "
                    "that they want the change applied (e.g. 'apply them', 'yes, update it'). "
                    "Defaults to false (propose for review)."
                ),
            },
        },
        "required": ["field", "new_value", "reason"],
    },
}

# ── Server-side update validation & application ──────────────────────────────

_THESIS_KEYS = {
    "executive_summary", "bull_case", "bear_case", "thesis_statement",
    "destination", "watch_points", "decision", "decision_rationale",
    "short_term_outlook", "short_term_catalysts", "short_term_risks",
    "medium_term_outlook", "medium_term_milestones",
}
_THESIS_ARRAY_FIELDS = {
    "bull_case", "bear_case", "watch_points",
    "short_term_catalysts", "short_term_risks", "medium_term_milestones",
}
_BMP_RATING_SCORE = {"YES": 1.0, "PARTIAL": 0.5, "NO": 0.0}
_FISHER_SCORES = {0.0, 0.5, 0.75, 1.0}
_BULLET_RE = re.compile(r"^\s*(?:[-*•→↑↓!✓◉]|\d+[.)])\s*")
# Editable intrinsic-value figures (stored as a flat map in overrides.valuation,
# values are TOTAL IV in millions of the reporting currency)
_VALUATION_FIELDS = {
    "dhandho.lower.iv", "dhandho.higher.iv",
    "graham.lower", "graham.higher",
    "dcf.iv", "exp_returns.iv",
}


def _parse_valuation_value(value: str) -> Optional[float]:
    try:
        v = float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
    return v if v > 0 else None


def _bmp_verdict(score: float) -> str:
    if score >= 4:
        return "STRONG PASS"
    if score >= 3:
        return "PASS"
    if score >= 2:
        return "BORDERLINE"
    return "FAIL"


def _fisher_rating(total: float) -> str:
    if total >= 12:
        return "EXCELLENT"
    if total >= 9:
        return "GOOD"
    if total >= 6:
        return "FAIR"
    return "POOR"


def _to_list_items(value: str) -> list[str]:
    lines = [_BULLET_RE.sub("", l).strip() for l in value.split("\n")]
    lines = [l for l in lines if l]
    return lines if len(lines) > 1 else [value.strip()]


def _load_overrides(analysis_id: str) -> dict:
    path = _overrides_path(analysis_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_overrides(analysis_id: str, overrides: dict) -> None:
    OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    overrides["analysis_id"] = analysis_id
    overrides["last_modified"] = datetime.now(timezone.utc).isoformat()
    _overrides_path(analysis_id).write_text(
        json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _invalid_field_msg(field: str) -> str:
    return (
        f"Invalid field '{field}'. Valid fields are: "
        + ", ".join(f"thesis.{k}" for k in sorted(_THESIS_KEYS))
        + ", bmp.answers.<idx>.rating (idx 0-4, value YES/PARTIAL/NO), "
        "fisher.points.<idx>.score (idx 0-14, value 0/0.5/0.75/1.0), "
        + ", ".join(f"valuation.{k}" for k in sorted(_VALUATION_FIELDS))
        + " (value: total IV in millions of the reporting currency). "
        "Re-issue the update with a valid field."
    )


def _validate_update(analysis: dict, update: dict) -> Optional[str]:
    """Return an error message if the update is invalid, else None."""
    field = update.get("field", "")
    new_value = str(update.get("new_value", ""))

    thesis_key = field[7:] if field.startswith("thesis.") else field
    if thesis_key in _THESIS_KEYS:
        return None

    m = re.match(r"^bmp\.answers\.(\d+)\.rating$", field)
    if m:
        n = len(analysis.get("scores", {}).get("bmp", {}).get("answers", []))
        if int(m.group(1)) >= n:
            return f"BMP answer index out of range (0-{n - 1})."
        if new_value.strip().upper() not in _BMP_RATING_SCORE:
            return "BMP rating must be YES, PARTIAL or NO."
        return None

    m = re.match(r"^fisher\.points\.(\d+)\.score$", field)
    if m:
        n = len(analysis.get("scores", {}).get("fisher", {}).get("points", []))
        if int(m.group(1)) >= n:
            return f"Fisher point index out of range (0-{n - 1})."
        try:
            score = float(new_value)
        except ValueError:
            return "Fisher score must be a number: 0, 0.5, 0.75 or 1.0."
        if score not in _FISHER_SCORES:
            return "Fisher score must be 0, 0.5, 0.75 or 1.0."
        return None

    if field.startswith("valuation."):
        sub = field[10:]
        if sub not in _VALUATION_FIELDS:
            return _invalid_field_msg(field)
        if _parse_valuation_value(new_value) is None:
            return (
                "Valuation value must be a positive number: the TOTAL intrinsic value in "
                "MILLIONS of the reporting currency (not per-share)."
            )
        return None

    return _invalid_field_msg(field)


def _apply_update(analysis_id: str, analysis: dict, update: dict) -> str:
    """Apply a validated update to the overrides file. Returns a status message."""
    field = update.get("field", "")
    new_value = str(update.get("new_value", ""))
    overrides = _load_overrides(analysis_id)

    thesis_key = field[7:] if field.startswith("thesis.") else field
    if thesis_key in _THESIS_KEYS:
        thesis = overrides.setdefault("thesis", {})
        thesis[thesis_key] = (
            _to_list_items(new_value) if thesis_key in _THESIS_ARRAY_FIELDS else new_value
        )
        _write_overrides(analysis_id, overrides)
        return f"Applied update to thesis.{thesis_key}. The page now shows the new value."

    m = re.match(r"^bmp\.answers\.(\d+)\.rating$", field)
    if m:
        idx = int(m.group(1))
        rating = new_value.strip().upper()
        answers = overrides.get("bmp", {}).get("answers") or [
            {
                "label": a.get("label", ""),
                "rating": a.get("rating", "NO"),
                "reasoning": a.get("reasoning", ""),
                "user_note": "",
            }
            for a in analysis.get("scores", {}).get("bmp", {}).get("answers", [])
        ]
        answers[idx] = {**answers[idx], "rating": rating}
        score = sum(_BMP_RATING_SCORE.get(a.get("rating", "NO"), 0.0) for a in answers)
        overrides["bmp"] = {"answers": answers, "score": score, "verdict": _bmp_verdict(score)}
        _write_overrides(analysis_id, overrides)
        return f"Applied BMP rating change (new score: {score}, verdict: {_bmp_verdict(score)})."

    m = re.match(r"^fisher\.points\.(\d+)\.score$", field)
    if m:
        idx = int(m.group(1))
        score = float(new_value)
        points = overrides.get("fisher", {}).get("points") or [
            {
                "key": p.get("key", ""),
                "label": p.get("label", ""),
                "score": p.get("score", 0),
                "reasoning": p.get("reasoning", ""),
                "user_note": "",
            }
            for p in analysis.get("scores", {}).get("fisher", {}).get("points", [])
        ]
        points[idx] = {**points[idx], "score": score}
        total = sum(float(p.get("score", 0)) for p in points)
        overrides["fisher"] = {"points": points, "total": total, "rating": _fisher_rating(total)}
        _write_overrides(analysis_id, overrides)
        return f"Applied Fisher score change (new total: {total}, rating: {_fisher_rating(total)})."

    if field.startswith("valuation."):
        sub = field[10:]
        value = _parse_valuation_value(new_value)
        valuation = overrides.setdefault("valuation", {})
        valuation[sub] = value
        _write_overrides(analysis_id, overrides)
        return f"Applied valuation change: {sub} = {value} mn. The valuation table now shows the new figure."

    return _invalid_field_msg(field)


def _chat_path(analysis_id: str) -> Path:
    return CHATS_DIR / f"{analysis_id}.json"


def _load_chat(analysis_id: str) -> list[dict]:
    path = _chat_path(analysis_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_chat(analysis_id: str, messages: list[dict]) -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    _chat_path(analysis_id).write_text(
        json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _run_web_search(query: str) -> tuple[str, list[dict]]:
    """Run web search (Brave -> Exa -> Tavily), return (content_for_claude, sources_list)."""
    try:
        from agents.search_client import web_search
        results = web_search(query, max_results=5)
        sources = [{"title": r["title"], "url": r["url"]} for r in results]
        snippets = [
            f"**{r['title']}** ({r['url']})\n{r['content']}"
            for r in results
        ]
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
        f"thesis_statement, watch_points, decision, decision_rationale), score changes, or "
        f"corrections to the intrinsic-value figures in the valuation table. Propose one update "
        f"per changed field with a clear reason.\n"
        f"Applying updates: a proposal (apply=false) changes NOTHING until the user either clicks "
        f"the Accept button in the UI or explicitly confirms in chat. When the user explicitly "
        f"confirms in chat (e.g. 'apply them', 'confirm the updates', 'yes, update it'), re-issue "
        f"each confirmed update with apply=true — only then is it actually applied. NEVER claim a "
        f"change has been applied unless you called update_thesis with apply=true and received a "
        f"success result. Only use the field paths listed in the tool definition.\n\n"
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

    # Prior conversation (persisted) — replay the last 20 turns for LLM context
    history = _load_chat(analysis_id)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-20:]
        if m.get("content")
    ]
    messages.append({"role": "user", "content": user_content})
    tools = [_WEB_SEARCH_TOOL, _UPDATE_THESIS_TOOL]

    all_sources: list[dict] = []
    proposed_updates: list[dict] = []
    applied_updates: list[dict] = []
    answer = ""

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
            break

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
                upd = dict(tool_use.input)
                apply_now = bool(upd.pop("apply", False))
                upd["new_value"] = str(upd.get("new_value", ""))
                if upd.get("old_value") is not None:
                    upd["old_value"] = str(upd["old_value"])
                error = _validate_update(data, upd)
                if error:
                    content = error
                elif apply_now:
                    content = _apply_update(analysis_id, data, upd)
                    applied_updates.append(upd)
                else:
                    proposed_updates.append(upd)
                    content = (
                        "Update proposal recorded. Nothing has changed yet — the user must "
                        "click Accept in the UI, or confirm in chat (then re-issue with apply=true)."
                    )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": content,
                })

        messages.append({"role": "user", "content": tool_results})
    else:
        # Loop exhausted — force a final text answer without tools
        resp = client.messages.create(
            model=CHAT_MODEL,
            max_tokens=1024,
            temperature=0.3,
            system=system_prompt,
            messages=messages,
        )
        text_blocks = [b for b in resp.content if b.type == "text"]
        answer = text_blocks[0].text if text_blocks else ""

    # Persist the exchange so chat survives page refreshes
    user_entry: dict = {"role": "user", "content": message}
    if file and file.filename:
        user_entry["attachment"] = file.filename
    history.append(user_entry)
    history.append({
        "role": "assistant",
        "content": answer,
        "sources": all_sources or None,
        "proposed_updates": proposed_updates or None,
        "applied_updates": applied_updates or None,
        "updates_applied": False,
    })
    _save_chat(analysis_id, history)

    return ChatResponse(
        answer=answer,
        sources=([ChatSource(**s) for s in all_sources] if all_sources else None),
        proposed_updates=([ProposedUpdate(**u) for u in proposed_updates] if proposed_updates else None),
        applied_updates=([ProposedUpdate(**u) for u in applied_updates] if applied_updates else None),
    )


@router.get("/chat/{analysis_id}/history")
def chat_history(analysis_id: str):
    """Return persisted chat history for an analysis."""
    return {"messages": _load_chat(analysis_id)}


@router.patch("/chat/{analysis_id}/history")
def patch_chat_message(analysis_id: str, body: dict):
    """Mark proposed updates on a message as applied or dismissed."""
    index = body.get("index")
    messages = _load_chat(analysis_id)
    if not isinstance(index, int) or not (0 <= index < len(messages)):
        raise HTTPException(404, "Message not found")
    if body.get("updates_applied"):
        messages[index]["updates_applied"] = True
    if body.get("dismissed"):
        messages[index].pop("proposed_updates", None)
    _save_chat(analysis_id, messages)
    return {"ok": True}
