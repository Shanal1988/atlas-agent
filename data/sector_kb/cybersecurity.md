# Cybersecurity Industry — Sector Knowledge Base

## Market Size and Growth (TAM)

The global cybersecurity market is estimated at $225–250 billion in 2024 and is projected to reach $370–450 billion by 2028, growing at 13–15% CAGR. Growth is structural and countercyclical: breach frequency, data privacy regulation, and cloud adoption each independently drive security spend regardless of macro conditions. Enterprise security budgets have grown as a percentage of IT spend from 5% to 8–12% over the past decade and are expected to continue rising.

The endpoint security (EDR/XDR) segment — the foundation of CrowdStrike and SentinelOne — is a $15–20 billion market growing at 20%+ annually. The adjacent identity security, cloud security (CNAPP), and SIEM/SOAR markets add a combined $30+ billion in TAM for platform-first vendors.

## Competitive Landscape

Three strategic positions have emerged:

**Platform consolidators**: CrowdStrike (Falcon), Palo Alto Networks (Cortex), Microsoft (Defender) — aim to become the operating system of enterprise security by expanding from a strong endpoint or network position into adjacent modules (identity, cloud, SIEM). CrowdStrike's Falcon platform has 24+ modules as of 2024; the strategy is to increase modules per customer (lower sales cost per dollar of ARR).

**Best-of-breed specialists**: Okta (identity), Zscaler (zero trust network), Cloudflare (edge), Varonis (data security) — dominate a single domain and resist platform consolidation by maintaining depth and integration breadth.

**Legacy incumbents**: IBM QRadar, Splunk (now Cisco), McAfee — losing market share as cloud-native architectures outperform on-premises deployments. Cloud-native vendors have a structural advantage in data pipeline latency and AI model training on real-time telemetry.

## The AI Flywheel in Cybersecurity

This is the most important structural dynamic in the sector. A security vendor with more sensors (endpoints, identities, cloud workloads) collects more attack telemetry, trains more accurate threat detection models, detects threats faster, wins more customers, installs more sensors — a compounding loop. CrowdStrike claims its AI model is trained on 1+ trillion signals per week from its installed base of 20,000+ customers.

This flywheel is why scale advantages compound more steeply in security than in most software markets: marginal detection accuracy improvement is hard to measure, but false negative rates (missed attacks) create existential liability for customers, making them reluctant to switch to smaller-data competitors.

## Moat Analysis

**Switching costs**: Security platforms require deep integration with endpoint agents, identity providers, cloud consoles, and SIEM stacks. Full rip-and-replace of CrowdStrike across a 50,000-employee enterprise takes 12–24 months of effort and introduces coverage gaps during migration. This creates high real-world switching barriers even when contract terms expire.

**Data network effects**: As described above, each new customer improves detection for all customers via shared threat intelligence. Customers explicitly value being part of a larger network — this is a genuine network effect unlike SaaS platforms that claim it without evidence.

**Regulatory tailwinds**: The SEC's 2023 cybersecurity disclosure rules (requiring public companies to disclose material breaches within 4 days) increase accountability for security failures, driving procurement urgency and budget prioritisation.

## Unit Economics

Best-in-class cybersecurity SaaS metrics:
- Gross margin: 70–80% (cloud-native delivery with no hardware)
- Net Revenue Retention (NRR): 120–130%+ for platform leaders (customers expand module usage)
- Annual Recurring Revenue (ARR) growth: 25–35% for mid-stage leaders
- Rule of 40: 40–60 for the leading public pure-plays

The ARR expansion model is critical: security platforms sell a base endpoint licence and then cross-sell identity protection, cloud security, SIEM, threat intelligence. Each incremental module sold to an existing customer has near-zero incremental CAC, making the economics significantly better than new logo growth.

## Key Risks

- **Microsoft competition**: Microsoft Defender is bundled free with Windows/Azure licences. Enterprise customers frequently evaluate Defender as a cost-saving measure. CrowdStrike's answer is superior detection rates and platform depth, but pricing pressure from Microsoft is a structural headwind.
- **Concentration in enterprise**: Top 20% of customers by ARR typically represent 50%+ of revenue for mid-large vendors. Losing one or two enterprise accounts has outsized impact.
- **Macroeconomic sensitivity**: While security is relatively recession-resistant, large enterprises do consolidate vendors during cost-cutting cycles — "platform bets" on CrowdStrike/Palo Alto benefit, while second-tier vendors lose contracts.
- **Incident risk**: A significant false negative (missed breach at a high-profile customer) or, worse, a Solarwinds-style supply chain compromise of the vendor's own software, would be severe reputational damage. CrowdStrike's July 2024 content update outage is an example of non-breach operational risk.
