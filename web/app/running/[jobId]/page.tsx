"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { useAnalysisProgress } from "@/hooks/useAnalysisProgress";
import { useAnalysisContext } from "@/contexts/AnalysisContext";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ChevronDown, ChevronUp } from "lucide-react";

const DEFAULT_STAGES = [
  { key: "discovery",  label: "Company Discovery",  order: 1 },
  { key: "industry",   label: "Industry Analysis",  order: 2 },
  { key: "bmp",        label: "BMP Gate",           order: 3 },
  { key: "fisher",     label: "Fisher Analysis",    order: 4 },
  { key: "selection",  label: "Stock Selection",    order: 5 },
  { key: "risk",       label: "Risk Scoring",       order: 6 },
  { key: "valuation",  label: "Valuation",          order: 7 },
  { key: "similar",    label: "Similar Companies",  order: 8 },
  { key: "thesis",     label: "Thesis Writer",      order: 9 },
];

export default function RunningPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const router = useRouter();
  const { setActiveJob } = useAnalysisContext();

  const { logs, currentStage, completedStages, isDone, isError, error, resultPath, ticker } =
    useAnalysisProgress(jobId);

  const [logsOpen, setLogsOpen] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  // Clear nav indicator and redirect on completion
  useEffect(() => {
    if (!isDone || !resultPath) return;
    setActiveJob(null);
    // Extract analysis ID from path: data/theses/NVDA_2026-06-30.json
    const fname = resultPath.replace(/\\/g, "/").split("/").pop()?.replace(".json", "");
    if (fname) {
      setTimeout(() => router.push(`/analysis/${fname}`), 1500);
    }
  }, [isDone, resultPath, router, setActiveJob]);

  // Clear nav indicator on error
  useEffect(() => {
    if (isError) setActiveJob(null);
  }, [isError, setActiveJob]);

  const pct = Math.round((completedStages.length / DEFAULT_STAGES.length) * 100);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-slate-800 rounded-2xl p-6 mb-4">
        <h1 className="text-xl font-bold text-white mb-1">Running Analysis</h1>
        <p className="text-slate-400 text-sm mb-6">Job ID: {jobId}</p>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>{completedStages.length}/{DEFAULT_STAGES.length} stages</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        <ProgressTracker
          stages={DEFAULT_STAGES}
          currentStage={currentStage}
          completedStages={completedStages}
          isDone={isDone}
          isError={isError}
        />

        {isError && error && (
          <div className="mt-4 bg-red-950 border border-red-800 rounded-lg p-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>

      {/* Logs */}
      <div className="bg-slate-800 rounded-2xl overflow-hidden">
        <button
          onClick={() => setLogsOpen((o) => !o)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm text-slate-400 hover:text-white transition-colors"
        >
          <span>Pipeline log ({logs.length} lines)</span>
          {logsOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {logsOpen && (
          <div
            ref={logRef}
            className="h-64 overflow-y-auto px-5 pb-4 font-mono text-xs text-slate-400 space-y-0.5"
          >
            {logs.map((l, i) => (
              <div key={i} className="leading-relaxed">
                {l.line}
              </div>
            ))}
            {logs.length === 0 && (
              <div className="text-slate-600 italic">Waiting for pipeline output...</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
