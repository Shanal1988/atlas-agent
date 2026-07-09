# Plan: Financial Statements Editor, File Upload, URL Import & Enhanced Chat

## Context

Atlas Agent runs a 9-stage analysis pipeline producing a read-only investment thesis. The user wants to:
1. View & edit financial statements (income statement, balance sheet, cash flow) in editable tables
2. Add historical year columns to the tables
3. Upload files (Excel/CSV/PDF) to populate the tables
4. Import from URLs (SEC filings, investor pages) to populate tables
5. Enhance follow-up chat with live web search via Tavily
6. Editable BMP score table (5 questions with rating/reasoning + user notes)
7. Editable Fisher analysis table (15 points with score/reasoning + user notes)
8. Real-time thesis updates from chat — chat can propose changes to the thesis, and user confirms

---

## Data Storage

User edits stored in an **overlay** file, keeping the original analysis intact:
- **Analysis**: `data/theses/{ANALYSIS_ID}.json` (original pipeline output)
- **Financials**: `data/financials/{ANALYSIS_ID}.json` (user-editable financial statements)
- **Overrides**: `data/overrides/{ANALYSIS_ID}.json` (user edits to scores, thesis, notes)

Schema — each line item is `Record<year, number | null>`:
```json
{
  "analysis_id": "AAPL_2026-06-29",
  "ticker": "AAPL", "company": "Apple Inc.",
  "last_modified": "...",
  "years": ["2025", "2024", "2023", "2022", "2021"],
  "income_statement": {
    "revenue": {"2025": 416161000000, "2024": 391035000000, "...": "..."},
    "cost_of_revenue": {"...": "..."},
    "gross_profit": {"...": "..."},
    "operating_expenses": {"...": "..."},
    "operating_income": {"...": "..."},
    "interest_expense": {"...": "..."},
    "net_income": {"...": "..."},
    "eps_diluted": {"...": "..."}
  },
  "balance_sheet": {
    "cash_and_equivalents": {"...": "..."},
    "total_current_assets": {"...": "..."},
    "total_assets": {"...": "..."},
    "total_current_liabilities": {"...": "..."},
    "total_debt": {"...": "..."},
    "total_liabilities": {"...": "..."},
    "total_equity": {"...": "..."},
    "shares_outstanding": {"...": "..."}
  },
  "cash_flow": {
    "operating_cash_flow": {"...": "..."},
    "capital_expenditures": {"...": "..."},
    "free_cash_flow": {"...": "..."},
    "dividends_paid": {"...": "..."},
    "share_buybacks": {"...": "..."}
  },
  "uploads": [{"filename": "...", "uploaded_at": "...", "source": "upload|url"}]
}
```

Overrides schema — `data/overrides/{ANALYSIS_ID}.json`:
```json
{
  "analysis_id": "AAPL_2026-06-29",
  "last_modified": "...",
  "bmp": {
    "answers": [
      {"label": "...", "rating": "YES|PARTIAL|NO", "reasoning": "...", "user_note": "My own research says..."}
    ],
    "score": 4.5,
    "verdict": "PASS"
  },
  "fisher": {
    "points": [
      {"key": "P1", "label": "...", "score": 1.0, "reasoning": "...", "user_note": "..."}
    ],
    "total": 12.5,
    "rating": "EXCELLENT"
  },
  "thesis": {
    "executive_summary": "...",
    "bull_case": ["..."],
    "bear_case": ["..."],
    "thesis_statement": "...",
    "decision": "INVEST",
    "decision_rationale": "..."
  }
}
```

When the analysis page loads, the frontend merges overrides on top of the original analysis data. Only fields present in the overrides file replace the originals.

---

## Phase 1 — Backend Financial Statements CRUD

### Create: `server/financial_parser.py`
- `seed_from_fmp(ticker, years=5)` — fetch FMP income-statement, balance-sheet-statement, cash-flow-statement (reuse `_fmp()` pattern from `agents/discovery.py:120`)
- `seed_from_analysis(analysis_json)` — extract revenues, FCF, OCF from existing analysis
- `parse_excel(file_path)` — parse Excel/CSV via `openpyxl` into schema dict
- `parse_pdf_financials(file_path)` — extract text via `pypdf`, LLM structured extraction
- `extract_from_url(url)` — fetch via Tavily extract or requests+BeautifulSoup, LLM extraction
- `merge_financials(existing, new_data)` — merge new values into existing (overwrite nulls)

