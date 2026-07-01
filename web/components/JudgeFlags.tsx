"use client";

import { JudgeFlag } from "@/lib/types";

interface Props {
  flags: Record<string, JudgeFlag>;
}

const SEV_CONFIG = {
  FAIL: { bg: "bg-red-950/40 border-red-900", badge: "bg-red-900 text-red-300", icon: "✕" },
  WARN: { bg: "bg-amber-950/40 border-amber-900", badge: "bg-amber-900 text-amber-300", icon: "⚠" },
  INFO: { bg: "bg-slate-800 border-slate-700", badge: "bg-slate-700 text-slate-300", icon: "i" },
};

export function JudgeFlags({ flags }: Props) {
  const entries = Object.entries(flags).filter(
    ([, v]) => v.flags?.length > 0
  );

  if (!entries.length) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
        LLM Judge Audit
      </h3>
      <div className="space-y-2">
        {entries.map(([key, flag]) => {
          const cfg = SEV_CONFIG[flag.severity] ?? SEV_CONFIG.INFO;
          return (
            <div key={key} className={`border rounded-lg p-3 ${cfg.bg}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${cfg.badge}`}>
                  {cfg.icon} {flag.severity}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {key.replace(/_/g, " ")}
                </span>
              </div>
              <ul className="space-y-1">
                {flag.flags.map((f, i) => (
                  <li key={i} className="text-xs text-slate-300 leading-relaxed">
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
