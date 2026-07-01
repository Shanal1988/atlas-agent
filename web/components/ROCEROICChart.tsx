"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { CompanyProfile } from "@/lib/types";

interface Props {
  profile: CompanyProfile;
}

export function ROCEROICChart({ profile }: Props) {
  const roce = (profile as any).roce_history as { year: string; roce: number | null }[] | undefined;
  const roic = (profile as any).roic_history as { year: string; roic: number | null }[] | undefined;

  if (!roce?.length && !roic?.length) return null;

  // Merge by year
  const years = new Set([
    ...(roce?.map((r) => r.year) ?? []),
    ...(roic?.map((r) => r.year) ?? []),
  ]);

  const data = Array.from(years)
    .sort()
    .reverse()
    .slice(0, 5)
    .reverse()
    .map((year) => ({
      year,
      ROCE: (() => {
        const v = roce?.find((r) => r.year === year)?.roce;
        return v != null ? +(v * 100).toFixed(1) : null;
      })(),
      ROIC: (() => {
        const v = roic?.find((r) => r.year === year)?.roic;
        return v != null ? +(v * 100).toFixed(1) : null;
      })(),
    }))
    .filter((d) => d.ROCE != null || d.ROIC != null);

  if (!data.length) return null;

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">
        ROCE / ROIC History
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <XAxis
            dataKey="year"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(v) => [`${v}%`]}
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
            itemStyle={{ color: "#ffffff" }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
          <Line
            type="monotone"
            dataKey="ROCE"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ fill: "#3b82f6" }}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="ROIC"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ fill: "#10b981" }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
