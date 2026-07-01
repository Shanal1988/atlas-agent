"use client";

import { SimilarCompany } from "@/lib/types";
import { fmtNum, fmtPct } from "@/lib/formatters";

interface Props {
  companies: SimilarCompany[];
}

export function SimilarCompanies({ companies }: Props) {
  if (!companies?.length) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">
        Similar Companies — Multibagger Candidates
      </h3>
      <div className="space-y-2">
        {companies.map((c, i) => {
          const scoreColor =
            c.multibagger_score >= 8
              ? "bg-emerald-900 text-emerald-300"
              : c.multibagger_score >= 5
              ? "bg-blue-900 text-blue-300"
              : c.multibagger_score >= 3
              ? "bg-amber-900 text-amber-300"
              : "bg-slate-700 text-slate-400";

          return (
            <div
              key={c.ticker}
              className="flex items-center gap-3 bg-slate-700/40 rounded-lg px-3 py-2"
            >
              <span className="text-slate-500 text-xs w-4">{i + 1}.</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-blue-400 text-sm">{c.ticker}</span>
                  <span className="text-slate-300 text-xs truncate">{c.name}</span>
                </div>
                <div className="text-slate-500 text-xs">{c.industry ?? c.sector}</div>
              </div>
              <div className="hidden sm:flex gap-4 text-xs text-slate-300 shrink-0">
                <div>
                  <div className="text-slate-500">Mkt Cap</div>
                  <div>{fmtNum(c.market_cap)}</div>
                </div>
                <div>
                  <div className="text-slate-500">Rev Growth</div>
                  <div className={c.revenue_growth && c.revenue_growth > 0.15 ? "text-emerald-400" : ""}>
                    {fmtPct(c.revenue_growth)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">ROE</div>
                  <div>{fmtPct(c.roe)}</div>
                </div>
                <div>
                  <div className="text-slate-500">Op Margin</div>
                  <div>{fmtPct(c.operating_margin)}</div>
                </div>
                <div>
                  <div className="text-slate-500">P/E</div>
                  <div>{c.pe_ratio != null ? c.pe_ratio.toFixed(1) : "N/A"}</div>
                </div>
              </div>
              <span
                className={`shrink-0 text-xs font-bold px-2 py-1 rounded ${scoreColor}`}
              >
                {c.multibagger_score}/12
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
