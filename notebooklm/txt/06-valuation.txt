# Stage 6 — Intrinsic Value Analysis (4 models)

Pure arithmetic — no judgement. Ask NotebookLM to walk each calculation step by step,
then **verify the arithmetic yourself** (spreadsheet recommended). All values in $ millions
(total IV, then ÷ shares outstanding for per-share).

## Constants

- Discount rate: **10%** (all models)
- Terminal growth (DCF only): **3%**
- Graham zero-growth P/E: **8.5**
- 3-phase growth schedules (defaults — adjust with judgement):
  - **Lower**: Yr 1–3: 12% · Yr 4–6: 10% · Yr 7–10: 8%
  - **Higher**: Yr 1–3: 15% · Yr 4–6: 12% · Yr 7–10: 10%

## Step 1 — Choose the base cash flow

1. **Financial / fintech company** (banks, payments, insurance, money transfer):
   OCF and FCF are distorted by customer float/deposits. Use **NOPAT Owner Earnings**:
   - NOPAT = Operating Income × (1 − effective tax rate); tax rate = income tax / pretax
     income, clamped to 10–40%, default 25%
   - NOPAT OE = NOPAT + maintenance D&A − maintenance capex (≈ NOPAT for asset-light)
   - Set **net cash = 0** (balance-sheet cash includes segregated customer funds)
2. **Capex-heavy reinvestment cycle** (FCF < 40% of OCF): FCF understates earnings power.
   Use **Owner Earnings = OCF − maintenance capex**.
3. **Otherwise**: use **FCF** (or OCF as last resort if FCF ≤ 0).

### Maintenance capex estimation (Buffett / Mauboussin / Mark Leonard)

- Physical PP&E depreciation = ~100% real maintenance cash cost.
- Amortisation of acquired intangibles = MOSTLY non-economic (customer relationships
  maintained via S&M opex, technology via R&D, brands don't wear out). Count only a small
  % as real cash cost (~8% tech, ~15% most sectors, ~20% utilities).
- If only total D&A is available, apply a sector-blended factor:
  Technology ~55% · Communication ~69% · Consumer ~83–87% · Healthcare ~67% ·
  Industrials ~87% · Financials ~45% · Utilities ~92% · Energy/Materials ~87–89% ·
  default ~70%.
- Cap: maintenance capex ≤ total capex actually spent.
- Floor: Owner Earnings ≥ reported FCF.
- Growth capex is deliberately NOT deducted — it creates the future cash flows already
  captured in the growth rates.

## Model 1 — Dhandho (lower & higher)

```
Project base CF for 10 years using the 3-phase schedule.
IV = Σ PV(CF_t)  for t = 1..10, discounted at 10%
   + PV of terminal value, where TV = CF_10 / 0.10   (zero-growth perpetuity)
   + net cash
```
Run once with the Lower phases, once with the Higher phases.

## Model 2 — Ben Graham (lower & higher)

```
IV ($M) = Avg 5-yr Net Income ($M) × (8.5 + 2 × G)
```
G is in percentage points. Base growth = 5-yr NI CAGR (else revenue CAGR, else 8%),
clamped to [−10, 30]. **Lower G = 50% of base; Higher G = 80% of base.**
A negative IV means the company fails the Graham test at that growth rate — exclude
negative Graham values from the final IV range.

## Model 3 — DCF (Gordon Growth terminal)

```
Same 10-year projection (Lower phases).
TV = CF_10 × 1.03 / (0.10 − 0.03)
IV = Σ PV(CF_t) + PV(TV) + net cash
```

## Model 4 — Expected Returns

```
Projected NI (yr 10) = latest NI × (1 + NI CAGR)^10
Exit P/E             = max(current P/E × 0.5, 15)
IV = Projected NI × Exit P/E / 1.10^10
```

## Summary & verdict

Build the summary table (IV total + per share for each model). Then:

- IV Range = min–max of Dhandho lower/higher, DCF, Expected Returns (exclude Graham
  negatives).
- Compare current market cap to the range **midpoint**:
  premium > 20% → **OVERVALUED** · discount > 20% → **UNDERVALUED** · else **FAIRLY VALUED**.

Also compute the **Operating Earnings Yield** (doc 03) — OEY < 5% is a price veto used by
later stages.
