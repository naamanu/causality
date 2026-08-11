import type { Analysis, Environment, Incident, Session, Usage, Workspace } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

export const getSession = () => request<Session>("/api/v1/auth/session");
export const getWorkspace = () => request<Workspace>("/api/v1/workspaces/current");
export const getEnvironments = () => request<Environment[]>("/api/v1/environments");
export const createEnvironment = (name: string, slug: string) => request<Environment>("/api/v1/environments", { method: "POST", body: JSON.stringify({ name, slug }) });
export const createIngestionKey = (environmentId: string, name: string) => request<{ secret: string; collector_headers: string }>("/api/v1/ingestion-keys", { method: "POST", body: JSON.stringify({ environment_id: environmentId, name }) });
export const getUsage = () => request<Usage>("/api/v1/usage");
export const getIncidents = () => request<Incident[]>("/api/v1/incidents");
export const createIncident = (body: { environment_id: string; title: string; services: string[]; window_start: number; window_end: number; summary: string }) => request<Incident>("/api/v1/incidents", { method: "POST", body: JSON.stringify(body) });
export const getIncidentTelemetry = (id: string) => request<{ spans: import("./types").Span[]; logs: import("./types").LogLine[] }>(`/api/v1/incidents/${id}/telemetry`);
export const createAnalysis = (incidentId: string) => request<Analysis>(`/api/v1/incidents/${incidentId}/analyses`, { method: "POST", body: JSON.stringify({ idempotency_key: crypto.randomUUID() }) });
