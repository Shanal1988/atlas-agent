"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { RiskScore } from "@/lib/types";

interface Props {
  risk: RiskScore;
}

const ANSWER_STYLE: Record<string, string> = {
  YES: "bg-emerald-950 text-emerald-300 border-emerald-600",
  NO: "bg-red-950 text-red-400 border-red-600",
  UNKNOWN: "bg-amber-950 text-amber-300 border-amber-600",
};

export function CrushabilityChecklist({ risk }: Props) {
  const [expanded, setExpanded] = useState(false);
  const questions = risk.questions ?? [];
  if (questions.length === 0) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between gap-2"
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-500" />
          )}
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
            Crushability Checklist (25 Questions)
          </h3>
        </div>
        <div className="text-sm">
          <span className="font-bold text-white">{risk.no_count ?? 0} NOs</span>
          {(risk.unknown_count ?? 0) > 0 && (
            <span className="text-amber-300 ml-2">
              ({risk.unknown_count} unknown)
            </span>
          )}
          <span className="text-slate-400 ml-2">→ {risk.category}</span>
        </div>
      </button>

      {expanded && (
        <div className="mt-4 space-y-2">
          {questions.map((q) => (
            <div key={q.key} className="flex items-start gap-2 text-xs">
              <span
                className={`shrink-0 w-[4.5rem] text-center border rounded px-1 py-0.5 font-bold ${
                  ANSWER_STYLE[q.answer] ?? ANSWER_STYLE.UNKNOWN
                }`}
              >
                {q.answer}
              </span>
              <div>
                <div className="text-slate-200 font-medium">
                  {q.key}. {q.label}
                  {q.method === "computed" && (
                    <span className="ml-1 text-[10px] text-slate-500">(computed)</span>
                  )}
                </div>
                <div className="text-slate-400 leading-tight">{q.reasoning}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
