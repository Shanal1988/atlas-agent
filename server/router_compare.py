import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

from server.models import CompareRequest

router = APIRouter()
THESES_DIR = Path("data/theses")


@router.post("/compare")
def compare_analyses(req: CompareRequest):
    """Return full data for multiple analyses for side-by-side comparison."""
    if not req.analysis_ids:
        raise HTTPException(400, "No analysis IDs provided")

    results = []
    for aid in req.analysis_ids[:5]:   # cap at 5
        path = THESES_DIR / f"{aid}.json"
        if path.exists():
            try:
                results.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue

    if not results:
        raise HTTPException(404, "No analyses found")
    return results
