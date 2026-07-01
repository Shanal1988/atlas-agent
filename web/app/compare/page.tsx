"use client";

import { useState } from "react";
import useSWR from "swr";
import { listAnalyses, compareAnalyses } from "@/lib/api";
import { Analysis, AnalysisSummary } from "@/lib/types";
import { fmtNum, fmtDate, fmtPct, fmtCagr } from "@/lib/formatters";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const DECISION_STYLE: Record<string, string> = {
  INVEST: "bg-emerald-900/60 text-emerald-300",
  WATCHLIST: "bg-amber-900/60 text-amber-300",
  PASS: "bg-red-900/60 text-red-400",
};

const BAR_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export default function ComparePage() {
  const { data: history } = useSWR<AnalysisSummary[]>("history", listAnalyses);
  const [selected, setSelected] = useState<string[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[] | null>(null);
  const [loading, setLoading] = useState(false);

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 5 ? [...prev, id] : prev
    );
  }

  async function compare() {
    if (!selected.length) return;
    setLoading(true);
    const data = await compareAnalyses(selected);
    setAnalyses(data);
    setLoading(false);
  }

  // Build chart data from analyses
  const scoreChartData = analyses?.map((a) => ({
    name: a.ticker,
    BMP: a.scores.bmp.score,
    Fisher: a.scores.fisher.total / 15 * 5, // scale to /5 for visual comparison
    Selection: a.scores.selection.score,
  })) ?? [];

  const metricsData = analyses?.map((a) => ({
    name: a.ticker,
    ROE: a.profile.roe != null ? +(a.profile.roe * 100).toFixed(1) : 0,
    ROCE: (a.profile as any).roce_avg != null ? +((a.profile as any).roce_avg * 100).toFixed(1) : 0,
    "Rev CAGR": a.profile.revenue_cagr != null ? +(a.profile.revenue_cagr * 100).toFixed(1) : 0,
  })) ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Compare Companies</h1>

      {/* Select analyses */}
      <div className="bg-slate-800 rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300">
            Select up to 5 analyses
          </h2>
          <button
            onClick={compare}
            disabled={loading || selected.length < 2}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {loading ? "Loading..." : `Compare (${selected.length})`}
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-64 overflow-y-auto pr-1">
          {(history ?? []).map((a) => {
            const sel = selected.includes(a.id);
            return (
              <button
                key={a.id}
                onClick={() => toggle(a.id)}
                className={`flex items-center gap-3 text-left rounded-lg p-2 border transition-colors ${
                  sel
                    ? "bg-blue-900/40 border-blue-600"
                    : "bg-slate-700/30 border-slate-700 hover:border-slate-500"
                }`}
              >
                <div
                  className={`w-4 h-4 rounded border shrink-0 flex items-center justify-center ${
                    sel ? "bg-blue-600 border-blue-500" : "border-slate-500"
                  }`}
                >
                  {sel && <span className="text-white text-xs">✓</span>}
                </div>
                <div>
                  <span className="font-mono font-bold text-blue-400 text-xs">{a.ticker}</span>
                  <span className="text-slate-400 text-xs ml-2">{fmtDate(a.date)}</span>
                  <div className="text-xs text-slate-500 truncate max-w-[150px]">{a.company}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Comparison results */}
      {analyses && (
        <div className="space-y-6">
          {/* Score chart */}
          {scoreChartData.length > 0 && (
            <div className="bg-slate-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">
                Scores (BMP /5, Fisher scaled /5, Selection /8)
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={scoreChartData}>
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                  <Bar dataKey="BMP" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Fisher" fill="#10b981" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Selection" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Metrics chart */}
          {metricsData.length > 0 && (
            <div className="bg-slate-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-3">Key Metrics (%)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={metricsData}>
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                  <Bar dataKey="ROE" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="ROCE" fill="#10b981" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Rev CAGR" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Side-by-side cards */}
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${analyses.length}, minmax(0, 1fr))` }}>
            {analyses.map((a, i) => (
              <div key={a.ticker} className="bg-slate-800 rounded-xl p-4 space-y-3 text-sm">
                <div>
                  <span className="font-mono font-bold text-blue-400">{a.ticker}</span>
                  <div className="text-xs text-slate-400">{a.company}</div>
                </div>
                {a.thesis.decision && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${DECISION_STYLE[a.thesis.decision] ?? ""}`}>
                    {a.thesis.decision}
                  </span>
                )}
                <div className="space-y-1 text-xs text-slate-300">
                  <div className="flex justify-between"><span className="text-slate-500">Mkt Cap</span><span>{fmtNum(a.profile.market_cap)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">BMP</span><span>{a.scores.bmp.score}/5</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Fisher</span><span>{a.scores.fisher.total}/15</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Selection</span><span>{a.scores.selection.score}/8</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Risk</span><span>{a.scores.risk.category} {a.scores.risk.position_pct}%</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">ROE</span><span>{fmtPct(a.profile.roe)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Rev CAGR</span><span>{fmtCagr(a.profile.revenue_cagr)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Moat</span><span className="text-right max-w-[100px] truncate">{a.profile.moat}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
