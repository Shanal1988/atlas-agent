"use client";

import { useState } from "react";
import { Save, Loader2 } from "lucide-react";
import { saveOverrides } from "@/lib/api";
import { BMPScore, AnalysisOverrides, BMPAnswerOverride } from "@/lib/types";

interface Props {
  analysisId: string;
  bmp: BMPScore;
  overrides: AnalysisOverrides;
  onOverridesChange: (updated: AnalysisOverrides) => void;
}

type Rating = "YES" | "PARTIAL" | "NO";

const RATING_SCORE: Record<Rating, number> = { YES: 1, PARTIAL: 0.5, NO: 0 };
const RATING_COLOR: Record<Rating, string> = {
  YES: "text-emerald-400",
  PARTIAL: "text-amber-400",
  NO: "text-red-400",
};
const RATING_BG: Record<Rating, string> = {
  YES: "bg-emerald-950/40 border-emerald-700/40",
  PARTIAL: "bg-amber-950/40 border-amber-700/40",
  NO: "bg-red-950/40 border-red-700/40",
};

function calcVerdict(score: number): string {
  if (score >= 4) return "STRONG PASS";
  if (score >= 3) return "PASS";
  if (score >= 2) return "BORDERLINE";
  return "FAIL";
}

export function BMPScoreTable({ analysisId, bmp, overrides, onOverridesChange }: Props) {
  // Initialise from overrides if present, else from original answers
  const [answers, setAnswers] = useState<BMPAnswerOverride[]>(() => {
    if (overrides.bmp?.answers?.length) {
      return overrides.bmp.answers.map((a, i) => ({
        label: a.label || bmp.answers[i]?.label || `Q${i + 1}`,
        rating: a.rating,
        reasoning: (a as any).reasoning ?? bmp.answers[i]?.reasoning ?? "",
        user_note: a.user_note ?? "",
      }));
    }
    return bmp.answers.map((a) => ({
      label: a.label,
      rating: a.rating,
      reasoning: a.reasoning,
      user_note: "",
    }));
  });

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const score = answers.reduce((s, a) => s + RATING_SCORE[a.rating], 0);
  const verdict = calcVerdict(score);

  function setRating(i: number, rating: Rating) {
    setAnswers((prev) => prev.map((a, idx) => (idx === i ? { ...a, rating } : a)));
    setSaved(false);
  }

  function setNote(i: number, note: string) {
    setAnswers((prev) => prev.map((a, idx) => (idx === i ? { ...a, user_note: note } : a)));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const updated: AnalysisOverrides = {
        ...overrides,
        bmp: { answers, score, verdict },
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

  return (
    <div className="bg-slate-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-300">BMP Score</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Business · Management · Price — {score.toFixed(1)} / 5 — {verdict}
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
              <th className="text-left text-xs text-slate-400 font-medium px-4 py-2 min-w-[200px]">
                Question
              </th>
              <th className="text-center text-xs text-slate-400 font-medium px-3 py-2 w-32">
                Rating
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
            {answers.map((a, i) => (
              <tr
                key={i}
                className={`border-b border-slate-700/50 ${RATING_BG[a.rating]}`}
              >
                <td className="px-4 py-3 text-slate-200 font-medium text-xs align-top">
                  {a.label}
                </td>
                <td className="px-3 py-3 text-center align-top">
                  <select
                    value={a.rating}
                    onChange={(e) => setRating(i, e.target.value as Rating)}
                    className={`bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs font-semibold outline-none cursor-pointer ${RATING_COLOR[a.rating]}`}
                  >
                    <option value="YES" className="text-emerald-400">YES</option>
                    <option value="PARTIAL" className="text-amber-400">PARTIAL</option>
                    <option value="NO" className="text-red-400">NO</option>
                  </select>
                </td>
                <td className="px-3 py-3 text-slate-400 text-xs align-top leading-relaxed">
                  {a.reasoning}
                </td>
                <td className="px-3 py-3 align-top">
                  <textarea
                    value={a.user_note ?? ""}
                    onChange={(e) => setNote(i, e.target.value)}
                    placeholder="Add your notes..."
                    rows={2}
                    className="w-full bg-slate-700/50 text-slate-200 text-xs rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-600 resize-none"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
