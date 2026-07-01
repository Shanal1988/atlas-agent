"use client";

import { useState } from "react";
import useSWR from "swr";
import { listAnalyses } from "@/lib/api";
import { AnalysisSummary } from "@/lib/types";
import { fmtNum, fmtDate, fmtPct, fmtCagr } from "@/lib/formatters";
import Link from "next/link";
import { Search } from "lucide-react";

const DECISION_STYLE = {
  INVEST: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  WATCHLIST: "bg-amber-900/60 text-amber-300 border-amber-700",
  PASS: "bg-red-900/60 text-red-400 border-red-800",
};

export default function HistoryPage() {
  const { data, isLoading } = useSWR<AnalysisSummary[]>("history", listAnalyses);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("ALL");

  const filtered = (data ?? []).filter((a) => {
    const matchSearch =
      !search ||
      a.ticker?.toLowerCase().includes(search.toLowerCase()) ||
      a.company?.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "ALL" || a.decision === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Analysis History</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ticker or company..."
            className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
        {(["ALL", "INVEST", "WATCHLIST", "PASS"] as const).map((d) => (
          <button
            key={d}
            onClick={() => setFilter(d)}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
              filter === d
                ? "bg-blue-600 border-blue-500 text-white"
                : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
            }`}
          >
            {d}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="text-slate-400 text-sm">Loading...</div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-slate-400 text-sm">No analyses found.</div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead>
            <tr className="text-slate-400 text-xs border-b border-slate-700">
              <th className="text-left pb-3 pr-4">Ticker</th>
              <th className="text-left pb-3 pr-4">Company</th>
              <th className="text-left pb-3 pr-4">Date</th>
              <th className="text-center pb-3 pr-4">Decision</th>
              <th className="text-right pb-3 pr-4">BMP</th>
              <th className="text-right pb-3 pr-4">Fisher</th>
              <th className="text-right pb-3 pr-4">Risk</th>
              <th className="text-right pb-3 pr-4">Position</th>
              <th className="text-right pb-3">ROE</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr
                key={a.id}
                className="border-b border-slate-800 hover:bg-slate-800/50 group"
              >
                <td className="py-3 pr-4">
                  <Link
                    href={`/analysis/${a.id}`}
                    className="font-mono font-bold text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    {a.ticker}
                  </Link>
                </td>
                <td className="py-3 pr-4">
                  <Link href={`/analysis/${a.id}`} className="text-slate-200 hover:text-white transition-colors">
                    {a.company}
                  </Link>
                </td>
                <td className="py-3 pr-4 text-slate-400 text-xs">{fmtDate(a.date)}</td>
                <td className="py-3 pr-4 text-center">
                  {a.decision && (
                    <span
                      className={`text-xs border px-2 py-0.5 rounded-full font-semibold ${
                        DECISION_STYLE[a.decision] ?? "bg-slate-700 text-slate-300 border-slate-600"
                      }`}
                    >
                      {a.decision}
                    </span>
                  )}
                </td>
                <td className="py-3 pr-4 text-right text-slate-300">
                  {a.bmp_score ?? "—"}/5
                </td>
                <td className="py-3 pr-4 text-right text-slate-300">
                  {a.fisher_score ?? "—"}/15
                </td>
                <td className="py-3 pr-4 text-right text-slate-300">
                  {a.risk_category ?? "—"}
                </td>
                <td className="py-3 pr-4 text-right text-slate-300">
                  {a.position_pct != null ? `${a.position_pct}%` : "—"}
                </td>
                <td className="py-3 text-right text-slate-300">
                  {fmtPct(a.roe)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
