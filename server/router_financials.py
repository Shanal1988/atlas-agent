"""
Financial Statements router — CRUD + file upload + URL extraction.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from server.models import UrlExtractRequest, AddYearsRequest
from server.financial_parser import (
    seed_from_fmp,
    seed_from_analysis,
    merge_financials,
    parse_excel,
    parse_pdf_financials,
    extract_from_url,
    _blank_financials,
    INCOME_KEYS,
    BALANCE_KEYS,
    CASHFLOW_KEYS,
)

router = APIRouter()

THESES_DIR = Path("data/theses")
FINANCIALS_DIR = Path("data/financials")
UPLOADS_DIR = Path("data/uploads")


def _financials_path(analysis_id: str) -> Path:
    return FINANCIALS_DIR / f"{analysis_id}.json"


def _load_or_seed(analysis_id: str) -> dict:
    """Load existing financials JSON or seed from FMP + analysis."""
    path = _financials_path(analysis_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # Need to create it — load analysis for context
    thesis_path = THESES_DIR / f"{analysis_id}.json"
    if not thesis_path.exists():
        raise HTTPException(404, f"Analysis '{analysis_id}' not found")

    analysis = json.loads(thesis_path.read_text(encoding="utf-8"))
    ticker = analysis.get("ticker", "")
    company = analysis.get("company", "")

    financials = _blank_financials(analysis_id, ticker, company)

    # Seed from analysis JSON first (always available)
    from_analysis = seed_from_analysis(analysis)
    financials = merge_financials(financials, from_analysis)

    # Try FMP if ticker looks like a US ticker
    if ticker and "." not in ticker and ":" not in ticker:
        fmp_data = seed_from_fmp(ticker, years=5)
        if fmp_data.get("years"):
            financials = merge_financials(financials, fmp_data)

    _save_financials(analysis_id, financials)
    return financials


def _save_financials(analysis_id: str, data: dict) -> None:
    FINANCIALS_DIR.mkdir(parents=True, exist_ok=True)
    data["last_modified"] = datetime.now(timezone.utc).isoformat()
    _financials_path(analysis_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@router.get("/financials/{analysis_id}")
def get_financials(analysis_id: str):
    """Get financial statements for an analysis, auto-seeding from FMP if needed."""
    return _load_or_seed(analysis_id)


@router.put("/financials/{analysis_id}")
def save_financials(analysis_id: str, data: dict):
    """Save edited financial statements."""
    # Validate analysis exists
    if not (THESES_DIR / f"{analysis_id}.json").exists():
        raise HTTPException(404, "Analysis not found")
    _save_financials(analysis_id, data)
    return {"ok": True}


@router.post("/financials/{analysis_id}/upload")
async def upload_financial_file(analysis_id: str, file: UploadFile = File(...)):
    """Upload Excel/CSV/PDF, parse it, and merge into financial statements."""
    if not (THESES_DIR / f"{analysis_id}.json").exists():
        raise HTTPException(404, "Analysis not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv", ".pdf"):
        raise HTTPException(400, "Unsupported file type. Use .xlsx, .csv, or .pdf")

    # Save uploaded file
    upload_dir = UPLOADS_DIR / analysis_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / (file.filename or f"upload{suffix}")
    content = await file.read()
    dest.write_bytes(content)

    # Parse
    if suffix == ".pdf":
        extracted = parse_pdf_financials(dest)
    else:
        extracted = parse_excel(dest)

    if "error" in extracted and not extracted.get("years"):
        raise HTTPException(422, f"Could not parse file: {extracted['error']}")

    # Merge into existing
    existing = _load_or_seed(analysis_id)

    # Record upload metadata
    existing.setdefault("uploads", []).append({
        "filename": file.filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "source": "upload",
    })

    merged = merge_financials(existing, extracted)
    merged["uploads"] = existing["uploads"]
    _save_financials(analysis_id, merged)
    return merged


@router.post("/financials/{analysis_id}/url")
def import_from_url(analysis_id: str, req: UrlExtractRequest):
    """Fetch URL content, extract financial data, and merge into statements."""
    if not (THESES_DIR / f"{analysis_id}.json").exists():
        raise HTTPException(404, "Analysis not found")

    extracted = extract_from_url(req.url)
    if "error" in extracted and not extracted.get("years"):
        raise HTTPException(422, f"Could not extract data from URL: {extracted['error']}")

    existing = _load_or_seed(analysis_id)
    existing.setdefault("uploads", []).append({
        "filename": req.url,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "source": "url",
    })

    merged = merge_financials(existing, extracted)
    merged["uploads"] = existing["uploads"]
    _save_financials(analysis_id, merged)
    return merged


@router.post("/financials/{analysis_id}/add-years")
def add_fmp_years(analysis_id: str, req: AddYearsRequest):
    """Fetch additional years of data from FMP and merge."""
    thesis_path = THESES_DIR / f"{analysis_id}.json"
    if not thesis_path.exists():
        raise HTTPException(404, "Analysis not found")

    analysis = json.loads(thesis_path.read_text(encoding="utf-8"))
    ticker = analysis.get("ticker", "")
    if not ticker:
        raise HTTPException(422, "No ticker found for this analysis")

    fmp_data = seed_from_fmp(ticker, years=req.years)
    existing = _load_or_seed(analysis_id)
    merged = merge_financials(existing, fmp_data)
    _save_financials(analysis_id, merged)
    return merged
