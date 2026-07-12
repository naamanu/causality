"""Import real trace files into Causality's data model.

Supports the two shapes on-call engineers actually have lying around from a
running server:

- **OTLP/JSON** — OpenTelemetry trace export (`resourceSpans` at the top level),
  the format `otel-collector`, the OTLP exporters, and `otlptracehttp` emit.
- **Jaeger JSON** — a trace export from the Jaeger query API / UI (`data` array
  of traces, each with `spans` + `processes`).

Both carry real spans; we map them onto `Span`/`Trace`/`Incident`, deriving what
the seeds hand-author: per-trace relative offsets (`start_ms`/`end_ms`), a `Trace`
per trace id, and one `Incident` spanning the file's time window. Imported bundles
have `root_cause=None` — there's no known answer to score, so the eval harness
ignores them, but the full UI + hypothesis pipeline work unchanged.

OTLP trace exports carry no logs (logs are a separate signal); imported incidents
are span-only, which the pipeline handles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Incident, ScenarioBundle, Span, Status, Trace


class ImportError_(ValueError):
    """Raised when a file can't be recognized or parsed as trace JSON."""


# --- format detection -------------------------------------------------------

def detect_format(data: object) -> str:
    if isinstance(data, dict):
        if "resourceSpans" in data:
            return "otlp"
        if "data" in data and isinstance(data["data"], list):
            return "jaeger"
    raise ImportError_(
        "unrecognized trace format — expected OTLP JSON ('resourceSpans') "
        "or Jaeger JSON ('data')"
    )


# --- OTLP -------------------------------------------------------------------

def _otlp_attr_value(v: dict) -> str:
    """Flatten an OTLP AnyValue to a string (attributes are string->string here)."""
    if "stringValue" in v:
        return v["stringValue"]
    if "intValue" in v:
        return str(v["intValue"])
    if "doubleValue" in v:
        return str(v["doubleValue"])
    if "boolValue" in v:
        return "true" if v["boolValue"] else "false"
    if "arrayValue" in v or "kvlistValue" in v or "bytesValue" in v:
        return json.dumps(v)
    return json.dumps(v)


