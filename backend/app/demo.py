"""Deterministic, dependency-light data for public visual preview deployments."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from .db import Environment, IncidentRecord, UsageDaily, Workspace, session_scope, utcnow
from .store import store

DEMO_INCIDENT_ID = "inc_demo_slow_db"
DEMO_ENVIRONMENT_ID = "env_demo_production"


def seed_demo_control_plane() -> None:
    bundle = store.bundles["slow-db-query"]
    with session_scope() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.external_org_id == "dev-org"))
        if workspace is None:
            workspace = Workspace(id="ws_demo", external_org_id="dev-org", name="Acme Engineering", is_demo=True)
            db.add(workspace)
            db.flush()
        else:
            workspace.name = "Acme Engineering"
            workspace.is_demo = True
        environment = db.scalar(select(Environment).where(
            Environment.workspace_id == workspace.id, Environment.slug == "production"
        ))
        if environment is None:
            environment = Environment(
                id=DEMO_ENVIRONMENT_ID, workspace_id=workspace.id, name="Production",
                slug="production", last_seen_at=utcnow(),
            )
            db.add(environment)
        if db.get(IncidentRecord, DEMO_INCIDENT_ID) is None:
            db.add(IncidentRecord(
                id=DEMO_INCIDENT_ID, workspace_id=workspace.id, environment_id=environment.id,
                created_by="dev-user", title=bundle.incident.title,
                services=sorted({span.service for span in bundle.spans}),
                window_start=bundle.incident.window_start, window_end=bundle.incident.window_end,
                summary=bundle.incident.summary,
            ))
        day = datetime.now(timezone.utc).date().isoformat()
        usage = db.scalar(select(UsageDaily).where(UsageDaily.workspace_id == workspace.id, UsageDaily.day == day))
        if usage is None:
            db.add(UsageDaily(workspace_id=workspace.id, day=day, telemetry_records=128_420, analyses=18,
                              input_tokens=41_280, output_tokens=9_140))


def demo_telemetry():
    bundle = store.bundles["slow-db-query"]
    return bundle.spans, bundle.logs
