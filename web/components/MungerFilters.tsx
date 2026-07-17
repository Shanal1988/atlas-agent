"use client";

import { MungerScore } from "@/lib/types";

interface Props {
  munger: MungerScore;
}

const RATING_STYLE: Record<string, string> = {
  YES: "bg-emerald-950 text-emerald-300 border-emerald-600",
  TBC: "bg-amber-950 text-amber-300 border-amber-600",
  NO: "bg-red-950 text-red-400 border-red-600",
};

export function MungerFilters({ munger }: Props) {
  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Munger Four Filters
        </h3>
        <span className="text-sm font-bold text-white">{munger.pass_count}/4</span>
      </div>
      <div className="space-y-2">
        {munger.filters.map((f) => (
          <div key={f.key} className="flex items-start gap-2 text-xs">
            <span
              className={`shrink-0 w-11 text-center border rounded px-1 py-0.5 font-bold ${
                RATING_STYLE[f.rating] ?? RATING_STYLE.TBC
              }`}
            >
              {f.rating}
            </span>
            <div>
              <div className="text-slate-200 font-medium">{f.label}</div>
              <div className="text-slate-400 leading-tight">{f.reasoning}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-700 mt-3 pt-2 text-xs text-slate-300">
        {munger.verdict}
      </div>
    </div>
  );
}
