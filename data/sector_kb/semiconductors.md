# Semiconductor Industry — Sector Knowledge Base

## Market Size and Growth (TAM)

The global semiconductor market was worth roughly $775 billion in 2024 and is projected to reach $1.5–1.8 trillion by 2030, a ~13% CAGR (McKinsey). Consensus estimates from PwC, Statista, and others cluster lower ($1.0–1.3 trillion by 2030) because they use narrower device definitions, so the honest read is a $1–1.6 trillion market by decade end depending on scope. The sector is structurally cyclical (inventory gluts and shortages swing revenue 20%+ year to year) but has a rising secular floor driven by silicon content per device increasing across autos, data centres, and industrial.

Growth is heavily concentrated at the leading edge. McKinsey projects a 22% CAGR for leading-edge non-memory nodes versus 2–4% for mature nodes. The starkest numbers are at the frontier: 3nm demand rising ~25% annually, 2nm (first available 2025) forecast to grow ~136% through 2030, and 1.4nm (expected ~2027) implying a triple-digit CAGR off a zero base. In memory, High Bandwidth Memory (HBM), the stacked DRAM that feeds AI accelerators, is growing ~20% versus ~12% for standard DDR DRAM and ~9% for NAND. The single largest demand vector is AI infrastructure: hyperscaler capital expenditure plans now top $1 trillion cumulatively by 2029, and AI-focused hardware is the fastest-growing end segment.

The largest structural sub-markets:

- Logic (CPUs, GPUs, accelerators, SoCs): the largest and fastest-growing value pool, pulled by AI compute
- Memory (DRAM, NAND, HBM): highly cyclical, commoditised at the low end, differentiated and supply-constrained in HBM
- Analog and power (Texas Instruments, Infineon, STMicro, onsemi): fragmented, sticky, geared to autos and industrial
- Semiconductor capital equipment: ~$83 billion in 2024, growing ~8–9%, the pick-and-shovel layer of the whole industry
- Advanced packaging (CoWoS, chiplets, 3D stacking): a ~$40 billion market growing ~10%+, increasingly where performance gains come from as transistor scaling slows

## Competitive Landscape

The industry splits by role in the value chain rather than by product, and the profit pools are distributed very unevenly across those roles.

**Fabless designers**: Nvidia, AMD, Qualcomm, Broadcom, Apple (in-house silicon), MediaTek. They own the architecture, IP, and, in Nvidia's case, the software ecosystem, and outsource manufacturing. They capture the highest margins because they carry no fab depreciation. Nvidia holds roughly 80–90% of the AI accelerator market by revenue and reported ~$194 billion of data centre revenue in FY2026.

**Foundries (pure-play manufacturers)**: TSMC, Samsung Foundry, GlobalFoundries, UMC, SMIC. TSMC held ~70% of the total foundry market in 2025 and upwards of 90% at the advanced node (3nm/2nm), where its yields (above 60%) materially exceed Samsung's (~40%). This is the tightest bottleneck in modern technology: TSMC fabricates the overwhelming majority of the world's advanced logic, making it the single point through which Nvidia, AMD, and Apple all pass.

**Integrated device manufacturers (IDMs)**: Intel, Samsung, Micron, SK Hynix, Texas Instruments. They design and manufacture in-house. Intel is attempting the hardest turnaround in the industry, pivoting to a contract foundry model with its 18A (1.8nm-class) node as the bet-the-company milestone; its foundry division remains structurally loss-making. Micron and SK Hynix, alongside Samsung, control the memory oligopoly, with SK Hynix currently leading in HBM for AI.

**Equipment and materials (toolmakers)**: ASML, Applied Materials, Lam Research, Tokyo Electron, KLA. This layer sells the physics-defying machinery every fab depends on. ASML holds a 100% monopoly on extreme ultraviolet (EUV) lithography and ~94% of lithography overall; no advanced chip is manufactured anywhere on Earth without its tools.

**Design software and IP**: Synopsys and Cadence form a near-duopoly in electronic design automation (EDA), the software without which no complex chip can be designed. Arm licenses the instruction-set architecture underneath nearly every mobile SoC and, increasingly, data centre CPUs.

## The Foundry Aggregation Flywheel and Process-Node Economics

This is the most important structural dynamic in the sector and the reason profit concentrates the way it does. Each new process node costs more to develop and requires a fab costing more to build (a leading-edge fab now exceeds $20 billion, and leading-edge wafers sell for $20,000+). No single chip designer generates enough volume to justify that capex alone. A foundry that aggregates demand from the entire industry (Nvidia, Apple, AMD, Qualcomm all at once) can fund the next node, achieve the yields that come only from massive cumulative volume, and therefore win the next generation of designs, which funds the node after that. This is a compounding loop that has driven the industry from dozens of leading-edge manufacturers in the 2000s to effectively one (TSMC) at the 2nm frontier.

