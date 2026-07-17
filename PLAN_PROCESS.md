# Plan: Integrate Personal Investing Process into Atlas Pipeline

## Context

The user's 5-year investing process was extracted from their Google Sheet ("Stock Analysis", 2022)
into `docs/INVESTING_PROCESS.md`. The pipeline already implements parts of it (BMP gate, Fisher 15,
8-question selection, Diamond→Egg sizing, valuation models). This work adds the missing frameworks,
aligns existing stages with the documented process, and makes the new scores drive the final
decision and position sizing.

**Confirmed scope:**
1. Implement everything: Munger Four Filters, Feroldi Quality Score (with Gauntlet), Anti-Fragile
   Score, 10 Vital Signs, Quality Score screen, Investment Stage + Lynch classification
2. Align existing stages: risk categories renamed to the sheet's Crushability names, BMP verdict
   wording per the sheet, earning-yield >5% price veto
3. New process scores **influence** the thesis decision and position sizing (not display-only)

---

## Architecture

New pipeline order (11 stages):

```
discover → industry → munger → bmp → fisher → selection → valuation → process → risk → similar → thesis
```

- **`munger`** (new stage): Munger Four Filters gate
- **`process`** (new stage): Feroldi Quality Score, Anti-Fragile (derived), Vital Signs,
  Quality Screen, Stage+Lynch — orchestrated by one agent
- **`risk`** (rewritten): 25-question Crushability checklist (# of NOs → Diamond / Marble /
  Jawbreaker / Coconut / Glass Bottle / Egg)
- `valuation` moves before `process`/`risk` (pure math, no LLM deps) so they can consume IV results

### Design decisions

| Decision | Policy |
|---|---|
| Deterministic vs LLM | Every quantifiable item computed in Python from profile data; only judgement items go to the LLM |
| LLM call splitting | ≤14 checklist items per LLM call for parsing reliability; line format `K1: [RATING] reasoning` |
| Fallback chain | House pattern from `agents/bmp_gate.py`: Groq → Gemini → Claude |
| Feroldi normalization | Sheet raw maxima sum to 110; Moat's 6 raw items (sum 75) scaled ×30/75 so pre-Gauntlet reports /100; raw per-item scores stored so policy can change without re-running |
| Unavailable data (Glassdoor, geo revenue) | Item scored N/A, contributes 0, subtracted from displayed denominator, listed in `data_gaps`. Non-NA revenue: try FMP geo segmentation, else LLM estimate flagged `"method": "llm_estimate"` |
| Method provenance | Every item carries `"method": "computed" \| "llm" \| "unavailable"` |
| Anti-Fragile | Derived from Feroldi items + profile (no extra LLM call). Bands: <7 IGNORE, 7–12 INVESTABLE, ≥12 FANTASTIC |
| Missing LLM answers | UNKNOWN, counted as NO (conservative) |
| Decision guardrails | Deterministic post-parse: AF<7 / Glass Bottle / Egg / price-veto can never yield INVEST |

---

## Phase 1 — Shared helpers: `agents/context.py` (new)

- `profile_context(profile)` — shared profile serializer (extracted from `bmp_gate.py`, extended
  with new fields)
- `compute_oey(profile)` — normalized operating-earnings-yield logic extracted from `bmp_gate.py`
  so BMP, Munger and risk sizing use identical numbers; earning-yield >5% veto lives here

## Phase 2 — Profile enrichment: `agents/discovery.py`

Add fields (FMP path + yfinance fallback, all nullable): `gross_profit`/`gross_margin`,
`net_income` + 5y history, `eps_history`, `total_debt`/`cash_and_equivalents`/`net_debt` (already
fetched in ROCE/ROIC helper — store into profile), `shares_history` → `dilution_cagr`,
`week52_high/low/change_pct`, `ps_ratio`, `sm_expense`, `revenue_quarterly` (last 5 quarters).

## Phase 3 — New framework agents

### `agents/munger.py` (1 LLM call)
F1 understand / F2 moat / F3 management via LLM (YES/TBC/NO); F4 price computed from
`compute_oey` (≥5% YES, 3–5% TBC, <3% NO). Returns `{filters[], pass_count, verdict}`.
Pipeline does not hard-stop; verdict feeds the thesis decision.

### `agents/feroldi.py` (3 LLM calls + deterministic; also derives Anti-Fragile)
- **Deterministic:** Financials section (resilience 0–5, gross margin 0–3, ROIC 0–3, FCF 0–3,
  EPS 0–3), inside ownership, dilution Gauntlet item, customer-acquisition from
  `sm_expense/gross_profit`, 5-yr performance where computable
- **LLM call A:** Moat + Potential (10 items, `M1: [12/15] reasoning`)
- **LLM call B:** Customers/Company/Management/Stock judgement items (~10 items)
- **LLM call C:** Gauntlet (12 penalty items with exact allowed values; deterministic overrides
  where computed)
