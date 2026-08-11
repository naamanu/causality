import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Span, Status } from "../api/types";
import { ms } from "../lib/format";

const statusColor: Record<Status, string> = { ok: "#7d9e8a", degraded: "#d49a43", error: "#c86258" };

export function SpanList({ spans }: { spans: Span[] }) {
  const [filter, setFilter] = useState<"all" | "errors">("all");
  const visible = useMemo(() => filter === "errors" ? spans.filter((span) => span.status !== "ok") : spans, [filter, spans]);
  const max = Math.max(...spans.map((span) => span.end_ms), 1);
  const parentIds = new Map(spans.map((span) => [span.id, span.parent_id]));
  const depth = (span: Span) => { let level = 0, parent = span.parent_id; while (parent && level < 4) { level += 1; parent = parentIds.get(parent) ?? null; } return level; };

  return (
    <section className="pt-8">
      <div className="mb-4 flex items-center justify-between">
        <div><h2 className="text-[14px] font-semibold tracking-[-.015em] text-[#292925]">Trace waterfall</h2><p className="mt-1 text-[11px] text-muted">Spans ordered by start time across the selected incident window.</p></div>
        <div className="flex rounded-md border border-[#deded7] bg-[#f8f8f4] p-0.5">
          <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>All <span>{spans.length}</span></FilterButton>
          <FilterButton active={filter === "errors"} onClick={() => setFilter("errors")}>Issues <span>{spans.filter((span) => span.status !== "ok").length}</span></FilterButton>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-[#deded7] bg-white">
        <div className="grid grid-cols-[230px_1fr_64px] gap-4 border-b border-[#e5e5df] bg-[#fafaf7] px-4 py-2 text-[9px] font-medium uppercase tracking-[.09em] text-[#999990]"><div>Operation</div><div>Timeline</div><div className="text-right">Duration</div></div>
        {!visible.length ? <div className="p-8 text-center text-xs text-muted">No issue spans in this window.</div> : visible.map((span, index) => {
          const left = (span.start_ms / max) * 100;
          const width = Math.max(((span.end_ms - span.start_ms) / max) * 100, 0.8);
          return (
            <div key={span.id} className={`group grid grid-cols-[230px_1fr_64px] items-center gap-4 px-4 py-3 ${index ? "border-t border-[#eeeeea]" : ""}`}>
              <div className="min-w-0" style={{ paddingLeft: `${depth(span) * 11}px` }}>
                <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: statusColor[span.status] }} /><span className="truncate text-[11px] font-medium text-[#3a3a35]">{span.name}</span></div>
                <div className="mt-1 truncate pl-3.5 font-mono text-[9px] text-[#9a9a92]">{span.service}</div>
              </div>
              <div className="relative h-[18px] rounded-[4px] bg-[#f2f2ed]">
                <div className="absolute inset-y-[3px] rounded-[3px] opacity-80 transition-opacity group-hover:opacity-100" style={{ left: `${left}%`, width: `${width}%`, background: statusColor[span.status] }} />
                <div className="absolute inset-y-0 left-1/4 border-l border-dashed border-[#deded7]" /><div className="absolute inset-y-0 left-1/2 border-l border-dashed border-[#deded7]" /><div className="absolute inset-y-0 left-3/4 border-l border-dashed border-[#deded7]" />
              </div>
              <div className="text-right font-mono text-[10px] tabular-nums text-[#777770]">{ms(span.end_ms - span.start_ms)}</div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex justify-between font-mono text-[9px] text-[#a0a098]"><span>0ms</span><span>{ms(max)}</span></div>
    </section>
  );
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button onClick={onClick} className={`rounded px-2 py-1 text-[10px] ${active ? "bg-white text-[#292925] shadow-sm ring-1 ring-[#deded7]" : "text-[#8b8b83]"}`}>{children}</button>;
}
