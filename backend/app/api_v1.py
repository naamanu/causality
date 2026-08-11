from __future__ import annotations

import gzip
import json
import logging
import time
from datetime import datetime, timezone
from typing import Iterator

import httpx
import redis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import (
    Principal,
    current_principal,
    encode_session,
    exchange_code,
    login_redirect,
    principal_from_workos,
    require_admin,
)
from .config import settings
from .db import (
    AnalysisRecord,
    AuditEvent,
    Environment,
    HypothesisRecord,
    IncidentRecord,
    IngestionKey,
    UsageDaily,
    Workspace,
    get_db,
    utcnow,
)
from .demo_live import demo_live_telemetry, deterministic_evidence_analysis
from .pipeline import generate_from_context
from .security import constant_time_key_matches, issue_ingestion_key
from .tasks import _decode_otlp, ingest_otlp, run_analysis
from .telemetry import normalize_otlp_json, query_window

router = APIRouter(prefix="/api/v1")
otlp_router = APIRouter()
logger = logging.getLogger("causality.api")

# The one incident seeded by `demo.seed_demo_control_plane` for the public preview.
# Analyses for it are scripted, not generated — see `_complete_demo_analysis`.
DEMO_INCIDENT_ID = "inc_demo_slow_db"


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")


class KeyCreate(BaseModel):
    environment_id: str
    name: str = Field(min_length=1, max_length=100)


class IncidentCreate(BaseModel):
    environment_id: str
    title: str = Field(min_length=1, max_length=240)
    services: list[str] = Field(default_factory=list, max_length=20)
    window_start: int
    window_end: int
    summary: str = Field(default="", max_length=2000)


class AnalysisCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


class InvitationCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)


def _audit(db: Session, p: Principal, action: str, target_type: str, target_id: str, metadata: dict | None = None) -> None:
    db.add(AuditEvent(workspace_id=p.workspace_id, actor_id=p.user_id, action=action, target_type=target_type, target_id=target_id, metadata_json=metadata or {}))


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _consume(workspace_id: str, kind: str, amount: int, limit: int) -> None:
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        key = f"quota:{workspace_id}:{_month()}:{kind}"
        used = int(client.incrby(key, amount))
        if client.ttl(key) < 0:
            client.expire(key, 40 * 24 * 3600)
        if used > limit:
            client.decrby(key, amount)
            raise HTTPException(429, f"monthly {kind} quota exceeded", headers={"Retry-After": "3600"})
    except HTTPException:
        raise
    except Exception as exc:
        if settings.production:
            raise HTTPException(503, "quota service unavailable") from exc


@router.get("/auth/login")
def auth_login():
    return login_redirect()


@router.get("/auth/callback")
def auth_callback(code: str, db: Session = Depends(get_db)):
    try:
        principal = principal_from_workos(exchange_code(code), db)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "identity provider exchange failed") from exc
    response = RedirectResponse(f"{settings.app_base_url.rstrip('/')}/app", status_code=303)
    response.set_cookie("causality_session", encode_session(principal), httponly=True, secure=settings.production, samesite="lax", max_age=3600)
    return response


@router.post("/auth/logout")
def auth_logout():
    response = Response(status_code=204)
    response.delete_cookie("causality_session")
    return response


@router.get("/auth/session")
def auth_session(p: Principal = Depends(current_principal)):
    return p.__dict__