### Create: `server/router_financials.py`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/financials/{analysis_id}` | Get or auto-seed from FMP + analysis |
| PUT | `/api/financials/{analysis_id}` | Save edited data |
| POST | `/api/financials/{analysis_id}/upload` | Upload file, parse, merge |
| POST | `/api/financials/{analysis_id}/url` | Fetch URL, extract, merge |
| POST | `/api/financials/{analysis_id}/add-years` | Fetch more years from FMP |

### Modify: `server/models.py`
- Add `FinancialStatements`, `UrlExtractRequest`, `AddYearsRequest` models
- Add `sources: list[dict] | None = None` to `ChatResponse`

### Modify: `server/app.py`
- Register `router_financials` with auth dependency
- Add `Path("data/financials").mkdir(parents=True, exist_ok=True)`

### Modify: `requirements.txt`
- Add `openpyxl`, `beautifulsoup4`

---

## Phase 2 — Frontend Editable Financial Tables

### Create: `web/components/EditableTable.tsx`
- HTML `<table>` with sticky first column (line item labels)
- Input cells: formatted currency on blur, raw number on focus
- Null cells show "–"
- Dark theme matching `ValuationTable.tsx` (slate-800, slate-700 borders)

### Create: `web/components/FinancialStatements.tsx`
- Three tabs: Income Statement / Balance Sheet / Cash Flow
- Toolbar: [Add Year] [Upload File] [Import URL] [Fetch FMP Data]
- Auto-save on cell change (debounced PUT)
- Renders `EditableTable` for active tab

### Modify: `web/lib/types.ts`
- Add `FinancialStatements` interface

### Modify: `web/lib/api.ts`
- Add `getFinancials()`, `saveFinancials()`, `uploadFinancialFile()`, `importFromUrl()`, `fetchFmpYears()`

### Modify: `web/app/analysis/[id]/page.tsx`
- Add `<FinancialStatements>` after charts section, before FollowUpChat

---

## Phase 3 — File Upload & URL Import UI

### Create: `web/components/FileUploadDialog.tsx`
- Modal with drag-and-drop zone, accepts `.xlsx`, `.csv`, `.pdf`
- Upload progress, success refresh

### Create: `web/components/UrlImportDialog.tsx`
- Modal with URL input, "Extract" button, loading state

Wire both into `FinancialStatements.tsx` toolbar.

---

## Phase 4 — Enhanced Chat with Web Search

### Modify: `server/router_chat.py`
- Add Tavily `web_search` tool via Claude tool-use API:
```python
tools = [{
    "name": "web_search",
    "description": "Search the web for real-time company info, news, or financial data",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
}]
```
- Flow: send message + tools → if Claude calls web_search → execute Tavily → return results → Claude generates final answer with sources
- Also load uploaded document context from `data/uploads/{analysis_id}/`

### Modify: `web/components/FollowUpChat.tsx`
- Render source links below assistant messages when `sources` present
- Small "Web search enabled" indicator near input

---

## Phase 5 — Editable BMP & Fisher Score Tables

### Create: `web/components/BMPScoreTable.tsx`
- Table with 5 rows (one per BMP question)
- Columns: Question | Rating (dropdown: YES/PARTIAL/NO) | AI Reasoning (read-only) | User Notes (editable textarea)
- Rating dropdown changes recalculate total score live
- Color-coded rows: green (YES), amber (PARTIAL), red (NO)
- Save button persists to overrides

### Create: `web/components/FisherScoreTable.tsx`
- Table with 15 rows (one per Fisher point)
- Columns: Point | Score (dropdown: 0/0.5/0.75/1.0) | AI Reasoning (read-only) | User Notes (editable textarea)
- Score changes recalculate total and rating live
- Grouped by category (Growth, Profitability, Management, Strategy, Integrity) matching existing FisherRadar

### Create: `server/router_overrides.py`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/overrides/{analysis_id}` | Get user overrides (or empty if none) |
| PUT | `/api/overrides/{analysis_id}` | Save overrides (scores, thesis, notes) |

### Modify: `web/app/analysis/[id]/page.tsx`
- Add expandable BMP and Fisher editable tables below the existing score gauges
- Load overrides on mount, merge with original analysis data
- Pass merged data to all components

---

## Phase 6 — Chat-Driven Thesis Updates