def _otlp_attrs(attrs: Optional[List[dict]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for a in attrs or []:
        key = a.get("key")
        val = a.get("value")
        if key is not None and isinstance(val, dict):
            out[key] = _otlp_attr_value(val)
    return out


def _otlp_status(span: dict) -> Status:
    code = (span.get("status") or {}).get("code")
    # code is 2 / "STATUS_CODE_ERROR" for errors depending on the encoder.
    if code in (2, "2", "STATUS_CODE_ERROR", "ERROR"):
        return Status.ERROR
    return Status.OK


def _ns_to_ms(v: object) -> int:
    return int(int(v) // 1_000_000)


def parse_otlp(data: dict) -> Tuple[List[dict], List[str]]:
    """Return (raw_spans, warnings). Raw spans carry absolute epoch-ms start/end."""
    raw: List[dict] = []
    warnings: List[str] = []
    for rs in data.get("resourceSpans", []):
        res_attrs = _otlp_attrs((rs.get("resource") or {}).get("attributes"))
        service = res_attrs.get("service.name", "unknown-service")
        # Newer exporters use `scopeSpans`; older ones `instrumentationLibrarySpans`.
        scopes = rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []
        for scope in scopes:
            for sp in scope.get("spans", []):
                try:
                    start = _ns_to_ms(sp["startTimeUnixNano"])
                    end = _ns_to_ms(sp["endTimeUnixNano"])
                except (KeyError, TypeError, ValueError):
                    warnings.append(f"skipped span {sp.get('spanId', '?')}: missing/bad timestamps")
                    continue
                span_id = sp.get("spanId")
                trace_id = sp.get("traceId")
                if not span_id or not trace_id:
                    warnings.append("skipped span: missing spanId/traceId")
                    continue
                raw.append({
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_id": sp.get("parentSpanId") or None,
                    "name": sp.get("name", "span"),
                    "service": service,
                    "start": start,
                    "end": max(end, start),
                    "status": _otlp_status(sp),
                    "attributes": _otlp_attrs(sp.get("attributes")),
                })
    return raw, warnings


# --- Jaeger -----------------------------------------------------------------

def _jaeger_tags(tags: Optional[List[dict]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in tags or []:
        key = t.get("key")
        if key is not None:
            out[key] = str(t.get("value"))
    return out


def _jaeger_status(tags: Dict[str, str]) -> Status:
    if tags.get("error") in ("true", "True", "1"):
        return Status.ERROR
    if tags.get("otel.status_code") in ("ERROR", "STATUS_CODE_ERROR"):
        return Status.ERROR
    http = tags.get("http.status_code") or tags.get("http.response.status_code")
    try:
        if http is not None and int(float(http)) >= 500:
            return Status.ERROR
    except (TypeError, ValueError):
        pass
    return Status.OK


def parse_jaeger(data: dict) -> Tuple[List[dict], List[str]]:
    raw: List[dict] = []
    warnings: List[str] = []
    for trace in data.get("data", []):
        processes = trace.get("processes", {}) or {}
        for sp in trace.get("spans", []):
            span_id = sp.get("spanID")
            trace_id = sp.get("traceID")
            if not span_id or not trace_id:
                warnings.append("skipped span: missing spanID/traceID")
                continue
            try:
                start = int(sp["startTime"]) // 1000  # micros -> ms
                dur = int(sp.get("duration", 0)) // 1000
            except (KeyError, TypeError, ValueError):
                warnings.append(f"skipped span {span_id}: missing/bad startTime")
                continue
            parent = None
            for ref in sp.get("references", []):
                if ref.get("refType") == "CHILD_OF":
                    parent = ref.get("spanID")
                    break
            proc = processes.get(sp.get("processID", ""), {})
            tags = _jaeger_tags(sp.get("tags"))
            raw.append({
                "id": span_id,
                "trace_id": trace_id,
                "parent_id": parent,
                "name": sp.get("operationName", "span"),
                "service": proc.get("serviceName", "unknown-service"),
                "start": start,
                "end": start + max(dur, 0),
                "status": _jaeger_status(tags),
                "attributes": tags,
            })
    return raw, warnings


# --- assembly ---------------------------------------------------------------

def _trace_status(spans: List[dict]) -> Status:
    if any(s["status"] == Status.ERROR for s in spans):
        return Status.ERROR
    if any(s["status"] == Status.DEGRADED for s in spans):
        return Status.DEGRADED
    return Status.OK


def build_bundle(
    raw_spans: List[dict],
    *,
    scenario_key: str,
    incident_id: str,
    title: str,
    description: str,
) -> ScenarioBundle:
    """Assemble parsed spans into a ScenarioBundle (one incident, N traces)."""
    if not raw_spans:
        raise ImportError_("no spans found in file")

    # Group by trace so we can compute per-trace relative offsets (what the
    # waterfall renders) and build one Trace object per trace id.
    by_trace: Dict[str, List[dict]] = {}
    for rs in raw_spans:
        by_trace.setdefault(rs["trace_id"], []).append(rs)

    spans: List[Span] = []
    traces: List[Trace] = []
    seen_ids: set = set()
    for tid, group in by_trace.items():
        t0 = min(s["start"] for s in group)
        for s in group:
            if s["id"] in seen_ids:
                continue  # duplicate span id — keep the first
            seen_ids.add(s["id"])
            spans.append(Span(
                id=s["id"],
                trace_id=tid,
                parent_id=s["parent_id"],
                name=s["name"],
                service=s["service"],
                start=s["start"],
                end=s["end"],
                start_ms=s["start"] - t0,
                end_ms=s["end"] - t0,
                status=s["status"],
                attributes=s["attributes"],
            ))
        root = next((s for s in group if not s["parent_id"]), group[0])
        traces.append(Trace(
            id=tid,
            service=root["service"],
            start=min(s["start"] for s in group),
            end=max(s["end"] for s in group),
            status=_trace_status(group),
        ))

    window_start = min(s.start for s in spans)
    window_end = max(s.end for s in spans)
    n_err = sum(1 for s in spans if s.status == Status.ERROR)
    summary = (
        f"Imported {len(spans)} spans across {len(traces)} trace(s); "
        f"{n_err} error span(s). Window {window_end - window_start}ms."
    )

    incident = Incident(
        id=incident_id,
        title=title,
        scenario_key=scenario_key,
        trace_ids=[t.id for t in traces],
        summary=summary,
        window_start=window_start,
        window_end=window_end,
    )
    return ScenarioBundle(
        scenario_key=scenario_key,
        title=title,
        description=description,
        incident=incident,
        traces=traces,
        spans=spans,
        logs=[],
        root_cause=None,
    )


def parse_trace_data(data: object) -> Tuple[List[dict], List[str]]:
    fmt = detect_format(data)
    if fmt == "otlp":
        return parse_otlp(data)  # type: ignore[arg-type]
    return parse_jaeger(data)  # type: ignore[arg-type]


def bundle_from_file(
    path: Path,
    *,
    scenario_key: str,
    incident_id: str,
    title: str,
) -> Tuple[ScenarioBundle, List[str]]:
    """Read a trace file and turn it into a bundle. Raises ImportError_ on bad input."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ImportError_(f"not valid JSON: {e}") from e
    fmt = detect_format(data)
    raw_spans, warnings = parse_trace_data(data)
    description = f"Imported from {path.name} ({fmt.upper()} · {len(raw_spans)} spans)."
    bundle = build_bundle(
        raw_spans,
        scenario_key=scenario_key,
        incident_id=incident_id,
        title=title,
        description=description,
    )
    return bundle, warnings
