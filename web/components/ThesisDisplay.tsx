"use client";

import { ThesisSections } from "@/lib/types";

interface Props {
  thesis: ThesisSections;
}

export function ThesisDisplay({ thesis }: Props) {
  return (
    <div className="space-y-5">
      {/* Executive Summary */}
      <div className="bg-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Executive Summary
        </h3>
        <p className="text-slate-200 leading-relaxed text-sm">{thesis.executive_summary}</p>
      </div>

      {/* Bull / Bear */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-emerald-950/40 border border-emerald-900 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-emerald-400 mb-3">Bull Case</h3>
          <ul className="space-y-2">
            {thesis.bull_case.map((b, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-200">
                <span className="text-emerald-500 font-bold shrink-0">↑</span>
                <span className="leading-relaxed">{b}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-red-950/40 border border-red-900 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-red-400 mb-3">Bear Case</h3>
          <ul className="space-y-2">
            {thesis.bear_case.map((b, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-200">
                <span className="text-red-500 font-bold shrink-0">↓</span>
                <span className="leading-relaxed">{b}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Thesis Statement */}
      <div className="bg-slate-800 rounded-xl p-4 border-l-4 border-blue-500">
        <h3 className="text-sm font-semibold text-blue-400 mb-2">Thesis Statement</h3>
        <p className="text-slate-200 leading-relaxed text-sm">{thesis.thesis_statement}</p>
      </div>

      {/* Destination */}
      <div className="bg-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-2">
          10-Year Destination
        </h3>
        <p className="text-slate-200 leading-relaxed text-sm">{thesis.destination}</p>
      </div>

      {/* Watch Points */}
      <div className="bg-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-amber-400 mb-3">Watch Points</h3>
        <ul className="space-y-2">
          {thesis.watch_points.map((w, i) => (
            <li key={i} className="flex gap-2 text-sm">
              <span className="text-amber-500 font-bold shrink-0">◉</span>
              <span className="text-slate-200 leading-relaxed">{w}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Short-term thesis (2-3 years) */}
      {thesis.short_term_outlook && (
        <div className="bg-slate-800 rounded-xl p-4 border-l-4 border-cyan-500">
          <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wide mb-3">
            Short-Term Outlook · 2–3 Years
          </h3>
          <p className="text-slate-200 leading-relaxed text-sm mb-4">
            {thesis.short_term_outlook}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {thesis.short_term_catalysts?.filter(Boolean).length ? (
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Catalysts</p>
                <ul className="space-y-1.5">
                  {thesis.short_term_catalysts.filter(Boolean).map((c, i) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span className="text-cyan-400 font-bold shrink-0">→</span>
                      <span className="text-slate-200 leading-relaxed">{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {thesis.short_term_risks?.filter(Boolean).length ? (
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Near-Term Risks</p>
                <ul className="space-y-1.5">
                  {thesis.short_term_risks.filter(Boolean).map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm">
                      <span className="text-orange-400 font-bold shrink-0">!</span>
                      <span className="text-slate-200 leading-relaxed">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Medium-term thesis (5 years) */}
      {thesis.medium_term_outlook && (
        <div className="bg-slate-800 rounded-xl p-4 border-l-4 border-violet-500">
          <h3 className="text-sm font-semibold text-violet-400 uppercase tracking-wide mb-3">
            Medium-Term Outlook · 5 Years
          </h3>
          <p className="text-slate-200 leading-relaxed text-sm mb-4">
            {thesis.medium_term_outlook}
          </p>
          {thesis.medium_term_milestones?.filter(Boolean).length ? (
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Milestones to Track</p>
              <ul className="space-y-1.5">
                {thesis.medium_term_milestones.filter(Boolean).map((m, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="text-violet-400 font-bold shrink-0">✓</span>
                    <span className="text-slate-200 leading-relaxed">{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
