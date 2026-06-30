# Atlas Agent Web Application

## Context
Atlas is a CLI-based equity research pipeline (`python main.py <company>`). The user wants a full web dashboard to run analyses, browse history, compare companies, view interactive charts, and export to PDF — with real-time progress streaming during the 2-3 minute pipeline runs.

**Stack**: Next.js + React frontend, FastAPI Python backend, SSE for live updates.

---

## Project Structure

```
atlas-agent/
  agents/            # existing — no changes
  data/theses/       # existing — shared between CLI and web
  main.py            # existing CLI — no changes

  server/            # NEW — FastAPI backend
    app.py           # FastAPI app, CORS, router mounting
    pipeline_runner.py  # Wraps pipeline stages with progress capture
    router_analysis.py  # POST /api/analysis, GET stream, GET status
    router_history.py   # GET /api/history, GET /api/history/{id}
    router_compare.py   # POST /api/compare
    models.py           # Pydantic request/response models

  web/               # NEW — Next.js frontend
    src/
      app/
        page.tsx              # Home — search bar + recent analyses
        analysis/[id]/page.tsx  # Full dashboard view
        history/page.tsx        # History browser
        compare/page.tsx        # Side-by-side comparison
        running/[jobId]/page.tsx  # Live progress view
      components/
        SearchBar.tsx
        ProgressTracker.tsx     # Stage-by-stage stepper with SSE
        CompanyProfileCard.tsx
        ScoreGauge.tsx          # Radial gauge (BMP/Fisher/Selection)
        FisherRadar.tsx         # 15-axis radar chart
        ValuationChart.tsx      # Bar chart: 4 models vs market cap
        ValuationTable.tsx      # IV summary table
        PeerTable.tsx           # Industry peers comparison
        SimilarCompanies.tsx    # Multibagger results
        ThesisDisplay.tsx       # Bull/bear/thesis/watchpoints
        RiskBadge.tsx           # Diamond-to-Egg badge + position %
        RevenueChart.tsx        # Revenue bars + CAGR
        ROCEROICChart.tsx       # ROCE/ROIC history line chart
        DecisionBanner.tsx      # INVEST/WATCHLIST/PASS banner
        JudgeFlags.tsx          # Audit trail
        ExportPDF.tsx           # Client-side PDF generation
        HistoryList.tsx         # Filterable table
        CompareView.tsx         # Side-by-side layout
      lib/
        types.ts       # TS interfaces matching thesis JSON schema
        api.ts         # Fetch wrappers
        formatters.ts  # $1.2B, 12.3% formatters
      hooks/
        useAnalysisProgress.ts  # SSE stream hook
        useAnalysis.ts          # SWR hook for analysis data
```

---

