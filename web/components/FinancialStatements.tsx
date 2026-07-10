"use client";

import { useState, useEffect, useRef } from "react";
import { Plus, Upload, Link, TrendingUp, Loader2 } from "lucide-react";
import { getFinancials, saveFinancials, fetchFmpYears } from "@/lib/api";
import { FinancialStatements } from "@/lib/types";
import { EditableTable } from "./EditableTable";
import { FileUploadDialog } from "./FileUploadDialog";
import { UrlImportDialog } from "./UrlImportDialog";

const INCOME_LABELS: Record<string, string> = {
  revenue: "Revenue",
  cost_of_revenue: "Cost of Revenue",
  gross_profit: "Gross Profit",
  operating_expenses: "Operating Expenses",
  operating_income: "Operating Income",
  interest_expense: "Interest Expense",
  net_income: "Net Income",
  eps_diluted: "EPS (Diluted)",
};

const BALANCE_LABELS: Record<string, string> = {
  cash_and_equivalents: "Cash & Equivalents",
  total_current_assets: "Total Current Assets",
  total_assets: "Total Assets",
  total_current_liabilities: "Total Current Liabilities",
  total_debt: "Total Debt",
  total_liabilities: "Total Liabilities",
  total_equity: "Total Equity",
  shares_outstanding: "Shares Outstanding",
};

const CASHFLOW_LABELS: Record<string, string> = {
  operating_cash_flow: "Operating Cash Flow",
  capital_expenditures: "Capital Expenditures",
  free_cash_flow: "Free Cash Flow",
  dividends_paid: "Dividends Paid",
  share_buybacks: "Share Buybacks",
};

type TabKey = "income_statement" | "balance_sheet" | "cash_flow";

const TABS: { key: TabKey; label: string; labels: Record<string, string> }[] = [
  { key: "income_statement", label: "Income Statement", labels: INCOME_LABELS },
  { key: "balance_sheet", label: "Balance Sheet", labels: BALANCE_LABELS },
  { key: "cash_flow", label: "Cash Flow", labels: CASHFLOW_LABELS },
];

interface Props {
  analysisId: string;
}

