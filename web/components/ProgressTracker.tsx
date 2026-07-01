"use client";

import { Stage } from "@/lib/types";
import { CheckCircle, Circle, Loader } from "lucide-react";

interface Props {
  stages: Stage[];
  currentStage: string;
  completedStages: string[];
  isDone: boolean;
  isError: boolean;
}

export function ProgressTracker({
  stages,
  currentStage,
  completedStages,
  isDone,
  isError,
}: Props) {
  return (
    <div className="space-y-3">
      {stages.map((stage) => {
        const isCompleted = completedStages.includes(stage.key);
        const isCurrent = currentStage === stage.key && !isCompleted;
        const isPending = !isCompleted && !isCurrent;

        return (
          <div key={stage.key} className="flex items-center gap-3">
            <div className="shrink-0">
              {isCompleted ? (
                <CheckCircle className="w-5 h-5 text-emerald-500" />
              ) : isCurrent ? (
                <Loader className="w-5 h-5 text-blue-400 animate-spin" />
              ) : (
                <Circle className="w-5 h-5 text-slate-600" />
              )}
            </div>
            <div
              className={`text-sm font-medium ${
                isCompleted
                  ? "text-emerald-400"
                  : isCurrent
                  ? "text-white"
                  : "text-slate-500"
              }`}
            >
              {stage.label}
            </div>
            {isCurrent && (
              <span className="text-xs text-blue-400 bg-blue-950 px-2 py-0.5 rounded-full animate-pulse">
                Running...
              </span>
            )}
            {isCompleted && (
              <span className="text-xs text-emerald-700">Done</span>
            )}
          </div>
        );
      })}

      {isDone && !isError && (
        <div className="mt-4 flex items-center gap-2 text-emerald-400 font-semibold">
          <CheckCircle className="w-5 h-5" />
          Analysis complete — redirecting...
        </div>
      )}
      {isError && (
        <div className="mt-4 text-red-400 text-sm">
          ✕ Analysis failed. Check logs below.
        </div>
      )}
    </div>
  );
}