- **Normalization:** pre-Gauntlet reported /100; total = pre_gauntlet + gauntlet (floor −54)
- **Anti-Fragile:** mapped from Feroldi items + profile (mission, moat pillars, optionality,
  cash/debt/FCF, concentration, founder, ownership; Glassdoor→0)

### `agents/vital_signs.py` (1 LLM call)
10 items scored 0/0.5/1 with condensed criteria in prompt; context includes BMP/Fisher scores +
IV summary. Closing free-text lines `SANE_VALUATION:` / `OPPORTUNITY_COST:`. Deterministic floors
(e.g. V1 capped 0.5 if net debt > 0).

### `agents/quality_screen.py` (1 LLM call + deterministic)
- Qualitative 8×1–5 via LLM (wheelhouse/interest scored via neutral proxy, flagged `proxy: true`)
- Quantitative + Valuation points fully deterministic from profile (revenue TTM, quarterly
  rev-growth points with accelerating bonus, cash/debt, OCF/rev, %op income, non-NA revenue, P/S,
  market cap, 52W growth; Glassdoor N/A)
- Output: qual/quant/val subtotals + overall + data_gaps

### `agents/stage_classifier.py` (1 small LLM call)
Deterministic pre-classification narrows candidate stages (profitability + growth + margin trend);
LLM picks exact stage + Lynch category within the window. Lookup tables map stage → allocation
guidance.

### `agents/process_scoring.py` (orchestrator for stage `process`)
`run(profile, bmp, fisher, selection, valuation)` → calls feroldi → vital_signs → quality_screen →
stage_classifier, prints house-style terminal blocks, computes `position_sizing` synthesis
(`stage_cap_pct`, `antifragile_ok`, `feroldi_band`, notes).

## Phase 4 — Rewrite `agents/risk_scoring.py` (Crushability) + align `agents/bmp_gate.py`

25 questions: **11 deterministic** (profitable TTM, FCF+, sales growth 10–40% with >41%=NO,
3-yr self-funding, disclosure, transparency, ROE≥15%, mkt cap>$500M, beta<1.3, 0<P/E<30,
insider>5%) + **14 via one LLM call** (brand, diversification, word of mouth, underdog, goliath,
moat, CXO tenure, SA/RB fit, fraud-free, want-to-know-more, 2 self-named company risks, macro
antifragility) + `CONVICTION:` line. Missing lines → UNKNOWN, counted as NO.

Categories per the sheet:

| Category | # NOs | Position size |
|---|---|---|
| Diamond | 0–5 | 6–10% |
| Marble | 6–8 | 3–5% |
| Jawbreaker | 9–11 | 1–2% |
| Coconut | 12–14 | <1% |
| Glass Bottle | 15–18 | 0% |
| Egg | 19–25 | 0% |

