# Artificial Intelligence Industry — Sector Knowledge Base

## Market Size and Growth (TAM)

AI is the hardest sector to size because estimates depend entirely on what you count. The narrow AI software market was ~$122 billion in 2024, forecast to reach ~$467 billion by 2030 at ~25% CAGR (ABI). Broader definitions that fold in hardware and services put the 2025 market at $244–391 billion and project $800 billion to $3.5 trillion by 2030–2033, with CAGRs of 28–31%. The wide spread is itself the signal: this is an early, fast-compounding market where the addressable opportunity is being redrawn every quarter.

The clearer numbers are on the infrastructure side, where real dollars are already being spent:

- Hyperscaler AI capex: $320 billion+ committed across AWS, Azure, Google Cloud, and Oracle in 2025, with plans rising toward $200 billion+ per year individually by 2027
- AI data centre market: ~$39 billion in 2025, forecast to reach ~$150 billion by 2031 at ~25% CAGR
- AI inference: ~$106 billion in 2025, projected to ~$255 billion by 2030 (~19% CAGR), and the fastest-growing workload as deployed models outnumber trained ones
- Venture funding: AI took ~50% of all global VC in 2025 (~$200 billion), including the largest private round in history (OpenAI at a $300 billion valuation)

The demand driver is the shift of enterprise and consumer software from deterministic code to model-based systems, plus the emergence of agentic workloads that consume far more compute per task than a single prompt.

## Competitive Landscape

AI is best understood as a stack, and the competitive dynamics, and durability of returns, differ sharply at each layer.

**Compute (accelerators)**: Nvidia dominates with ~80–90% of the AI accelerator market by revenue and the CUDA software moat. The credible challenge comes less from AMD (the clearest merchant-silicon alternative) than from hyperscalers designing their own ASICs to reduce Nvidia dependence: Google TPU, AWS Trainium/Inferentia, Microsoft Maia, Meta MTIA. Custom silicon is forecast to take a growing share of inference specifically.

**Cloud infrastructure**: AWS, Microsoft Azure, Google Cloud, and Oracle rent the compute, plus a new tier of AI-native "neoclouds" (CoreWeave, Nebius, Lambda) built specifically around GPU clusters. This layer is capital-intensive but captures durable, recurring demand as the toll road for everyone above it.

**Foundation models**: OpenAI, Anthropic, Google DeepMind, Meta (open-weight Llama), xAI, Mistral, and China's DeepSeek and Alibaba. This is the most contested and least settled layer. Capability leadership rotates between labs on a months-long cadence, and the release of highly capable open-weight models (DeepSeek's low-cost training claims being the sharpest example) repeatedly compresses the premium that closed frontier models can charge.

**Applications and tooling**: The layer closest to end revenue, ranging from horizontal assistants (Microsoft Copilot, ChatGPT, Gemini) to vertical AI products and the orchestration/agent tooling that sits between models and applications. Distribution is the main advantage here: incumbents with existing enterprise reach (Microsoft, Salesforce, ServiceNow) can attach AI to a captive install base faster than a standalone product can acquire users.

## The Compute-Cost and Monetisation Gap

This is the most important structural tension in the sector and the equivalent, for AI, of float economics in fintech: a place where standard metrics mislead. The industry is spending hundreds of billions on infrastructure years ahead of the revenue that infrastructure is meant to produce. Hyperscaler and lab capex is being laid down against a demand curve that is real but unproven at the scale implied by the spending. The result is a widening gap between capital deployed and revenue recognised, and the terminal value of the whole sector rests on that gap closing.

Two features make this gap hard to read from the outside. First, GPU depreciation is contested: whether an accelerator has a useful life of three, five, or six years swings reported margins and returns on invested capital dramatically, and the true rate of obsolescence (as each Nvidia generation leaps ahead) is unknown. Aggressive depreciation assumptions flatter near-term profitability while risking large write-downs if the hardware ages faster than modelled. Second, some of the demand is circular: model labs, chipmakers, and clouds increasingly invest in, prepay, or take equity in one another, so a portion of reported AI revenue reflects capital recycling within the ecosystem rather than independent end-customer demand.

