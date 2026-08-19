"""Dependency-light live telemetry for the public, synthetic demo environment."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import RLock

from .models import AIMetrics, Hypothesis, LogLevel, LogLine, Span, Status


class DemoTelemetryBuffer:
    """Bounded in-process OTLP storage used only when APP_ENV=demo."""

    def __init__(self, max_records: int = 10_000) -> None:
        self.max_records = max_records
        self._lock = RLock()
        self._spans: dict[str, tuple[str, str, Span]] = {}
        self._logs: dict[str, tuple[str, str, LogLine]] = {}

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()
            self._logs.clear()

    def ingest(
        self, kind: str, workspace_id: str, environment_id: str, rows: list[dict]
    ) -> int:
        with self._lock:
            if kind == "traces":
                for row in rows:
                    span = Span(
                        id=row["id"],
                        trace_id=row["trace_id"],
                        parent_id=row.get("parent_id"),
                        name=row["name"],
                        service=row["service"],
                        start=row["start"],
                        end=row["end"],
                        start_ms=0,
                        end_ms=max(row["end"] - row["start"], 0),
                        status=Status(row["status"]),
                        attributes=row.get("attributes", {}),
                    )
                    self._spans[span.id] = (workspace_id, environment_id, span)
                self._trim(self._spans)
            else:
                for row in rows:
                    raw_level = str(row.get("level", "info")).lower()
                    level = (
                        LogLevel.WARN
                        if raw_level in {"warn", "warning"}
                        else (
                            LogLevel(raw_level)
                            if raw_level in {item.value for item in LogLevel}
                            else LogLevel.INFO
                        )
                    )
                    log = LogLine(
                        id=row["id"],
                        trace_id=row.get("trace_id"),
                        span_id=row.get("span_id"),
                        ts=row["ts"],
                        level=level,
                        message=row["message"],
                        attributes=row.get("attributes", {}),
                    )
                    self._logs[log.id] = (workspace_id, environment_id, log)
                self._trim(self._logs)
        return len(rows)

    def _trim(self, records: dict) -> None:
        overflow = len(records) - self.max_records
        if overflow <= 0:
            return

        def timestamp(item: tuple) -> int:
            record = item[1][2]
            return getattr(record, "start", getattr(record, "ts", 0))

        for key, _value in sorted(records.items(), key=timestamp)[:overflow]:
            records.pop(key, None)

    def query(
        self,
        workspace_id: str,
        environment_id: str,
        start: int,
        end: int,
        services: list[str],
        limit: int = 250,
    ) -> tuple[list[Span], list[LogLine]]:
        with self._lock:
            spans = [
                span.model_copy(deep=True)
                for ws, env, span in self._spans.values()
                if ws == workspace_id
                and env == environment_id
                and start <= span.start <= end
                and (not services or span.service in services)
            ]
            logs = [
                log.model_copy(deep=True)
                for ws, env, log in self._logs.values()
                if ws == workspace_id
                and env == environment_id
                and start <= log.ts <= end
                and (not services or log.attributes.get("service.name") in services)
            ]

        trace_starts: dict[str, int] = defaultdict(lambda: 2**63 - 1)
        for span in spans:
            trace_starts[span.trace_id] = min(trace_starts[span.trace_id], span.start)
        for span in spans:
            span.start_ms = span.start - trace_starts[span.trace_id]
            span.end_ms = span.end - trace_starts[span.trace_id]
        spans.sort(
            key=lambda span: (
                {Status.ERROR: 0, Status.DEGRADED: 1, Status.OK: 2}[span.status],
                -span.duration_ms,
            )
        )
        logs.sort(
            key=lambda log: (
                {LogLevel.ERROR: 0, LogLevel.WARN: 1}.get(log.level, 2),
                log.ts,
            )
        )
        return spans[:limit], logs[:limit]


def deterministic_evidence_analysis(
    analysis_id: str, spans: list[Span], logs: list[LogLine]
) -> tuple[list[Hypothesis], AIMetrics]:
    """Summarize measured demo evidence without pretending an LLM was called."""

    started = time.monotonic()
    hypotheses: list[Hypothesis] = []

    lock_spans = [
        span for span in spans if _number(span.attributes.get("db.lock_wait_ms")) > 100
    ]
    if lock_spans:
        worst = max(
            lock_spans, key=lambda span: _number(span.attributes.get("db.lock_wait_ms"))
        )
        wait_ms = int(_number(worst.attributes.get("db.lock_wait_ms")))
        evidence_logs = [log.id for log in logs if "lock wait" in log.message.lower()]
        hypotheses.append(
            Hypothesis(
                id=f"{analysis_id}-h1",
                incident_id=analysis_id,
                rank=1,
                confidence=0.98,
                title="Inventory lock contention",
                explanation=(
                    f"The inventory query waited {wait_ms}ms to acquire its lock, above the 100ms budget. "
                    "Concurrent checkout traces queue at the same operation while payment remains fast."
                ),
                evidence_span_ids=[
                    span.id
                    for span in sorted(lock_spans, key=lambda item: -item.duration_ms)[
                        :4
                    ]
                ],
                evidence_log_ids=evidence_logs[:4],
            )
        )

    retry_spans = [
        span
        for span in spans
        if span.name == "authorize-payment" and span.status == Status.ERROR
    ]
    if retry_spans and not hypotheses:
        traces = {span.trace_id for span in retry_spans}
        evidence_logs = [
            log.id
            for log in logs
            if "payment authorization retry" in log.message.lower()
        ]
        hypotheses.append(
            Hypothesis(
                id=f"{analysis_id}-h1",
                incident_id=analysis_id,
                rank=1,
                confidence=0.96,
                title="Payment retry amplification",
                explanation=(
                    f"Payment authorization failed repeatedly across {len(traces)} checkout traces before "
                    "recovering. The retries add directly to critical-path latency."
                ),
                evidence_span_ids=[span.id for span in retry_spans[:4]],
                evidence_log_ids=evidence_logs[:4],
            )
        )

    timeout_spans = [
        span
        for span in spans
        if span.status == Status.ERROR
        and str(span.attributes.get("error.type", "")).lower() == "timeout"
    ]
    if timeout_spans and not hypotheses:
        worst = max(timeout_spans, key=lambda span: span.duration_ms)
        evidence_logs = [
            log.id
            for log in logs
            if "shipping quote exceeded timeout" in log.message.lower()
        ]
        hypotheses.append(
            Hypothesis(
                id=f"{analysis_id}-h1",
                incident_id=analysis_id,
                rank=1,
                confidence=0.99,
                title="Shipping dependency timeout",
                explanation=(
                    f"The shipping quote call took {worst.duration_ms}ms and exceeded its configured timeout. "
                    "Checkout fails only after this dependency returns an error."
                ),
                evidence_span_ids=[span.id for span in timeout_spans[:4]],
                evidence_log_ids=evidence_logs[:4],
            )
        )

    metrics = AIMetrics(
        model="deterministic evidence summary (no LLM)",
        input_tokens=0,
        output_tokens=0,
        latency_ms=max(int((time.monotonic() - started) * 1000), 1),
        tool_calls=0,
        hypothesis_count=len(hypotheses),
    )
    return hypotheses, metrics


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


demo_live_telemetry = DemoTelemetryBuffer()
