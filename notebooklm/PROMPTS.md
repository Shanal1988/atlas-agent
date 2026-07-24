# Atlas Prompt Pack for NotebookLM

Keep this file locally — do NOT upload it as a source. Paste one prompt at a time into
NotebookLM chat, in order. Replace `<COMPANY>` with the company name. After each stage,
copy the output into your Stock Analysis sheet (or a running summary doc) before moving on.

Tip: NotebookLM answers only from sources. If it says data is missing, upload the missing
document (or paste the figures into a new source doc) and re-ask.

---

## Prompt 0 — Company snapshot (run first)

```
From the uploaded company documents for <COMPANY>, build a company snapshot: what the
company does in plain language, business segments with % of revenue, sector/industry,
market cap, current price, shares outstanding, P/E, beta, exchange, last 3-5 years of
revenue with CAGR, latest net income, operating income, operating cash flow, free cash
flow, capex, cash and total debt (net cash/debt), ROE, insider ownership and share class
structure, identified moat, growth drivers, and key risk factors. Flag anything not found
in the sources. I will provide current price/market cap if the documents are stale:
[PASTE CURRENT PRICE, MARKET CAP, SHARES OUTSTANDING HERE]
```

## Prompt 1 — Industry & competitors

```
Apply the source "01-industry-analysis" to <COMPANY>. Define the specific industry from
the business description (not the generic sector label), identify 4-6 publicly traded
DIRECT competitors per the peer selection rules, build the peer comparison table from the
uploaded data (mark gaps as N/A), and reply using exactly the labels
INDUSTRY_OVERVIEW / MARKET_STRUCTURE / COMPETITIVE_POSITION / KEY_DYNAMICS /
PEER_COMPARISON / MOAT_VS_PEERS.
```

## Prompt 2 — Munger Four Filters

```
Apply the source "02-munger-four-filters" to <COMPANY>. Answer F1-F3 with [YES/TBC/NO]
plus one sentence of reasoning each, strictly from the sources. For F4, compute the
Operating Earnings Yield (Operating Income × 0.79 / Market Cap × 100), show the
calculation, and apply the thresholds. End with PASSED: n/4 and the VERDICT per the
verdict logic.
```

## Prompt 3 — BMP Gate

```
Apply the source "03-bmp-gate" to <COMPANY>. Work through Q1 (including the 3 steps:
material segments with share/TAM/moat/trajectory, optionality bets, revenue-mix
diversification), Q2 (look specifically for Scale Economics Shared), Q3 (check voting
control before economic ownership), Q4, and Q5 (compute Reported OEY, and Normalized OEY
if this is a digital company with suppressed margins — state which you use). Answer each
[YES/PARTIAL/NO] with one sentence of reasoning, then SCORE: n/5 (YES=1, PARTIAL=0.5)
and VERDICT per the scorecard. Be brutally honest; no benefit of the doubt without
evidence.
```

## Prompt 4 — Fisher 15 Points

```
Apply the source "04-fisher-15-points" to <COMPANY>. Score all 15 points using only
1 / 0.75 / 0.5 / 0, one evidence-based sentence each, citing which source document the
evidence comes from. If evidence is absent for a point, score 0 and say so. End with
FISHER SCORE: n/15 and FISHER RATING per the bands. List the points where the sources
were insufficient so I can upload more material.
```

## Prompt 5 — Stock Selection Checklist

```
Apply the source "05-stock-selection" to <COMPANY>. First compute the inputs: Buffett
Ratio (change in market cap over ~5 years ÷ cumulative retained earnings), capex % of
revenue, FCF margin and FCF/NI conversion — show the arithmetic. If this is a
financial/fintech company, score Q8 on OCF instead of FCF per the adjustment rule. Then
score Q1-Q8 [YES/PARTIAL/NO] with one sentence each, and end with SELECTION SCORE: n/8
and the verdict.
```

## Prompt 6 — Valuation (4 models)

