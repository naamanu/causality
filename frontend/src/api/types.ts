// Mirrors backend/app/models.py. Kept hand-written (small, stable schema) rather
// than generated — matches the weekend scope.

export type Status = "ok" | "error" | "degraded";
export type LogLevel = "debug" | "info" | "warn" | "error";

export interface Span {
  id: string;
  trace_id: string;
  parent_id: string | null;
  name: string;
  service: string;
  start: number;
  end: number;
  start_ms: number;
  end_ms: number;
  status: Status;
  attributes: Record<string, string>;
}

export interface LogLine {
  id: string;
  trace_id: string | null;
  span_id: string | null;
  ts: number;
  level: LogLevel;
  message: string;
  attributes: Record<string, string>;
}

export interface Incident {
  id: string;
  environment_id: string;
  title: string;
  services: string[];
  summary: string;
  window_start: number;
  window_end: number;
  created_at: string;
}

export interface Session { user_id: string; email: string; workspace_id: string; external_org_id: string; role: string }
export interface Workspace { id: string; name: string; role: string; is_demo: boolean; limits: { members: number; environments: number; records_month: number; analyses_month: number } }
export interface Environment { id: string; name: string; slug: string; last_seen_at: string | null }
export interface Usage { telemetry_records: number; analyses: number; input_tokens: number; output_tokens: number; limits: { telemetry_records: number; analyses: number } }
export interface Analysis { id: string; incident_id: string; status: "queued" | "running" | "completed" | "failed"; error: string | null; metrics: AIMetrics | null; hypotheses: Hypothesis[] }

export interface Hypothesis {
  id: string;
  incident_id: string;
  rank: number;
  confidence: number;
  title: string;
  explanation: string;
  evidence_span_ids: string[];
  evidence_log_ids: string[];
}

export interface AIMetrics {
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  tool_calls: number;
  hypothesis_count: number;
}

export interface ScenarioSummary {
  scenario_key: string;
  title: string;
  description: string;
  incident_id: string;
  default: boolean;
  // "seed" = hand-authored scenario; "import" = loaded from an OTLP/Jaeger file.
  source?: "seed" | "import";
}
