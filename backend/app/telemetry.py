from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from .config import settings
from .importer import _otlp_attrs, _otlp_status, parse_otlp
from .models import LogLevel, LogLine, Span, Status
from .security import redact_attributes, redact_text


@lru_cache(maxsize=1)
def clickhouse_client():
    if not settings.clickhouse_host:
        return None
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        secure=settings.clickhouse_secure,
    )


def ensure_clickhouse_schema() -> None:
    client = clickhouse_client()
    if client is None:
        return
    ttl = settings.telemetry_retention_days
    client.command(f"""
        CREATE TABLE IF NOT EXISTS spans (
          workspace_id String, environment_id String, span_id String, trace_id String,
          parent_id Nullable(String), name String, service String, start_ms Int64,
          end_ms Int64, duration_ms Int64, status LowCardinality(String),
          attributes Map(String, String), ingested_at DateTime64(3, 'UTC') DEFAULT now64()
        ) ENGINE = ReplacingMergeTree(ingested_at)
        ORDER BY (workspace_id, environment_id, trace_id, span_id)
        TTL toDateTime(start_ms / 1000) + INTERVAL {ttl} DAY DELETE
    """)
    client.command(f"""
        CREATE TABLE IF NOT EXISTS logs (
          workspace_id String, environment_id String, log_id String, trace_id Nullable(String),
          span_id Nullable(String), ts_ms Int64, level LowCardinality(String), body String,
          attributes Map(String, String), ingested_at DateTime64(3, 'UTC') DEFAULT now64()
        ) ENGINE = ReplacingMergeTree(ingested_at)
        ORDER BY (workspace_id, environment_id, ts_ms, log_id)
        TTL toDateTime(ts_ms / 1000) + INTERVAL {ttl} DAY DELETE
    """)


def normalize_otlp_json(kind: str, data: dict) -> tuple[list[dict], list[str]]:
    if kind == "traces":
        rows, warnings = parse_otlp(data)
        for row in rows:
            row["attributes"] = redact_attributes(row.get("attributes", {}))
            row["status"] = row["status"].value
        return rows, warnings

    rows: list[dict] = []
    warnings: list[str] = []
    for resource_logs in data.get("resourceLogs", []):
        resource_attrs = _otlp_attrs((resource_logs.get("resource") or {}).get("attributes"))
        scopes = resource_logs.get("scopeLogs") or resource_logs.get("instrumentationLibraryLogs") or []
        for scope in scopes:
            for record in scope.get("logRecords", []):
                try:
                    ts = int(record.get("timeUnixNano") or record.get("observedTimeUnixNano")) // 1_000_000
                except (TypeError, ValueError):
                    warnings.append("skipped log: missing/bad timestamp")
                    continue
                body_value = record.get("body") or {}
                body = next(iter(body_value.values()), "") if isinstance(body_value, dict) else str(body_value)
                attrs = {**resource_attrs, **_otlp_attrs(record.get("attributes"))}
                identity = f"{record.get('traceId','')}:{record.get('spanId','')}:{ts}:{body}"
                rows.append({
                    "id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                    "trace_id": record.get("traceId") or None,
                    "span_id": record.get("spanId") or None,
                    "ts": ts,
                    "level": str(record.get("severityText") or "info").lower(),
                    "message": redact_text(str(body)),
                    "attributes": redact_attributes(attrs),
                })
    return rows, warnings


def insert_rows(kind: str, workspace_id: str, environment_id: str, rows: list[dict]) -> None:
    client = clickhouse_client()
    if client is None:
        raise RuntimeError("ClickHouse is not configured")
    if kind == "traces":
        columns = ["workspace_id", "environment_id", "span_id", "trace_id", "parent_id", "name", "service", "start_ms", "end_ms", "duration_ms", "status", "attributes"]
        values = [[workspace_id, environment_id, r["id"], r["trace_id"], r.get("parent_id"), r["name"], r["service"], r["start"], r["end"], r["end"] - r["start"], r["status"], r["attributes"]] for r in rows]
        client.insert("spans", values, column_names=columns)
    else:
        columns = ["workspace_id", "environment_id", "log_id", "trace_id", "span_id", "ts_ms", "level", "body", "attributes"]
        values = [[workspace_id, environment_id, r["id"], r.get("trace_id"), r.get("span_id"), r["ts"], r["level"], r["message"], r["attributes"]] for r in rows]
        client.insert("logs", values, column_names=columns)


def query_window(workspace_id: str, environment_id: str, start: int, end: int, services: list[str], limit: int = 250) -> tuple[list[Span], list[LogLine]]:
    client = clickhouse_client()
    if client is None:
        return [], []
    service_filter = " AND service IN %(services)s" if services else ""
    span_rows = client.query(
        "SELECT span_id,trace_id,parent_id,name,service,start_ms,end_ms,status,attributes FROM spans FINAL "
        "WHERE workspace_id=%(ws)s AND environment_id=%(env)s AND start_ms BETWEEN %(start)s AND %(end)s"
        + service_filter + " ORDER BY (status='error') DESC,duration_ms DESC LIMIT %(limit)s",
        parameters={"ws": workspace_id, "env": environment_id, "start": start, "end": end, "services": services, "limit": limit},
    ).result_rows
    spans = [Span(id=r[0], trace_id=r[1], parent_id=r[2], name=r[3], service=r[4], start=r[5], end=r[6], start_ms=0, end_ms=r[6]-r[5], status=Status(r[7]), attributes=dict(r[8])) for r in span_rows]
    log_rows = client.query(
        "SELECT log_id,trace_id,span_id,ts_ms,level,body,attributes FROM logs FINAL WHERE workspace_id=%(ws)s "
        "AND environment_id=%(env)s AND ts_ms BETWEEN %(start)s AND %(end)s "
        "ORDER BY (level='error') DESC,ts_ms LIMIT %(limit)s",
        parameters={"ws": workspace_id, "env": environment_id, "start": start, "end": end, "limit": limit},
    ).result_rows
    logs = [LogLine(id=r[0], trace_id=r[1], span_id=r[2], ts=r[3], level=LogLevel(r[4]) if r[4] in {x.value for x in LogLevel} else LogLevel.INFO, message=r[5], attributes=dict(r[6])) for r in log_rows]
    return spans, logs
