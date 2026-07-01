"use client";

import { RiskScore } from "@/lib/types";

interface Props {
  risk: RiskScore;
}

const CATEGORY_CONFIG: Record<string, { bg: string; text: string; border: string }> = {
  Diamond: { bg: "bg-blue-950", text: "text-blue-300", border: "border-blue-500" },
  Gold:    { bg: "bg-yellow-950", text: "text-yellow-300", border: "border-yellow-500" },
  Silver:  { bg: "bg-slate-800", text: "text-slate-200", border: "border-slate-400" },
  Bronze:  { bg: "bg-orange-950", text: "text-orange-300", border: "border-orange-500" },
  Glass:   { bg: "bg-purple-950", text: "text-purple-300", border: "border-purple-500" },
  Egg:     { bg: "bg-red-950", text: "text-red-400", border: "border-red-600" },
};

export function RiskBadge({ risk }: Props) {
  const cfg = CATEGORY_CONFIG[risk.category] ?? CATEGORY_CONFIG.Silver;

  return (
    <div className={`${cfg.bg} border ${cfg.border} rounded-xl p-4`}>
      <div className="flex items-center justify-between mb-3">
        <span className={`text-xl font-bold ${cfg.text}`}>{risk.category}</span>
        <span className="text-slate-400 text-sm">{risk.conviction} conviction</span>
      </div>
      <div className="flex items-end gap-2 mb-3">
        <span className="text-4xl font-bold text-white">{risk.position_pct}%</span>
        <span className="text-slate-400 text-sm mb-1">position size</span>
      </div>
      <div className="text-xs text-slate-400 mb-3">{risk.alloc_label} allocation range</div>

      <div className="border-t border-slate-700 pt-3 space-y-2">
        {risk.factors.map((f) => (
          <div key={f.key} className="flex gap-2 text-xs">
            <span
              className={`shrink-0 font-bold ${
                f.penalty === 0
                  ? "text-emerald-400"
                  : f.penalty === 1
                  ? "text-amber-400"
                  : "text-red-400"
              }`}
            >
              {f.key} {f.penalty > 0 ? `+${f.penalty}` : "✓"}
            </span>
            <span className="text-slate-300 leading-tight">{f.reasoning}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
