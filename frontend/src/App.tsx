import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createEnvironment, createIncident, createIngestionKey, getEnvironments, getIncidentTelemetry, getIncidents, getSession, getUsage, getWorkspace } from "./api/client";
import type { Environment, Incident, Session, Span, Usage, Workspace } from "./api/types";
import { useAnalyzeStream } from "./api/useAnalyzeStream";
import { HypothesisList } from "./components/HypothesisList";
import { IncidentHeader } from "./components/IncidentHeader";
import { SpanList } from "./components/SpanList";

export default function App() {
  const [session, setSession] = useState<Session | null>(null), [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [environments, setEnvironments] = useState<Environment[]>([]), [incidents, setIncidents] = useState<Incident[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null), [selected, setSelected] = useState<Incident | null>(null), [spans, setSpans] = useState<Span[]>([]);
  const [error, setError] = useState<string | null>(null), [loading, setLoading] = useState(true), [showNew, setShowNew] = useState(false);
  const analyze = useAnalyzeStream(selected?.id ?? null);

  const refresh = async () => {
    const [s, w, e, i, u] = await Promise.all([getSession(), getWorkspace(), getEnvironments(), getIncidents(), getUsage()]);
    setSession(s); setWorkspace(w); setEnvironments(e); setIncidents(i); setSelected(x => x ?? i[0] ?? null); setUsage(u);
  };
  useEffect(() => { refresh().catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => { if (!selected) { setSpans([]); return; } getIncidentTelemetry(selected.id).then(x => setSpans(x.spans)).catch(e => setError(e.message)); }, [selected]);

  if (loading) return <div className="grid h-full place-items-center text-zinc-500">Starting Causality…</div>;
  if (error && !session) return <Login error={error} />;
  if (!workspace) return <Login />;
  return (
    <div className="grid h-screen grid-cols-[270px_1fr_400px] overflow-hidden">
      <aside className="flex flex-col border-r border-ink-800 bg-ink-950 p-5">
        <div className="mb-6"><div className="font-serif text-xl">Causality</div><div className="text-[11px] text-zinc-600">{workspace.name} · {session?.role}</div></div>
        <button onClick={() => setShowNew(true)} disabled={!environments.length} className="mb-4 rounded-md bg-accent px-3 py-2 text-xs font-semibold text-ink-950 disabled:opacity-40">New investigation</button>
        {!environments.length ? <Onboarding onDone={async () => { await refresh(); }} /> : <IncidentList incidents={incidents} selected={selected} onSelect={setSelected} />}
        {usage && <div className="mt-auto border-t border-ink-800 pt-3 text-[10px] text-zinc-500"><div>{usage.telemetry_records.toLocaleString()} / {usage.limits.telemetry_records.toLocaleString()} records</div><div>{usage.analyses} / {usage.limits.analyses} analyses</div></div>}
      </aside>
      <main className="overflow-y-auto px-8 py-7">
        {error && <div className="mb-4 rounded border border-error/30 bg-error/5 p-3 text-xs text-error">{error}</div>}
        {selected ? <div className="mx-auto max-w-3xl space-y-7"><IncidentHeader incident={selected} spans={spans} /><SpanList spans={spans} /></div> : <Empty environments={environments} />}
      </main>
      <aside className="border-l border-ink-800 bg-ink-950 p-5"><HypothesisList {...analyze} onAnalyze={analyze.run} /></aside>
      {showNew && <NewIncident environments={environments} onClose={() => setShowNew(false)} onCreated={async inc => { setIncidents(x => [inc, ...x]); setSelected(inc); setShowNew(false); }} />}
    </div>
  );
}

function Login({ error }: { error?: string }) { return <div className="grid h-full place-items-center"><div className="max-w-sm text-center"><h1 className="font-serif text-4xl">Causality</h1><p className="mt-3 text-sm text-zinc-500">Secure incident root-cause analysis for engineering teams.</p>{error && <p className="mt-3 text-xs text-error">{error}</p>}<a href="/api/v1/auth/login" className="mt-6 inline-block rounded bg-accent px-5 py-2 text-sm font-semibold text-ink-950">Sign in</a></div></div>; }
function Empty({ environments }: { environments: Environment[] }) { return <div className="grid min-h-[70vh] place-items-center text-center"><div><h2 className="font-serif text-2xl">{environments.length ? "No investigations yet" : "Connect your first environment"}</h2><p className="mt-2 text-sm text-zinc-500">{environments.length ? "Choose a service window when an incident begins." : "Create an environment and forward OTLP traces and logs."}</p></div></div>; }
function IncidentList({ incidents, selected, onSelect }: { incidents: Incident[]; selected: Incident | null; onSelect: (x: Incident) => void }) { return <div className="space-y-1"><div className="mb-2 text-[11px] uppercase tracking-widest text-zinc-500">Investigations</div>{incidents.map(i => <button key={i.id} onClick={() => onSelect(i)} className={`w-full rounded-md border px-3 py-2 text-left ${selected?.id === i.id ? "border-accent/40 bg-ink-850" : "border-transparent hover:bg-ink-900"}`}><div className="text-sm text-zinc-200">{i.title}</div><div className="mt-1 text-[10px] text-zinc-600">{i.services.join(", ") || "all services"}</div></button>)}</div>; }

function Onboarding({ onDone }: { onDone: () => Promise<void> }) {
  const [name, setName] = useState("Production"), [secret, setSecret] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); const env = await createEnvironment(name, slug); const key = await createIngestionKey(env.id, "Collector"); setSecret(key.secret); await onDone(); setBusy(false); };
  if (secret) return <div className="rounded border border-accent/30 bg-accent/5 p-3 text-xs"><div className="text-accent">Save this key now</div><code className="mt-2 block break-all text-zinc-300">{secret}</code><p className="mt-3 text-zinc-500">OTEL_EXPORTER_OTLP_HEADERS=&quot;Authorization=Bearer {secret}&quot;</p></div>;
  return <form onSubmit={submit} className="rounded border border-ink-800 p-3"><div className="text-sm">Connect telemetry</div><input value={name} onChange={e => setName(e.target.value)} className="mt-3 w-full rounded border border-ink-700 bg-ink-900 px-2 py-1.5 text-xs" /><button disabled={busy} className="mt-2 w-full rounded border border-accent/40 px-2 py-1.5 text-xs text-accent">{busy ? "Creating…" : "Create environment & key"}</button></form>;
}

