"use client";

import { StageScore } from "@/lib/types";

interface Props {
  stage: StageScore;
}

function segColor(n: number, active: number): string {
  if (n !== active) return "bg-slate-700";
  if (n <= 4) return "bg-red-500";
  if (n <= 7) return "bg-amber-500";
  if (n <= 10) return "bg-emerald-500";
  return "bg-blue-500";
}

export function StageBadge({ stage }: Props) {
  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Investment Stage
        </h3>
        <span className="text-sm font-bold text-white">
          Stage {stage.stage_number}/12
        </span>
      </div>

      {/* 12-segment stage strip */}
      <div className="flex gap-0.5 mb-1">
        {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
          <div
            key={n}
            className={`h-2.5 flex-1 first:rounded-l-full last:rounded-r-full ${segColor(
              n,
              stage.stage_number
            )}`}
            title={`Stage ${n}`}
          />
        ))}
      </div>
      <div className="text-xs text-slate-300 font-medium mb-3">{stage.stage_label}</div>

      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-slate-400">Risk</span>
          <span className="text-slate-200">{stage.risk}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Return potential</span>
          <span className="text-slate-200">{stage.return_potential}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Allocation guidance</span>
          <span className={stage.do_invest ? "text-emerald-300" : "text-red-400"}>
            {stage.allocation_guidance} (cap {stage.stage_cap_pct}%)
          </span>
        </div>
      </div>

      <div className="border-t border-slate-700 mt-3 pt-2 flex items-center gap-2">
        <span className="text-xs bg-blue-950 text-blue-300 border border-blue-600 rounded px-2 py-0.5 font-semibold">
          {stage.lynch_category}
        </span>
        <span className="text-[10px] text-slate-400">
          {stage.lynch_attributes} · alloc {stage.lynch_allocation}
        </span>
      </div>
      {stage.reasoning && (
        <div className="text-xs text-slate-400 mt-2 leading-tight">{stage.reasoning}</div>
      )}
    </div>
  );
}
