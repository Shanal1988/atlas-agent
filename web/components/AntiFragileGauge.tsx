"use client";

import { AntiFragileScore } from "@/lib/types";

interface Props {
  antifragile: AntiFragileScore;
}

const MIN = -7;
const MAX = 17;

function bandColor(total: number): string {
  if (total >= 12) return "text-emerald-300";
  if (total >= 7) return "text-blue-300";
  return "text-red-400";
}

export function AntiFragileGauge({ antifragile }: Props) {
  const pct = ((antifragile.total - MIN) / (MAX - MIN)) * 100;
  const mark7 = ((7 - MIN) / (MAX - MIN)) * 100;
  const mark12 = ((12 - MIN) / (MAX - MIN)) * 100;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Anti-Fragile Score
        </h3>
        <span className={`text-sm font-bold ${bandColor(antifragile.total)}`}>
          {antifragile.total} · {antifragile.band}
        </span>
      </div>

      <div className="relative h-3 rounded-full bg-slate-700 mb-1">
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${
            antifragile.total >= 12
              ? "bg-emerald-500"
              : antifragile.total >= 7
              ? "bg-blue-500"
              : "bg-red-500"
          }`}
          style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
        />
        {/* Band markers at 7 (investable) and 12 (fantastic) */}
        <div className="absolute inset-y-0 w-px bg-slate-300/60" style={{ left: `${mark7}%` }} />
        <div className="absolute inset-y-0 w-px bg-slate-300/60" style={{ left: `${mark12}%` }} />
      </div>
      <div className="relative text-[10px] text-slate-500 h-4 mb-2">
        <span className="absolute left-0">-7</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${mark7}%` }}>7</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${mark12}%` }}>12</span>
        <span className="absolute right-0">17</span>
      </div>
      <div className="text-[10px] text-slate-500 mb-3">
        &lt;7 IGNORE · 7–12 INVESTABLE · ≥12 FANTASTIC
      </div>

      <div className="space-y-1">
        {antifragile.items.map((it) => (
          <div key={it.key} className="flex justify-between gap-2 text-xs">
            <span className="text-slate-300">{it.label}</span>
            <span
              className={`font-mono font-bold ${
                it.points > 0
                  ? "text-emerald-400"
                  : it.points < 0
                  ? "text-red-400"
                  : "text-slate-400"
              }`}
            >
              {it.points > 0 ? `+${it.points}` : it.points}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
