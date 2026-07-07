import type { Span } from "../api/types";
import { ms, statusBg, statusText } from "../lib/format";

interface Props {
  spans: Span[];
}

/**
 * Minimal proportional span bars — a placeholder for the full depth-nested,
 * interactive TraceWaterfall (next stacked PR). Already shows timing + status.
 */
export function SpanList({ spans }: Props) {
  if (spans.length === 0) return null;
  const max = Math.max(...spans.map((s) => s.end_ms), 1);

  return (
    <section>
      <div className="text-[11px] uppercase tracking-widest text-zinc-500 mb-3">
        Trace
      </div>
      <div className="space-y-1">
        {spans.map((s) => {
          const left = (s.start_ms / max) * 100;
          const width = Math.max(((s.end_ms - s.start_ms) / max) * 100, 0.8);
          return (
            <div key={s.id} className="group grid grid-cols-[200px_1fr_64px] items-center gap-3">
              <div className="truncate text-xs">
                <span className={statusText[s.status]}>{s.service}</span>
                <span className="text-zinc-600"> · </span>
                <span className="text-zinc-400">{s.name}</span>
              </div>
              <div className="relative h-4 rounded bg-ink-900">
                <div
                  className={[
                    "absolute top-0 h-4 rounded opacity-80 group-hover:opacity-100 transition-opacity",
                    statusBg[s.status],
                  ].join(" ")}
                  style={{ left: `${left}%`, width: `${width}%` }}
                  title={`${s.name} · ${ms(s.end_ms - s.start_ms)}`}
                />
              </div>
              <div className="text-right text-xs tabular-nums text-zinc-500">
                {ms(s.end_ms - s.start_ms)}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
