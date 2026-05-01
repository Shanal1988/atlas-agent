# Payments Industry — Sector Knowledge Base

## Market Size and Growth (TAM)

The global payments industry processes over $2 quadrillion in transaction value annually. The digital payments segment — covering card networks, payment processors, cross-border transfers, and embedded finance — is estimated at $130–150 billion in revenue as of 2024, growing at 8–12% annually. Cross-border B2B payments represent the fastest-growing sub-segment, with the market projected to reach $250 billion by 2027 as international trade and remote work drive multi-currency flows.

Consumer cross-border remittances total approximately $850 billion annually (World Bank). Digital remittance providers (Wise, Remitly, WorldRemit) have captured 15–20% of this market, displacing traditional bank wire transfers and Western Union as price competition intensifies. Penetration of digital channels is still under 30% in most corridors, indicating significant runway.

## Competitive Landscape

The payments stack has three distinct layers:
- **Network layer**: Visa, Mastercard, American Express — collect basis points on interchange, benefit from extreme network effects (every new merchant and cardholder increases the utility of all existing participants). Combined they process ~$20 trillion in card volume annually.
- **Processor / acquirer layer**: Stripe, Adyen, Worldpay, Fiserv — provide connectivity between merchants and networks, compete on developer experience, reliability, and cross-border capabilities.
- **Money movement / FX layer**: Wise, Revolut, PayPal — specialise in currency conversion and real-time settlement at lower FX spreads than traditional banks.

Adyen occupies an unusual position: it holds acquiring licences across 40+ countries, operates its own processing infrastructure end-to-end, and charges a simple interchange-plus-processing fee. This vertical integration allows gross margins of 40–50% at scale. Stripe competes on developer experience and ecosystem breadth; it has voluntarily avoided card-issuing and FX to remain platform-neutral.

## Regulatory Environment

Payments is heavily regulated but regulation has been net positive for disruptors:
- **PSD2 (Europe)**: Mandates open banking APIs, reducing switching costs for fintechs and enabling account-to-account payments that bypass card networks.
- **Faster Payments / SEPA Instant**: Real-time settlement infrastructure reduces float economics but improves customer experience.
- **FCA Electronic Money Institution (EMI) regulations**: Wise, Revolut, and Monzo hold EMI licences, giving them near-bank capabilities without full banking capital requirements.
- **Anti-Money Laundering (AML) and KYC**: Compliance burden is high but creates moat for established players — obtaining licences in 40+ countries takes years and significant capital.

## Unit Economics and Moat

Payment networks exhibit the strongest network effects in financial services — Metcalfe's law applies directly. For a processor like Adyen, value compounds as more merchants onboard: data from billions of transactions improves fraud detection, which reduces chargeback rates, which improves economics for merchants, which drives more volume.

Switching costs are high: a merchant integrating Adyen's full payment stack (online, in-store, unified commerce reporting) faces 12–18 months of migration work to switch to a competitor. This creates sticky, recurring revenue with net revenue retention typically above 100% for enterprise-focused processors.

## Key Risks

- **Margin compression**: Card network fee disputes (merchants periodically win fee reductions in regulatory proceedings) can compress take rates for processors.
- **Real-time payment bypass**: A2A (account-to-account) payments via open banking could reduce card interchange revenue if adoption scales — early adoption has been slower than forecast in Europe.
- **FX volatility**: Cross-border processors carry short-term FX exposure on the spread between transaction time and settlement; rapid currency moves can generate episodic losses.
- **Concentration in a few corridors**: Most cross-border payment profitability concentrates in USD/EUR/GBP corridors; emerging market expansion is growth-accretive but higher-risk.
