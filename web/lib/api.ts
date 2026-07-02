import { Analysis, AnalysisSummary, Stage } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function startAnalysis(
  companyName: string
): Promise<{ job_id: string; stages: Stage[] }> {
  const res = await fetch(`${API}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API}/api/analysis/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function streamProgress(jobId: string): EventSource {
  return new EventSource(`${API}/api/analysis/${jobId}/stream`);
}

export async function listAnalyses(): Promise<AnalysisSummary[]> {
  const res = await fetch(`${API}/api/history`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const res = await fetch(`${API}/api/history/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function compareAnalyses(ids: string[]): Promise<Analysis[]> {
  const res = await fetch(`${API}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_ids: ids }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function exportTxtUrl(id: string): string {
  return `${API}/api/export/${id}/txt`;
}

export async function askFollowUp(analysisId: string, message: string): Promise<{ answer: string }> {
  const res = await fetch(`${API}/api/chat/${analysisId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