```
Apply the source "06-valuation" to <COMPANY>. Step 1: choose the base cash flow (FCF,
Owner Earnings if FCF < 40% of OCF, or NOPAT Owner Earnings if financial/fintech) and
show the derivation including maintenance capex estimation and net cash treatment.
Step 2: compute all four models — Dhandho lower & higher, Ben Graham lower & higher
(derive G from NI CAGR: lower=50%, higher=80% of base), DCF, and Expected Returns —
showing the year-by-year projection tables and every formula. Step 3: produce the
IV summary table (total $M and per share), the IV range excluding negative Graham
values, the premium/discount to the midpoint vs current market cap, the
OVERVALUED/FAIRLY VALUED/UNDERVALUED verdict, and the OEY with the price-veto flag if
OEY < 5%. Show all arithmetic so I can verify it in a spreadsheet.
```

## Prompt 7 — Process scores (Feroldi, Anti-Fragile, Vital Signs, Stage)

Run as four short chats to keep outputs complete:

```
7a. Apply section 7a of source "07-process-scoring" plus §9 of "00-master-process" to
<COMPANY>. Score the financial items from the uploaded financials, then M1-M6, P1-P4,
C0-C1, K1-K2, G1-G2, S1-S3, and the Gauntlet X1-X12 (exact allowed values only), one
sentence each, conservative. Show: Moat subtotal scaled ×30/75, Pre-Gauntlet /100,
Gauntlet total, FINAL SCORE, and a list of data gaps.
```

```
7b. Using §10 of "00-master-process" and the Feroldi answers above, derive the
Anti-Fragile Score (-7 to 17) item by item and state the band: <7 IGNORE, 7-12
INVESTABLE, 12+ FANTASTIC.
```

```
7c. Apply section 7c of source "07-process-scoring" to <COMPANY>. Score V1-V10 with
0/0.5/1 and one sentence each (remember: net debt > 0 caps V1 at 0.5), total /10, then
answer SANE_VALUATION and OPPORTUNITY_COST in one sentence each using the Stage 6 IV
range.
```

```
7d. Apply section 7e of source "07-process-scoring" to <COMPANY>. First state the
deterministic candidate window from profitability + growth, then pick the single best
stage within that window and the Lynch category. Reply as STAGE / LYNCH / REASON and
state the stage_cap_pct and whether the stage says "do not invest".
```

## Prompt 8 — Crushability & position sizing

```
Apply the source "08-crushability-risk" to <COMPANY>. Answer D1-D11 from the financial
data (show the number behind each) and L1-L14 as judgement calls, one sentence each,
[YES/NO] only — when in doubt or data is missing, answer NO/UNKNOWN. Count NOs
(UNKNOWN counts as NO), state the crushability category and base position range, give
CONVICTION [HIGH/MEDIUM/LOW], then resolve the final position size: pick the point in
range by conviction, cap at the stage_cap_pct from stage 7d, force to 0% if
Anti-Fragile < 7, and flag the price veto if OEY < 5%. Finish with the one-paragraph
fund-manager memo.
```

## Prompt 9 — Thesis & decision

```
Apply the source "09-thesis-template" to <COMPANY>. Using everything established in this
chat's earlier stages (scores, IV range, crushability, sizing), write the full thesis
using exactly the labels EXECUTIVE_SUMMARY through DECISION_RATIONALE. Bears and watch
points must contain numbers or named events. Acknowledge where price sits vs the IV
range. Then check the hard guardrails (AF < 7, Glass Bottle/Egg, price veto) and
downgrade INVEST to WATCHLIST with the guardrail note if any apply. DECISION_RATIONALE
must reference the Feroldi score and stage allocation guidance.
```

## Prompt 10 — Record sheet row (optional)

```
Summarise this analysis as a single record: Date | Company | Ticker | Munger n/4 |
BMP n/5 | Fisher n/15 | Selection n/8 | Feroldi score | Anti-Fragile score | Vital
Signs n/10 | Stage + Lynch | Crushability category + NO count | Final position % |
IV range ($M and per share) | Price vs IV | OEY | DECISION | one-line rationale.
```
