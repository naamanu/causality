import type { Incident, Span } from "../api/types";
import { ms } from "../lib/format";

interface Props {
  incident: Incident;
  spans: Span[];
}

export function IncidentHeader({ incident, spans }: Props) {
  const errors = spans.filter((s) => s.status === "error").length;
  const degraded = spans.filter((s) => s.status === "degraded").length;
  const window = incident.window_end - incident.window_start;

  return (
    <header className="border-b border-ink-800 pb-5">
      <div className="text-[11px] uppercase tracking-widest text-accent/80">
        Incident · {incident.scenario_key}
      </div>
      <h1 className="mt-1.5 font-serif text-3xl leading-tight text-zinc-50">
        {incident.title}
      </h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
        {incident.summary}
      </p>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-zinc-500">
        <Stat label="window" value={ms(window)} />
        <Stat label="spans" value={String(spans.length)} />
        <Stat label="errors" value={String(errors)} tone={errors ? "text-error" : undefined} />
        <Stat
          label="degraded"
          value={String(degraded)}
          tone={degraded ? "text-degraded" : undefined}
        />
        <Stat label="traces" value={String(incident.trace_ids.length)} />
      </dl>
    </header>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-zinc-600">{label}</span>
      <span className={tone ?? "text-zinc-300"}>{value}</span>
    </div>
  );
}
