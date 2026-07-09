"use client";

import { Fragment, useState } from "react";
import { Save, Loader2 } from "lucide-react";
import { saveOverrides } from "@/lib/api";
import { FisherScore, AnalysisOverrides, FisherPointOverride } from "@/lib/types";

interface Props {
  analysisId: string;
  fisher: FisherScore;
  overrides: AnalysisOverrides;
  onOverridesChange: (updated: AnalysisOverrides) => void;
}

const SCORE_OPTIONS = [0, 0.5, 0.75, 1.0];

// Fisher categories for grouping
const CATEGORIES: { label: string; keys: string[] }[] = [
  { label: "Growth", keys: ["P1", "P2", "P3"] },
  { label: "Profitability", keys: ["P4", "P5", "P6"] },
  { label: "Management", keys: ["P7", "P8", "P9", "P10"] },
  { label: "Strategy", keys: ["P11", "P12", "P13"] },
  { label: "Integrity", keys: ["P14", "P15"] },
];

function calcRating(total: number): string {
  if (total >= 12) return "EXCELLENT";
  if (total >= 9) return "GOOD";
  if (total >= 6) return "FAIR";
  return "POOR";
}

function scoreColor(score: number): string {
  if (score >= 0.75) return "text-emerald-400";
  if (score >= 0.5) return "text-amber-400";
  return "text-red-400";
}

export function FisherScoreTable({ analysisId, fisher, overrides, onOverridesChange }: Props) {
  const [points, setPoints] = useState<FisherPointOverride[]>(() => {
    if (overrides.fisher?.points?.length) {
      return overrides.fisher.points.map((p, i) => ({
        key: p.key || fisher.points[i]?.key || `P${i + 1}`,
        label: p.label || fisher.points[i]?.label || `Point ${i + 1}`,
        score: p.score,
        reasoning: (p as any).reasoning ?? fisher.points[i]?.reasoning ?? "",
        user_note: p.user_note ?? "",
      }));
    }
    return fisher.points.map((p) => ({
      key: p.key,
      label: p.label,
      score: p.score,
      reasoning: p.reasoning,
      user_note: "",
    }));
  });

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const total = points.reduce((s, p) => s + p.score, 0);
  const rating = calcRating(total);

  function setScore(i: number, score: number) {
    setPoints((prev) => prev.map((p, idx) => (idx === i ? { ...p, score } : p)));
    setSaved(false);
  }

  function setNote(i: number, note: string) {
    setPoints((prev) => prev.map((p, idx) => (idx === i ? { ...p, user_note: note } : p)));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated: AnalysisOverrides = {
        ...overrides,
        fisher: { points, total, rating },
      };
      await saveOverrides(analysisId, updated);
      onOverridesChange(updated);
      setSaved(true);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  }

  // Build category → points index map
  const byKey = Object.fromEntries(points.map((p, i) => [p.key, i]));

  return (
    <div className="bg-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-300">Fisher Analysis</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {total.toFixed(2)} / 15 — {rating}
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition-colors"
        >
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
          {saved ? "Saved" : "Save"}
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left text-xs text-slate-400 font-medium px-4 py-2 min-w-[220px]">
                Point
              </th>
              <th className="text-center text-xs text-slate-400 font-medium px-3 py-2 w-24">
                Score
              </th>
              <th className="text-left text-xs text-slate-400 font-medium px-3 py-2 min-w-[250px]">
                AI Reasoning
              </th>
              <th className="text-left text-xs text-slate-400 font-medium px-3 py-2 min-w-[200px]">
                Your Notes
              </th>
            </tr>
          </thead>
          <tbody>
            {CATEGORIES.map((cat) => {
              const catPoints = cat.keys
                .map((k) => ({ idx: byKey[k], point: points[byKey[k]] }))
                .filter((x) => x.point !== undefined);

              if (!catPoints.length) return null;

              return (
                <Fragment key={cat.label}>
                  <tr className="bg-slate-750">
                    <td
                      colSpan={4}
                      className="px-4 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-700/50"
                    >
                      {cat.label}
                    </td>
                  </tr>
                  {catPoints.map(({ idx, point }) => (
                    <tr
                      key={point.key}
                      className="border-b border-slate-700/50 hover:bg-slate-700/20"
                    >
                      <td className="px-4 py-3 text-xs align-top">
                        <span className="font-mono text-slate-500 mr-1.5">{point.key}</span>
                        <span className="text-slate-200 font-medium">{point.label}</span>
                      </td>
                      <td className="px-3 py-3 text-center align-top">
                        <select
                          value={point.score}
                          onChange={(e) => setScore(idx, parseFloat(e.target.value))}
                          className={`bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs font-semibold outline-none cursor-pointer ${scoreColor(point.score)}`}
                        >
                          {SCORE_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3 text-slate-400 text-xs align-top leading-relaxed">
                        {point.reasoning}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <textarea
                          value={point.user_note ?? ""}
                          onChange={(e) => setNote(idx, e.target.value)}
                          placeholder="Add your notes..."
                          rows={2}
                          className="w-full bg-slate-700/50 text-slate-200 text-xs rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-600 resize-none"
                        />
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
