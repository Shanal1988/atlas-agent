# Fintech Industry — Sector Knowledge Base

## Market Size and Growth (TAM)

Global financial services revenue is approximately $25 trillion annually (McKinsey). Fintech companies have captured 5–8% of this — roughly $1.5–2 trillion — with the share growing at 15–20% per year as technology-first businesses take market share from incumbent banks and insurers. The largest sub-segments by revenue potential:

- **Consumer banking and neobanks**: $800B+ addressable in deposits, lending, and premium accounts
- **B2B payments infrastructure**: $200B+ in processing fees, FX, and treasury management
- **Wealthtech and investment platforms**: $150B+ in AUM-based and subscription revenue
- **Lending and credit (BNPL, digital mortgages)**: $500B+ in net interest margin potential
- **Insurance technology**: $400B+ in premiums, with 3–5% technology uplift opportunity

## The Regulatory Moat and Risk

Fintech is simultaneously one of the most regulated and most disruption-prone industries. The regulatory framework creates barriers to entry (licences, capital requirements, AML compliance) that advantage established players, but also creates opportunities for disruptors who can navigate it faster than incumbents.

**Key licences and their significance:**
- **Electronic Money Institution (EMI) licence (UK/EU)**: Allows accepting deposits, issuing prepaid cards, and processing payments. Wise and Revolut hold this. Capital requirement ~€350k. Does NOT allow lending.
- **Banking licence (full)**: Allows deposit-taking and lending with fractional reserve. Capital requirement €5M+. Monzo, Revolut (in Europe), and N26 hold these.
- **FCA Authorised Payment Institution**: Required for payment services in the UK. Lower capital requirement; limits to payment execution only.
- **US Money Services Business (MSB) / State Money Transmitter Licences**: Required in each US state individually — a major moat for established players (Wise, PayPal hold all 50).

Obtaining all 50 US state licences takes 2–4 years and $5–15M in compliance cost, creating a significant barrier for new entrants offering cross-border money transfer.

## Float Economics and FCF Distortion

The most important accounting concept for fintech investors: **customer float**. Many fintech companies hold customer funds in transit — money deposited by a user before it is transferred or converted. This creates a timing difference in cash flows that makes standard FCF metrics unreliable.

**Example (Wise)**: Wise holds £10B+ in customer balances at any given moment. These balances appear as liabilities on the balance sheet but generate real float revenue (interest income from investing customer funds in short-duration government bonds). When interest rates rise from 0% to 5%, Wise's float income increases by ~£500M — an enormous earnings tailwind that does not appear as operating leverage in traditional revenue metrics.

Conversely, the operating cash flow statement at Wise includes large changes in customer balance liabilities, making FCF appear inflated relative to actual business cash generation. **FCF for fintech companies should not be used as a valuation metric without adjusting for float movements.** Analysts use underlying free cash flow or operating profit before float income adjustments.

For investors using Atlas, the FCF distortion flag for financial companies reflects this accounting reality.

## Competitive Dynamics

**Neobanks vs. incumbent banks**: Neobanks (Revolut, Monzo, Nubank, Starling) compete primarily on user experience, transparency, and lower fees. They have captured significant account numbers (Revolut: 40M+ users, Nubank: 90M+ users in Brazil) but face structural limitations: without a full banking licence, they cannot lend profitably; with a banking licence, they face the same regulatory capital requirements as incumbents, eliminating their cost advantage.

**B2B infrastructure fintechs**: Wise for Business, Airwallex, Currencycloud (Visa) — compete on multi-currency account infrastructure for SMEs conducting international trade. These businesses have superior economics to consumer fintechs because SME customers have higher lifetime value, lower churn, and higher transaction volumes. The moat is connectivity (direct integrations with 100+ banking partners and payment systems globally) plus regulatory licences in key corridors.

**Embedded finance**: Shopify Balance, Stripe Treasury, Unit Finance, Synapse — fintech-as-a-service allowing non-financial companies (e-commerce platforms, HR software, vertical SaaS) to embed financial products for their customers. This is high-growth because the distribution channel is already built — Shopify doesn't need to acquire new customers to sell them financial products.

## Key Risks

- **Rate sensitivity**: Fintech lending businesses (BNPL, digital mortgages) are highly sensitive to interest rates. Higher rates compress net interest margins for funded lenders; BNPL providers saw credit losses increase significantly in 2022–2023 as consumers struggled with higher cost of living.
- **Regulatory tightening**: BNPL is coming under consumer credit regulation in the UK and EU, requiring affordability checks that may reduce approval rates and growth. Neobanks face increasing scrutiny on AML controls (Revolut faced FCA concerns over transaction monitoring).
- **Customer acquisition costs**: Consumer fintechs spend heavily on acquisition (£20–50 per customer in the UK) to compete with banks that have 20-year customer relationships. The unit economics only work if customers become multi-product and maintain balances for years.
- **Fraud and operational risk**: Real-time payments and instant account opening increase fraud exposure. Starling Bank disclosed elevated fraud losses in 2023 related to authorised push payment (APP) fraud — a risk that scales with transaction volume.
