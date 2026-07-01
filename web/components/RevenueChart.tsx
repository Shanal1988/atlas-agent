"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from "recharts";
import { RevenueYear } from "@/lib/types";
import { fmtMn, fmtCagr } from "@/lib/formatters";

interface Props {
  revenues: RevenueYear[];
  cagr: number | null;
}

export function RevenueChart({ revenues, cagr }: Props) {
  if (!revenues?.length) return null;

  const data = [...revenues]
    .reverse()
    .map((r) => ({
      year: r.year,
      // revenues are stored in raw dollars
      value: r.revenue / 1_000_000_000, // convert to billions
      display: fmtMn(r.revenue / 1_000_000), // display in millions context
    }));

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-300">Revenue History</h3>
        {cagr != null && (
          <span className="text-xs bg-blue-900 text-blue-300 px-2 py-1 rounded font-mono">
            CAGR {fmtCagr(cagr)}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 20, right: 10, left: 10, bottom: 5 }}>
          <XAxis
            dataKey="year"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis hide />
          <Tooltip
            formatter={(v) => [`$${Number(v).toFixed(2)}B`, "Revenue"]}
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
            itemStyle={{ color: "#ffffff" }}
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
          />
          <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]}>
            <LabelList
              dataKey="display"
              position="top"
              style={{ fill: "#94a3b8", fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
