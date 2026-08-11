import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { createEnvironment, createIncident, createIngestionKey, getEnvironments, getIncidentTelemetry, getIncidents, getSession, getUsage, getWorkspace } from "./api/client";
import type { Environment, Incident, Session, Span, Usage, Workspace } from "./api/types";
import { useAnalyzeStream } from "./api/useAnalyzeStream";
import { HypothesisList } from "./components/HypothesisList";
import { IncidentHeader } from "./components/IncidentHeader";
import { SpanList } from "./components/SpanList";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const analyze = useAnalyzeStream(selected?.id ?? null);

  const refresh = async () => {
    const [nextSession, nextWorkspace, nextEnvironments, nextIncidents, nextUsage] = await Promise.all([
      getSession(), getWorkspace(), getEnvironments(), getIncidents(), getUsage(),
    ]);
    setSession(nextSession);
    setWorkspace(nextWorkspace);
    setEnvironments(nextEnvironments);
    setIncidents(nextIncidents);
    setSelected((current) => current ?? nextIncidents[0] ?? null);
    setUsage(nextUsage);
  };

  useEffect(() => {
    refresh().catch((cause: Error) => setError(cause.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) { setSpans([]); return; }
    getIncidentTelemetry(selected.id).then((data) => setSpans(data.spans)).catch((cause: Error) => setError(cause.message));
  }, [selected]);

  if (loading) return <LoadingScreen />;
  if (error && !session) return <Login error={error} />;
  if (!workspace) return <Login />;

  return (
    <div className="app-shell">
      <Topbar workspace={workspace} environment={environments[0]} session={session} />
      <aside className="navigation-panel">
        <div className="px-3 pb-4 pt-3">
          <button onClick={() => setShowNew(true)} disabled={!environments.length} className="button button-primary w-full">
            <PlusIcon /> New investigation
          </button>
        </div>
        {!environments.length ? (
          <div className="px-3"><Onboarding onDone={refresh} /></div>
        ) : (
          <IncidentList incidents={incidents} selected={selected} onSelect={setSelected} />
        )}
        <UsageSummary usage={usage} />
      </aside>

      <main className="investigation-canvas">
        {error && <ErrorNotice message={error} onDismiss={() => setError(null)} />}
        {selected ? (
          <div className="content-column">
            <IncidentHeader incident={selected} spans={spans} />
            <SpanList spans={spans} />
          </div>
        ) : <Empty environments={environments} onCreate={() => setShowNew(true)} />}
      </main>

      <aside className="analysis-panel">
        <HypothesisList {...analyze} onAnalyze={analyze.run} />
      </aside>

      {showNew && (
        <NewIncident
          environments={environments}
          onClose={() => setShowNew(false)}
          onCreated={(incident) => {
            setIncidents((current) => [incident, ...current]);
            setSelected(incident);
            setShowNew(false);
          }}
        />
      )}
    </div>
  );
}

function Topbar({ workspace, environment, session }: { workspace: Workspace; environment?: Environment; session: Session | null }) {
  return (
    <header className="topbar">
      <div className="brand-mark" aria-label="Causality">C</div>
      <div className="brand-name">causality</div>
      <div className="topbar-divider" />
      <button className="workspace-switcher">
        <span className="workspace-avatar">{workspace.name.slice(0, 1).toUpperCase()}</span>
        <span>{workspace.name}</span>
        <ChevronDown />
      </button>
      {environment && (
        <div className="environment-pill">
          <span className={`live-dot ${environment.last_seen_at ? "is-live" : ""}`} />
          {environment.name}
        </div>
      )}
      <div className="ml-auto flex items-center gap-3">
        <a className="topbar-link" href="/docs" target="_blank" rel="noreferrer">API</a>
        <div className="user-avatar" title={session?.email}>{session?.email.slice(0, 1).toUpperCase() ?? "U"}</div>
      </div>
    </header>
  );
}

