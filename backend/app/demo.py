"""Deterministic, dependency-light data for public visual preview deployments."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from .config import settings
from .db import (
    Environment,
    IncidentRecord,
    IngestionKey,
    UsageDaily,
    Workspace,
    session_scope,
    utcnow,
)
from .security import hash_key
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
        if settings.demo_ingestion_key:
            prefix = settings.demo_ingestion_key.split(".", 1)[0]
            key = db.get(IngestionKey, "key_demo_checkout_lab")
            if key is None:
                db.add(IngestionKey(
                    id="key_demo_checkout_lab", workspace_id=workspace.id, environment_id=environment.id,
                    name="Checkout Lab", prefix=prefix, secret_hash=hash_key(settings.demo_ingestion_key),
                ))
            else:
                key.prefix = prefix
                key.secret_hash = hash_key(settings.demo_ingestion_key)
                key.revoked_at = None
        day = datetime.now(timezone.utc).date().isoformat()
        usage = db.scalar(select(UsageDaily).where(UsageDaily.workspace_id == workspace.id, UsageDaily.day == day))
        if usage is None:
            db.add(UsageDaily(workspace_id=workspace.id, day=day))


def demo_telemetry():
    bundle = store.bundles["slow-db-query"]
    return bundle.spans, bundle.logs
