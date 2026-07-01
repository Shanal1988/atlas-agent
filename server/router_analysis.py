import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.models import AnalysisRequest
from server.pipeline_runner import start_job, get_job, list_jobs, STAGES

router = APIRouter()


@router.post("/analysis")
def create_analysis(req: AnalysisRequest):
    """Start a new analysis. Returns job_id immediately."""
    job = start_job(req.company_name.strip())
    return {
        "job_id": job.id,
        "status": "started",
        "stages": STAGES,
    }


@router.get("/analysis/{job_id}/stream")
async def stream_progress(job_id: str):
    """SSE endpoint — streams pipeline progress events to the browser."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            try:
                event = await loop.run_in_executor(
                    None, lambda: job.progress_queue.get(timeout=1.0)
                )
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ("done", "error"):
                    break
            except Exception:
                # Timeout — check if job already finished (queue drained)
                if job.status in ("completed", "failed"):
                    payload: dict = {"type": "done" if job.status == "completed" else "error"}
                    if job.error:
                        payload["error"] = job.error
                    if job.result_json_path:
                        payload["json_path"] = job.result_json_path
                    if job.ticker:
                        payload["ticker"] = job.ticker
                    yield f"data: {json.dumps(payload)}\n\n"
                    break
                # Send keepalive comment to prevent proxy timeout
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/analysis/{job_id}")
def get_analysis_status(job_id: str):
    """Get current job status (polling fallback)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.id,
        "company_name": job.company_name,
        "ticker": job.ticker,
        "status": job.status,
        "current_stage": job.current_stage,
        "completed_stages": job.completed_stages,
        "error": job.error,
        "result_json_path": job.result_json_path,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.get("/jobs")
def list_active_jobs():
    """List all jobs (active and completed) in current server session."""
    return list_jobs()