function IncidentList({ incidents, selected, onSelect }: { incidents: Incident[]; selected: Incident | null; onSelect: (incident: Incident) => void }) {
  const groups = useMemo(() => ({ recent: incidents.slice(0, 8), older: incidents.slice(8) }), [incidents]);
  return (
    <nav className="flex min-h-0 flex-1 flex-col px-2" aria-label="Investigations">
      <div className="section-label px-2 pb-2 pt-3">Investigations <span>{incidents.length}</span></div>
      <div className="min-h-0 overflow-y-auto">
        {!incidents.length && <p className="px-2 py-4 text-xs leading-5 text-muted">No investigations yet. Select a recent window to begin.</p>}
        {groups.recent.map((incident) => (
          <button key={incident.id} onClick={() => onSelect(incident)} className={`incident-row ${selected?.id === incident.id ? "is-selected" : ""}`}>
            <span className="incident-status" />
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-medium text-strong">{incident.title}</span>
              <span className="mt-0.5 block truncate text-[11px] text-muted">{incident.services.join(", ") || "All services"}</span>
            </span>
          </button>
        ))}
        {!!groups.older.length && <div className="section-label px-2 pb-2 pt-5">Earlier</div>}
        {groups.older.map((incident) => (
          <button key={incident.id} onClick={() => onSelect(incident)} className={`incident-row ${selected?.id === incident.id ? "is-selected" : ""}`}>
            <span className="incident-status" /><span className="truncate text-[13px]">{incident.title}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}

function UsageSummary({ usage }: { usage: Usage | null }) {
  if (!usage) return null;
  const percentage = Math.min((usage.telemetry_records / usage.limits.telemetry_records) * 100, 100);
  return (
    <div className="usage-summary">
      <div className="flex items-center justify-between text-[11px]"><span className="text-muted">Monthly usage</span><span className="tabular-nums text-strong">{percentage.toFixed(1)}%</span></div>
      <div className="usage-track"><span style={{ width: `${Math.max(percentage, 1)}%` }} /></div>
      <div className="mt-2 flex justify-between text-[10px] text-faint"><span>{usage.telemetry_records.toLocaleString()} events</span><span>{usage.analyses} analyses</span></div>
    </div>
  );
}

function Onboarding({ onDone }: { onDone: () => Promise<void> }) {
  const [name, setName] = useState("Production");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setFormError(null);
    try {
      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
      const environment = await createEnvironment(name, slug);
      const key = await createIngestionKey(environment.id, "Collector");
      setSecret(key.secret); await onDone();
    } catch (cause) { setFormError((cause as Error).message); }
    finally { setBusy(false); }
  };

  if (secret) return (
    <div className="setup-card">
      <div className="eyebrow">One-time secret</div>
      <h3 className="mt-2 text-sm font-semibold text-strong">Save your ingestion key</h3>
      <code className="secret-value">{secret}</code>
      <p className="mt-3 text-[11px] leading-5 text-muted">Add it to <span className="font-mono text-strong">OTEL_EXPORTER_OTLP_HEADERS</span>. It won’t be shown again.</p>
    </div>
  );

  return (
    <form onSubmit={submit} className="setup-card">
      <div className="eyebrow">Get started</div>
      <h3 className="mt-2 text-sm font-semibold text-strong">Connect an environment</h3>
      <p className="mt-1 text-[11px] leading-5 text-muted">Create an ingestion key for your OpenTelemetry collector.</p>
      <label className="field-label mt-4">Environment name<input value={name} onChange={(event) => setName(event.target.value)} className="field-input" /></label>
      {formError && <p className="mt-2 text-[11px] text-danger">{formError}</p>}
      <button disabled={busy} className="button button-primary mt-3 w-full">{busy ? "Creating…" : "Create environment"}</button>
    </form>
  );
}

function NewIncident({ environments, onClose, onCreated }: { environments: Environment[]; onClose: () => void; onCreated: (incident: Incident) => void }) {
  const [environmentId, setEnvironmentId] = useState(environments[0]?.id ?? "");
  const [title, setTitle] = useState("Production incident");
  const [services, setServices] = useState("");
  const [minutes, setMinutes] = useState(15);
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true);
    const end = Date.now();
    try {
      onCreated(await createIncident({ environment_id: environmentId, title, services: services.split(",").map((service) => service.trim()).filter(Boolean), window_start: end - minutes * 60_000, window_end: end, summary: "Manual investigation window" }));
    } finally { setBusy(false); }
  };
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <form onSubmit={submit} className="modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-header"><div><div className="eyebrow">Investigation</div><h2 className="mt-1 text-xl font-semibold tracking-tight text-strong">Choose an incident window</h2></div><button type="button" onClick={onClose} className="icon-button" aria-label="Close">×</button></div>
        <div className="space-y-4 p-6">
          <label className="field-label">Title<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} className="field-input" /></label>
          <label className="field-label">Environment<select value={environmentId} onChange={(event) => setEnvironmentId(event.target.value)} className="field-input">{environments.map((environment) => <option key={environment.id} value={environment.id}>{environment.name}</option>)}</select></label>
          <label className="field-label">Services <span className="font-normal text-faint">optional, comma-separated</span><input value={services} onChange={(event) => setServices(event.target.value)} placeholder="api, payments, orders" className="field-input" /></label>
          <label className="field-label">Time window<div className="range-control"><input type="range" min="5" max="60" step="5" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /><span>Last {minutes} min</span></div></label>
        </div>
        <div className="modal-footer"><button type="button" onClick={onClose} className="button button-secondary">Cancel</button><button disabled={busy || !environmentId} className="button button-primary">{busy ? "Creating…" : "Create investigation"}</button></div>
      </form>
    </div>
  );
}

function Empty({ environments, onCreate }: { environments: Environment[]; onCreate: () => void }) {
  return <div className="empty-canvas"><div className="empty-icon">↗</div><h2>{environments.length ? "Start an investigation" : "Connect your telemetry"}</h2><p>{environments.length ? "Select a service and recent time window to isolate what changed." : "Create an environment and send OpenTelemetry traces and logs."}</p>{!!environments.length && <button onClick={onCreate} className="button button-primary mt-5"><PlusIcon /> New investigation</button>}</div>;
}

function Login({ error }: { error?: string }) {
  return <div className="login-screen"><div className="login-wordmark"><span>C</span> causality</div><div className="login-card"><div className="eyebrow">Incident intelligence</div><h1>Find the cause,<br />not just the symptom.</h1><p>Trace failures across services and turn noisy telemetry into ranked, evidence-backed explanations.</p>{error && <div className="mt-5 rounded-md bg-red-50 p-3 text-xs text-danger">{error}</div>}<a href="/api/v1/auth/login" className="button button-primary mt-7 w-full">Continue with SSO <span className="ml-auto">→</span></a></div><div className="login-footer">OpenTelemetry native · Evidence linked · Built for on-call</div></div>;
}

function LoadingScreen() { return <div className="loading-screen"><div className="brand-mark">C</div><span>Loading workspace</span></div>; }
function ErrorNotice({ message, onDismiss }: { message: string; onDismiss: () => void }) { return <div className="error-notice"><span>{message}</span><button onClick={onDismiss}>Dismiss</button></div>; }
function PlusIcon() { return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>; }
function ChevronDown() { return <svg className="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m5 6 3 3 3-3" /></svg>; }
