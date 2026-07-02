"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, TrendingUp } from "lucide-react";
import { startAnalysis, listAnalyses } from "@/lib/api";
import useSWR from "swr";
import { AnalysisSummary } from "@/lib/types";
import { fmtNum, fmtDate } from "@/lib/formatters";
import Link from "next/link";
import { useAnalysisContext } from "@/contexts/AnalysisContext";

const DECISION_STYLE = {
  INVEST: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  WATCHLIST: "bg-amber-900/60 text-amber-300 border-amber-700",
  PASS: "bg-red-900/60 text-red-400 border-red-800",
};

export default function HomePage() {
  const router = useRouter();
  const { setActiveJob } = useAnalysisContext();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: history } = useSWR<AnalysisSummary[]>("history", listAnalyses, {
    refreshInterval: 10000,
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { job_id } = await startAnalysis(query.trim());
      setActiveJob({ jobId: job_id, company: query.trim() });
      router.push(`/running/${job_id}`);
    } catch (err: any) {
      setError(err.message ?? "Failed to start analysis");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <div className="text-center mb-12 mt-8">
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="text-blue-400 text-4xl">▲</span>
          <h1 className="text-4xl font-bold text-white">Atlas</h1>
        </div>
        <p className="text-slate-400 text-lg">
          Long-term equity research, fully automated
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSubmit} className="w-full max-w-xl mb-12">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter a company name (e.g. Nvidia, Apple, Wise PLC)"
            className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-12 pr-32 py-4 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-sm"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
          >
            {loading ? "Starting..." : "Analyse"}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </form>

      {/* Recent Analyses */}
      {history && history.length > 0 && (
        <div className="w-full">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              Recent Analyses
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {history.slice(0, 9).map((a) => (
              <Link
                key={a.id}
                href={`/analysis/${a.id}`}
                className="bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl p-4 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <span className="font-mono font-bold text-blue-400 text-sm">
                      {a.ticker}
                    </span>
                    <div className="text-xs text-slate-400 mt-0.5">{fmtDate(a.date)}</div>
                  </div>
                  {a.decision && (
                    <span
                      className={`text-xs border px-2 py-0.5 rounded-full font-semibold shrink-0 ${
                        DECISION_STYLE[a.decision] ?? "bg-slate-700 text-slate-300 border-slate-600"
                      }`}
                    >
                      {a.decision}
                    </span>
                  )}
                </div>
                <div className="text-sm text-white font-medium mb-1 group-hover:text-blue-300 transition-colors">
                  {a.company}
                </div>
                <div className="text-xs text-slate-500">
                  {a.sector} · {fmtNum(a.market_cap)}
                </div>
                {a.risk_category && (
                  <div className="mt-2 text-xs text-slate-400">
                    {a.risk_category} · {a.position_pct}% position
                  </div>
                )}
              </Link>
            ))}
          </div>
          {history.length > 9 && (
            <div className="text-center mt-4">
              <Link
                href="/history"
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                View all {history.length} analyses →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
