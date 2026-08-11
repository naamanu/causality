from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone

from celery import Celery
from google.protobuf.json_format import MessageToDict
from sqlalchemy import select

from .config import settings
from .db import AnalysisRecord, Environment, HypothesisRecord, IncidentRecord, UsageDaily, session_scope, utcnow
from .pipeline import generate_from_context
from .telemetry import insert_rows, normalize_otlp_json, query_window


celery = Celery("causality", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, task_default_queue="default")


def _decode_otlp(kind: str, body: bytes, content_type: str) -> dict:
    if "json" in content_type:
        return json.loads(body)
    if kind == "traces":
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
        message = ExportTraceServiceRequest.FromString(body)
    else:
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
        message = ExportLogsServiceRequest.FromString(body)
    return MessageToDict(message, preserving_proto_field_name=False)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def ingest_otlp(self, kind: str, workspace_id: str, environment_id: str, body_hex: str, content_type: str) -> int:
    data = _decode_otlp(kind, bytes.fromhex(body_hex), content_type)
    rows, _warnings = normalize_otlp_json(kind, data)
    if rows:
        insert_rows(kind, workspace_id, environment_id, rows)
    with session_scope() as db:
        env = db.get(Environment, environment_id)
        if env and env.workspace_id == workspace_id:
            env.last_seen_at = utcnow()
        day = datetime.now(timezone.utc).date().isoformat()
        usage = db.scalar(select(UsageDaily).where(UsageDaily.workspace_id == workspace_id, UsageDaily.day == day))
        if usage is None:
            usage = UsageDaily(workspace_id=workspace_id, day=day)
            db.add(usage)
        usage.telemetry_records = (usage.telemetry_records or 0) + len(rows)
    return len(rows)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def run_analysis(self, analysis_id: str) -> None:
    with session_scope() as db:
        analysis = db.get(AnalysisRecord, analysis_id)
        if analysis is None or analysis.status == "completed":
            return
        incident = db.get(IncidentRecord, analysis.incident_id)
        if incident is None or incident.workspace_id != analysis.workspace_id:
            analysis.status, analysis.error = "failed", "incident not found"
            return
        analysis.status = "running"
        workspace_id, environment_id = incident.workspace_id, incident.environment_id
        title, summary = incident.title, incident.summary
        start, end, services = incident.window_start, incident.window_end, incident.services
    try:
        spans, logs = query_window(workspace_id, environment_id, start, end, services)
        if not spans and not logs:
            raise RuntimeError("no telemetry found in the selected window")
        hyps, metrics = generate_from_context(analysis_id, title, summary, spans, logs)
        with session_scope() as db:
            analysis = db.get(AnalysisRecord, analysis_id)
            if analysis is None:
                return
            for h in hyps:
                db.add(HypothesisRecord(
                    id=h.id, workspace_id=workspace_id, analysis_id=analysis_id,
                    rank=h.rank, confidence=h.confidence, title=h.title,
                    explanation=h.explanation, evidence_span_ids=h.evidence_span_ids,
                    evidence_log_ids=h.evidence_log_ids,
                ))
            analysis.status = "completed"
            analysis.model = metrics.model
            analysis.input_tokens = metrics.input_tokens
            analysis.output_tokens = metrics.output_tokens
            analysis.latency_ms = metrics.latency_ms
            analysis.tool_calls = metrics.tool_calls
            analysis.completed_at = utcnow()
            day = datetime.now(timezone.utc).date().isoformat()
            usage = db.scalar(select(UsageDaily).where(UsageDaily.workspace_id == workspace_id, UsageDaily.day == day))
            if usage is None:
                usage = UsageDaily(workspace_id=workspace_id, day=day)
                db.add(usage)
            usage.input_tokens = (usage.input_tokens or 0) + metrics.input_tokens
            usage.output_tokens = (usage.output_tokens or 0) + metrics.output_tokens
    except Exception as exc:
        with session_scope() as db:
            analysis = db.get(AnalysisRecord, analysis_id)
            if analysis:
                analysis.status = "failed"
                analysis.error = str(exc)[:2000]
        raise
