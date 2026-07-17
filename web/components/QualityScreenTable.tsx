"use client";

import { QualityScreenScore, QualityScreenSection } from "@/lib/types";

interface Props {
  quality: QualityScreenScore;
}

function SubTable({ title, section }: { title: string; section: QualityScreenSection }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
          {title}
        </span>
        <span className="text-xs font-bold text-white">
          {section.total}/{section.max}
        </span>
      </div>
      <div className="space-y-1">
        {section.items.map((it) => (
          <div key={it.key} className="flex gap-2 text-xs" title={it.reasoning}>
            <span
              className={`shrink-0 font-mono w-9 ${
                it.method === "unavailable"
                  ? "text-slate-500"
                  : it.score / it.max >= 0.6
                  ? "text-emerald-400"
                  : it.score / it.max >= 0.3
                  ? "text-amber-400"
                  : "text-red-400"
              }`}
            >
              {it.method === "unavailable" ? "N/A" : `${it.score}/${it.max}`}
            </span>
            <span className="text-slate-300 leading-tight">
              {it.label}
              {it.proxy && (
                <span className="ml-1 text-[10px] text-slate-500">(proxy)</span>
              )}
              {it.method === "llm_estimate" && (
                <span className="ml-1 text-[10px] text-slate-500">(est.)</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function QualityScreenTable({ quality }: Props) {
  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          Quality Score Screen
        </h3>
        <div className="flex items-end gap-2">
          <span className="text-3xl font-bold text-white">{quality.overall}</span>
          <span className="text-slate-400 text-sm mb-0.5">overall rank score</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SubTable title="Qualitative" section={quality.qualitative} />
        <SubTable title="Quantitative" section={quality.quantitative} />
        <SubTable title="Valuation" section={quality.valuation} />
      </div>

      {quality.data_gaps.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {quality.data_gaps.map((g) => (
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