The same aggregation logic runs up the supply chain to ASML. Only a monopoly lithography supplier can absorb the multi-decade, multi-billion-dollar R&D required to make EUV work; a single EUV machine contains over 100,000 parts from ~5,000 suppliers and its High-NA successor sells for up to €400 million. The result is a stacked set of monopolies and near-monopolies (ASML in EUV, TSMC in advanced foundry, Synopsys/Cadence in EDA, Nvidia in AI accelerators) each protected by the fact that the capital and cumulative-learning barriers to entry now exceed what any new entrant can rationally fund.

The corollary for investors: value does not accrue evenly across the chain. The layers with the deepest moats (equipment, advanced foundry, AI accelerators, EDA) capture disproportionate profit, while commoditised layers (mature-node foundry, standard memory) earn cyclical, capital-intensive returns.

## Moat Analysis

**Cumulative process leadership**: Advanced-node manufacturing is a learning-curve business. Yield improvement comes from running enormous wafer volumes and accumulating defect data no competitor can replicate. TSMC's lead is less a single technology than an institutional trust advantage: designers commit 2–3 years ahead to its roadmap, which compounds its volume advantage further.

**Equipment monopoly**: ASML's EUV position is close to unassailable. Nikon and Canon compete only in older lithography and have invested a fraction of what ASML has over three decades. ASML also earns ~€8 billion of high-margin recurring revenue from servicing its installed base, growing ~26% annually, which gives it exceptional earnings quality on top of the monopoly.

**Software and ecosystem lock-in**: Nvidia's CUDA is the clearest example. Fifteen years of libraries, tooling, and developer familiarity mean that even a cheaper or faster competing accelerator faces a huge software-migration cost. The EDA duopoly and Arm's architecture licensing work the same way: the switching cost is the entire toolchain and IP ecosystem built on top of them.

**Advanced packaging as the new bottleneck**: As transistor scaling slows, performance increasingly comes from packaging multiple dies together (TSMC's CoWoS, chiplets, 3D stacking). Priority access to constrained CoWoS capacity has itself become a competitive weapon, and Nvidia's preferential allocation is part of why competitors struggle to ship at volume.

## Unit Economics

Margins vary dramatically by position in the value chain, which is the single most important thing to model:

- Fabless designers (Nvidia): gross margins ~70–75%, no fab depreciation, but dependent on foundry capacity allocation
- Advanced foundry (TSMC): gross margins ~58–59%, carrying a crushing depreciation burden but aggregating whole-industry volume
- Equipment (ASML): gross margins ~51–53% on systems, higher on the recurring service/upgrade base
- Memory (Micron, SK Hynix): deeply cyclical, gross margins swinging from negative in gluts to 50%+ at peaks

Key economic features to hold in mind: capital intensity is extreme (a modern fab is a $20B+ commitment against a node with a finite commercial life), depreciation dominates foundry cost structures, and R&D runs 15–25% of revenue at the leading edge. Because so much cost is fixed and sunk, utilisation is everything: a fab running below capacity destroys margin fast, which is why the cycle whips earnings so hard. The recurring-revenue layers (ASML service base, EDA subscriptions, foundry long-term commitments) are what smooth otherwise violent cyclicality.

## Key Risks

- **Cyclicality**: The industry over- and under-builds capacity on a multi-year cycle. Inventory corrections (as in 2022–2023) can cut segment revenue sharply even while the long-term trend is up. Memory is the most extreme, capable of swinging from record profit to loss within a year.
- **Geopolitics and Taiwan concentration**: The single largest tail risk in global technology. TSMC produces the majority of the world's advanced logic from Taiwan; any disruption from cross-strait conflict, natural disaster, or blockade would be an economic shock with no near-term substitute. Fab diversification to Arizona, Japan, and Germany is under way but reproduces only a fraction of capacity.
- **Export controls**: US restrictions on advanced chips and equipment to China are tightening and unpredictable. ASML's China revenue is falling from ~33% of sales in 2025 toward ~20% in 2026 on export curbs; Nvidia has repeatedly had to redesign or halt China-specific products. Rules can change with little notice and reprice affected companies quickly.
- **Capex overbuild tied to AI**: The current supercycle assumes AI demand keeps absorbing accelerator supply. If model-training cadence slows or hyperscaler capex is cut, the leading edge is exposed to a sharp inventory correction, with foundry and equipment orders the first to fall.
- **Customer concentration**: Concentration is severe at every layer. ASML's top two customers are ~38% of revenue; TSMC's largest customers (Apple, Nvidia) are a large share of advanced-node loading. Losing or seeing a pause from one anchor customer has outsized impact.
- **Execution risk at the frontier**: The economics assume the next node arrives on schedule. Intel's 18A and High-NA EUV ramps, Samsung's yield recovery, and TSMC's 2nm/1.4nm transitions each carry real technical risk; a stumble reshuffles competitive position and years of design wins.
