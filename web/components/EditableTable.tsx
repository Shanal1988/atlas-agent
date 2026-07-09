"use client";

import { useState, useCallback } from "react";

interface EditableTableProps {
  years: string[];
  data: Record<string, Record<string, number | null>>;
  lineItemLabels: Record<string, string>;
  onCellChange: (lineItem: string, year: string, value: number | null) => void;
}

function formatNumber(val: number | null): string {
  if (val === null || val === undefined) return "";
  const abs = Math.abs(val);
  if (abs >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
  return val.toFixed(2);
}

function parseInput(raw: string): number | null {
  const s = raw.trim().toUpperCase();
  if (!s) return null;
  const multipliers: Record<string, number> = { B: 1e9, M: 1e6, K: 1e3 };
  for (const [suffix, mult] of Object.entries(multipliers)) {
    if (s.endsWith(suffix)) {
      const n = parseFloat(s.slice(0, -1));
      return isNaN(n) ? null : n * mult;
    }
  }
  const n = parseFloat(s.replace(/,/g, ""));
  return isNaN(n) ? null : n;
}

function Cell({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  const [focused, setFocused] = useState(false);
  const [raw, setRaw] = useState("");

  const display = focused ? raw : (value !== null ? formatNumber(value) : "");

  return (
    <input
      type="text"
      value={display}
      placeholder="–"
      onFocus={() => {
        setFocused(true);
        setRaw(value !== null ? String(value) : "");
      }}
      onChange={(e) => setRaw(e.target.value)}
      onBlur={() => {
        setFocused(false);
        onChange(parseInput(raw));
      }}
      className="w-full bg-transparent text-right text-slate-200 text-sm px-2 py-1.5 outline-none focus:bg-slate-700 rounded placeholder-slate-600 min-w-[90px]"
    />
  );
}

export function EditableTable({ years, data, lineItemLabels, onCellChange }: EditableTableProps) {
  const sortedYears = [...years].sort((a, b) => b.localeCompare(a));
  const keys = Object.keys(lineItemLabels);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left text-slate-400 font-medium px-3 py-2 sticky left-0 bg-slate-800 min-w-[200px]">
              Line Item
            </th>
            {sortedYears.map((yr) => (
              <th key={yr} className="text-right text-slate-400 font-medium px-2 py-2 min-w-[100px]">
                {yr}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keys.map((key, i) => (
            <tr
              key={key}
              className={`border-b border-slate-700/50 hover:bg-slate-700/30 ${
                i % 2 === 0 ? "bg-slate-800/30" : ""
              }`}
            >
              <td className="sticky left-0 bg-slate-800 px-3 py-1 text-slate-300 font-medium whitespace-nowrap">
                {lineItemLabels[key]}
              </td>
              {sortedYears.map((yr) => (
                <td key={yr} className="px-1 py-0.5">
                  <Cell
                    value={data[key]?.[yr] ?? null}
                    onChange={(v) => onCellChange(key, yr, v)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
