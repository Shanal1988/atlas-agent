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
- **LLM scoring** — Groq `llama-3.3-70b-versatile` for all structured scoring and writing

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