export function FinancialStatementsPanel({ analysisId }: Props) {
  const [data, setData] = useState<FinancialStatements | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("income_statement");
  const [showUpload, setShowUpload] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [addingYear, setAddingYear] = useState(false);
  const [newYear, setNewYear] = useState("");
  const [fmpLoading, setFmpLoading] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    getFinancials(analysisId)
      .then(setData)
      .catch((e: Error) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [analysisId]);

  function scheduleSave(updated: FinancialStatements) {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveFinancials(analysisId, updated).catch(console.error);
    }, 800);
  }

  function handleCellChange(lineItem: string, year: string, value: number | null) {
    if (!data) return;
    const section = data[activeTab] as Record<string, Record<string, number | null>>;
    const updated: FinancialStatements = {
      ...data,
      [activeTab]: {
        ...section,
        [lineItem]: { ...(section[lineItem] ?? {}), [year]: value },
      },
    };
    setData(updated);
    scheduleSave(updated);
  }

  function handleAddYear() {
    const yr = newYear.trim();
    // Validate: 4-digit year in a sensible range
    if (!/^\d{4}$/.test(yr) || +yr < 1980 || +yr > 2100) {
      setNewYear("");
      return; // keep the input open so the user can correct it
    }
    if (!data || data.years.includes(yr)) {
      setAddingYear(false);
      setNewYear("");
      return;
    }
    const updated: FinancialStatements = { ...data, years: [...data.years, yr] };
    setData(updated);
    setNewYear("");
    setAddingYear(false);
    saveFinancials(analysisId, updated).catch(console.error);
  }

  function handleRemoveYear(year: string) {
    if (!data) return;
    if (!window.confirm(`Remove the ${year} column and all its values?`)) return;
    const updated: FinancialStatements = {
      ...data,
      years: data.years.filter((y) => y !== year),
    };
    // Strip the year's values from all three statements
    for (const stmt of ["income_statement", "balance_sheet", "cash_flow"] as const) {
      const section = { ...(updated[stmt] as Record<string, Record<string, number | null>>) };
      for (const key of Object.keys(section)) {
        if (section[key] && year in section[key]) {
          const { [year]: _removed, ...rest } = section[key];
          section[key] = rest;
        }
      }
      updated[stmt] = section;
    }
    setData(updated);
    saveFinancials(analysisId, updated).catch(console.error);
  }

  async function handleFetchFmp() {
    setFmpLoading(true);
    try {
      const updated = await fetchFmpYears(analysisId);
      setData(updated as FinancialStatements);
    } catch (e) {
      console.error(e);
    } finally {
      setFmpLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-xl p-6 flex items-center gap-2 text-slate-400 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading financial statements...
      </div>
    );
  }

  if (loadError || !data) {
    return (
      <div className="bg-slate-800 rounded-xl p-6 text-red-400 text-sm">
        Failed to load financial statements: {loadError}
      </div>
    );
  }

  const tab = TABS.find((t) => t.key === activeTab)!;
  const tableData = data[activeTab] as Record<string, Record<string, number | null>>;

  return (
    <>
      <div className="bg-slate-800 rounded-xl overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between gap-3 flex-wrap">
          <h3 className="text-sm font-semibold text-slate-300">Financial Statements</h3>
          <div className="flex items-center gap-2 flex-wrap">
            {addingYear ? (
              <div className="flex items-center gap-1">
                <input
                  autoFocus
                  value={newYear}
                  onChange={(e) => setNewYear(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAddYear();
                    if (e.key === "Escape") { setAddingYear(false); setNewYear(""); }
                  }}
                  placeholder="e.g. 2020"
                  className="bg-slate-700 text-white text-xs px-2 py-1 rounded w-24 outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button
                  onClick={handleAddYear}
                  className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded transition-colors"
                >
                  Add
                </button>
                <button
                  onClick={() => { setAddingYear(false); setNewYear(""); }}
                  className="text-xs text-slate-400 hover:text-white px-1"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAddingYear(true)}
                className="flex items-center gap-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1.5 rounded-lg transition-colors"
              >
                <Plus className="w-3 h-3" /> Add Year
              </button>
            )}
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1.5 rounded-lg transition-colors"
            >
              <Upload className="w-3 h-3" /> Upload File
            </button>
            <button
              onClick={() => setShowUrl(true)}
              className="flex items-center gap-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1.5 rounded-lg transition-colors"
            >
              <Link className="w-3 h-3" /> Import URL
            </button>
            <button
              onClick={handleFetchFmp}
              disabled={fmpLoading}
              className="flex items-center gap-1 text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-300 px-2 py-1.5 rounded-lg transition-colors"
            >
              {fmpLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <TrendingUp className="w-3 h-3" />
              )}
              Fetch FMP Data
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                activeTab === t.key
                  ? "text-white border-blue-500"
                  : "text-slate-400 hover:text-slate-200 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="p-4">
          <EditableTable
            years={data.years}
            data={tableData}
            lineItemLabels={tab.labels}
            onCellChange={handleCellChange}
            onRemoveYear={handleRemoveYear}
          />
        </div>

        {data.uploads?.length > 0 && (
          <div className="px-4 pb-3 text-xs text-slate-500">
            Sources:{" "}
            {data.uploads.map((u) => u.filename).join(", ")}
          </div>
        )}
      </div>

      {showUpload && (
        <FileUploadDialog
          analysisId={analysisId}
          onSuccess={(d) => setData(d as FinancialStatements)}
          onClose={() => setShowUpload(false)}
        />
      )}
      {showUrl && (
        <UrlImportDialog
          analysisId={analysisId}
          onSuccess={(d) => setData(d as FinancialStatements)}
          onClose={() => setShowUrl(false)}
        />
      )}
    </>
  );
}
