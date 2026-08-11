from sqlalchemy import select

from app.db import Environment, IncidentRecord, Workspace, session_scope
from app.demo import DEMO_INCIDENT_ID, demo_telemetry, seed_demo_control_plane
from app.store import store


def test_demo_seed_is_reproducible():
    store.load_seeds()
    seed_demo_control_plane()
    seed_demo_control_plane()
    with session_scope() as db:
        workspace = db.scalar(select(Workspace).where(Workspace.external_org_id == "dev-org"))
        incident = db.get(IncidentRecord, DEMO_INCIDENT_ID)
        environment = db.scalar(select(Environment).where(
            Environment.workspace_id == workspace.id, Environment.slug == "production"
        ))
        assert workspace is not None and workspace.is_demo
        assert incident is not None and incident.workspace_id == workspace.id
        assert environment is not None and environment.workspace_id == workspace.id
    spans, logs = demo_telemetry()
    assert len(spans) == 6
    assert any("lock wait" in log.message for log in logs)
