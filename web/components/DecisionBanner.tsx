"use client";

interface Props {
  decision: "INVEST" | "WATCHLIST" | "PASS" | null;
  rationale: string;
  company: string;
  ticker: string;
}

const CONFIG = {
  INVEST: {
    bg: "bg-emerald-600",
    badge: "bg-emerald-800",
    icon: "✓",
    label: "INVEST",
  },
  WATCHLIST: {
    bg: "bg-amber-500",
    badge: "bg-amber-700",
    icon: "◎",
    label: "WATCHLIST",
  },
  PASS: {
    bg: "bg-red-600",
    badge: "bg-red-800",
    icon: "✕",
    label: "PASS",
  },
};

export function DecisionBanner({ decision, rationale, company, ticker }: Props) {
  if (!decision) return null;
  const cfg = CONFIG[decision];

  return (
    <div className={`${cfg.bg} text-white rounded-xl p-5 mb-6 flex items-start gap-4`}>
      <div
        className={`${cfg.badge} rounded-lg px-3 py-2 text-xl font-bold shrink-0 flex items-center gap-2`}
      >
        <span>{cfg.icon}</span>
        <span className="text-sm tracking-widest">{cfg.label}</span>
      </div>
      <div>
        <div className="font-semibold text-lg">
          {company} ({ticker})
        </div>
        <p className="text-sm opacity-90 mt-1 leading-relaxed">{rationale}</p>
      </div>
    </div>
  );
}
