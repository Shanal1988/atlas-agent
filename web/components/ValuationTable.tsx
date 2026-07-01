"use client";

import { ValuationResult } from "@/lib/types";
import { fmtMn, fmtPrice } from "@/lib/formatters";

interface Props {
  valuation: ValuationResult;
  shares: number;
}

function ivPerShare(ivMn: number | undefined | null, shares: number): string {
  if (!ivMn || !shares) return "N/A";
  return fmtPrice((ivMn * 1_000_000) / shares);
}

function premium(ivMn: number | undefined | null, mktcapMn: number): string {
  if (!ivMn) return "N/A";
  const pct = ((mktcapMn - ivMn) / ivMn) * 100;
  const sign = pct > 0 ? "+" : "";
  const cls = pct > 15 ? "text-red-400" : pct < -15 ? "text-emerald-400" : "text-amber-400";
  return `<span class="${cls}">${sign}${pct.toFixed(0)}%</span>`;
}

export function ValuationTable({ valuation, shares }: Props) {
  if (!valuation?.available) {
    return (
      <div className="bg-slate-800 rounded-xl p-4 text-slate-400 text-sm">
        Valuation data not available.
      </div>
    );
  }

  const mkt = valuation.mktcap_mn;

  const rows = [
    {
      model: "Dhandho (Conservative)",
      iv: valuation.dhandho?.lower?.iv,
      label: "Lower",
    },
    {
      model: "Dhandho (Optimistic)",
      iv: valuation.dhandho?.higher?.iv,
      label: "Higher",
    },
    {
      model: "Ben Graham (Conservative)",
      iv: valuation.graham?.lower,
      label: "Lower",
    },
    {
      model: "Ben Graham (Optimistic)",
      iv: valuation.graham?.higher,
      label: "Higher",
    },
    { model: "DCF", iv: valuation.dcf?.iv, label: "" },
    { model: "Expected Returns", iv: valuation.exp_returns?.iv, label: "" },
  ].filter((r) => r.iv != null && r.iv > 0);

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="text-xs text-slate-400 mb-3">
        Market Cap: <span className="text-white font-semibold">{fmtMn(mkt)}</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-400 text-xs border-b border-slate-700">
            <th className="text-left pb-2">Model</th>
            <th className="text-right pb-2">IV (Total)</th>
            <th className="text-right pb-2">Per Share</th>
            <th className="text-right pb-2">Premium</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model} className="border-b border-slate-700/50">
              <td className="py-2 text-slate-200 text-xs">{r.model}</td>
              <td className="py-2 text-right text-white font-mono text-xs">
                {fmtMn(r.iv!)}
              </td>
              <td className="py-2 text-right text-white font-mono text-xs">
                {ivPerShare(r.iv!, shares)}
              </td>
              <td
                className="py-2 text-right text-xs"
                dangerouslySetInnerHTML={{ __html: premium(r.iv!, mkt) }}
              />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
