# Atlas — Personal Equity Research Agent

Atlas is a command-line equity research pipeline that takes a company name and runs it through six analytical stages, producing a scored investment thesis with a position size recommendation.

It is built for long-term, value-growth investors who want a disciplined, repeatable framework — not a trading signal.

---

## What it does

```
python main.py Adyen
```

Atlas runs the company through six stages and prints the full analysis to the terminal. At the end it saves a structured thesis to `data/theses/`.

---

## The Pipeline

| Stage | Agent | What it does |
|-------|-------|-------------|
| 1 | **Discovery** | Resolves ticker, fetches financials from FMP + yfinance, pulls qualitative context via Tavily + Groq |
| 2 | **BMP Gate** | 5-question Business / Moat / Price checklist — scores YES / PARTIAL / NO via Groq |
| 3 | **Fisher Analysis** | Philip Fisher 15-point analysis scored 1 / 0.75 / 0.5 / 0 via Groq + Tavily research |
| 4 | **Stock Selection** | 8-question checklist including Buffett Dollar Test and Capex %; flags FCF distortion for fintech/financial companies |
| 5 | **Risk Scoring** | Diamond-to-Egg framework — counts NOs across all checklists, adds Groq-assessed risk penalties, outputs position size |
| 6 | **Thesis Writer** | Writes a structured investment thesis (bull case, bear case, watch points, decision) and saves JSON + TXT |

---

## Diamond-to-Egg Position Sizing

Total NO answers across all three checklists + risk penalties determine the position size tier.

| Category | Adjusted NOs | Position Size |
|----------|-------------|---------------|
| Diamond  | 0 – 5       | 6 – 10%       |
| Gold     | 6 – 8       | 4 – 6%        |
| Silver   | 9 – 11      | 2 – 4%        |
| Bronze   | 12 – 14     | 1 – 2%        |
| Glass    | 15 – 18     | 0.5 – 1%      |
| Egg      | 19+         | 0% — do not invest |

