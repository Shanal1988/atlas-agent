"use client";

import { CompanyProfile } from "@/lib/types";
import { fmtNum, fmtPct, fmtPrice, fmtCagr } from "@/lib/formatters";

interface Props {
  profile: CompanyProfile;
}

const MOAT_COLOR: Record<string, string> = {
  "Network effects": "bg-purple-900 text-purple-300",
  "Switching costs": "bg-blue-900 text-blue-300",
  "Cost advantage": "bg-green-900 text-green-300",
  "Intangible assets": "bg-orange-900 text-orange-300",
  "Efficient scale": "bg-teal-900 text-teal-300",
};

export function CompanyProfileCard({ profile }: Props) {
  const moatClass =
    MOAT_COLOR[profile.moat] ?? "bg-slate-700 text-slate-300";

  return (
    <div className="bg-slate-800 rounded-xl p-4 mb-4">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h2 className="text-lg font-bold text-white">{profile.name}</h2>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-sm font-mono text-blue-400 font-bold">{profile.ticker}</span>
            <span className="text-slate-500">•</span>
            <span className="text-sm text-slate-400">{profile.exchange}</span>
            <span className="text-slate-500">•</span>
            <span className="text-sm text-slate-400">{profile.sector} / {profile.industry}</span>
          </div>
        </div>
        <span className={`shrink-0 text-xs px-2 py-1 rounded font-medium ${moatClass}`}>
          {profile.moat || "No moat"}
        </span>
      </div>

      <p className="text-sm text-slate-300 leading-relaxed mb-4">{profile.description}</p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Market Cap", value: fmtNum(profile.market_cap) },
          { label: "Price", value: fmtPrice(profile.current_price) },
          { label: "P/E", value: profile.pe_ratio?.toFixed(1) ?? "N/A" },
          { label: "Beta", value: profile.beta?.toFixed(2) ?? "N/A" },
          { label: "Rev CAGR", value: fmtCagr(profile.revenue_cagr) },
          { label: "ROE", value: fmtPct(profile.roe) },
          {
            label: "ROCE (avg)",
            value:
              (profile as any).roce_avg != null
                ? fmtPct((profile as any).roce_avg)
                : "N/A",
          },
          { label: "Insider Own.", value: fmtPct(profile.insider_ownership_pct) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-700/50 rounded-lg p-2">
            <div className="text-xs text-slate-400">{label}</div>
            <div className="text-sm font-semibold text-white mt-0.5">{value}</div>
          </div>
        ))}
      </div>

      {profile.growth_drivers?.length > 0 && (
        <div className="mt-4">
          <div className="text-xs text-slate-400 uppercase tracking-wide mb-2">
            Growth Drivers
          </div>
          <ul className="space-y-1">
            {profile.growth_drivers.map((g, i) => (
              <li key={i} className="text-xs text-slate-300 flex gap-2">
                <span className="text-emerald-500">→</span> {g}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
