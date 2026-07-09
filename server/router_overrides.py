"""
User overrides router — stores edits to BMP/Fisher scores, thesis, and notes.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

router = APIRouter()

THESES_DIR = Path("data/theses")
OVERRIDES_DIR = Path("data/overrides")


def _overrides_path(analysis_id: str) -> Path:
    return OVERRIDES_DIR / f"{analysis_id}.json"


@router.get("/overrides/{analysis_id}")
def get_overrides(analysis_id: str):
    """Get user overrides for an analysis. Returns empty object if none exist."""
    if not (THESES_DIR / f"{analysis_id}.json").exists():
        raise HTTPException(404, "Analysis not found")

    path = _overrides_path(analysis_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@router.put("/overrides/{analysis_id}")
def save_overrides(analysis_id: str, data: dict):
    """Save user overrides (scores, thesis sections, notes)."""
    if not (THESES_DIR / f"{analysis_id}.json").exists():
        raise HTTPException(404, "Analysis not found")

    OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    data["analysis_id"] = analysis_id
    data["last_modified"] = datetime.now(timezone.utc).isoformat()
    _overrides_path(analysis_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True}