@router.get("/workspaces/current")
def current_workspace(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    ws = db.get(Workspace, p.workspace_id)
    return {"id": ws.id, "name": ws.name, "role": p.role, "is_demo": ws.is_demo,
            "limits": {"members": ws.max_members, "environments": ws.max_environments, "records_month": ws.max_records_month, "analyses_month": ws.max_analyses_month}}


@router.get("/environments")
def list_environments(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(Environment).where(Environment.workspace_id == p.workspace_id).order_by(Environment.created_at)).all()
    return [{"id": x.id, "name": x.name, "slug": x.slug, "last_seen_at": x.last_seen_at} for x in rows]


@router.post("/environments", status_code=201)
def create_environment(body: EnvironmentCreate, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    ws = db.get(Workspace, p.workspace_id)
    count = db.scalar(select(func.count()).select_from(Environment).where(Environment.workspace_id == p.workspace_id)) or 0
    if count >= ws.max_environments:
        raise HTTPException(409, "environment limit reached")
    if db.scalar(select(Environment).where(Environment.workspace_id == p.workspace_id, Environment.slug == body.slug)):
        raise HTTPException(409, "environment slug already exists")
    env = Environment(workspace_id=p.workspace_id, name=body.name, slug=body.slug)
    db.add(env); db.flush(); _audit(db, p, "environment.created", "environment", env.id)
    return {"id": env.id, "name": env.name, "slug": env.slug}


@router.get("/ingestion-keys")
def list_keys(p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionKey).where(IngestionKey.workspace_id == p.workspace_id).order_by(IngestionKey.created_at.desc())).all()
    return [{"id": x.id, "environment_id": x.environment_id, "name": x.name, "prefix": x.prefix, "revoked_at": x.revoked_at, "last_used_at": x.last_used_at, "created_at": x.created_at} for x in rows]


@router.post("/ingestion-keys", status_code=201)
def create_key(body: KeyCreate, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    env = db.get(Environment, body.environment_id)
    if env is None or env.workspace_id != p.workspace_id:
        raise HTTPException(404, "environment not found")
    raw, prefix, digest = issue_ingestion_key()
    key = IngestionKey(workspace_id=p.workspace_id, environment_id=env.id, name=body.name, prefix=prefix, secret_hash=digest)
    db.add(key); db.flush(); _audit(db, p, "ingestion_key.created", "ingestion_key", key.id, {"environment_id": env.id})
    return {"id": key.id, "name": key.name, "prefix": key.prefix, "secret": raw,
            "collector_headers": f"Authorization=Bearer {raw}"}


@router.delete("/ingestion-keys/{key_id}", status_code=204)
def revoke_key(key_id: str, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    key = db.get(IngestionKey, key_id)
    if key is None or key.workspace_id != p.workspace_id:
        raise HTTPException(404, "key not found")
    key.revoked_at = utcnow(); _audit(db, p, "ingestion_key.revoked", "ingestion_key", key.id)


@router.get("/incidents")
def list_incidents(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(IncidentRecord).where(IncidentRecord.workspace_id == p.workspace_id).order_by(IncidentRecord.created_at.desc()).limit(100)).all()
    return [_incident_json(x) for x in rows]


def _incident_json(x: IncidentRecord) -> dict:
    return {"id": x.id, "environment_id": x.environment_id, "title": x.title, "services": x.services,
            "window_start": x.window_start, "window_end": x.window_end, "summary": x.summary, "created_at": x.created_at}


@router.post("/incidents", status_code=201)
def create_incident(
    body: IncidentCreate,
    authorization: str | None = Header(None),
    p: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    env = db.get(Environment, body.environment_id)
    if env is None or env.workspace_id != p.workspace_id:
        raise HTTPException(404, "environment not found")
    if settings.demo:
        ingestion_key, _workspace = _authenticate_ingestion(authorization, db)
        if ingestion_key.workspace_id != p.workspace_id or ingestion_key.environment_id != env.id:
            raise HTTPException(403, "ingestion key cannot create incidents in this environment")
    if body.window_end <= body.window_start or body.window_end - body.window_start > settings.analysis_window_max_ms:
        raise HTTPException(422, "window must be positive and no longer than 60 minutes")
    inc = IncidentRecord(workspace_id=p.workspace_id, environment_id=env.id, created_by=p.user_id,
                         title=body.title, services=body.services, window_start=body.window_start,
                         window_end=body.window_end, summary=body.summary)
    db.add(inc); db.flush(); _audit(db, p, "incident.created", "incident", inc.id)
    return _incident_json(inc)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    inc = db.get(IncidentRecord, incident_id)
    if inc is None or inc.workspace_id != p.workspace_id:
        raise HTTPException(404, "incident not found")
    return _incident_json(inc)


@router.get("/incidents/{incident_id}/telemetry")
def incident_telemetry(incident_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    inc = db.get(IncidentRecord, incident_id)
    if inc is None or inc.workspace_id != p.workspace_id:
        raise HTTPException(404, "incident not found")
    spans, logs = _telemetry_for_incident(inc)
    return {"spans": [x.model_dump() for x in spans], "logs": [x.model_dump() for x in logs]}


def _telemetry_for_incident(inc: IncidentRecord):
    if settings.demo:
        spans, logs = demo_live_telemetry.query(
            inc.workspace_id,
            inc.environment_id,
            inc.window_start,
            inc.window_end,
            inc.services,
        )
        if spans or logs:
            return spans, logs
        if inc.id == DEMO_INCIDENT_ID:
            from .demo import demo_telemetry

            return demo_telemetry()
        return [], []
    return query_window(
        inc.workspace_id,
        inc.environment_id,
        inc.window_start,
        inc.window_end,
        inc.services,
    )


@router.post("/incidents/{incident_id}/analyses", status_code=202)
def create_analysis(
    incident_id: str,
    body: AnalysisCreate,
    authorization: str | None = Header(None),
    p: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    inc = db.get(IncidentRecord, incident_id)
    if inc is None or inc.workspace_id != p.workspace_id:
        raise HTTPException(404, "incident not found")
    if settings.demo and incident_id != DEMO_INCIDENT_ID:
        ingestion_key, _workspace = _authenticate_ingestion(authorization, db)
        if (
            ingestion_key.workspace_id != p.workspace_id
            or ingestion_key.environment_id != inc.environment_id
        ):
            raise HTTPException(403, "ingestion key cannot analyze incidents in this environment")
    existing = db.scalar(select(AnalysisRecord).where(AnalysisRecord.workspace_id == p.workspace_id, AnalysisRecord.idempotency_key == body.idempotency_key))
    if existing:
        return _analysis_json(existing, db)
    ws = db.get(Workspace, p.workspace_id)
    _consume(p.workspace_id, "analyses", 1, ws.max_analyses_month)
    row = AnalysisRecord(workspace_id=p.workspace_id, incident_id=inc.id, requested_by=p.user_id, idempotency_key=body.idempotency_key)
    db.add(row); db.flush()
    day = datetime.now(timezone.utc).date().isoformat()
    usage = db.scalar(select(UsageDaily).where(UsageDaily.workspace_id == p.workspace_id, UsageDaily.day == day))
    if usage is None:
        usage = UsageDaily(workspace_id=p.workspace_id, day=day); db.add(usage)
    usage.analyses = (usage.analyses or 0) + 1
    _audit(db, p, "analysis.created", "analysis", row.id)
    if settings.demo:
        if incident_id == DEMO_INCIDENT_ID:
            _complete_demo_analysis(row, db)
        else:
            _complete_live_demo_analysis(row, inc, db)
        db.commit()
        return _analysis_json(row, db)
    # The worker must not race the transaction that created its job.
    db.commit()
    run_analysis.delay(row.id)
    return _analysis_json(row, db)


def _complete_demo_analysis(row: AnalysisRecord, db: Session) -> None:
    """Fill the public preview incident with a fixed, hand-written result.

    This is a scripted product preview, not a model run. Nothing here calls
    Anthropic, so the analysis reports no model and no token/latency metrics;
    responses carry `scripted_preview: true` so the UI can say so plainly.
    """
    from .demo import demo_telemetry
    spans, logs = demo_telemetry()
    candidates = [
        (0.94, "Lock-contended inventory query", "An unindexed SELECT … FOR UPDATE scans roughly 1.8M inventory rows and spends 402ms waiting on a row lock, dominating checkout latency.", [span.id for span in spans if span.name in {"persist-order", "db.query SELECT inventory FOR UPDATE"}], [log.id for log in logs if "lock wait" in log.message.lower()]),
        (0.61, "Order persistence is the bottleneck", "The persist-order branch accounts for most of the trace duration while payment and cart validation remain within their normal budgets.", [span.id for span in spans if span.name in {"persist-order", "POST /checkout"}], []),
        (0.24, "Payment provider latency", "Payment is on the critical path, but its span completes quickly and has no correlated error evidence, making it an unlikely primary cause.", [span.id for span in spans if span.service == "payment-svc"], [log.id for log in logs if "payment" in log.message.lower()]),
    ]
    for rank, (confidence, title, explanation, span_ids, log_ids) in enumerate(candidates, start=1):
        db.add(HypothesisRecord(
            id=f"hyp_demo_{row.id}_{rank}", workspace_id=row.workspace_id, analysis_id=row.id,
            rank=rank, confidence=confidence, title=title, explanation=explanation,
            evidence_span_ids=span_ids, evidence_log_ids=log_ids,
        ))
    # No model call happened here, so no model name and no usage metrics are recorded.
    # Leaving `model` as None makes `_analysis_json` emit `metrics: null`, and the
    # `scripted_preview` flag tells the client to label the result as scripted.
    row.status = "completed"
    row.completed_at = utcnow()


def _complete_live_demo_analysis(row: AnalysisRecord, inc: IncidentRecord, db: Session) -> None:
    """Analyze the checkout lab's measured telemetry without demo infrastructure."""

    spans, logs = _telemetry_for_incident(inc)
    if not spans and not logs:
        row.status = "failed"
        row.error = "no telemetry found in the selected window"
        row.completed_at = utcnow()
        return

    try:
        hypotheses, metrics = generate_from_context(
            row.id,
            inc.title,
            inc.summary,
            spans,
            logs,
        )
    except Exception as exc:  # noqa: BLE001 - provider/SDK failures share the honest fallback
        logger.warning("live demo model analysis failed; using measured fallback: %s", exc)
        # Keep the public demo useful during provider outages without inventing
        # measurements. This fallback only describes attributes present in OTLP.
        hypotheses, metrics = deterministic_evidence_analysis(row.id, spans, logs)
        if not hypotheses:
            row.status = "failed"
            row.error = "analysis provider unavailable and no deterministic evidence matched"
            row.completed_at = utcnow()
            return

    for hypothesis in hypotheses:
        db.add(
            HypothesisRecord(
                id=hypothesis.id,
                workspace_id=row.workspace_id,
                analysis_id=row.id,
                rank=hypothesis.rank,
                confidence=hypothesis.confidence,
                title=hypothesis.title,
                explanation=hypothesis.explanation,
                evidence_span_ids=hypothesis.evidence_span_ids,
                evidence_log_ids=hypothesis.evidence_log_ids,
            )
        )
    row.status = "completed"
    row.model = metrics.model
    row.input_tokens = metrics.input_tokens
    row.output_tokens = metrics.output_tokens
    row.latency_ms = metrics.latency_ms
    row.tool_calls = metrics.tool_calls
    row.completed_at = utcnow()

    day = datetime.now(timezone.utc).date().isoformat()
    usage = db.scalar(
        select(UsageDaily).where(
            UsageDaily.workspace_id == row.workspace_id,
            UsageDaily.day == day,
        )
    )
    if usage is None:
        usage = UsageDaily(workspace_id=row.workspace_id, day=day)
        db.add(usage)
    usage.input_tokens = (usage.input_tokens or 0) + metrics.input_tokens
    usage.output_tokens = (usage.output_tokens or 0) + metrics.output_tokens


def _analysis_json(row: AnalysisRecord, db: Session) -> dict:
    hypotheses = db.scalars(select(HypothesisRecord).where(HypothesisRecord.analysis_id == row.id).order_by(HypothesisRecord.rank)).all()
    return {"id": row.id, "incident_id": row.incident_id, "status": row.status, "error": row.error,
            "scripted_preview": settings.demo and row.incident_id == DEMO_INCIDENT_ID,
            "metrics": {"model": row.model, "input_tokens": row.input_tokens, "output_tokens": row.output_tokens,
                        "latency_ms": row.latency_ms, "tool_calls": row.tool_calls, "hypothesis_count": len(hypotheses)} if row.model else None,
            "hypotheses": [{"id": h.id, "incident_id": row.incident_id, "rank": h.rank, "confidence": h.confidence,
                             "title": h.title, "explanation": h.explanation, "evidence_span_ids": h.evidence_span_ids,
                             "evidence_log_ids": h.evidence_log_ids} for h in hypotheses]}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    row = db.get(AnalysisRecord, analysis_id)
    if row is None or row.workspace_id != p.workspace_id:
        raise HTTPException(404, "analysis not found")
    return _analysis_json(row, db)


@router.get("/analyses/{analysis_id}/events")
def analysis_events(analysis_id: str, p: Principal = Depends(current_principal)):
    def events() -> Iterator[str]:
        last = None
        for _ in range(180):
            from .db import session_scope
            with session_scope() as db:
                row = db.get(AnalysisRecord, analysis_id)
                if row is None or row.workspace_id != p.workspace_id:
                    yield "event: error\ndata: {\"message\":\"analysis not found\"}\n\n"; return
                payload = _analysis_json(row, db)
            encoded = json.dumps(payload, default=str)
            if encoded != last:
                yield f"event: analysis\ndata: {encoded}\n\n"; last = encoded
            if payload["status"] in {"completed", "failed"}:
                yield "event: done\ndata: {}\n\n"; return
            time.sleep(1)
        yield "event: error\ndata: {\"message\":\"analysis stream timed out\"}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/usage")
def usage(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    prefix = _month()
    rows = db.scalars(select(UsageDaily).where(UsageDaily.workspace_id == p.workspace_id, UsageDaily.day.like(f"{prefix}%"))).all()
    ws = db.get(Workspace, p.workspace_id)
    return {"telemetry_records": sum(x.telemetry_records or 0 for x in rows), "analyses": sum(x.analyses or 0 for x in rows),
            "input_tokens": sum(x.input_tokens or 0 for x in rows), "output_tokens": sum(x.output_tokens or 0 for x in rows),
            "limits": {"telemetry_records": ws.max_records_month, "analyses": ws.max_analyses_month}}


@router.post("/invitations", status_code=201)
def create_invitation(body: InvitationCreate, p: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    ws = db.get(Workspace, p.workspace_id)
    if not settings.workos_api_key:
        raise HTTPException(503, "WorkOS is not configured")
    headers = {"Authorization": f"Bearer {settings.workos_api_key}"}
    members = httpx.get("https://api.workos.com/user_management/organization_memberships", headers=headers,
                        params={"organization_id": p.external_org_id, "limit": 100}, timeout=10)
    members.raise_for_status()
    if len(members.json().get("data", [])) >= ws.max_members:
        raise HTTPException(409, "member limit reached")
    response = httpx.post("https://api.workos.com/user_management/invitations", headers=headers,
                          json={"email": body.email, "organization_id": p.external_org_id}, timeout=10)
    if response.status_code >= 400:
        raise HTTPException(502, "identity provider rejected invitation")
    invite = response.json(); _audit(db, p, "invitation.created", "invitation", invite.get("id", body.email))
    return {"id": invite.get("id"), "email": body.email, "status": "pending"}


def _authenticate_ingestion(authorization: str | None, db: Session) -> tuple[IngestionKey, Workspace]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing ingestion bearer key")
    raw = authorization[7:]
    prefix = raw.split(".", 1)[0]
    key = db.scalar(select(IngestionKey).where(IngestionKey.prefix == prefix, IngestionKey.revoked_at.is_(None)))
    if key is None or not constant_time_key_matches(raw, key.secret_hash):
        raise HTTPException(401, "invalid ingestion key")
    return key, db.get(Workspace, key.workspace_id)


async def _receive_otlp(kind: str, request: Request, authorization: str | None, content_encoding: str | None, db: Session) -> Response:
    content_length = int(request.headers.get("content-length", "0") or 0)
    if content_length > settings.max_request_compressed:
        raise HTTPException(413, "compressed payload exceeds 10 MiB")
    key, ws = _authenticate_ingestion(authorization, db)
    body = await request.body()
    if len(body) > settings.max_request_compressed:
        raise HTTPException(413, "compressed payload exceeds 10 MiB")
    if content_encoding == "gzip":
        try: body = gzip.decompress(body)
        except gzip.BadGzipFile as exc: raise HTTPException(400, "invalid gzip payload") from exc
    if len(body) > settings.max_request_decompressed:
        raise HTTPException(413, "decompressed payload exceeds 50 MiB")
    content_type = request.headers.get("content-type", "application/x-protobuf").split(";", 1)[0]
    try:
        data = _decode_otlp(kind, body, content_type)
        rows, warnings = normalize_otlp_json(kind, data)
    except Exception as exc:
        raise HTTPException(400, f"invalid OTLP {kind} payload") from exc
    key.last_used_at = utcnow()
    if settings.demo:
        demo_live_telemetry.ingest(kind, key.workspace_id, key.environment_id, rows)
        environment = db.get(Environment, key.environment_id)
        if environment and environment.workspace_id == key.workspace_id:
            environment.last_seen_at = utcnow()
        day = datetime.now(timezone.utc).date().isoformat()
        usage = db.scalar(
            select(UsageDaily).where(
                UsageDaily.workspace_id == key.workspace_id,
                UsageDaily.day == day,
            )
        )
        if usage is None:
            usage = UsageDaily(workspace_id=key.workspace_id, day=day)
            db.add(usage)
        usage.telemetry_records = (usage.telemetry_records or 0) + len(rows)
    else:
        _consume(key.workspace_id, "records", len(rows), ws.max_records_month)
        ingest_otlp.delay(kind, key.workspace_id, key.environment_id, body.hex(), content_type)
    if "json" not in content_type:
        if kind == "traces":
            from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
                ExportTraceServiceResponse,
            )
            payload = ExportTraceServiceResponse().SerializeToString()
        else:
            from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
                ExportLogsServiceResponse,
            )
            payload = ExportLogsServiceResponse().SerializeToString()
        return Response(content=payload, media_type="application/x-protobuf")
    return Response(content=json.dumps({"partialSuccess": {"rejectedSpans" if kind == "traces" else "rejectedLogRecords": 0, "errorMessage": "; ".join(warnings)}}), media_type="application/json")


@otlp_router.post("/v1/traces")
async def receive_traces(request: Request, authorization: str | None = Header(None), content_encoding: str | None = Header(None), db: Session = Depends(get_db)):
    return await _receive_otlp("traces", request, authorization, content_encoding, db)


@otlp_router.post("/v1/logs")
async def receive_logs(request: Request, authorization: str | None = Header(None), content_encoding: str | None = Header(None), db: Session = Depends(get_db)):
    return await _receive_otlp("logs", request, authorization, content_encoding, db)
