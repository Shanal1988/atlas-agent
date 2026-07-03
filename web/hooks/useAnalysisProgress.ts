"use client";

import { useState, useEffect } from "react";
import { ProgressEvent } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/token");
    if (!res.ok) return null;
    const data = await res.json();
    return data.token ?? null;
  } catch {
    return null;
  }
}

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

    let es: EventSource | null = null;

    getAuthToken().then((token) => {
      const url = token
        ? `${API}/api/analysis/${jobId}/stream?token=${encodeURIComponent(token)}`
        : `${API}/api/analysis/${jobId}/stream`;

      es = new EventSource(url);

      es.onmessage = (e) => {
        const event: ProgressEvent = JSON.parse(e.data);

        switch (event.type) {
          case "snapshot":
            setCompletedStages(event.completed_stages ?? []);
            setCurrentStage(event.current_stage ?? "");
            setLogs(
              (event.logs ?? []).map((l: any) => ({ line: l.line ?? "", stage: l.stage ?? "" }))
            );
            if (event.ticker) setTicker(event.ticker);
            if (event.status === "completed") {
              setIsDone(true);
              setResultPath(event.result_json_path ?? null);
              es?.close();
            } else if (event.status === "failed") {
              setIsError(true);
              setError(event.error ?? "Unknown error");
              es?.close();
            }
            break;
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
            es?.close();
            break;
          case "error":
            setIsError(true);
            setError(event.error);
            es?.close();
            break;
        }
      };

      es.onerror = () => {
        setIsError(true);
        setError("Connection to server lost");
        es?.close();
      };
    });

    return () => es?.close();
  }, [jobId]);

  return { logs, currentStage, completedStages, isDone, isError, error, resultPath, ticker };
}
