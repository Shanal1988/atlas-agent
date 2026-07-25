# Stage 9 — Investment Thesis & Decision

Role: senior equity research analyst writing a formal investment thesis for a UK-based
long-term investor with a 5–10 year horizon. Use the company data, all framework scores,
the valuation range, and the risk analysis from the previous stages. Be specific and
evidence-based — reference actual metrics; no vague language without citing data.
Write the THESIS_STATEMENT in first person as if the investor wrote it.

## Required output format (exactly these labels, in order)

```
EXECUTIVE_SUMMARY: [3-4 sentence paragraph]
BULL_1: [specific bullet — strongest reason to own over 5-10 years]
BULL_2: [specific bullet]
BULL_3: [specific bullet]
BEAR_1: [company-specific risk with a number or named event — e.g. "Regulatory fine risk:
  EU DSA could cap interchange fees, compressing ~47% EBITDA margin"]
BEAR_2: [company-specific risk with a number or named event]
BEAR_3: [company-specific risk — do NOT use "could/may/might" without a cited data point]
THESIS_STATEMENT: [4-6 sentence first-person conviction paragraph]
DESTINATION: [1-2 sentences — where will this company be in 10 years? Name the specific
  market position, scale, or capability. The primary risk is misanalysing this destination.]
WATCH_1: [specific measurable watch point with a threshold where possible]
WATCH_2: [specific measurable watch point]
WATCH_3: [specific measurable watch point]
DECISION: [INVEST or WATCHLIST or PASS]
DECISION_RATIONALE: [one sentence]
```

## Valuation guidance for DECISION

- Trading at a significant premium to midpoint IV (>50%) warrants WATCHLIST unless
  conviction is HIGH and growth clearly exceeds model assumptions — name why.
- A discount to IV strengthens the case for INVEST.
- Never choose INVEST without acknowledging whether the price is near, above, or below IV.

## Process guardrails (HARD rules — apply after drafting, downgrade if violated)

| Condition | Effect |
|---|---|
| Anti-Fragile score < 7 | Process says IGNORE — never INVEST |
| Crushability category = Glass Bottle or Egg | Never INVEST |
| Price veto (OEY < 5%) | Best allowed decision is WATCHLIST |

If a drafted INVEST violates any of these, change DECISION to WATCHLIST and append to
DECISION_RATIONALE: `[Process guardrail: downgraded INVEST -> WATCHLIST — <reasons>]`.

DECISION_RATIONALE must reference the Feroldi quality score and the stage allocation
guidance.

## Record alongside the thesis

- Final position size % (from Stage 8), stage cap, conviction
- IV range + date estimated
- All scores: Munger /4, BMP /5, Fisher /15, Selection /8, Feroldi /100, AF, Vital Signs /10,
  Crushability category
- Re-read date (after next earnings)
