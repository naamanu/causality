"""Causality API — FastAPI app.

Saturday scaffold: serves the seeded scenarios and exposes the read/query layer.
The AI hypothesis pipeline (structured output + streaming) lands in `pipeline.py`
next; the `/incidents/{id}/analyze` route below is stubbed to make the contract
explicit for the frontend.
"""

from __future__ import annotations

import json
from typing import Iterator, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .models import AIMetrics, Hypothesis, Incident, LogLine, ScenarioBundle, Span, Status
from .store import store

app = FastAPI(title="Causality", version="0.1.0",
              description="AI incident root-cause copilot — backend")

# Frontend (Vite dev server) lands Sunday; allow it now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    store.load_seeds()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "incidents": len(store.incidents), "spans": len(store.spans)}


@app.get("/scenarios")
def list_scenarios() -> List[dict]:
    """Demo picker source. `default` flags the 10-second-wow scenario."""
    out = []
    for i, (key, bundle) in enumerate(store.bundles.items()):
        out.append({
            "scenario_key": key,
            "title": bundle.title,
            "description": bundle.description,
            "incident_id": bundle.incident.id,
            "default": i == 0,
        })
    return out


@app.get("/incidents", response_model=List[Incident])
def list_incidents() -> List[Incident]:
    return store.list_incidents()


@app.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    inc = store.get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, f"unknown incident {incident_id}")
    return inc


@app.get("/incidents/{incident_id}/spans", response_model=List[Span])
def incident_spans(incident_id: str) -> List[Span]:
    inc = store.get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, f"unknown incident {incident_id}")
    spans: List[Span] = []
    for tid in inc.trace_ids:
        spans.extend(store.query_spans(trace_id=tid))
    return spans


@app.get("/incidents/{incident_id}/logs", response_model=List[LogLine])
def incident_logs(incident_id: str) -> List[LogLine]:
    inc = store.get_incident(incident_id)
    if inc is None:
        raise HTTPException(404, f"unknown incident {incident_id}")
    logs: List[LogLine] = []
    for tid in inc.trace_ids:
        logs.extend(store.query_logs(trace_id=tid))
    return logs


@app.get("/spans")
def query_spans(
    trace_id: Optional[str] = None,
    service: Optional[str] = None,
    status: Optional[Status] = None,
    min_duration_ms: Optional[int] = None,
) -> List[Span]:
    """Raw query layer — also the surface the AI's `query_traces` tool wraps."""
    return store.query_spans(trace_id, service, status, min_duration_ms)


@app.post("/ingest")
def ingest(bundle: ScenarioBundle) -> dict:
    """One clean ingest endpoint (CLAUDE.md). Accepts a full scenario bundle."""
    store.ingest_bundle(bundle)
    store.bundles[bundle.scenario_key] = bundle
    return {"ingested": bundle.scenario_key, "spans": len(bundle.spans)}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/incidents/{incident_id}/analyze")
def analyze(incident_id: str, verify: bool = False) -> StreamingResponse:
    """Run the hypothesis pipeline and stream results to the client as SSE.

    Emits one `hypothesis` event per ranked card (so the UI can animate them in),
    then a `metrics` event (tokens / latency / tool-calls), then `done`. Errors
    surface as an `error` event rather than a broken stream.

    `?verify=true` runs the agentic loop — the model may call `query_traces` to
    test hypotheses against the data before finalizing rank (tool-calls show in
    the metrics).
    """
    if store.get_incident(incident_id) is None:
        raise HTTPException(404, f"unknown incident {incident_id}")

    # Import here so a missing SDK degrades to a clean error event, not an import-time crash.
    from .pipeline import generate_hypotheses

    def gen() -> Iterator[str]:
        try:
            hyps, metrics = generate_hypotheses(incident_id, verify=verify)
        except RuntimeError as e:
            yield _sse("error", {"message": str(e)})
            return
        for h in hyps:
            yield _sse("hypothesis", h.model_dump())
        yield _sse("metrics", metrics.model_dump())
        yield _sse("done", {"incident_id": incident_id, "count": len(hyps)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/incidents/{incident_id}/metrics", response_model=AIMetrics)
def last_metrics(incident_id: str) -> AIMetrics:
    """AIMetricsBar source — self-instrumentation for the most recent run."""
    m = store.last_metrics.get(incident_id)
    if m is None:
        raise HTTPException(404, f"no run recorded for {incident_id}")
    return m


@app.get("/incidents/{incident_id}/hypotheses", response_model=List[Hypothesis])
def last_hypotheses(incident_id: str) -> List[Hypothesis]:
    """Cached hypotheses from the most recent run (non-streaming fetch)."""
    h = store.last_hypotheses.get(incident_id)
    if h is None:
        raise HTTPException(404, f"no run recorded for {incident_id}")
    return h
