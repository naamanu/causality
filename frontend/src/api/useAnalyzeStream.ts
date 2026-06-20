import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "./client";
import type { AIMetrics, Hypothesis } from "./types";

export type StreamState = "idle" | "streaming" | "done" | "error";

export interface AnalyzeStream {
  state: StreamState;
  hypotheses: Hypothesis[];
  metrics: AIMetrics | null;
  error: string | null;
  run: (verify?: boolean) => void;
  reset: () => void;
}

/**
 * Drives `POST /incidents/{id}/analyze` (SSE). EventSource can't POST, so we read
 * the fetch body stream and parse SSE frames by hand. Hypotheses arrive one event
 * at a time, so the UI can animate each card in as it lands.
 */
export function useAnalyzeStream(incidentId: string | null): AnalyzeStream {
  const [state, setState] = useState<StreamState>("idle");
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [metrics, setMetrics] = useState<AIMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState("idle");
    setHypotheses([]);
    setMetrics(null);
    setError(null);
  }, []);

  // Reset whenever the selected incident changes.
  useEffect(() => {
    reset();
    return () => abortRef.current?.abort();
  }, [incidentId, reset]);

  const run = useCallback(
    (verify = false) => {
      if (!incidentId) return;
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setState("streaming");
      setHypotheses([]);
      setMetrics(null);
      setError(null);

      void (async () => {
        try {
          const res = await fetch(
            `${API_BASE}/incidents/${incidentId}/analyze?verify=${verify}`,
            { method: "POST", signal: ctrl.signal },
          );
          if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // SSE frames are separated by a blank line.
            let sep: number;
            while ((sep = buffer.indexOf("\n\n")) !== -1) {
              const frame = buffer.slice(0, sep);
              buffer = buffer.slice(sep + 2);
              handleFrame(frame);
            }
          }
          setState((s) => (s === "error" ? s : "done"));
        } catch (e) {
          if ((e as Error).name === "AbortError") return;
          setError((e as Error).message);
          setState("error");
        }
      })();

      function handleFrame(frame: string) {
        let event = "message";
        const dataLines: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) return;
        const data = JSON.parse(dataLines.join("\n"));

        if (event === "hypothesis") {
          setHypotheses((prev) => [...prev, data as Hypothesis]);
        } else if (event === "metrics") {
          setMetrics(data as AIMetrics);
        } else if (event === "error") {
          setError(data.message ?? "Unknown error");
          setState("error");
        }
      }
    },
    [incidentId],
  );

  return { state, hypotheses, metrics, error, run, reset };
}
