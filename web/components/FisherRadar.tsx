"use client";

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { FisherScore } from "@/lib/types";

interface Props {
  fisher: FisherScore;
}

// Group 15 Fisher points into 5 categories for the radar
const CATEGORIES: { label: string; keys: string[] }[] = [
  { label: "Growth", keys: ["P1", "P2", "P3"] },
  { label: "Profitability", keys: ["P4", "P5", "P6"] },
  { label: "Management", keys: ["P7", "P8", "P9", "P10"] },
  { label: "Strategy", keys: ["P11", "P12", "P13"] },
  { label: "Integrity", keys: ["P14", "P15"] },
];

export function FisherRadar({ fisher }: Props) {
  if (!fisher?.points?.length) return null;

  const byKey = Object.fromEntries(fisher.points.map((p) => [p.key, p.score]));

  const data = CATEGORIES.map((cat) => {
    const maxPts = cat.keys.length;
    const actual = cat.keys.reduce((sum, k) => sum + (byKey[k] ?? 0), 0);
    return {
      category: cat.label,
      score: +((actual / maxPts) * 100).toFixed(0),
      fullMark: 100,
    };
  });

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Fisher Analysis</h3>
        <span className="text-xs bg-slate-700 text-slate-200 px-2 py-1 rounded font-mono">
          {fisher.total}/15 — {fisher.rating.split(" — ")[0]}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="#334155" />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
          />
          <Tooltip
            formatter={(v) => [`${v}%`, "Score"]}
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
            itemStyle={{ color: "#ffffff" }}
          />
          <Radar
            dataKey="score"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.3}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
