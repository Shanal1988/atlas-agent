"""
Atlas Agent — FastAPI server

Start with:
  uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server.router_analysis import router as analysis_router
from server.router_history import router as history_router
from server.router_compare import router as compare_router

THESES_DIR = Path("data/theses")

# Ensure data directories exist (important on Railway where filesystem starts empty)
Path("data/theses").mkdir(parents=True, exist_ok=True)
Path("data/uploads").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Atlas Agent API", version="1.0.0")

_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra = os.environ.get("CORS_ORIGINS", "")
_allowed_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(compare_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "Atlas Agent API"}


@app.get("/api/export/{analysis_id}/txt")
def export_txt(analysis_id: str):
    """Download the formatted thesis as plain text."""
    path = THESES_DIR / f"{analysis_id}.txt"
    if not path.exists():
        raise HTTPException(404, "Thesis text not found")
    return FileResponse(
        path,
        media_type="text/plain",
        filename=f"{analysis_id}_thesis.txt",
    )
