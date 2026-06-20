"""Causality API — FastAPI app.

Saturday scaffold: serves the seeded scenarios and exposes the read/query layer.
The AI hypothesis pipeline (structured output + streaming) lands in `pipeline.py`
next; the `/incidents/{id}/analyze` route below is stubbed to make the contract
explicit for the frontend.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import Incident, LogLine, ScenarioBundle, Span, Status
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


@app.post("/incidents/{incident_id}/analyze")
def analyze(incident_id: str) -> dict:
    """STUB — wired in Saturday #4. Will stream ranked `Hypothesis` objects from
    a Claude tool-call over the assembled context. Returns the context for now so
    the contract is visible."""
    ctx = store.assemble_context(incident_id)
    if not ctx:
        raise HTTPException(404, f"unknown incident {incident_id}")
    return {
        "incident_id": incident_id,
        "status": "not_implemented",
        "note": "hypothesis pipeline pending (Saturday #4: structured output + streaming)",
        "context_span_count": len(ctx["spans"]),
        "context_log_count": len(ctx["logs"]),
    }
