# Atlas Process — NotebookLM Edition

This folder converts the automated Atlas pipeline into a manual, document-driven process
you run inside Google NotebookLM.

## Setup (per company)

1. Create a new NotebookLM notebook named after the ticker (e.g. "WISE analysis").
2. Upload the **10 process docs** in this folder (`00`–`09`) as sources — they are the "brain".
3. Upload the **company documents** (see checklist below).
4. Open `PROMPTS.md` locally (do NOT upload it) and paste the prompts into NotebookLM chat
   one stage at a time, in order.
5. Record each stage's output in your Stock Analysis sheet (or a running summary doc).

## Company document checklist (manual ingestion)

- Latest annual report / 10-K (and prior year if available)
- Latest quarterly report / 10-Q
- 2–4 most recent earnings call transcripts
- Investor presentation / capital markets day deck
- Proxy statement (management comp, insider ownership, share classes)
- Key financials: 5–10 years of income statement, balance sheet, cash flow
  (export from TIKR/FMP or paste the filing tables into a doc)
- 1–2 industry reports or credible market-size articles
- Optional: Glassdoor summary, peer comparison table (market cap, P/E, ROE, ROIC,
  operating margin, revenue growth for 4–6 direct competitors)

## Stage order

```
1. Industry & competitors   (01)
2. Munger Four Filters      (02)
3. BMP Gate                 (03)
4. Fisher 15 Points         (04)
5. Stock Selection 8Q       (05)
6. Valuation (4 models)     (06)
7. Process scores           (07)  Feroldi / Anti-Fragile / Vital Signs / Stage+Lynch
8. Crushability & sizing    (08)
9. Thesis & decision        (09)
```

## Known limits vs the app

- NotebookLM cannot fetch live prices or run code — you supply current price,
  market cap, and share count, and you verify all arithmetic (especially DCF).
- No screening/discover stage — pick tickers with an external screener.
- Save outputs yourself; chats are not your system of record.
