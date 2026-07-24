# Stage 8 — Crushability Risk Rating & Position Sizing (25 YES/NO questions)

Count the **NO** answers; fewer NOs = harder to crush = bigger position.
Be conservative — when in doubt, answer NO. **UNKNOWN counts as NO.**

## Part A — 11 data questions (compute from financials)

| # | Question | YES rule |
|---|---|---|
| D1 | Profitable (TTM)? | TTM net income > 0 |
| D2 | FCF-positive (TTM)? | FCF > 0 |
| D3 | Sales growth 10–40% (3yr)? | 10% ≤ CAGR ≤ 40% (>41% = NO, too hot; <10% = NO) |
| D4 | 3-yr self-funding? | FCF positive, OR cash > 3× annual burn |
| D5 | High disclosure standard? | Listed on a major regulated exchange |
| D6 | Transparency? | Financials & insider ownership easy to find |
| D7 | Well-managed? | ROE ≥ 15% most recent FY |
| D8 | Market cap > $500M? | |
| D9 | Beta < 1.3? | (past 12 months) |
| D10 | Positive P/E < 30? | 0 < P/E < 30 |
| D11 | Key insider owns > 5%? | |

## Part B — 14 judgement questions

```
L1  Recognisable brand — do everyday customers know this company's name?
L2  Diversified buyer base — no single customer above 20% of revenue?
L3  Positive word of mouth — do customers actively recommend it / are there fans?
L4  Underdog — free of a direct competitor with materially greater resources?
L5  Goliath — free of disruptive upstarts attacking its core business?
L6  Moat — entry barriers high enough that direct competitors pose limited threat?
L7  Top-3 CXOs — combined leadership tenure over 15 years?
L8  Stock Advisor fit — quality business, proven management, stalwart balance sheet,
    conscious capitalism?
L9  Rule Breaker fit — at least 4 of 6 traits (top dog, sustainable advantage, price
    appreciation, good management, strong brand, seemingly overvalued) and able to
    withstand a binary outcome?
L10 Fraud-free — no history of fraud or misleading statements/deeds?
L11 Want to know more — a business you'd genuinely enjoy studying deeper?
L12 Company-specific risk #1 — name the single biggest risk; positioned to survive it?
L13 Company-specific risk #2 — name the second biggest risk; positioned to survive it?
L14 Macro antifragile — bulletproof to macro shocks, inflation and natural events?
```

Finish with: `CONVICTION: [HIGH/MEDIUM/LOW] One sentence overall conviction.`

## Category & base position size

| # of NOs (incl. UNKNOWN) | Crushable like a… | Position range |
|---|---|---|
| 0–5 | Diamond | 6–10% |
| 6–8 | Marble | 3–5% |
| 9–11 | Jawbreaker | 1–2% |
| 12–14 | Coconut | 0.25–0.75% (<1%) |
| 15–18 | Glass Bottle | 0% |
| 19–25 | Egg | 0% |

Point in range by conviction: HIGH → top of range · MEDIUM → midpoint · LOW → bottom.
Glass Bottle / Egg → always 0%.

## Position-size resolution (in order)

1. Start from the crushability size above.
2. **Cap** at the Investment Stage `stage_cap_pct` (doc 07e).
3. **Anti-Fragile < 7 → forced to 0%.**
4. **Price veto** (OEY < 5%) → flag it: do not buy until Mr. Market offers a better price
   (blocks INVEST in the thesis; doesn't zero the target size).

## Closing memo

Write one paragraph (4–6 sentences) in a professional fund-manager tone summarising the
investment case and position-size rationale. Reference actual data; no bullet points.
