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

SYSTEM = (
    "You are Causality, an incident root-cause copilot for on-call engineers. "
    "Given a window of spans and log lines from a failing service, identify the most "
    "likely root causes. Reason from evidence: error/degraded spans, latency outliers, "
    "and temporal proximity to the first failure. Prefer a single confident hypothesis "
    "backed by specific spans/logs over many vague ones. Always answer by calling the "
    "emit_hypotheses tool."
)


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


def generate_hypotheses(incident_id: str) -> Tuple[List[Hypothesis], AIMetrics]:
    """Run the structured call and return ranked hypotheses + run metrics.

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
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        tools=[HYPOTHESIS_TOOL],
        tool_choice={"type": "tool", "name": "emit_hypotheses"},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    latency_ms = int((time.monotonic() - t0) * 1000)

    raw = next(
        (b.input["hypotheses"] for b in message.content if b.type == "tool_use"),
        [],
    )

    hyps: List[Hypothesis] = []
    span_ids = {s.id for s in spans}
    log_ids = {l.id for l in logs}
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
                # Drop any hallucinated ids that aren't in the provided context.
                evidence_span_ids=[i for i in h.get("evidence_span_ids", []) if i in span_ids],
                evidence_log_ids=[i for i in h.get("evidence_log_ids", []) if i in log_ids],
            )
        )

    metrics = AIMetrics(
        model=MODEL,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        latency_ms=latency_ms,
        tool_calls=1,
        hypothesis_count=len(hyps),
    )
    store.last_hypotheses[incident_id] = hyps
    store.last_metrics[incident_id] = metrics
    return hyps, metrics
