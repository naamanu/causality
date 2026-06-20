"""Tiny fluent builder for assembling a trace out of spans and logs.

Keeps the scenario files declarative: you describe spans by relative offset and
duration; the builder handles absolute timestamps and id minting.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..models import LogLevel, LogLine, Span, Status, Trace

# Fixed base epoch (2026-06-20T14:00:00Z) so every build is byte-identical.
BASE_TS = 1_781_013_600_000


class TraceBuilder:
    def __init__(self, trace_id: str, root_service: str, t0_ms: int = 0):
        self.trace_id = trace_id
        self.root_service = root_service
        self.t0 = BASE_TS + t0_ms
        self.spans: List[Span] = []
        self.logs: List[LogLine] = []
        self._span_seq = 0
        self._log_seq = 0

    def span(
        self,
        name: str,
        service: str,
        start_ms: int,
        duration_ms: int,
        status: Status = Status.OK,
        parent: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> str:
        self._span_seq += 1
        span_id = f"{self.trace_id}-s{self._span_seq:02d}"
        end_ms = start_ms + duration_ms
        self.spans.append(
            Span(
                id=span_id,
                trace_id=self.trace_id,
                parent_id=parent,
                name=name,
                service=service,
                start=self.t0 + start_ms,
                end=self.t0 + end_ms,
                start_ms=start_ms,
                end_ms=end_ms,
                status=status,
                attributes=attributes or {},
            )
        )
        return span_id

    def log(
        self,
        ts_ms: int,
        level: LogLevel,
        message: str,
        span_id: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> str:
        self._log_seq += 1
        log_id = f"{self.trace_id}-l{self._log_seq:02d}"
        self.logs.append(
            LogLine(
                id=log_id,
                trace_id=self.trace_id,
                span_id=span_id,
                ts=self.t0 + ts_ms,
                level=level,
                message=message,
                attributes=attributes or {},
            )
        )
        return log_id

    def trace(self) -> Trace:
        start = min(s.start for s in self.spans)
        end = max(s.end for s in self.spans)
        status = Status.OK
        if any(s.status == Status.ERROR for s in self.spans):
            status = Status.ERROR
        elif any(s.status == Status.DEGRADED for s in self.spans):
            status = Status.DEGRADED
        return Trace(
            id=self.trace_id,
            service=self.root_service,
            start=start,
            end=end,
            status=status,
        )
