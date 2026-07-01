"use client";

import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";

interface Props {
  label: string;
  score: number;
  max: number;
  verdict?: string;
  color?: string;
}

export function ScoreGauge({ label, score, max, verdict, color = "#3b82f6" }: Props) {
  const pct = Math.min((score / max) * 100, 100);

  const fill =
    pct >= 70 ? "#10b981" : pct >= 45 ? "#f59e0b" : "#ef4444";

  const data = [
    { name: label, value: pct, fill },
    { name: "bg", value: 100 - pct, fill: "#1e293b" },
  ];

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-28 h-28">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="65%"
            outerRadius="100%"
            data={data}
            startAngle={180}
            endAngle={0}
            barSize={12}
          >
            <RadialBar dataKey="value" background={false} isAnimationActive />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center mt-6">
          <span className="text-2xl font-bold text-white">
            {score % 1 === 0 ? score : score.toFixed(1)}
          </span>
          <span className="text-xs text-slate-400">/ {max}</span>
        </div>
      </div>
      <div className="text-sm font-semibold text-white text-center">{label}</div>
      {verdict && (
        <div className="text-xs text-slate-400 text-center max-w-[130px] leading-tight">
          {verdict}
        </div>
      )}
    </div>
  );
}
