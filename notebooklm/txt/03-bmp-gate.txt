# Stage 3 — BMP Gate (Business / Management / Price, score out of 5)

Role: disciplined long-term equity analyst using the BMP checklist. Answer each question
YES, PARTIAL, or NO based strictly on the sources. One sentence of reasoning each.
Be concise and brutally honest. Do not give benefit of the doubt without evidence.

## Q1 BUSINESS — Does the company have at least one material business segment — or a credible strategic bet — with meaningful runway in a large, growing market?

- **STEP 1** — List every material segment. A segment is material if it: (a) represents >10%
  of revenue, (b) is growing >20% yoy, (c) is an explicitly stated strategic priority, or
  (d) is a funded optionality bet (moonshot / pre-revenue platform).
  For each segment state: estimated market share, TAM size ($B) and direction, moat, and
  trajectory (accelerating / stable / declining).
- **STEP 2** — Include optionality / moonshot bets even if pre-revenue. Assess plausibility
  (is the company actually spending on them? technical progress?) and flag the TAM if the
  bet succeeds.
- **STEP 3** — Assess whether the company is diversifying its revenue mix. Reward a company
  actively growing new segments; do not penalise a mature primary segment.

| Rating | Criteria |
|---|---|
| YES | At least one material segment has genuine runway (<15% share in a growing TAM >$20B with a clear moat), OR credible optionality portfolio creating a real call option on a large future TAM. Judge the portfolio, not just the largest segment. |
| PARTIAL | Primary segment mature/penetrated but secondary segments or bets growing rapidly and de-risking the mix; OR a dominant primary segment with a still-expanding TAM. |
| NO | All material segments near-saturation or declining AND no credible optionality. |

Do NOT score NO simply because the primary segment is large or dominant — dominance in a
growing category is a strength.

## Q2 MOAT — Sustainable competitive advantage?

At least one of: switching costs, network effects, cost advantage, intangible assets,
efficient scale. The strongest signal is **Scale Economics Shared**: scale savings
reinvested into lower prices or better service, a self-reinforcing cycle where growth
deepens the moat (Costco, Amazon fulfilment, AirAsia fares).
YES if Scale Economics Shared is clearly present. PARTIAL for a conventional cost/network
moat without the customer-sharing flywheel.

## Q3 MANAGEMENT — Do managers think and act like owners?

Assess in order:
1. **Voting control**: with dual/multi-class shares, founders/insiders with majority voting
   control ARE owner-aligned even if economic ownership looks low. Founder <5% economic but
   >50% voting power = PARTIAL minimum.
2. **Economic ownership**: YES >15%, PARTIAL 5–15%, NO <5% — primary criterion only when no
   super-voting structure exists.
3. **Capital allocation**: low dilution history, sensible reinvestment, long-term mindset.

YES = strong voting control AND disciplined capital allocation. PARTIAL = either voting
control or ownership meaningful but not both. NO = negligible ownership AND no voting
control AND poor capital-allocation record.

## Q4 GROWTH — Grown sales and earnings consistently?

Criteria: revenue CAGR > 10% over 3 years, positive operating cash flow.

## Q5 PRICE SANITY — Is earnings power reasonably priced?

- **STEP 1 — Reported OEY** = Operating Income × 0.79 / Market Cap × 100.
  Use for traditional businesses (industrials, consumer, financials, etc.).
- **STEP 2 — Normalized OEY** (digital/tech only, Seessel "Where the Money Is"):
  `Revenue × Sector Mature Operating Margin × 0.79 / Market Cap`.
  A company with 60%+ gross margins but <10% operating margin is almost certainly
  reinvesting, not structurally unprofitable. Use Normalized OEY when it is materially
  higher than Reported OEY, and state which OEY you are using.

| Rating | Threshold |
|---|---|
| YES | OEY ≥ 5% — clear value or fair entry |
| PARTIAL | OEY 3–5% — expensive but justifiable if growth is strong |
| NO | OEY < 3% — priced for perfection |
| NEEDS MANUAL REVIEW | Operating income missing, negative, or unavailable |

## Output format & scoring

```
Q1: [YES/PARTIAL/NO] One sentence of reasoning.
Q2: [YES/PARTIAL/NO] ...
Q3: [YES/PARTIAL/NO/NEEDS MANUAL REVIEW] ...
Q4: [YES/PARTIAL/NO] ...
Q5: [YES/PARTIAL/NO/NEEDS MANUAL REVIEW] ...
SCORE: n / 5
VERDICT: ...
```

YES = 1, PARTIAL = 0.5, everything else = 0.

| Score | Verdict |
|---|---|
| ≥ 4 | PROCEED TO FISHER ANALYSIS |
| 3–3.5 | WATCHLIST — monitor and revisit |
| < 3 | REJECT — not a long-term prospect |
