"""Causality API — FastAPI app.

Saturday scaffold: serves the seeded scenarios and exposes the read/query layer.
The AI hypothesis pipeline (structured output + streaming) lands in `pipeline.py`
next; the `/incidents/{id}/analyze` route below is stubbed to make the contract
explicit for the frontend.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Iterator, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .importer import ImportError_, bundle_from_file
from .models import AIMetrics, Hypothesis, Incident, LogLine, ScenarioBundle, Span, Status
from .store import store
from .config import settings
from .db import init_database
from .telemetry import ensure_clickhouse_schema
from .api_v1 import router as api_v1_router, otlp_router
from .extensions import load_extension

# Directory the server is allowed to read trace files from — "where you'd store a
# logfile". Files dropped here are auto-loaded on startup; `POST /import` reads only
# from within this dir (path allow-listing, so it can't read arbitrary files).
IMPORT_DIR = Path(os.environ.get("CAUSALITY_IMPORT_DIR", "data/imports")).resolve()

app = FastAPI(title="Causality", version="0.1.0",
              description="AI incident root-cause copilot — backend")

# Frontend (Vite dev server) lands Sunday; allow it now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({"http://localhost:5173", "http://127.0.0.1:5173", settings.app_base_url}),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router)
app.include_router(otlp_router)
extension = load_extension()
for extension_router in extension.routers:
    app.include_router(extension_router)


@app.middleware("http")
async def production_boundary(request, call_next):
    """Disable demo APIs and enforce same-origin cookie mutations in production."""
    path = request.url.path
    if settings.production and not path.startswith(("/api/v1", "/v1", "/health", "/docs", "/openapi.json")) and path != "/":
        return JSONResponse({"detail": "not found"}, status_code=404)
    if settings.production and path.startswith("/api/v1") and request.method not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get("causality_session"):
        if request.headers.get("origin") != settings.app_base_url.rstrip("/"):
            return JSONResponse({"detail": "invalid request origin"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    return response


@app.on_event("startup")
def _startup() -> None:
    settings.validate()
    extension.validate()
    init_database()
    ensure_clickhouse_schema()
    extension.startup()
    store.load_seeds()
    _scan_import_dir()


# --- trace-file import ------------------------------------------------------

def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "import"


def _unique_key(base: str) -> str:
    """A scenario_key not already taken (imports must not collide with seeds)."""
    key = base
    n = 2
    while key in store.bundles:
        key = f"{base}-{n}"
        n += 1
    return key


def _resolve_in_import_dir(raw_path: str) -> Path:
    """Resolve a requested path and confirm it stays inside IMPORT_DIR.

    Prevents `../../etc/passwd`-style reads: relative paths resolve under the
    import dir, and any resolved path must be contained by it.
    """
    p = Path(raw_path)
    resolved = (p if p.is_absolute() else IMPORT_DIR / p).resolve()
    if resolved != IMPORT_DIR and IMPORT_DIR not in resolved.parents:
        raise HTTPException(403, f"path is outside the allowed import dir ({IMPORT_DIR})")
    if not resolved.is_file():
        raise HTTPException(404, f"no such file: {raw_path}")
    return resolved


def _import_path(path: Path, title: Optional[str] = None) -> dict:
    scenario_key = _unique_key(f"import-{_slug(path.stem)}")
    incident_id = f"inc-{scenario_key}"
    bundle, warnings = bundle_from_file(
        path,
        scenario_key=scenario_key,
        incident_id=incident_id,
        title=title or f"Imported: {path.stem}",
    )
    store.register_import(bundle)
    return {
        "scenario_key": scenario_key,
        "incident_id": incident_id,
        "title": bundle.title,
        "spans": len(bundle.spans),
        "traces": len(bundle.traces),
        "warnings": warnings,
    }


def _scan_import_dir() -> None:
    """Auto-load every *.json in the import dir on startup (best-effort)."""
    if not IMPORT_DIR.is_dir():
        return
    for f in sorted(IMPORT_DIR.glob("*.json")):
        try:
            _import_path(f)
        except Exception as e:  # never let one bad file block startup
            print(f"[import] skipped {f.name}: {e}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "incidents": len(store.incidents), "spans": len(store.spans)}


@app.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    from sqlalchemy import text
    from .db import session_scope
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(503, "database unavailable") from exc


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
            "source": "import" if key in store.imported_keys else "seed",
        })
    return out


class ImportRequest(BaseModel):
    path: str
    title: Optional[str] = None


@app.get("/imports")
def list_import_files() -> dict:
    """Trace files available in the server's import dir, and which are loaded."""
    files = []
    if IMPORT_DIR.is_dir():
        for f in sorted(IMPORT_DIR.glob("*.json")):
            files.append(f.name)
    return {"import_dir": str(IMPORT_DIR), "files": files}


@app.post("/import")
def import_trace_file(req: ImportRequest) -> dict:
    """Read an OTLP/Jaeger trace file from the allow-listed import dir and load it
    as an incident (appears in the scenario picker, runs through the AI pipeline)."""
    path = _resolve_in_import_dir(req.path)
    try:
        return _import_path(path, title=req.title)
    except ImportError_ as e:
        raise HTTPException(422, f"could not import {path.name}: {e}")


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


# The production image copies the Vite build here. API routes are registered
# first, so the SPA fallback cannot shadow them.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
