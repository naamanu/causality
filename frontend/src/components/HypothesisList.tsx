import type { AIMetrics, Hypothesis } from "../api/types";
import type { StreamState } from "../api/useAnalyzeStream";
import { pct } from "../lib/format";

interface Props {
  state: StreamState;
  hypotheses: Hypothesis[];
  metrics: AIMetrics | null;
  error: string | null;
  onAnalyze: (verify?: boolean) => void;
}

export function HypothesisList({ state, hypotheses, metrics, error, onAnalyze }: Props) {
  const running = state === "streaming";
  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="border-b border-[#dfdfd8] bg-[#fbfbf8] px-5 py-[17px]">
        <div className="flex items-center justify-between"><div><div className="eyebrow">Causal analysis</div><h2 className="mt-1.5 text-[15px] font-semibold tracking-[-.02em] text-[#252521]">Likely causes</h2></div>{state === "done" && <span className="rounded-full bg-[#e3f1e9] px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-[#377154]">Complete</span>}</div>
        <p className="mt-2 text-[11px] leading-[1.6] text-muted">Ranked explanations grounded in the selected traces and logs.</p>
        <button onClick={() => onAnalyze(false)} disabled={running} className="button button-primary mt-4 w-full">
          {running ? <><Spinner /> Analyzing telemetry…</> : <>Run causal analysis <span className="ml-auto text-[#aaa9a2]">⌘ ↵</span></>}
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {state === "idle" && <EmptyState />}
        {state === "error" && <ErrorBanner message={error} onRetry={() => onAnalyze(false)} />}
        {running && hypotheses.length === 0 && <Skeletons />}
        <div className="space-y-2.5">{hypotheses.map((hypothesis) => <HypothesisCard key={hypothesis.id} hypothesis={hypothesis} />)}</div>
      </div>
      {metrics && <MetricsFooter metrics={metrics} />}
    </section>
  );
}

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const confidence = Math.round(hypothesis.confidence * 100);
  return (
    <article className="animate-fade-up overflow-hidden rounded-lg border border-[#deded7] bg-white shadow-[0_1px_2px_rgba(0,0,0,.025)]">
      <div className="flex gap-3 p-4">
        <div className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-[#efefe9] font-mono text-[10px] font-medium text-[#65655f]">{hypothesis.rank}</div>
        <div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><h3 className="text-[13px] font-semibold leading-5 tracking-[-.01em] text-[#2b2b26]">{hypothesis.title}</h3><span className="shrink-0 font-mono text-[10px] tabular-nums text-[#6f6f68]">{pct(hypothesis.confidence)}</span></div><div className="mt-2 h-1 overflow-hidden rounded-full bg-[#ecece7]"><div className="h-full rounded-full bg-[#696961]" style={{ width: `${confidence}%` }} /></div></div>
      </div>
      <p className="border-t border-[#ecece7] bg-[#fafaf7] px-4 py-3 text-[11px] leading-[1.7] text-[#66665f]">{hypothesis.explanation}</p>
      {(hypothesis.evidence_span_ids.length > 0 || hypothesis.evidence_log_ids.length > 0) && (
        <div className="flex flex-wrap gap-1.5 border-t border-[#ecece7] px-4 py-3">
          <span className="mr-1 self-center text-[9px] font-semibold uppercase tracking-wider text-[#a0a098]">Evidence</span>
          {[...hypothesis.evidence_span_ids, ...hypothesis.evidence_log_ids].slice(0, 4).map((id) => <button key={id} className="rounded border border-[#dfdfd8] bg-[#fbfbf8] px-1.5 py-1 font-mono text-[8px] text-[#75756e] hover:border-[#bdbdb5] hover:text-[#33332f]">{id.slice(-8)}</button>)}
        </div>
      )}
    </article>
  );
}

function EmptyState() {
  return <div className="flex h-full min-h-[360px] flex-col items-center justify-center px-8 text-center"><div className="relative grid h-12 w-12 place-items-center rounded-xl border border-[#deded7] bg-white"><span className="absolute inset-2 rounded-lg border border-dashed border-[#c8c8c0]" /><span className="relative text-sm">✦</span></div><h3 className="mt-4 text-[13px] font-semibold text-[#353530]">Ready to investigate</h3><p className="mt-2 max-w-[250px] text-[11px] leading-[1.65] text-muted">Causality will inspect the trace graph, rank likely causes, and link every claim to evidence.</p><div className="mt-5 flex items-center gap-2 font-mono text-[9px] text-[#aaa9a2]"><span>TRACE CONTEXT</span><span>→</span><span>HYPOTHESES</span></div></div>;
}

function ErrorBanner({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return <div className="rounded-lg border border-[#edcbc6] bg-[#fff8f6] p-4"><div className="text-[12px] font-semibold text-[#a6433b]">Analysis couldn’t complete</div><p className="mt-2 text-[10px] leading-5 text-[#835f5b]">{message ?? "Unknown error"}</p><button onClick={onRetry} className="button button-secondary mt-4">Try again</button></div>;
}

function MetricsFooter({ metrics }: { metrics: AIMetrics }) {
  return <footer className="border-t border-[#dfdfd8] bg-[#f5f5f1] px-5 py-3"><div className="grid grid-cols-3 gap-3"><Metric label="Latency" value={`${metrics.latency_ms}ms`} /><Metric label="Tokens" value={(metrics.input_tokens + metrics.output_tokens).toLocaleString()} /><Metric label="Evidence" value={String(metrics.hypothesis_count)} /></div><div className="mt-2 truncate font-mono text-[8px] text-[#aaa9a2]">{metrics.model}</div></footer>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div><div className="text-[8px] uppercase tracking-wider text-[#a0a098]">{label}</div><div className="mt-0.5 font-mono text-[10px] text-[#4f4f49]">{value}</div></div>; }
function Spinner() { return <span className="h-3 w-3 animate-spin rounded-full border border-white/40 border-t-white" />; }
function Skeletons() { return <div className="space-y-2.5">{[0,1,2].map((index) => <div key={index} className="rounded-lg border border-[#e2e2db] bg-white p-4"><div className="skeleton h-3.5 w-2/3" /><div className="skeleton mt-3 h-2.5 w-full" /><div className="skeleton mt-2 h-2.5 w-4/5" /></div>)}</div>; }
