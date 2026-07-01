"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ValuationResult } from "@/lib/types";
import { fmtMn } from "@/lib/formatters";

interface Props {
  valuation: ValuationResult;
}

export function ValuationChart({ valuation }: Props) {
  if (!valuation?.available) return null;

  const mkt = valuation.mktcap_mn;

  const data = [
    { name: "Dhandho Lo", value: valuation.dhandho?.lower?.iv },
    { name: "Dhandho Hi", value: valuation.dhandho?.higher?.iv },
    { name: "Graham Lo", value: valuation.graham?.lower },
    { name: "Graham Hi", value: valuation.graham?.higher },
    { name: "DCF", value: valuation.dcf?.iv },
    { name: "Exp Returns", value: valuation.exp_returns?.iv },
  ].filter((d) => d.value != null && d.value > 0) as { name: string; value: number }[];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const iv = payload[0].value as number;
    const prem = ((mkt - iv) / iv) * 100;
    return (
      <div className="bg-slate-900 border border-slate-600 rounded p-2 text-xs">
        <div className="font-semibold text-white mb-1">{label}</div>
        <div className="text-slate-300">IV: {fmtMn(iv)}</div>
        <div className={prem > 0 ? "text-red-400" : "text-emerald-400"}>
          {prem > 0 ? "+" : ""}{prem.toFixed(0)}% vs market cap
        </div>
      </div>
    );
  };

  return (
    <div className="bg-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">
        Intrinsic Value vs Market Cap
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => fmtMn(v)}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
          <ReferenceLine
            y={mkt}
            stroke="#f43f5e"
            strokeDasharray="5 4"
            label={{
              value: `Mkt Cap ${fmtMn(mkt)}`,
              position: "insideTopRight",
              fill: "#f43f5e",
              fontSize: 10,
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={entry.value >= mkt ? "#10b981" : "#3b82f6"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-500 mt-1">
        Green bars = trading below IV (discount). Blue = above IV (premium). Red line = current market cap.
      </p>
    </div>
  );
}
