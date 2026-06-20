"""In-memory store + query layer.

Two jobs:
1. Hold the seeded scenarios (and anything POSTed to /ingest) for the weekend.
2. Expose the read primitives the AI pipeline calls — `query_spans` / `query_logs`
   are exactly what the agentic verification loop's `query_traces` tool will wrap.

No persistence on purpose (CLAUDE.md: don't over-engineer). Swap for SQLite later
without touching callers.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    Incident,
    LogLine,
    ScenarioBundle,
    Span,
    Status,
    Trace,
)
from . import seeds


class Store:
    def __init__(self) -> None:
        self.incidents: Dict[str, Incident] = {}
        self.traces: Dict[str, Trace] = {}
        self.spans: Dict[str, Span] = {}
        self.logs: Dict[str, LogLine] = {}
        # scenario_key -> bundle, kept for the eval harness (ground truth lives here).
        self.bundles: Dict[str, ScenarioBundle] = {}

    def load_seeds(self) -> None:
        for key, bundle in seeds.build_all().items():
            self.ingest_bundle(bundle)
            self.bundles[key] = bundle

    def ingest_bundle(self, bundle: ScenarioBundle) -> None:
        self.incidents[bundle.incident.id] = bundle.incident
        for t in bundle.traces:
            self.traces[t.id] = t
        for s in bundle.spans:
            self.spans[s.id] = s
        for l in bundle.logs:
            self.logs[l.id] = l

    # --- read primitives (also the AI query layer) ---

    def list_incidents(self) -> List[Incident]:
        return list(self.incidents.values())

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.incidents.get(incident_id)

    def incident_by_scenario(self, scenario_key: str) -> Optional[Incident]:
        for inc in self.incidents.values():
            if inc.scenario_key == scenario_key:
                return inc
        return None

    def query_spans(
        self,
        trace_id: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[Status] = None,
        min_duration_ms: Optional[int] = None,
    ) -> List[Span]:
        """The filterable span query the AI's `query_traces` tool will expose."""
        out = list(self.spans.values())
        if trace_id is not None:
            out = [s for s in out if s.trace_id == trace_id]
        if service is not None:
            out = [s for s in out if s.service == service]
        if status is not None:
            out = [s for s in out if s.status == status]
        if min_duration_ms is not None:
            out = [s for s in out if s.duration_ms >= min_duration_ms]
        return sorted(out, key=lambda s: s.start)

    def query_logs(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        min_level: Optional[str] = None,
    ) -> List[LogLine]:
        order = {"debug": 0, "info": 1, "warn": 2, "error": 3}
        out = list(self.logs.values())
        if trace_id is not None:
            out = [l for l in out if l.trace_id == trace_id]
        if span_id is not None:
            out = [l for l in out if l.span_id == span_id]
        if min_level is not None:
            floor = order.get(min_level, 0)
            out = [l for l in out if order.get(l.level.value, 0) >= floor]
        return sorted(out, key=lambda l: l.ts)

    def assemble_context(self, incident_id: str) -> Dict[str, object]:
        """Pipeline step 1 (context assembly): gather candidate spans/logs for an
        incident, ranked so the most suspicious surface first. This is the payload
        the hypothesis-generation call (Saturday #4) will be handed."""
        inc = self.get_incident(incident_id)
        if inc is None:
            return {}

        spans: List[Span] = []
        for tid in inc.trace_ids:
            spans.extend(self.query_spans(trace_id=tid))

        def span_rank(s: Span) -> tuple:
            sev = {Status.ERROR: 0, Status.DEGRADED: 1, Status.OK: 2}[s.status]
            return (sev, -s.duration_ms)

        logs: List[LogLine] = []
        for tid in inc.trace_ids:
            logs.extend(self.query_logs(trace_id=tid))
        logs.sort(key=lambda l: ({"error": 0, "warn": 1, "info": 2, "debug": 3}.get(l.level.value, 4), l.ts))

        return {
            "incident": inc,
            "spans": sorted(spans, key=span_rank),
            "logs": logs,
        }


store = Store()
