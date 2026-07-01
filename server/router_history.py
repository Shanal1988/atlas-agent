import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()
THESES_DIR = Path("data/theses")


def _summary(data: dict, filename: str) -> dict:
    """Extract lightweight summary from full thesis JSON."""
    profile = data.get("profile", {})
    thesis = data.get("thesis", {})
    scores = data.get("scores", {})
    risk = scores.get("risk", {})
    return {
        "id": Path(filename).stem,
        "file": filename,
        "company": data.get("company"),
        "ticker": data.get("ticker"),
        "date": data.get("date"),
        "exchange": profile.get("exchange"),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "market_cap": profile.get("market_cap"),
        "current_price": profile.get("current_price"),
        "decision": thesis.get("decision"),
        "decision_rationale": thesis.get("decision_rationale"),
        "bmp_score": scores.get("bmp", {}).get("score"),
        "fisher_score": scores.get("fisher", {}).get("total"),
        "selection_score": scores.get("selection", {}).get("score"),
        "risk_category": risk.get("category"),
        "position_pct": risk.get("position_pct"),
        "conviction": risk.get("conviction"),
        "revenue_cagr": profile.get("revenue_cagr"),
        "roe": profile.get("roe"),
        "moat": profile.get("moat"),
    }


@router.get("/history")
def list_analyses():
    """List all past analyses, newest first."""
    files = sorted(
        THESES_DIR.glob("*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(_summary(data, f.name))
        except Exception:
            continue
    return results


@router.get("/history/{analysis_id}")
def get_analysis(analysis_id: str):
    """Get the full JSON for one analysis."""
    path = THESES_DIR / f"{analysis_id}.json"
    if not path.exists():
        raise HTTPException(404, "Analysis not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/history/ticker/{ticker}")
def get_ticker_history(ticker: str):
    """All analyses for a specific ticker, newest first."""
    safe = ticker.upper().replace(".", "_")
    files = sorted(THESES_DIR.glob(f"{safe}_*.json"), key=lambda f: f.name, reverse=True)
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(_summary(data, f.name))
        except Exception:
            continue
    return results
