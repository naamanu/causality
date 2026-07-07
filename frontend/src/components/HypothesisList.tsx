import type { AIMetrics, Hypothesis } from "../api/types";
import type { StreamState } from "../api/useAnalyzeStream";
import { pct } from "../lib/format";

interface Props {
  state: StreamState;
  hypotheses: Hypothesis[];
  metrics: AIMetrics | null;
  error: string | null;
  onAnalyze: (verify: boolean) => void;
}

export function HypothesisList({ state, hypotheses, metrics, error, onAnalyze }: Props) {
  return (
    <section className="flex h-full flex-col">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-widest text-zinc-500">
          Hypotheses
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onAnalyze(false)}
            disabled={state === "streaming"}
            className="rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs text-accent hover:bg-accent/20 disabled:opacity-40"
          >
            {state === "streaming" ? "Analyzing…" : "Analyze"}
          </button>
          <button
            onClick={() => onAnalyze(true)}
            disabled={state === "streaming"}
            className="rounded-md border border-ink-700 px-3 py-1.5 text-xs text-zinc-400 hover:bg-ink-850 disabled:opacity-40"
            title="Agentic: model queries the data to verify before ranking"
          >
            Verify
          </button>
        </div>
      </div>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {state === "idle" && <EmptyState />}
        {state === "error" && <ErrorBanner message={error} />}
        {state === "streaming" && hypotheses.length === 0 && <Skeletons />}

        {hypotheses.map((h) => (
          <HypothesisCard key={h.id} h={h} />
        ))}
      </div>

      {metrics && <MetricsFooter metrics={metrics} />}
    </section>
  );
}

function HypothesisCard({ h }: { h: Hypothesis }) {
  return (
    <article className="animate-fade-up rounded-lg border border-ink-800 bg-ink-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-serif text-lg leading-snug text-zinc-100">
          <span className="mr-2 text-zinc-600">#{h.rank}</span>
          {h.title}
        </h3>
        <ConfidenceBadge value={h.confidence} />
      </div>
      <p className="mt-2 text-sm leading-relaxed text-zinc-400">{h.explanation}</p>
      {(h.evidence_span_ids.length > 0 || h.evidence_log_ids.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {[...h.evidence_span_ids, ...h.evidence_log_ids].map((id) => (
            <span
              key={id}
              className="rounded border border-ink-700 px-1.5 py-0.5 text-[10px] text-zinc-500"
            >
              {id}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const tone =
    value >= 0.66 ? "text-ok" : value >= 0.33 ? "text-degraded" : "text-zinc-400";
  return (
    <div className="shrink-0 text-right">
      <div className={`text-sm tabular-nums ${tone}`}>{pct(value)}</div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-600">conf</div>
    </div>
  );
}

function MetricsFooter({ metrics }: { metrics: AIMetrics }) {
  const cells: [string, string][] = [
    ["model", metrics.model],
    ["in", String(metrics.input_tokens)],
    ["out", String(metrics.output_tokens)],
    ["latency", `${metrics.latency_ms}ms`],
    ["tool-calls", String(metrics.tool_calls)],
  ];
  return (
    <footer className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-ink-800 pt-3 text-[11px] text-zinc-500">
      {cells.map(([k, v]) => (
        <span key={k} className="flex items-baseline gap-1.5">
          <span className="text-zinc-600">{k}</span>
          <span className="tabular-nums text-zinc-300">{v}</span>
        </span>
      ))}
    </footer>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-[12rem] flex-col items-center justify-center rounded-lg border border-dashed border-ink-800 p-8 text-center">
      <p className="font-serif text-lg text-zinc-300">Ready when you are.</p>
      <p className="mt-1 max-w-xs text-sm text-zinc-500">
        Run the analysis to stream ranked root-cause hypotheses, each backed by the
        spans and logs that support it.
      </p>
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  return (
    <div className="rounded-lg border border-error/30 bg-error/5 p-4">
      <div className="text-sm text-error">Analysis failed</div>
      <p className="mt-1 font-mono text-xs leading-relaxed text-zinc-400">
        {message ?? "Unknown error"}
      </p>
      <p className="mt-2 text-xs text-zinc-600">
        Set <code className="text-zinc-400">ANTHROPIC_API_KEY</code> on the backend and
        retry.
      </p>
    </div>
  );
}

function Skeletons() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-lg border border-ink-800 bg-ink-900 p-4">
          <div className="skeleton h-5 w-2/3" />
          <div className="skeleton mt-2.5 h-3 w-full" />
          <div className="skeleton mt-1.5 h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}