Conviction (HIGH / MEDIUM / LOW) adjusts to the upper, mid, or lower end of the range.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Shanal1988/atlas-agent.git
cd atlas-agent
pip install -r requirements.txt
```

### 2. API keys

Create a `.env` file in the project root:

```
FMP_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
```

| API | Free tier | Used for |
|-----|-----------|---------|
| [Financial Modeling Prep](https://financialmodelingprep.com) | Yes | US stock financials |
| [Tavily](https://tavily.com) | Yes | Web research for Fisher + qualitative |
| [Groq](https://console.groq.com) | Yes (100k tokens/day) | All LLM scoring and writing |

> **Note on Groq limits:** The free tier allows ~6 full company runs per day. Each run uses approximately 15–20k tokens across 8 Groq calls. Upgrade to Dev Tier for higher limits.

### 3. Run

```bash
python main.py <company name>
```

Examples:
```bash
python main.py Adyen
python main.py CrowdStrike
python main.py "Berkshire Hathaway"
```

---

## Output

**Terminal** — each stage prints its results as it runs.

**Saved files** in `data/theses/`:
- `{TICKER}_{date}.txt` — clean formatted thesis for reading
- `{TICKER}_{date}.json` — full structured output with all raw scores, suitable for building a portfolio tracker or conviction monitor on top

---

## Project Structure

```
atlas-agent/
├── main.py                  # Entry point — runs the full pipeline
├── agents/
│   ├── discovery.py         # Stage 1: ticker resolution + financials
│   ├── bmp_gate.py          # Stage 2: BMP checklist
│   ├── fisher.py            # Stage 3: Fisher 15-point analysis
│   ├── stock_selection.py   # Stage 4: stock selection checklist
│   ├── risk_scoring.py      # Stage 5: Diamond-to-Egg risk framework
│   └── thesis_writer.py     # Stage 6: investment thesis generation
├── data/
│   └── theses/              # Saved thesis files (gitignored)
├── .env                     # API keys (gitignored)
└── requirements.txt
```

---

## Data Sources

- **US stocks** — primary data from [FMP stable API](https://financialmodelingprep.com/developer/docs), gap-filled from yfinance
- **International stocks** — primary data from yfinance (auto-detected by ticker suffix: `.L`, `.AS`, `.TO`, etc.)
- **Web research** — Tavily search for Fisher analysis and qualitative context
- **LLM scoring** — Groq `openai/gpt-oss-120b` for all structured scoring and writing

---

## Sample Results

| Company | BMP | Fisher | Selection | Risk | Position |
|---------|-----|--------|-----------|------|---------|
| Wise (WISE.L) | 4.0/5 | 12.0/15 | 7.0/8 | Diamond / HIGH | 10% |
| Adyen (ADYEN.AS) | 3.5/5 | 14.0/15 | 6.0/8 | Diamond / MEDIUM | 8% |
| CrowdStrike (CRWD) | 3.0/5 | 9.25/15 | 5.5/8 | Diamond / LOW | 6% |

---

## Limitations

- **Not financial advice.** Atlas is a personal research tool. All outputs are LLM-generated and should be verified independently before making any investment decision.
- FCF from yfinance is unreliable for fintech and financial companies due to customer float; Atlas flags this automatically.
- Groq free tier: 100k tokens/day shared across all calls.
- P/E ratios are occasionally missing from FMP for companies reporting losses; BMP Q5 will flag for manual review in these cases.

---

## Roadmap

The pipeline currently has no validation between stages and no mechanism to detect hallucinations or measure scoring quality. The roadmap below adds five layers — guardrails, evals, RAG, fine-tuning, and LLM-as-a-judge — each designed to be implemented independently without restructuring the pipeline.

---

### 1. Guardrails

**Architecture:** All guardrail logic lives in a new `agents/guardrails.py`. Each agent imports only what it needs. No restructuring of existing agents required.

**New file:** `agents/guardrails.py`

```
Function signatures:

check_security_type(ticker, info) -> str | None
  Returns error string if quoteType is ETF/MUTUALFUND/INDEX/CURRENCY/
  CRYPTOCURRENCY/FUTURE/OPTION, or if company name contains SPAC keywords.
  Returns None if the ticker is a valid investable equity.

check_data_sufficiency(profile) -> list[str]
  Returns list of warning strings for: fewer than 2 valid revenue years,
  missing market cap, missing current price.

check_score_sanity_bmp(answers) -> str | None
  Warns if all 5 BMP ratings are YES or all are NO.

check_score_sanity_fisher(points) -> str | None
  Warns if all 15 Fisher scores are 1.0 or all are 0.0, or if fewer
  than 15 points were parsed.

check_score_sanity_selection(answers) -> str | None
  Warns if all 8 Selection ratings are YES or all are NO.

print_warnings(warnings, label="GUARDRAIL") -> None
  Prints a formatted warning block to the terminal.
```

#### Guardrail 1 — Input Validation (fatal)

After `_resolve_ticker()` in `discovery.py`, fetch `info["quoteType"]` from yfinance. If the type is not an investable equity, print a clear error and call `sys.exit(1)`. Pipeline stops immediately — no data is fetched, no Groq tokens are used.

Rejected quote types: `ETF`, `MUTUALFUND`, `INDEX`, `CURRENCY`, `CRYPTOCURRENCY`, `FUTURE`, `OPTION`

SPAC detection: check `longName` for the words "acquisition", "blank check", "special purpose".

```
Example output:
  [INPUT ERROR] SPY resolves to an ETF (SPDR S&P 500 ETF Trust).
  Atlas only analyses individual equities. Please provide a company name or stock ticker.