For an investor, the practical implication mirrors the fintech float lesson: headline AI revenue growth and reported infrastructure margins should not be taken at face value without asking who the end customer is, what depreciation schedule underpins the margin, and whether the demand is externally funded or recycled inside the stack.

## Moat Analysis

Moats in AI are strong at the bottom of the stack and fragile in the middle, which is the opposite of where most capital and attention flow.

**Durable at the infrastructure layer**: Nvidia's CUDA ecosystem, the hyperscalers' capital scale, and physical constraints (power, land, and grid interconnection for data centres) are genuine, compounding barriers. Access to constrained resources, advanced-packaging capacity, HBM supply, and multi-gigawatt power, is becoming as much of a moat as any technology.

**Fragile at the model layer**: Frontier capability is expensive to build but has so far proven quick to replicate or approximate, and open-weight releases repeatedly reset the price of "good enough." A lab's defensibility rests less on model weights than on distribution, proprietary data, product surface, and switching costs it can build around the model, not the model itself.

**Thin at the application layer, unless attached to distribution or data**: A standalone AI feature is easy to copy and easy to churn away from. The applications that hold up are those embedded in a workflow, dataset, or install base the user cannot easily leave, the same logic that governs any software moat, now with a faster commoditisation clock.

## Unit Economics

The economics differ so much by layer that a single "AI margin" is meaningless:

- Accelerator vendors (Nvidia): gross margins ~70–75%, effectively selling the scarce input to everyone else
- Cloud and neocloud infrastructure: capital-heavy, margins depend entirely on GPU utilisation and the depreciation schedule applied; underutilised clusters lose money quickly
- Foundation model labs: enormous fixed training cost (a frontier run is a large sunk investment), then a per-token inference cost that must be priced above serving cost to make gross margin, which open-weight competition keeps compressing
- Applications: potentially high gross margin, but carrying a variable model-inference cost of goods that pure software never had, so scaling revenue does not scale margin the way traditional SaaS did

The defining feature is that inference is a real, recurring cost of goods sold. Unlike classic software, where marginal cost is near zero, every AI query consumes compute. This caps gross margins for anyone reselling model output and makes cost-per-token, and the ability to drive it down through better models or cheaper silicon, a central competitive variable rather than a footnote.

## Key Risks

- **Monetisation lagging capex**: The central risk. If enterprise and consumer willingness to pay does not grow into the infrastructure being built, the sector faces a correction in capex, GPU orders, and valuations. The spending is committed years ahead of the proof.
- **Model commoditisation**: Capable open-weight models (the DeepSeek episode being the clearest warning) compress the price of frontier capability and threaten the economics of labs that spent the most to build it. The premium for being marginally ahead may be smaller and shorter-lived than the capital required to get there.
- **GPU depreciation and obsolescence**: If accelerators age faster than the (often aggressive) schedules on which margins are reported, the industry faces large write-downs and returns well below what current accounting implies. This risk is largely invisible until it is realised.
- **Power and physical constraints**: AI data centres are projected to consume ~8.5% of US electricity by 2030. Grid interconnection, power availability, and cooling are becoming the binding constraint on buildout, capable of stranding planned capacity regardless of chip supply.
- **Concentration and circular financing**: A handful of players (Nvidia, a few hyperscalers, a few labs) dominate, and they are increasingly financially entangled through cross-investment and prepayment. This concentrates systemic risk and makes reported demand harder to trust as independent.
- **Regulation and geopolitics**: Frontier-model rules, data and copyright litigation, and US–China export controls all bear directly on the sector. Restrictions on advanced-chip exports can halve the addressable market for specific products and reroute billions in planned spend, as recent Nvidia and ASML China restrictions show.
