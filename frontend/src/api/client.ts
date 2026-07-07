import type { Incident, LogLine, ScenarioSummary, Span } from "./types";

// Backend base URL — override with VITE_API_BASE for a deployed demo.
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export const getScenarios = () => getJSON<ScenarioSummary[]>("/scenarios");
export const getIncident = (id: string) => getJSON<Incident>(`/incidents/${id}`);
export const getSpans = (id: string) =>
  getJSON<Span[]>(`/incidents/${id}/spans`);
export const getLogs = (id: string) =>
  getJSON<LogLine[]>(`/incidents/${id}/logs`);
