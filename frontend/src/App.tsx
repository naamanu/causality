import { useEffect, useState } from "react";
import { getIncident, getLogs, getScenarios, getSpans } from "./api/client";
import type { Incident, LogLine, ScenarioSummary, Span } from "./api/types";
import { useAnalyzeStream } from "./api/useAnalyzeStream";
import { ScenarioPicker } from "./components/ScenarioPicker";
import { IncidentHeader } from "./components/IncidentHeader";
import { SpanList } from "./components/SpanList";
import { HypothesisList } from "./components/HypothesisList";

export default function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);

  const [incident, setIncident] = useState<Incident | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [, setLogs] = useState<LogLine[]>([]); // logs wired now; rendered by the timeline PR
  const [loadingData, setLoadingData] = useState(false);

  const analyze = useAnalyzeStream(incidentId);

  // Load scenarios once; auto-select the demo default for the 10-second wow.
  useEffect(() => {
    getScenarios()
      .then((s) => {
        setScenarios(s);
        const def = s.find((x) => x.default) ?? s[0];
        if (def) setIncidentId(def.incident_id);
      })
      .catch((e) => setBootError((e as Error).message));
  }, []);

  // Load the selected incident's telemetry.
  useEffect(() => {
    if (!incidentId) return;
    let live = true;
    setLoadingData(true);
    Promise.all([getIncident(incidentId), getSpans(incidentId), getLogs(incidentId)])
      .then(([inc, sp, lg]) => {
        if (!live) return;
        setIncident(inc);
        setSpans(sp);
        setLogs(lg);
      })
      .catch((e) => live && setBootError((e as Error).message))
      .finally(() => live && setLoadingData(false));
    return () => {
      live = false;
    };
  }, [incidentId]);

  return (
    <div className="grid h-screen grid-cols-[260px_1fr_400px] overflow-hidden">
      {/* Left rail — brand + scenario picker */}
      <aside className="flex flex-col border-r border-ink-800 bg-ink-950 p-5">
        <div className="mb-8">
          <div className="font-serif text-xl text-zinc-50">Causality</div>
          <div className="text-[11px] tracking-wide text-zinc-600">
            incident root-cause copilot
          </div>
        </div>
        {bootError ? (
          <BootError message={bootError} />
        ) : (
          <ScenarioPicker
            scenarios={scenarios}
            selectedIncidentId={incidentId}
            onSelect={setIncidentId}
          />
        )}
      </aside>

      {/* Center — incident + trace */}
      <main className="overflow-y-auto px-8 py-7">
        {incident && !loadingData ? (
          <div className="mx-auto max-w-3xl space-y-7">
            <IncidentHeader incident={incident} spans={spans} />
            <SpanList spans={spans} />
          </div>
        ) : (
          <CenterSkeleton />
        )}
      </main>

      {/* Right — hypotheses */}
      <aside className="border-l border-ink-800 bg-ink-950 p-5">
        <HypothesisList
          state={analyze.state}
          hypotheses={analyze.hypotheses}
          metrics={analyze.metrics}
          error={analyze.error}
          onAnalyze={analyze.run}
        />
      </aside>
    </div>
  );
}

function BootError({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-error/30 bg-error/5 p-3 text-xs">
      <div className="text-error">Can't reach the backend</div>
      <p className="mt-1 text-zinc-500">{message}</p>
      <p className="mt-2 text-zinc-600">
        Start it: <code className="text-zinc-400">uvicorn app.main:app</code>
      </p>
    </div>
  );
}

function CenterSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="skeleton h-4 w-40" />
      <div className="skeleton h-9 w-2/3" />
      <div className="skeleton h-3 w-full" />
      <div className="skeleton h-3 w-5/6" />
      <div className="mt-8 space-y-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton h-4" style={{ width: `${90 - i * 8}%` }} />
        ))}
      </div>
    </div>
  );
}
