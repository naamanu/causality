import type { Incident, Span } from "../api/types";
import { ms } from "../lib/format";

export function IncidentHeader({ incident, spans }: { incident: Incident; spans: Span[] }) {
  const errors = spans.filter((span) => span.status === "error").length;
  const degraded = spans.filter((span) => span.status === "degraded").length;
  const services = new Set(spans.map((span) => span.service)).size;
  const created = new Date(incident.created_at);

  return (
    <header className="border-b border-[#e3e3dc] pb-7">
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span>Investigations</span><span className="text-[#b5b5ad]">/</span>
        <span className="font-mono text-strong">{incident.id.slice(-8)}</span>
        <span className="ml-auto rounded-full border border-[#deded7] bg-[#fafaf7] px-2 py-1 font-mono text-[9px] text-muted">{created.toLocaleDateString(undefined, { month: "short", day: "numeric" })} · {created.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <div className="mt-5 flex items-start justify-between gap-8">
        <div className="min-w-0">
          <div className="mb-3 flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#d68435] shadow-[0_0_0_3px_#fff1df]" /><span className="text-[10px] font-semibold uppercase tracking-[.12em] text-[#8e5c25]">Investigating</span></div>
          <h1 className="max-w-2xl text-[28px] font-semibold leading-[1.16] tracking-[-.035em] text-[#20201c]">{incident.title}</h1>
          <p className="mt-3 max-w-2xl text-[13px] leading-6 text-muted">{incident.summary || "Telemetry selected for root-cause analysis."}</p>
        </div>
      </div>
      <dl className="mt-7 grid grid-cols-5 divide-x divide-[#e3e3dc] rounded-lg border border-[#e1e1da] bg-[#fafaf7] py-3">
        <Stat label="Window" value={ms(incident.window_end - incident.window_start)} />
        <Stat label="Services" value={String(services || incident.services.length || "—")} />
        <Stat label="Spans" value={String(spans.length)} />
        <Stat label="Errors" value={String(errors)} tone={errors ? "danger" : undefined} />
        <Stat label="Degraded" value={String(degraded)} tone={degraded ? "warning" : undefined} />
      </dl>
    </header>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "danger" | "warning" }) {
  const color = tone === "danger" ? "text-[#b94e45]" : tone === "warning" ? "text-[#a76717]" : "text-[#2c2c27]";
  return <div className="px-4"><dt className="text-[9px] font-medium uppercase tracking-[.1em] text-[#999990]">{label}</dt><dd className={`mt-1 font-mono text-[13px] font-medium tabular-nums ${color}`}>{value}</dd></div>;
}
