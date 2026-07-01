"use client";

import { IndustryResult } from "@/lib/types";
import { fmtNum, fmtPct } from "@/lib/formatters";

interface Props {
  industry: IndustryResult;
}

export function PeerTable({ industry }: Props) {
  if (!industry?.peers?.length) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">Peer Comparison</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[500px]">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700">
              <th className="text-left pb-2">Ticker</th>
              <th className="text-left pb-2">Company</th>
              <th className="text-right pb-2">Mkt Cap</th>
              <th className="text-right pb-2">P/E</th>
              <th className="text-right pb-2">ROE</th>
              <th className="text-right pb-2">ROIC</th>
              <th className="text-right pb-2">Op Margin</th>
              <th className="text-right pb-2">Rev Growth</th>
            </tr>
          </thead>
          <tbody>
            {industry.peers.map((p) => (
              <tr key={p.ticker} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                <td className="py-2 font-mono font-bold text-blue-400">{p.ticker}</td>
                <td className="py-2 text-slate-300 max-w-[140px] truncate">{p.name ?? "—"}</td>
                <td className="py-2 text-right text-white font-mono">{fmtNum(p.market_cap)}</td>
                <td className="py-2 text-right text-slate-200">
                  {p.pe_ratio != null ? p.pe_ratio.toFixed(1) : "N/A"}
                </td>
                <td className="py-2 text-right text-slate-200">{fmtPct(p.roe)}</td>
                <td className="py-2 text-right text-slate-200">{fmtPct(p.roic)}</td>
                <td className="py-2 text-right text-slate-200">{fmtPct(p.operating_margin)}</td>
                <td
                  className={`py-2 text-right font-semibold ${
                    (p.revenue_growth ?? 0) > 0.1
                      ? "text-emerald-400"
                      : (p.revenue_growth ?? 0) < 0
                      ? "text-red-400"
                      : "text-slate-200"
                  }`}
                >
                  {fmtPct(p.revenue_growth)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {industry.sections?.INDUSTRY_OVERVIEW && (
        <div className="mt-4 space-y-3">
          {(["INDUSTRY_OVERVIEW", "MARKET_STRUCTURE", "COMPETITIVE_POSITION"] as const).map(
            (key) =>
              industry.sections[key] ? (
                <div key={key}>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">
                    {key.replace(/_/g, " ")}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {industry.sections[key]}
                  </p>
                </div>
              ) : null
          )}
        </div>
      )}
    </div>
  );
}
