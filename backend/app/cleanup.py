from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete

from .config import settings
from .db import AnalysisRecord, AuditEvent, IncidentRecord, session_scope, utcnow


def run() -> None:
    cutoff = utcnow() - timedelta(days=settings.findings_retention_days)
    with session_scope() as db:
        db.execute(delete(AnalysisRecord).where(AnalysisRecord.created_at < cutoff))
        db.execute(delete(IncidentRecord).where(IncidentRecord.created_at < cutoff))
        db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))


if __name__ == "__main__":
    run()