function NewIncident({ environments, onClose, onCreated }: { environments: Environment[]; onClose: () => void; onCreated: (x: Incident) => void }) {
  const [title, setTitle] = useState("Production incident"), [services, setServices] = useState(""); const [minutes, setMinutes] = useState(15);
  const submit = async (e: FormEvent) => { e.preventDefault(); const end = Date.now(); onCreated(await createIncident({ environment_id: environments[0].id, title, services: services.split(",").map(x => x.trim()).filter(Boolean), window_start: end - minutes * 60_000, window_end: end, summary: "Manual investigation window" })); };
  return <div className="fixed inset-0 z-20 grid place-items-center bg-black/70"><form onSubmit={submit} className="w-[420px] rounded-xl border border-ink-700 bg-ink-950 p-6"><h2 className="font-serif text-2xl">New investigation</h2><label className="mt-4 block text-xs text-zinc-500">Title<input value={title} onChange={e => setTitle(e.target.value)} className="mt-1 w-full rounded border border-ink-700 bg-ink-900 p-2 text-zinc-200" /></label><label className="mt-3 block text-xs text-zinc-500">Services, comma-separated<input value={services} onChange={e => setServices(e.target.value)} className="mt-1 w-full rounded border border-ink-700 bg-ink-900 p-2 text-zinc-200" /></label><label className="mt-3 block text-xs text-zinc-500">Last {minutes} minutes<input type="range" min="5" max="60" step="5" value={minutes} onChange={e => setMinutes(Number(e.target.value))} className="mt-2 w-full" /></label><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="px-3 py-2 text-xs text-zinc-500">Cancel</button><button className="rounded bg-accent px-3 py-2 text-xs font-semibold text-ink-950">Create</button></div></form></div>;
}