**Position-size resolution (where the new scores bite):**
1. Crushability range, point picked by conviction
2. Capped by `stage_cap_pct` (Investment Stage framework)
3. Anti-Fragile < 7 → force 0% with note
4. OEY < 5% → `price_veto: true` (blocks INVEST in thesis, doesn't zero size)

Result keeps `category/conviction/position_pct/summary` keys; adds `questions[25]`, `no_count`,
`unknown_count`, `price_veto`, `sizing_notes`. Keep `judge` cross-stage check (updated for new
category names).

**BMP alignment:** verdict wording per the sheet — ≥4 "COULD BE A GREAT LONG-TERM HOLDING —
proceed to price" / 3–3.99 "WAIT AND WATCH — NOs could become YESes" / <3 "NOT A LONG-TERM
PROSPECT — reject". Add `price_veto` + `active_oey` to result via shared `compute_oey`.

## Phase 5 — Orchestration + thesis integration

- `main.py`: insert `munger()` after industry; move `valuation()` before `process_scoring()`;
  pass `process_result` to `risk_scoring()`; pass `munger_result` + `process_result` to
  `thesis_writer()`
- `server/pipeline_runner.py`: new 11-entry STAGES list (munger order 3, valuation 7, process 8,
  risk 9) + mirror call order in `_run_pipeline`
- `agents/thesis_writer.py`: new params `munger_result`, `process_result`; `_build_context` adds
  `=== PROCESS SCORES ===` block (Munger filters, Feroldi total + sections + top Gauntlet
  deductions, Anti-Fragile band, Vital Signs total + weakest 2, Quality Screen totals, Stage +
  Lynch + allocation, Crushability + final %). System prompt: AF<7 → never INVEST; Glass
  Bottle/Egg → never INVEST; price veto → best is WATCHLIST; rationale must reference Feroldi
  score + stage allocation. **Deterministic guardrail after parsing:** downgrade INVEST →
  WATCHLIST if AF<7 / Glass Bottle / Egg / price_veto, append `[Process guardrail: <reason>]`
  to rationale. `_save()` writes `scores.munger` + `scores.process`; `_format_thesis` adds a
  PROCESS SCORECARD text section
- `agents/judge.py`: new `check_process_consistency()` → flags stored under `judge_flags`

## Phase 6 — Frontend (`web/`)

- `web/lib/types.ts`: new interfaces mirroring the schema; `Scores` gains optional
  `munger?`/`process?`; `RiskScore.category` widened to new + legacy names; optional
  `questions`/`no_count`/`price_veto`
- New components (dark slate style, matching `ValuationTable`/`RiskBadge`):
  - `MungerFilters.tsx` — 4 rows YES/TBC/NO chips (right column)
  - `FeroldiScoreCard.tsx` — total/100 gauge, collapsible section bars, Gauntlet deductions in
    red, data_gaps badges (full-width "Process Scorecards" section after `FisherRadar`)
  - `AntiFragileGauge.tsx` — linear −7→17 bar, band markers at 7/12
  - `VitalSignsTable.tsx` — 10 rows 0/0.5/1 + closing callouts
  - `QualityScreenTable.tsx` — 3 sub-tables + overall rank headline
  - `StageBadge.tsx` — 12-segment stage strip, Lynch chip, allocation guidance
  - `CrushabilityChecklist.tsx` — collapsible 25-question list + NO-count headline
- Modified: `RiskBadge.tsx` (new category configs, keep legacy; guard `factors` vs `questions`),
  `web/app/analysis/[id]/page.tsx` (mount everything behind `{scores.process && ...}` guards)
- **Backward compat:** old theses without `scores.process` render exactly as today

---

## JSON schema (under `scores`)

```jsonc
"munger": {"filters":[{key,label,rating,reasoning,method}], "pass_count", "verdict"},
"process": {
  "feroldi": {"sections":[{key,label,score,max,items:[{key,label,score,max,method,value?,reasoning}]}],
              "pre_gauntlet", "gauntlet_items":[...], "gauntlet", "total", "max":100, "data_gaps":[]},
  "antifragile": {"items":[{key,label,points,min,max,source,reasoning}], "total", "band"},
  "vital_signs": {"items":[{key,label,score,reasoning}], "total", "max":10,
                  "closing":{sane_valuation, opportunity_cost}},
  "quality_screen": {"qualitative":{items,total,max:40}, "quantitative":{items,total},
                     "valuation":{items,total,max:15}, "overall", "data_gaps":[]},
  "stage": {stage_number, stage_label, risk, return_potential, allocation_guidance,
            do_invest, lynch_category, lynch_allocation, reasoning},
  "position_sizing": {crushability_pct, stage_cap_pct, antifragile_ok, price_veto, final_pct, notes:[]}
}
```

---

## Files summary

| Action | Files |
|---|---|
| Create | `agents/context.py`, `agents/munger.py`, `agents/feroldi.py`, `agents/vital_signs.py`, `agents/quality_screen.py`, `agents/stage_classifier.py`, `agents/process_scoring.py`, `web/components/MungerFilters.tsx`, `FeroldiScoreCard.tsx`, `AntiFragileGauge.tsx`, `VitalSignsTable.tsx`, `QualityScreenTable.tsx`, `StageBadge.tsx`, `CrushabilityChecklist.tsx` |
| Modify | `agents/discovery.py`, `agents/risk_scoring.py`, `agents/bmp_gate.py`, `agents/thesis_writer.py`, `agents/judge.py`, `main.py`, `server/pipeline_runner.py`, `web/lib/types.ts`, `web/components/RiskBadge.tsx`, `web/app/analysis/[id]/page.tsx` |

---

## Verification

1. `python main.py Apple` (rich data) + an international ticker (sparse yfinance path) — pipeline
   completes, terminal shows all new framework blocks
2. Inspect `data/theses/{TICKER}_{DATE}.json` — schema matches; Feroldi
   `total = pre_gauntlet + gauntlet`; risk category maps from `no_count` per table;
   `final_pct ≤ stage_cap_pct`; AF<7 forces 0%
3. Guardrail test — AF<7 / Glass Bottle / Egg / price-veto run never yields `decision: "INVEST"`
4. `uvicorn server.app:app` + `cd web && npm run dev` — 11 stages tick in the progress tracker;
   new scorecards render; an old pre-change analysis renders unchanged with no console errors
5. Temporarily unset `GROQ_API_KEY` — Gemini fallback keeps parsers alive (UNKNOWN defaults,
   no crash)

## Risks

- **Long-checklist parsing:** mitigated by ≤14 LLM items/call + per-key defaults (UNKNOWN/0) +
  optional single retry when >3 keys missing
- **Groq TPM limits:** +7 LLM calls/run; existing Gemini fallback absorbs; tight max_tokens
  budgets (250–900)
- **Runtime:** +30–90s per analysis; per-framework stage logs keep SSE UX acceptable
- **Feroldi normalization judgement call** (110→100): raw per-item scores stored so policy can
  change without re-running
- **Subjective items** (wheelhouse, conviction×interest): proxy-scored + flagged; true fidelity
  via future user-editable overrides