```

#### Guardrail 2 — Data Sufficiency Gate (warning, non-blocking)

After the profile is built in `discovery.py`, check:
- Fewer than 2 valid revenue years → CAGR unreliable; Fisher and Selection flagged
- Market cap missing → valuation checks unreliable
- Current price missing → P/E ratio unreliable

Warnings are stored in `profile["data_warnings"]`. In `main.py`, if `data_warnings` is non-empty, a `[DATA WARNING]` block is printed before BMP runs. Pipeline continues — analyst decides whether to proceed.

#### Guardrail 3 — Score Sanity Checks (warning, non-blocking)

After each scoring agent parses its Groq response, check whether the output is suspiciously uniform — all YES or all NO is a strong sign of hallucination or prompt collapse.

| Agent | Trigger |
|-------|---------|
| `bmp_gate.py` | All 5 ratings are YES or all are NO |
| `fisher.py` | All 15 scores are 1.0 or all are 0.0, or fewer than 15 parsed |
| `stock_selection.py` | All 8 ratings are YES or all are NO |

Pipeline continues with a `[GUARDRAIL]` warning printed to the terminal.

#### Guardrail 4 — FCF Generalisation

Extend the financial company FCF distortion flag (currently fintech-only) to REITs. REITs report FFO (Funds From Operations), not FCF — yfinance FCF for REITs is distorted by property acquisition/disposal flows.

Change in `stock_selection.py` and `thesis_writer.py`:

```python
# Before
_FINANCIAL_SECTORS = {"Financial Services"}

