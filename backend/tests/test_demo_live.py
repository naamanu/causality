from app.demo_live import DemoTelemetryBuffer, deterministic_evidence_analysis


def _span(
    span_id: str,
    *,
    start: int = 1_000,
    service: str = "causality-checkout-lab",
    name: str = "SELECT inventory FOR UPDATE",
    status: str = "ok",
    attributes: dict | None = None,
) -> dict:
    return {
        "id": span_id,
        "trace_id": f"trace-{span_id}",
        "parent_id": None,
        "name": name,
        "service": service,
        "start": start,
        "end": start + 420,
        "status": status,
        "attributes": attributes or {},
    }


def _log(log_id: str, *, ts: int = 1_200, service: str = "causality-checkout-lab") -> dict:
    return {
        "id": log_id,
        "trace_id": f"trace-{log_id}",
        "span_id": None,
        "ts": ts,
        "level": "warning",
        "message": "inventory lock wait exceeded budget",
        "attributes": {"service.name": service},
    }


def test_demo_buffer_isolates_tenants_windows_and_services() -> None:
    buffer = DemoTelemetryBuffer()
    buffer.ingest("traces", "ws-a", "env-a", [_span("matching")])
    buffer.ingest("traces", "ws-b", "env-a", [_span("other-tenant")])
    buffer.ingest("traces", "ws-a", "env-a", [_span("other-service", service="worker")])
    buffer.ingest("traces", "ws-a", "env-a", [_span("outside-window", start=9_000)])

    spans, logs = buffer.query("ws-a", "env-a", 900, 2_000, ["causality-checkout-lab"])

    assert [span.id for span in spans] == ["matching"]
    assert logs == []
    assert spans[0].start_ms == 0
    assert spans[0].end_ms == 420


def test_demo_buffer_filters_logs_by_resource_service() -> None:
    buffer = DemoTelemetryBuffer()
    buffer.ingest("logs", "ws-a", "env-a", [_log("matching"), _log("other", service="worker")])

    _spans, logs = buffer.query("ws-a", "env-a", 900, 2_000, ["causality-checkout-lab"])

    assert [log.id for log in logs] == ["matching"]


def test_deterministic_fallback_only_cites_measured_lock_evidence() -> None:
    buffer = DemoTelemetryBuffer()
    buffer.ingest(
        "traces",
        "ws-a",
        "env-a",
        [_span("slow-lock", attributes={"db.lock_wait_ms": "402"})],
    )
    buffer.ingest("logs", "ws-a", "env-a", [_log("lock-log")])
    spans, logs = buffer.query("ws-a", "env-a", 900, 2_000, [])

    hypotheses, metrics = deterministic_evidence_analysis("ana-1", spans, logs)

    assert len(hypotheses) == 1
    assert hypotheses[0].title == "Inventory lock contention"
    assert hypotheses[0].evidence_span_ids == ["slow-lock"]
    assert hypotheses[0].evidence_log_ids == ["lock-log"]
    assert "402ms" in hypotheses[0].explanation
    assert metrics.model == "deterministic evidence summary (no LLM)"
    assert metrics.input_tokens == 0


def test_deterministic_fallback_abstains_without_supported_evidence() -> None:
    buffer = DemoTelemetryBuffer()
    buffer.ingest("traces", "ws-a", "env-a", [_span("healthy", attributes={})])
    spans, logs = buffer.query("ws-a", "env-a", 900, 2_000, [])

    hypotheses, _metrics = deterministic_evidence_analysis("ana-1", spans, logs)

    assert hypotheses == []
