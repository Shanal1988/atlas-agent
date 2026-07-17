"""
Wraps the Atlas pipeline stages in a background thread.
Each stage emits structured events to a queue consumed by the SSE endpoint.
"""

import io
import sys
import time
import uuid
import queue
import threading
from contextlib import redirect_stdout
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

# Pipeline stage imports
from agents.discovery import run as discover
from agents.industry_analysis import run as industry_analysis
from agents.munger import run as munger
from agents.bmp_gate import run as bmp_gate
from agents.fisher import run as fisher
from agents.stock_selection import run as stock_selection
from agents.process_scoring import run as process_scoring
from agents.risk_scoring import run as risk_scoring
from agents.valuation import run as valuation
from agents.similar_companies import run as similar_companies
from agents.thesis_writer import run as thesis_writer


STAGES = [
    {"key": "discovery",  "label": "Company Discovery",   "order": 1},
    {"key": "industry",   "label": "Industry Analysis",   "order": 2},
    {"key": "munger",     "label": "Munger Four Filters", "order": 3},
    {"key": "bmp",        "label": "BMP Gate",            "order": 4},
    {"key": "fisher",     "label": "Fisher Analysis",     "order": 5},
    {"key": "selection",  "label": "Stock Selection",     "order": 6},
    {"key": "valuation",  "label": "Valuation",           "order": 7},
    {"key": "process",    "label": "Process Scorecards",  "order": 8},
    {"key": "risk",       "label": "Risk Scoring",        "order": 9},
    {"key": "similar",    "label": "Similar Companies",   "order": 10},
    {"key": "thesis",     "label": "Thesis Writer",       "order": 11},
]


@dataclass
class Job:
    id: str
    company_name: str
    status: str = "pending"          # pending | running | completed | failed
    current_stage: str = ""
    completed_stages: list = field(default_factory=list)
    progress_queue: queue.Queue = field(default_factory=queue.Queue)
    result_json_path: str | None = None
    result_txt_path: str | None = None
    ticker: str | None = None
    error: str | None = None
    stdout_log: list = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None


# In-memory job store
_jobs: dict[str, Job] = {}


class _ProgressCapture(io.TextIOBase):
    """Captures stdout and emits log events to the job queue."""

    def __init__(self, job: Job, original):
        self.job = job
        self.original = original

    def write(self, s: str):
        self.original.write(s)
        stripped = s.strip()
        if stripped:
            event = {
                "type": "log",
                "line": stripped,
                "stage": self.job.current_stage,
                "timestamp": time.time(),
            }
            self.job.stdout_log.append(event)
            self.job.progress_queue.put(event)
        return len(s)

    def flush(self):
        self.original.flush()


def _emit(job: Job, event: dict):
    job.progress_queue.put(event)


def _run_pipeline(job: Job):
    job.status = "running"
    job.started_at = time.time()

    capture = _ProgressCapture(job, sys.stdout)

    try:
        with redirect_stdout(capture):

            def run_stage(key: str):
                job.current_stage = key
                _emit(job, {"type": "stage_start", "stage": key, "timestamp": time.time()})

            def complete_stage(key: str):
                job.completed_stages.append(key)
                _emit(job, {"type": "stage_complete", "stage": key, "timestamp": time.time()})

            # Stage 1: Discovery
            run_stage("discovery")
            profile = discover(job.company_name)
            job.ticker = profile.get("ticker")
            complete_stage("discovery")

            # Stage 2: Industry Analysis
            run_stage("industry")
            industry_result = industry_analysis(profile)
            complete_stage("industry")

            # Stage 3: Munger Four Filters
            run_stage("munger")
            munger_result = munger(profile)
            complete_stage("munger")

            # Stage 4: BMP Gate
            run_stage("bmp")
            bmp_result = bmp_gate(profile)
            complete_stage("bmp")

            # Stage 5: Fisher
            run_stage("fisher")
            fisher_result = fisher(profile, bmp_result["verdict"])
            complete_stage("fisher")

            # Stage 6: Stock Selection
            run_stage("selection")
            selection_result = stock_selection(profile, bmp_result["verdict"])
            complete_stage("selection")

            # Stage 7: Valuation
            run_stage("valuation")
            valuation_result = valuation(profile)
            complete_stage("valuation")

            # Stage 8: Process Scorecards
            run_stage("process")
            process_result = process_scoring(
                profile, bmp_result, fisher_result, selection_result, valuation_result,
            )
            complete_stage("process")

            # Stage 9: Risk Scoring
            run_stage("risk")
            risk_result = risk_scoring(
                profile, bmp_result, fisher_result, selection_result, process_result,
            )
            complete_stage("risk")

            # Stage 10: Similar Companies
            run_stage("similar")
            similar_result = similar_companies(profile, industry_result)
            complete_stage("similar")

            # Stage 11: Thesis Writer
            run_stage("thesis")
            thesis_result = thesis_writer(
                profile, bmp_result, fisher_result, selection_result,
                risk_result, valuation_result, industry_result, similar_result,
                munger_result=munger_result, process_result=process_result,
            )
            complete_stage("thesis")

        job.status = "completed"
        job.result_json_path = thesis_result.get("json_path")
        job.result_txt_path = thesis_result.get("txt_path")
        job.finished_at = time.time()
        _emit(job, {
            "type": "done",
            "json_path": job.result_json_path,
            "txt_path": job.result_txt_path,
            "ticker": job.ticker,
            "timestamp": time.time(),
        })

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.finished_at = time.time()
        _emit(job, {"type": "error", "error": str(e), "stage": job.current_stage})


def start_job(company_name: str) -> Job:
    job_id = str(uuid.uuid4())[:8]
    job = Job(id=job_id, company_name=company_name)
    _jobs[job_id] = job
    thread = threading.Thread(target=_run_pipeline, args=(job,), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def list_jobs() -> list[dict]:
    return [
        {
            "job_id": j.id,
            "company_name": j.company_name,
            "status": j.status,
            "ticker": j.ticker,
            "current_stage": j.current_stage,
            "completed_stages": j.completed_stages,
            "started_at": j.started_at,
            "finished_at": j.finished_at,
        }
        for j in _jobs.values()
    ]