# After
_FINANCIAL_SECTORS = {"Financial Services", "Real Estate"}
```

**Files modified:** `agents/guardrails.py` (new), `agents/discovery.py`, `agents/bmp_gate.py`, `agents/fisher.py`, `agents/stock_selection.py`, `agents/thesis_writer.py`, `main.py`

---

### 2. Evals

**Architecture:** All evals live in a new `evals/` directory. They read from and write to `evals/results/` (gitignored). No eval modifies the main pipeline. All four are runnable independently from the command line.

```
evals/
├── __init__.py
├── consistency_eval.py      # Eval 1: score variance across N runs
├── regression_suite.py      # Eval 2: known-answer regression tests
├── parser_coverage_eval.py  # Eval 3: fallback rate from existing JSONs
└── backtest.py              # Eval 4: price performance since thesis date
```

#### Eval 1 — Scoring Consistency

**Run:** `python evals/consistency_eval.py --ticker CRWD --runs 5`

Runs all Groq scoring calls N times on the same company and measures variance. Discovery is run once and cached to avoid repeated API calls. Tavily research for Fisher is also cached — variance should come from Groq only, not from different web results.

Collects: `bmp.score`, all `bmp.answers[].rating`, `fisher.total`, all `fisher.points[].score`, `selection.score`, `risk.conviction`, `risk.position_pct`. Computes mean + std dev for numeric fields and frequency distribution for categorical fields.

**Flag threshold:** numeric std dev > 0.5, or categorical mode < 60% agreement.

```
Scoring Consistency Eval -- CRWD (5 runs)
-----------------------------------------
Field                  Mean    StdDev  Status
BMP Score              3.00    0.00    PASS
Fisher Total           9.45    0.62    WARN  <- std dev > 0.5
Selection Score        5.50    0.00    PASS
Position %             6.00    0.00    PASS
```

Output saved to `evals/results/{ticker}_consistency_{date}.json`.

#### Eval 2 — Prompt Regression Suite

**Run:** `python evals/regression_suite.py`

Runs the full pipeline on known companies and checks whether scores fall within expected ranges. Run this after any prompt change to catch regressions. Exits with code 1 if any check fails (CI-compatible).

```python
SUITE = {
    "CRWD":     {"bmp": (2.5, 4.0), "fisher": (8.0, 12.0), "selection": (4.5, 7.0), "decision": {"INVEST", "WATCHLIST"}},
    "WISE.L":   {"bmp": (3.5, 5.0), "fisher": (10.0, 15.0), "selection": (6.0, 8.0), "decision": {"INVEST"}},
    "ADYEN.AS": {"bmp": (3.0, 5.0), "fisher": (12.0, 15.0), "selection": (5.0, 8.0), "decision": {"INVEST", "WATCHLIST"}},
}
```

```
Prompt Regression Suite -- 2026-05-01
---------------------------------------
Company     BMP       Fisher    Selection Decision  Status
CRWD        3.0 PASS  9.25 PASS 5.5  PASS INVEST   PASS
WISE.L      4.0 PASS  12.0 PASS 7.0  PASS INVEST   PASS
ADYEN.AS    3.5 PASS  14.5 PASS 6.0  PASS INVEST   PASS
```

#### Eval 3 — Parser Coverage

**Run:** `python evals/parser_coverage_eval.py`

Reads all existing `data/theses/*.json` files and checks how often each field falls back to a default or null value. No new API calls — free to run at any time.

Fields checked:

| Field | Fallback indicator |
|-------|--------------------|
| `bmp.answers[].rating` | "N/A" |
| `fisher.points[].reasoning` | "No response parsed." |
| `selection.answers[].rating` | "N/A" |
| `risk.factors[].reasoning` | "No response parsed." |
| `profile.pe_ratio` | null |
| `profile.roe` | null |
| `profile.insider_ownership_pct` | null |

**Flag threshold:** fallback rate > 20% for any field.

#### Eval 4 — Historical Backtest

**Run:** `python evals/backtest.py`

Reads all saved thesis JSONs, fetches current price via yfinance, computes return % since thesis date, and groups by Diamond-to-Egg category, conviction level, and decision.

```
Historical Backtest -- 3 theses (limited sample)
-------------------------------------------------
Category   Count  Avg Return  vs MSCI World
Diamond    3      +12.4%      +4.1%

Note: sample too small for statistical significance (need 20+ theses)
```

Becomes meaningful at 20+ theses accumulated over 12+ months.

---

### 3. RAG / Knowledge Retrieval

**Architecture:** A new `agents/rag.py` module handles all three document types using the same embedding + retrieval infrastructure. Integration point is `fisher.py`'s `_gather_evidence()` only — thesis writer uses no web search and is not modified. If ChromaDB is not installed, `rag.retrieve()` returns `""` and the pipeline falls back to Tavily with no crash.

**Tech stack:**

| Library | Purpose |
|---------|---------|
| `chromadb` | Persistent local vector store, one collection per ticker |
| `sentence-transformers` | Embeddings (`all-MiniLM-L6-v2`) — free, local, no API key |
| `pypdf` | PDF text extraction for annual reports |

Add to `requirements.txt`: `chromadb`, `sentence-transformers`, `pypdf`

**New directory structure:**

```
data/
├── theses/                   # existing
├── reports/{TICKER}/         # user drops PDFs here
├── transcripts/{TICKER}/     # earnings call .txt files
├── sector_kb/                # static sector markdown files
│   ├── payments.md
│   ├── cybersecurity.md
│   ├── cloud_saas.md
│   └── fintech.md
└── vectorstore/              # ChromaDB storage (gitignored)
```

**`agents/rag.py` key functions:**

```python
auto_index(ticker, sector)   # Scans data/reports/ and data/transcripts/ for new
                              # files and indexes any not yet in the vector store.
                              # Also indexes matching sector KB file if available.
                              # Called at the end of discovery.py run().

has_documents(ticker)        # Returns True if any documents are indexed for ticker.

retrieve(ticker, query, n=4, include_sector=True)
                              # Returns formatted evidence string. Returns "" if
                              # no documents indexed (graceful no-op).

index_pdf(ticker, pdf_path)  # Chunk + embed a PDF annual report.
index_transcript(ticker, txt_path, label)  # Chunk + embed earnings transcript.
index_sector_kb(sector)      # Embed a sector KB markdown file.
```

Chunking: 400 tokens, 50-token overlap. Metadata per chunk: `{ticker, source_type, source_file, page_number, chunk_index}`.

**Integration with `fisher.py`:**

```python
# Modified _gather_evidence() — graceful degradation

if rag.has_documents(ticker):
    rag_evidence     = rag.retrieve(ticker, query)
    tavily_evidence  = [existing Tavily searches]
    combined = rag_evidence + "\n\n=== Live Web Search ===\n" + tavily_evidence
else:
    combined = [existing Tavily searches -- no change]
```

**Sector KB files** cover stable industry-level context (TAM, competitive dynamics, regulatory trends) for: payments, cybersecurity, cloud/SaaS, fintech. Retrieved for Fisher P1 (Market Potential) and P11 (Industry Position) to ground TAM claims in stable reference material.

**Files created/modified:** `agents/rag.py` (new), `data/sector_kb/*.md` (4 files, new), `agents/discovery.py` (add `auto_index()` call), `agents/fisher.py` (modify `_gather_evidence()`), `requirements.txt`, `.gitignore`

---

### 4. Fine-tuning

**Context:** Groq does not support fine-tuning. Fine-tuned models are hosted on OpenAI (`gpt-4o-mini`). Activation is strictly opt-in via environment variables — if the env vars are not set, the pipeline runs exactly as today with Groq.

**When to fine-tune:**

| Threshold | Action |
|-----------|--------|
| < 50 theses | Do not fine-tune — collect more data first |
| 50–100 theses | Fine-tune BMP, Selection, Risk stages |
| 100+ theses | Fine-tune Fisher stage too (requires saving Tavily evidence) |

**New directory structure:**

```
fine_tuning/
├── prepare_scoring_data.py  # Extract BMP/Selection/Risk training pairs from thesis JSONs
├── prepare_style_data.py    # Format thesis style training data
├── train_scoring_model.py   # Upload to OpenAI + start fine-tuning job
└── train_style_model.py     # Fine-tune thesis writer style
```

#### Fine-tune 1 — Scoring Calibration

`prepare_scoring_data.py` reads all `data/theses/*.json` and reconstructs message-format training pairs for BMP, Selection, and Risk. The `assistant` turn is rebuilt from the saved `answers`/`factors` arrays — no new Groq calls needed.

```
Output: fine_tuning/training_data/bmp_training.jsonl
        fine_tuning/training_data/selection_training.jsonl
        fine_tuning/training_data/risk_training.jsonl
```

`train_scoring_model.py --stage bmp` uploads the JSONL to OpenAI Files API, creates a fine-tuning job on `gpt-4o-mini`, polls for completion, and prints the model ID. Add the ID to `.env`:

```
OPENAI_FT_BMP_MODEL=ft:gpt-4o-mini:...:...
OPENAI_FT_SELECTION_MODEL=ft:gpt-4o-mini:...:...
OPENAI_FT_RISK_MODEL=ft:gpt-4o-mini:...:...
```

**Fisher excluded for now:** The thesis JSON does not save the Tavily evidence string, so Fisher training pairs cannot be reconstructed from stored data. A future change to `thesis_writer.py` will add a `fisher_evidence` field to the JSON, unlocking Fisher fine-tuning at 100+ theses.

#### Fine-tune 2 — Thesis Style

`prepare_style_data.py` pairs the structured context block (same as `_build_context()` output) with high-quality thesis text that the user has edited or curated.

User workflow:
1. Drop examples of professional investment memos (CFA reports, Berkshire letters, Fundsmith letters) into `data/style_examples/`
2. Run `prepare_style_data.py` to generate a draft training set
3. Review and manually rewrite any sections that feel too generic
4. Save edited versions to `data/style_examples/edited/`
5. Run `train_style_model.py` to fine-tune

Activate with: `OPENAI_FT_THESIS_MODEL=ft:gpt-4o-mini:...:...`

Add to `requirements.txt`: `openai`

---

### 5. LLM as a Judge

**Architecture:** All judge logic lives in a new `agents/judge.py`. All judges are **non-blocking** — they print a `[JUDGE]` warning but never halt the pipeline. The analyst reviews the flags and decides whether to re-run or override.

**Model:** Same Groq `openai/gpt-oss-120b`. No additional API key. Adds ~900–1100 tokens per full pipeline run across all four judges.

**New file:** `agents/judge.py`

```python
class JudgeResult:
    judge:    str          # e.g. "score_justification_bmp"
    passed:   bool
    severity: str          # "INFO" | "WARN" | "FAIL"
    flags:    list[str]    # specific issues found, empty if passed
```

#### Judge 1 — Score Justification Auditor (Groq)

**Where:** `bmp_gate.py`, `fisher.py`, `stock_selection.py` — called after parsing, before printing.

Checks whether the reasoning for each extreme score (top 3 highest and bottom 3 lowest per stage) is consistent with the company data provided. A second Groq pass on the flagged items only — not a full re-score.

Examples of what it catches:
- Fisher P5 scored 1.0 (strong margins) but profile shows negative operating margin
- BMP Q4 scored YES (strong growth) but revenue CAGR is below 10%
- Selection Q2 scored YES (earnings consistency) but net income shows 3 loss years

```
[JUDGE] Score Justification -- BMP
P5: INCONSISTENT -- Score is 1.0 but operating margin is -5.16%
Q3: CONSISTENT
```

#### Judge 2 — Bull/Bear Balance Check (Groq)

**Where:** `thesis_writer.py` — after `_parse_sections()`.

Checks whether the three bear case bullets are genuinely company-specific risks or are generic/speculative hedges. Flags each bear point as STRONG / SPECULATIVE / GENERIC / WEAK.

```
[JUDGE] Bull/Bear Balance -- CrowdStrike Holdings
Bear 1: GENERIC -- "competition may intensify" applies to any tech company
Bear 2: STRONG
Bear 3: SPECULATIVE -- no quantitative threshold cited
```

#### Judge 3 — Thesis Coherence Check (rules + conditional Groq)

**Where:** `thesis_writer.py` — after `_parse_sections()`.

Rule-based checks run first (zero tokens):

| Condition | Severity |
|-----------|---------|
| `category == "Egg"` and `decision == "INVEST"` | FAIL |
| `bmp_verdict == "REJECT"` and `decision == "INVEST"` | FAIL |
| `fisher_total >= 12` and `selection_score >= 7` and `decision == "PASS"` | WARN |
| `fisher_total < 6` and `decision == "INVEST"` | WARN |
| `conviction == "LOW"` and `decision == "INVEST"` at full position | WARN |

If no rule triggers, a brief Groq pass checks whether the decision narrative is logically consistent with the position size and conviction stated in the scores.

#### Judge 4 — Cross-Stage Consistency (pure rules, zero tokens)

**Where:** `risk_scoring.py` — after conviction and position size are calculated.

Pure arithmetic on existing result dicts — no Groq call.

| Condition | Severity |
|-----------|---------|
| `fisher_total >= 12` and `selection_score >= 7` and `conviction == "LOW"` | WARN |
| `fisher_total < 7` and `selection_score < 4` and `conviction == "HIGH"` | WARN |
| `category == "Diamond"` and `base_nos >= 4` | INFO (borderline) |
| `total_penalty == 0` and all 5 factors scored 0 | INFO (may be optimistic) |

```
[JUDGE] Cross-Stage Consistency
INFO -- Diamond with 5 NOs is borderline; 1 more NO would move to Gold (4-6%)
```

**Files created/modified:** `agents/judge.py` (new), `agents/bmp_gate.py`, `agents/fisher.py`, `agents/stock_selection.py`, `agents/risk_scoring.py`, `agents/thesis_writer.py`