### Modify: `server/router_chat.py`
- Add `update_thesis` tool alongside `web_search`:
```python
{
    "name": "update_thesis",
    "description": "Propose an update to the investment thesis based on the conversation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "field": {"type": "string", "description": "Field to update e.g. 'thesis.bull_case', 'thesis.decision'"},
            "old_value": {"type": "string"},
            "new_value": {"type": "string"},
            "reason": {"type": "string"}
        },
        "required": ["field", "new_value", "reason"]
    }
}
```
- When Claude calls `update_thesis`, return proposed changes as `proposed_updates` array in response

### Modify: `web/components/FollowUpChat.tsx`
- When response contains `proposed_updates`, show inline "Apply Changes" card:
  - Shows what will change (field, old → new, reason)
  - [Accept] and [Dismiss] buttons
  - On Accept: PUT to `/api/overrides/{id}` then refresh page data

### Modify: `web/lib/types.ts`
- Add `ProposedUpdate` interface: `{ field: string, old_value?: string, new_value: string, reason: string }`
- Update `ChatResponseData` to include `proposed_updates?: ProposedUpdate[]`

---

## Implementation Order

1. `server/models.py` — Pydantic models (financials, overrides, chat updates)
2. `server/financial_parser.py` — FMP seeding + merge utilities
3. `server/router_financials.py` — GET + PUT endpoints
4. `server/router_overrides.py` — GET + PUT for score/thesis overrides
5. `server/app.py` — register both new routers, ensure data dirs
6. `web/lib/types.ts` + `web/lib/api.ts` — types and API functions
7. `web/components/EditableTable.tsx` — editable financial table
8. `web/components/FinancialStatements.tsx` — tab container
9. `web/components/BMPScoreTable.tsx` — editable BMP scores + notes
10. `web/components/FisherScoreTable.tsx` — editable Fisher scores + notes
11. `web/app/analysis/[id]/page.tsx` — integrate all new components + overrides merge
12. `server/financial_parser.py` — add file parsing + URL extraction
13. `server/router_financials.py` — add upload + URL endpoints
14. `web/components/FileUploadDialog.tsx` + `UrlImportDialog.tsx`
15. `server/router_chat.py` — Tavily web_search + update_thesis tools
16. `web/components/FollowUpChat.tsx` — render sources + proposed updates with accept/dismiss

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `server/router_financials.py` | Create | Financial statements CRUD + upload + URL |
| `server/router_overrides.py` | Create | User overrides for scores/thesis/notes |
| `server/financial_parser.py` | Create | FMP seeding, file parsing, URL extraction, merge |
| `server/models.py` | Modify | Add all new Pydantic models |
| `server/app.py` | Modify | Register financials + overrides routers |
| `server/router_chat.py` | Modify | Add web_search + update_thesis tools |
| `requirements.txt` | Modify | Add openpyxl, beautifulsoup4 |
| `web/lib/types.ts` | Modify | Add FinancialStatements, overrides, ProposedUpdate |
| `web/lib/api.ts` | Modify | Add financial + overrides API functions |
| `web/components/EditableTable.tsx` | Create | Editable spreadsheet table |
| `web/components/FinancialStatements.tsx` | Create | Tab container with toolbar |
| `web/components/BMPScoreTable.tsx` | Create | Editable BMP 5-question table with notes |
| `web/components/FisherScoreTable.tsx` | Create | Editable Fisher 15-point table with notes |
| `web/components/FileUploadDialog.tsx` | Create | File upload modal |
| `web/components/UrlImportDialog.tsx` | Create | URL import modal |
| `web/app/analysis/[id]/page.tsx` | Modify | Add all new sections + overrides merge |
| `web/components/FollowUpChat.tsx` | Modify | Render sources + proposed thesis updates |

---

## Verification

1. Open existing analysis → financial statements section loads with FMP-seeded data
2. Edit a financial cell → value saves and persists on reload
3. Click "Add Year" → new column appears
4. Upload an Excel file → table updates with parsed data
5. Enter a URL → table updates with extracted data
6. BMP table shows 5 questions with editable ratings + user notes → saves to overrides
7. Fisher table shows 15 points with editable scores + user notes → saves to overrides
8. Edit a BMP rating → total score recalculates live
9. Ask chat question needing current info → response includes web search sources
10. Chat proposes thesis update → "Apply Changes" card appears → accept writes to overrides
11. All endpoints return 401 without auth token
