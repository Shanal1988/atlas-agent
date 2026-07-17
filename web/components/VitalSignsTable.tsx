"use client";

import { VitalSignsScore } from "@/lib/types";

interface Props {
  vitals: VitalSignsScore;
}

function scoreStyle(score: number): string {
  if (score >= 1) return "bg-emerald-950 text-emerald-300 border-emerald-600";
  if (score >= 0.5) return "bg-amber-950 text-amber-300 border-amber-600";
  return "bg-red-950 text-red-400 border-red-600";
}

export function VitalSignsTable({ vitals }: Props) {
  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Ten Vital Signs
        </h3>
        <span className="text-sm font-bold text-white">
          {vitals.total}/{vitals.max}
        </span>
      </div>

      <div className="space-y-2">
        {vitals.items.map((it) => (
          <div key={it.key} className="flex items-start gap-2 text-xs">
            <span
              className={`shrink-0 w-9 text-center border rounded px-1 py-0.5 font-bold font-mono ${scoreStyle(
                it.score
              )}`}
            >
              {it.score}
            </span>
            <div>
              <div className="text-slate-200 font-medium">{it.label}</div>
              <div className="text-slate-400 leading-tight">{it.reasoning}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-700 mt-3 pt-3 space-y-2 text-xs">
        <div>
          <span className="text-slate-400 font-semibold">Sane valuation? </span>
          <span className="text-slate-300">{vitals.closing.sane_valuation}</span>
        </div>
        <div>
          <span className="text-slate-400 font-semibold">Opportunity cost: </span>
          <span className="text-slate-300">{vitals.closing.opportunity_cost}</span>
        </div>
      </div>
    </div>
  );
}
