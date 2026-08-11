import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, createAnalysis } from "./client";
import type { AIMetrics, Analysis, Hypothesis } from "./types";

export type StreamState = "idle" | "streaming" | "done" | "error";
export function useAnalyzeStream(incidentId: string | null) {
  const [state, setState] = useState<StreamState>("idle");
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [metrics, setMetrics] = useState<AIMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reset = useCallback(() => { abortRef.current?.abort(); setState("idle"); setHypotheses([]); setMetrics(null); setError(null); }, []);
  useEffect(() => { reset(); return () => abortRef.current?.abort(); }, [incidentId, reset]);
  const run = useCallback(() => {
    if (!incidentId) return;
    const ctrl = new AbortController(); abortRef.current = ctrl; setState("streaming"); setError(null);
    void createAnalysis(incidentId).then(async initial => {
      const res = await fetch(`${API_BASE}/api/v1/analyses/${initial.id}/events`, { credentials: "include", signal: ctrl.signal });
      if (!res.ok || !res.body) throw new Error("Unable to stream analysis");
      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = "";
      for (;;) {
        const part = await reader.read(); if (part.done) break; buffer += decoder.decode(part.value, { stream: true });
        let sep; while ((sep = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, sep); buffer = buffer.slice(sep + 2);
          const line = frame.split("\n").find(x => x.startsWith("data:")); if (!line) continue;
          const payload = JSON.parse(line.slice(5)) as Analysis;
          if (payload.status) { setHypotheses(payload.hypotheses); setMetrics(payload.metrics); if (payload.status === "failed") { setError(payload.error); setState("error"); } if (payload.status === "completed") setState("done"); }
        }
      }
    }).catch(e => { if (e.name !== "AbortError") { setError(e.message); setState("error"); } });
  }, [incidentId]);
  return { state, hypotheses, metrics, error, run, reset };
}
