from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./causality.sqlite")
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:5173")
    database_url: str = _database_url()
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    clickhouse_host: str = os.getenv("CLICKHOUSE_HOST", "")
    clickhouse_port: int = int(os.getenv("CLICKHOUSE_PORT", "8443"))
    clickhouse_database: str = os.getenv("CLICKHOUSE_DATABASE", "default")
    clickhouse_user: str = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password: str = os.getenv("CLICKHOUSE_PASSWORD", "")
    clickhouse_secure: bool = _bool("CLICKHOUSE_SECURE", True)
    session_secret: str = os.getenv("SESSION_SECRET", "development-only-change-me")
    workos_client_id: str = os.getenv("WORKOS_CLIENT_ID", "")
    workos_api_key: str = os.getenv("WORKOS_API_KEY", "")
    dev_auth_enabled: bool = _bool("DEV_AUTH_ENABLED", True)
    telemetry_retention_days: int = int(os.getenv("TELEMETRY_RETENTION_DAYS", "7"))
    findings_retention_days: int = int(os.getenv("FINDINGS_RETENTION_DAYS", "90"))
    max_members: int = int(os.getenv("DEFAULT_MAX_MEMBERS", "10"))
    max_environments: int = int(os.getenv("DEFAULT_MAX_ENVIRONMENTS", "3"))
    max_records_month: int = int(os.getenv("DEFAULT_MAX_RECORDS_MONTH", "10000000"))
    max_analyses_month: int = int(os.getenv("DEFAULT_MAX_ANALYSES_MONTH", "200"))
    max_request_compressed: int = int(os.getenv("MAX_REQUEST_COMPRESSED", str(10 * 1024 * 1024)))
    max_request_decompressed: int = int(os.getenv("MAX_REQUEST_DECOMPRESSED", str(50 * 1024 * 1024)))
    analysis_window_max_ms: int = 60 * 60 * 1000

    @property
    def production(self) -> bool:
        return self.app_env == "production"

    def validate(self) -> None:
        if not self.production:
            return
        missing = []
        required = {
            "DATABASE_URL": self.database_url.startswith("postgres"),
            "REDIS_URL": bool(os.getenv("REDIS_URL")),
            "CLICKHOUSE_HOST": bool(self.clickhouse_host),
            "SESSION_SECRET": self.session_secret != "development-only-change-me",
            "WORKOS_CLIENT_ID": bool(self.workos_client_id),
            "WORKOS_API_KEY": bool(self.workos_api_key),
            "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
        }
        missing.extend(k for k, ok in required.items() if not ok)
        if missing:
            raise RuntimeError(f"unsafe production configuration; missing: {', '.join(missing)}")


settings = Settings()
