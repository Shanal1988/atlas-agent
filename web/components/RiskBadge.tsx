"use client";

import { RiskScore } from "@/lib/types";

interface Props {
  risk: RiskScore;
}

const CATEGORY_CONFIG: Record<string, { bg: string; text: string; border: string }> = {
  // Crushability categories
  Diamond:        { bg: "bg-blue-950", text: "text-blue-300", border: "border-blue-500" },
  Marble:         { bg: "bg-slate-800", text: "text-slate-200", border: "border-slate-400" },
  Jawbreaker:     { bg: "bg-amber-950", text: "text-amber-300", border: "border-amber-500" },
  Coconut:        { bg: "bg-orange-950", text: "text-orange-300", border: "border-orange-500" },
  "Glass Bottle": { bg: "bg-purple-950", text: "text-purple-300", border: "border-purple-500" },
  Egg:            { bg: "bg-red-950", text: "text-red-400", border: "border-red-600" },
  // Legacy categories (older analyses)
  Gold:   { bg: "bg-yellow-950", text: "text-yellow-300", border: "border-yellow-500" },
  Silver: { bg: "bg-slate-800", text: "text-slate-200", border: "border-slate-400" },
  Bronze: { bg: "bg-orange-950", text: "text-orange-300", border: "border-orange-500" },
  Glass:  { bg: "bg-purple-950", text: "text-purple-300", border: "border-purple-500" },
};

export function RiskBadge({ risk }: Props) {
  const cfg = CATEGORY_CONFIG[risk.category] ?? CATEGORY_CONFIG.Marble;
  const noItems = (risk.questions ?? []).filter(
    (q) => q.answer === "NO" || q.answer === "UNKNOWN"
  );

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
      <div className="text-xs text-slate-400 mb-3">
        {risk.alloc_label} allocation range
        {risk.no_count != null && (
          <span className="ml-2">· {risk.no_count} NOs / 25</span>
        )}
        {risk.price_veto && (
          <span className="ml-2 text-red-400 font-semibold">· PRICE VETO</span>
        )}
      </div>

      {(risk.sizing_notes ?? []).length > 0 && (
        <div className="border-t border-slate-700 pt-3 space-y-1 mb-1">
          {risk.sizing_notes!.map((n, i) => (
            <div key={i} className="text-xs text-amber-300 leading-tight">! {n}</div>
          ))}
        </div>
      )}

      {noItems.length > 0 && (
        <div className="border-t border-slate-700 pt-3 space-y-2">
          {noItems.slice(0, 6).map((q) => (
            <div key={q.key} className="flex gap-2 text-xs">
              <span
                className={`shrink-0 font-bold ${
                  q.answer === "UNKNOWN" ? "text-amber-400" : "text-red-400"
                }`}
              >
                {q.key} {q.answer === "UNKNOWN" ? "?" : "✗"}
              </span>
              <span className="text-slate-300 leading-tight">{q.label}</span>
            </div>
          ))}
          {noItems.length > 6 && (
            <div className="text-xs text-slate-500">
              +{noItems.length - 6} more in the Crushability checklist below
            </div>
          )}
        </div>
      )}

      {/* Legacy analyses: 5 penalty factors */}
      {!risk.questions && risk.factors?.length > 0 && (
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
      )}
    </div>
  );
}
