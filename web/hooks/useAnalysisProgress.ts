"use client";

import { useState, useEffect } from "react";
import { ProgressEvent, Stage } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useAnalysisProgress(jobId: string | null) {
  const [logs, setLogs] = useState<{ line: string; stage: string }[]>([]);
  const [currentStage, setCurrentStage] = useState<string>("");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [isDone, setIsDone] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultPath, setResultPath] = useState<string | null>(null);
  const [ticker, setTicker] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const es = new EventSource(`${API}/api/analysis/${jobId}/stream`);

    es.onmessage = (e) => {
      const event: ProgressEvent = JSON.parse(e.data);

      switch (event.type) {
        case "stage_start":
          setCurrentStage(event.stage);
          break;
        case "stage_complete":
          setCompletedStages((prev) =>
            prev.includes(event.stage) ? prev : [...prev, event.stage]
          );
          break;
        case "log":
          setLogs((prev) => [...prev, { line: event.line, stage: event.stage }]);
          break;
        case "done":
          setIsDone(true);
          setResultPath(event.json_path ?? null);
          setTicker(event.ticker ?? null);
          es.close();
          break;
        case "error":
          setIsError(true);
          setError(event.error);
          es.close();
          break;
      }
    };

    es.onerror = () => {
      setIsError(true);
      setError("Connection to server lost");
      es.close();
    };

    return () => es.close();
  }, [jobId]);

  return { logs, currentStage, completedStages, isDone, isError, error, resultPath, ticker };
}
