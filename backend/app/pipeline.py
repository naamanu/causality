"""AI hypothesis pipeline (Saturday #4).

One structured Claude call turns an incident's assembled context into a ranked
list of root-cause `Hypothesis` objects, each citing the specific spans/log lines
that support it. The schema is enforced via tool-calling (`strict: true` + forced
`tool_choice`), and the call streams so a large `max_tokens` can't hit an HTTP
timeout — `get_final_message()` then yields the complete, validated tool input.

Model is `claude-sonnet-4-6` per CLAUDE.md (override with CAUSALITY_MODEL).
The Anthropic SDK is imported lazily so the app boots without it / without a key;
`analyze` raises a clean error only when actually invoked.
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Tuple

from .models import AIMetrics, Hypothesis, LogLine, Span, Status
from .store import store

MODEL = os.environ.get("CAUSALITY_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 8000

# Tool schema = the Hypothesis contract. The model fills title/explanation/
# confidence/evidence; the server mints ids and assigns rank from confidence.
HYPOTHESIS_TOOL = {
    "name": "emit_hypotheses",
    "description": (
        "Return the ranked root-cause hypotheses for this incident. Order does not "
        "matter — rank is derived from confidence. Cite only span/log ids that appear "
        "in the provided context."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "hypotheses": {
                "type": "array",
                "description": "2-4 candidate root causes, most likely first.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "description": "One-line root-cause claim."},
                        "explanation": {
                            "type": "string",
                            "description": "2-4 sentences: the mechanism, grounded in the evidence.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0-1.0 likelihood this is the true root cause.",
                        },
                        "evidence_span_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Span ids from the context that support this hypothesis.",
                        },
                        "evidence_log_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Log ids from the context that support this hypothesis.",
                        },
                    },
                    "required": [
                        "title",
                        "explanation",
                        "confidence",
                        "evidence_span_ids",
                        "evidence_log_ids",
                    ],
                },
            }
        },
        "required": ["hypotheses"],
    },
}

# Agentic verification tool (pipeline step 3): lets the model query the data to
# test a hunch before committing to a ranking. Wraps store.query_spans/query_logs,
# scoped to the incident's traces.
QUERY_TRACES_TOOL = {
    "name": "query_traces",
    "description": (
        "Query the incident's telemetry to test a hypothesis before finalizing. "
        "Returns matching spans or logs (capped). Use it to confirm a culprit, e.g. "
        "filter to error spans in a service, or logs at warn+ for a trace."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["spans", "logs"], "description": "What to query."},
            "trace_id": {"type": "string"},
            "service": {"type": "string", "description": "spans only"},
            "status": {"type": "string", "enum": ["ok", "error", "degraded"], "description": "spans only"},
            "min_duration_ms": {"type": "integer", "description": "spans only"},
            "min_level": {"type": "string", "enum": ["debug", "info", "warn", "error"], "description": "logs only"},
        },
        "required": ["kind"],
    },
}

SYSTEM = (
    "You are Causality, an incident root-cause copilot for on-call engineers. "
    "Given a window of spans and log lines from a failing service, identify the most "
    "likely root causes. Reason from evidence: error/degraded spans, latency outliers, "
    "and temporal proximity to the first failure. Prefer a single confident hypothesis "
    "backed by specific spans/logs over many vague ones. Always answer by calling the "
    "emit_hypotheses tool."
)

SYSTEM_VERIFY = SYSTEM + (
    " You may call query_traces first to test a hunch against the data — confirm the "
    "culprit before you commit to a ranking — then call emit_hypotheses to finish."
)


def run_query_traces(incident_id: str, args: dict) -> str:
    """Execute one query_traces tool call, scoped to the incident's traces.

    Returns a compact text block (ids + key fields) — small enough to feed back
    into the loop without blowing the context budget.
    """
    inc = store.get_incident(incident_id)
    if inc is None:
        return "error: unknown incident"
    trace_ids = [args["trace_id"]] if args.get("trace_id") in inc.trace_ids else inc.trace_ids

    if args.get("kind") == "logs":
        rows: List[LogLine] = []
        for tid in trace_ids:
            rows.extend(store.query_logs(trace_id=tid, min_level=args.get("min_level")))
        rows = rows[:40]
        if not rows:
            return "no matching logs"
        return "\n".join(f"[{l.id}] {l.level.value.upper()} {l.message}" for l in rows)

    status = Status(args["status"]) if args.get("status") else None
    spans: List[Span] = []
    for tid in trace_ids:
        spans.extend(
            store.query_spans(
                trace_id=tid,
                service=args.get("service"),
                status=status,
                min_duration_ms=args.get("min_duration_ms"),
            )
        )
    spans = spans[:40]
    if not spans:
        return "no matching spans"
    return "\n".join(
        f"[{s.id}] {s.service} · {s.name} · {s.duration_ms}ms · {s.status.value}" for s in spans
    )


def _parse_hypotheses(
    raw: List[dict], incident_id: str, spans: List[Span], logs: List[LogLine]
) -> List[Hypothesis]:
    span_ids = {s.id for s in spans}
    log_ids = {l.id for l in logs}
    hyps: List[Hypothesis] = []
    for h in sorted(raw, key=lambda h: h.get("confidence", 0.0), reverse=True):
        rank = len(hyps) + 1
        hyps.append(
            Hypothesis(
                id=f"{incident_id}-h{rank}",
                incident_id=incident_id,
                rank=rank,
                confidence=max(0.0, min(1.0, float(h.get("confidence", 0.0)))),
                title=h["title"],
                explanation=h["explanation"],
                evidence_span_ids=[i for i in h.get("evidence_span_ids", []) if i in span_ids],
                evidence_log_ids=[i for i in h.get("evidence_log_ids", []) if i in log_ids],
            )
        )
    return hyps


def _format_context(spans: List[Span], logs: List[LogLine]) -> str:
    lines = ["## Spans (ranked: errors and latency outliers first)"]
    for s in spans:
        attrs = " ".join(f"{k}={v}" for k, v in s.attributes.items())
        lines.append(
            f"- [{s.id}] {s.service} · {s.name} · {s.duration_ms}ms · {s.status.value}"
            + (f" · {attrs}" if attrs else "")
        )
    lines.append("\n## Logs")
    for l in logs:
        lines.append(f"- [{l.id}] {l.level.value.upper()} {l.message}")
    return "\n".join(lines)


def generate_hypotheses(
    incident_id: str, verify: bool = False
) -> Tuple[List[Hypothesis], AIMetrics]:
    """Run the structured call and return ranked hypotheses + run metrics.

    With ``verify=True``, runs the agentic loop: the model may call ``query_traces``
    to test hunches against the data before committing to a ranking.

    Raises RuntimeError with a readable message if the SDK/key is missing.
    """
    ctx = store.assemble_context(incident_id)
    if not ctx:
        raise KeyError(incident_id)

    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - environment guard
        raise RuntimeError(
            "anthropic SDK not installed — `pip install -r requirements.txt`"
        ) from e
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    inc = ctx["incident"]
    spans: List[Span] = ctx["spans"]
    logs: List[LogLine] = ctx["logs"]
    user = (
        f"Incident: {inc.title}\n{inc.summary}\n\n"
        + _format_context(spans, logs)
        + "\n\nCall emit_hypotheses with 2-4 ranked root-cause hypotheses."
    )

    client = anthropic.Anthropic()
    t0 = time.monotonic()
    if verify:
        raw, in_tok, out_tok, tool_calls = _run_agentic(client, incident_id, user)
    else:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            tools=[HYPOTHESIS_TOOL],
            tool_choice={"type": "tool", "name": "emit_hypotheses"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
        raw = next((b.input["hypotheses"] for b in message.content if b.type == "tool_use"), [])
        in_tok, out_tok, tool_calls = message.usage.input_tokens, message.usage.output_tokens, 1
    latency_ms = int((time.monotonic() - t0) * 1000)

    hyps = _parse_hypotheses(raw, incident_id, spans, logs)
    metrics = AIMetrics(
        model=MODEL,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        tool_calls=tool_calls,
        hypothesis_count=len(hyps),
    )
    store.last_hypotheses[incident_id] = hyps
    store.last_metrics[incident_id] = metrics
    return hyps, metrics


MAX_VERIFY_TURNS = 4


def _run_agentic(client, incident_id: str, user: str) -> Tuple[List[dict], int, int, int]:
    """Manual tool-use loop: the model may call query_traces N times, then
    emit_hypotheses. Returns (raw_hypotheses, input_tokens, output_tokens, tool_calls).
    """
    messages = [{"role": "user", "content": user}]
    in_tok = out_tok = tool_calls = 0

    for turn in range(MAX_VERIFY_TURNS):
        # Force the final structured emit on the last turn so the loop always terminates.
        last = turn == MAX_VERIFY_TURNS - 1
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_VERIFY,
            tools=[QUERY_TRACES_TOOL, HYPOTHESIS_TOOL],
            tool_choice=(
                {"type": "tool", "name": "emit_hypotheses"} if last else {"type": "any"}
            ),
            messages=messages,
        ) as stream:
            msg = stream.get_final_message()
        in_tok += msg.usage.input_tokens
        out_tok += msg.usage.output_tokens

        tool_uses = [b for b in msg.content if b.type == "tool_use"]
        tool_calls += len(tool_uses)

        emit = next((b for b in tool_uses if b.name == "emit_hypotheses"), None)
        if emit is not None:
            return emit.input["hypotheses"], in_tok, out_tok, tool_calls

        # Otherwise execute the query_traces calls and feed results back.
        messages.append({"role": "assistant", "content": msg.content})
        results = [
            {
                "type": "tool_result",
                "tool_use_id": b.id,
                "content": run_query_traces(incident_id, b.input),
            }
            for b in tool_uses
            if b.name == "query_traces"
        ]
        messages.append({"role": "user", "content": results})

    return [], in_tok, out_tok, tool_calls  # pragma: no cover - last turn forces emit
