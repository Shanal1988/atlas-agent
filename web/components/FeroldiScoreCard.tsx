"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { FeroldiScore } from "@/lib/types";

interface Props {
  feroldi: FeroldiScore;
}

function bandColor(band: string): string {
  const b = band.toUpperCase();
  if (b.includes("EXCEPTIONAL") || b.includes("GREAT")) return "text-emerald-300";
  if (b.includes("GOOD") || b.includes("AVERAGE")) return "text-amber-300";
  return "text-red-400";
}

export function FeroldiScoreCard({ feroldi }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const deductions = feroldi.gauntlet_items.filter((g) => g.score < 0);

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Feroldi Quality Score
        </h3>
        <div className="flex items-end gap-2">
          <span className="text-3xl font-bold text-white">{feroldi.total}</span>
          <span className="text-slate-400 text-sm mb-0.5">/ 100</span>
          <span className={`text-sm font-bold mb-0.5 ml-2 ${bandColor(feroldi.band)}`}>
            {feroldi.band}
          </span>
        </div>
      </div>

      <div className="text-xs text-slate-400 mb-3">
        Pre-Gauntlet {feroldi.pre_gauntlet}/100 (raw {feroldi.pre_gauntlet_raw}/
        {feroldi.max_effective}) · Gauntlet {feroldi.gauntlet}
      </div>

      {/* Section bars (collapsible) */}
      <div className="space-y-2">
        {feroldi.sections.map((sec) => {
          const pct = sec.max > 0 ? (sec.score / sec.max) * 100 : 0;
          const isOpen = open[sec.key];
          return (
            <div key={sec.key}>
              <button
                onClick={() => setOpen((o) => ({ ...o, [sec.key]: !o[sec.key] }))}
                className="w-full flex items-center gap-2 text-left"
              >
                {isOpen ? (
                  <ChevronDown className="w-3 h-3 text-slate-500 shrink-0" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-slate-500 shrink-0" />
                )}
                <span className="text-xs text-slate-300 w-40 shrink-0">{sec.label}</span>
                <div className="flex-1 h-2 rounded-full bg-slate-700">
                  <div
                    className={`h-2 rounded-full ${
                      pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400 font-mono w-16 text-right shrink-0">
                  {sec.score}/{sec.max}
                </span>
              </button>
              {isOpen && (
                <div className="ml-5 mt-1 mb-2 space-y-1">
                  {sec.items.map((it) => (
                    <div key={it.key} className="flex gap-2 text-xs">
                      <span
                        className={`shrink-0 font-mono ${
                          it.method === "unavailable" ? "text-slate-500" : "text-slate-400"
                        }`}
                      >
                        {it.method === "unavailable" ? "N/A" : `${it.score}/${it.max}`}
                      </span>
                      <span className="text-slate-300">{it.label}</span>
                      <span className="text-slate-500 leading-tight">{it.reasoning}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Gauntlet deductions */}
      {deductions.length > 0 && (
        <div className="border-t border-slate-700 mt-3 pt-3">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
            Gauntlet Deductions
          </div>
          <div className="space-y-1">
            {deductions.map((g) => (
              <div key={g.key} className="flex gap-2 text-xs">
                <span className="shrink-0 font-mono font-bold text-red-400">{g.score}</span>
                <span className="text-slate-300">{g.label}</span>
                <span className="text-slate-500 leading-tight">{g.reasoning}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data gaps */}
      {feroldi.data_gaps.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {feroldi.data_gaps.map((g) => (
            <span
              key={g}
              className="text-[10px] bg-slate-700 text-slate-400 rounded px-1.5 py-0.5"
            >
              no data: {g}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