## Backend (FastAPI)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/analysis` | Start new analysis, returns `{ job_id }` |
| GET | `/api/analysis/{jobId}/stream` | SSE progress stream |
| GET | `/api/analysis/{jobId}` | Job status (polling fallback) |
| GET | `/api/history` | List all past analyses (from data/theses/*.json) |
| GET | `/api/history/{id}` | Full JSON for one analysis |
| GET | `/api/history/ticker/{ticker}` | All analyses for a ticker |
| POST | `/api/compare` | Return multiple analyses for comparison |
| GET | `/api/export/{id}/pdf` | Download thesis as PDF |

### Pipeline Runner (`server/pipeline_runner.py`)

Key design: run pipeline stages **in-process in a background thread** (not subprocess), capturing stdout via `contextlib.redirect_stdout` with a custom writer that pushes events to a `queue.Queue`. The SSE endpoint drains this queue.

- `Job` dataclass: id, company_name, status, current_stage, completed_stages, progress_queue, result
- `start_job(company_name)` → creates Job, spawns daemon thread, returns Job
- Thread runs all 9 stages sequentially, wrapping each in stage_start/stage_complete events
- In-memory `_jobs` dict (sufficient for single-user; ~6 runs/day on free tier)

### SSE Progress Stream

SSE chosen over WebSocket (simpler, unidirectional, auto-reconnect in browser).

Events emitted:
```json
{ "type": "stage_start", "stage": "discovery" }
{ "type": "log", "line": "[1/3] Resolving ticker...", "stage": "discovery" }
{ "type": "stage_complete", "stage": "discovery" }
...
{ "type": "done", "json_path": "data/theses/NVDA_2026-06-30.json" }
```

### Dependencies
Only add: `fastapi`, `uvicorn[standard]` — no database, no Redis, no new heavy deps.

---

## Frontend (Next.js + React)

### Tech Choices
- **Next.js 14+** (App Router) — file-based routing, SSR for history
- **Tailwind CSS + shadcn/ui** — rapid component development
- **Recharts** — financial charts (bar, radial, radar, line)
- **SWR** — data fetching with caching
- **@react-pdf/renderer** — client-side PDF export
- **Lucide React** — icons

### Pages

**Home** (`page.tsx`):
- Large centered search bar
- Grid of recent analyses (cards: ticker, company, decision badge, date)
- Search triggers POST → redirects to `/running/{jobId}`

**Running** (`running/[jobId]/page.tsx`):
- Vertical stepper showing 9 stages
- Current stage: spinner + pulse animation
- Completed: green checkmarks
- Pending: greyed out
- Collapsible stdout log at bottom
- Auto-redirect to `/analysis/{id}` on completion

**Analysis Dashboard** (`analysis/[id]/page.tsx`):
- Top: `DecisionBanner` (full-width, color-coded)
- Two-column layout:
  - Left (2/3): ProfileCard, ThesisDisplay, JudgeFlags
  - Right (1/3): 3x ScoreGauge, RiskBadge, ValuationTable
- Full-width below: ValuationChart, RevenueChart, ROCEROICChart, FisherRadar, PeerTable, SimilarCompanies
- Top-right: ExportPDF button

**History** (`history/page.tsx`):
- Sortable/filterable table (ticker, company, date, decision, scores)
- Filter by decision type, date range, ticker search
- Click → opens analysis

**Compare** (`compare/page.tsx`):
- Multi-select from history (max 5)
- Side-by-side columns: profile, scores, valuation, risk
- Comparative bar charts

### Data Flow
```
User types "Nvidia" → POST /api/analysis → { job_id }
  → redirect to /running/{jobId}
  → SSE stream: /api/analysis/{jobId}/stream
  → ProgressTracker updates in real-time (9 stages, ~2-3 min)
  → "done" event → redirect to /analysis/NVDA_2026-06-30
  → SWR fetch: GET /api/history/NVDA_2026-06-30 → full JSON
  → All dashboard components render from single JSON object
```

---

## Implementation Phases

### Phase 1: Backend API
- Create `server/` with app.py, pipeline_runner.py, router_analysis.py, router_history.py
- Test: `uvicorn server.app:app` → `GET /api/history` serves existing JSONs
- Test: `POST /api/analysis` runs pipeline, SSE delivers events

### Phase 2: Frontend Scaffold
- `npx create-next-app@latest web` (TypeScript + Tailwind)
- types.ts, api.ts, SSE hook
- SearchBar, ProgressTracker, HistoryList
- Wire up end-to-end: search → run → progress → results

### Phase 3: Analysis Dashboard
- All visualization components: ScoreGauge, FisherRadar, ValuationChart, ValuationTable, PeerTable, ThesisDisplay, RiskBadge, DecisionBanner, RevenueChart, ROCEROICChart, SimilarCompanies, JudgeFlags
- Compose into Analysis page layout
- Test with real JSON from data/theses/

### Phase 4: History & Compare
- History page with sorting, filtering
- Compare page with side-by-side layout

### Phase 5: PDF Export
- @react-pdf/renderer document template
- ExportPDF component

---

## Key Files to Reference
- `main.py` (lines 22-37) — pipeline stage sequence and argument threading
- `agents/thesis_writer.py` `_save()` (lines 612-709) — JSON output schema (TypeScript interfaces match this)
- `agents/discovery.py` — stdout patterns for progress parsing
- `data/theses/NVDA_2026-06-30.json` — reference JSON for testing components

## Verification
- Start backend: `uvicorn server.app:app --port 8000`
- Start frontend: `cd web && npm run dev` (port 3000)
- Search "Nvidia" → watch 9 stages complete with live updates → view full dashboard
- Browse history → see all past analyses → compare 2-3 companies
- Export PDF from analysis page
