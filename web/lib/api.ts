import { Analysis, AnalysisSummary, Stage } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _cachedToken: string | null = null;
let _tokenFetchedAt = 0;
const TOKEN_TTL_MS = 5 * 60 * 1000; // re-fetch every 5 minutes

async function getAuthToken(): Promise<string | null> {
  if (_cachedToken && Date.now() - _tokenFetchedAt < TOKEN_TTL_MS) {
    return _cachedToken;
  }
  try {
    const res = await fetch("/api/auth/token");
    if (!res.ok) return null;
    const data = await res.json();
    _cachedToken = data.token ?? null;
    _tokenFetchedAt = Date.now();
    return _cachedToken;
  } catch {
    return null;
  }
}

async function authHeaders(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token
    ? { ...extra, Authorization: `Bearer ${token}` }
    : extra;
}

export async function startAnalysis(
  companyName: string
): Promise<{ job_id: string; stages: Stage[] }> {
  const res = await fetch(`${API}/api/analysis`, {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ company_name: companyName }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API}/api/analysis/${jobId}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function streamProgressWithAuth(jobId: string): Promise<EventSource> {
  // EventSource doesn't support custom headers; pass token as query param
  const token = await getAuthToken();
  const url = token
    ? `${API}/api/analysis/${jobId}/stream?token=${encodeURIComponent(token)}`
    : `${API}/api/analysis/${jobId}/stream`;
  return new EventSource(url);
}

export function streamProgress(jobId: string): EventSource {
  return new EventSource(`${API}/api/analysis/${jobId}/stream`);
}

export async function listAnalyses(): Promise<AnalysisSummary[]> {
  const res = await fetch(`${API}/api/history`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAnalysis(id: string): Promise<Analysis> {
  const res = await fetch(`${API}/api/history/${id}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function compareAnalyses(ids: string[]): Promise<Analysis[]> {
  const res = await fetch(`${API}/api/compare`, {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
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
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
