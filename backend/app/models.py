"""Core data model for Causality.

Mirrors the sketch in CLAUDE.md. Timestamps are epoch milliseconds (int) so the
frontend timeline can do plain arithmetic without date parsing. Spans also carry
relative offsets (`start_ms`/`end_ms`, ms since the trace start) which is what the
waterfall actually renders.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    OK = "ok"
    ERROR = "error"
    # "ok but slow" — not failing, but a latency outlier worth surfacing.
    DEGRADED = "degraded"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class Span(BaseModel):
    id: str
    trace_id: str
    parent_id: Optional[str] = None
    name: str
    service: str
    # Absolute epoch-ms…
    start: int
    end: int
    # …and relative to the trace start, for the waterfall.
    start_ms: int
    end_ms: int
    status: Status = Status.OK
    attributes: Dict[str, str] = Field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return self.end - self.start


class LogLine(BaseModel):
    id: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    ts: int
    level: LogLevel = LogLevel.INFO
    message: str
    attributes: Dict[str, str] = Field(default_factory=dict)


class Trace(BaseModel):
    id: str
    service: str
    start: int
    end: int
    status: Status = Status.OK

    @property
    def duration_ms(self) -> int:
        return self.end - self.start


class Hypothesis(BaseModel):
    """A single candidate root cause. Produced by the AI pipeline (Saturday #4).

    The schema is deliberately flat and JSON-friendly so it can be enforced as a
    Claude tool-call output and streamed card-by-card to the client.
    """

    id: str
    incident_id: str
    rank: int
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    explanation: str
    evidence_span_ids: List[str] = Field(default_factory=list)
    evidence_log_ids: List[str] = Field(default_factory=list)


class Incident(BaseModel):
    id: str
    title: str
    scenario_key: str
    trace_ids: List[str] = Field(default_factory=list)
    summary: str
    # Wall-clock window of interest [start, end] in epoch-ms.
    window_start: int
    window_end: int


class RootCause(BaseModel):
    """Ground truth for one scenario — used only by the eval harness, never sent
    to the model. The hypothesis engine is scored against this.
    """

    scenario_key: str
    summary: str
    culprit_service: str
    # Lower-cased terms the top hypothesis should hit for a "match".
    keywords: List[str] = Field(default_factory=list)
    evidence_span_ids: List[str] = Field(default_factory=list)
    evidence_log_ids: List[str] = Field(default_factory=list)


class ScenarioBundle(BaseModel):
    """Everything one seed scenario produces: the incident, its telemetry, and the
    hidden ground-truth root cause."""

    scenario_key: str
    title: str
    description: str
    incident: Incident
    traces: List[Trace]
    spans: List[Span]
    logs: List[LogLine]
    root_cause: RootCause
