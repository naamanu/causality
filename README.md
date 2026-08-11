# Causality

Causality is a multi-tenant incident root-cause copilot. It accepts OpenTelemetry
traces and logs, lets an engineer define an incident window, and produces ranked,
evidence-linked hypotheses with Anthropic.

## Local quickstart

OrbStack or another Docker-compatible runtime is sufficient.

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env to run analyses.
docker compose up --build
```

Open `http://localhost:5173`. Development mode supplies a local owner identity;
production requires WorkOS AuthKit. The API is also available at
`http://localhost:8000/docs`.

The first-run UI creates an environment and displays its ingestion key exactly
once. Configure an OpenTelemetry Collector with:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <ingestion-key>"
```

Then create an investigation for the relevant service and time window. Stop the
stack with `docker compose down`; named volumes preserve its data.

## Architecture

- React/Vite frontend and FastAPI API
- PostgreSQL control plane for workspaces, environments, incidents, analyses,
  usage, keys, and audit events
- ClickHouse telemetry plane with seven-day trace/log retention
- Redis quotas and Celery ingestion/analysis workers
- WorkOS AuthKit organizations and roles
- Anthropic platform-managed analysis, with token/latency metrics

Every control-plane query and telemetry query is workspace-scoped. Ingestion keys
are hashed, revocable, environment-specific, and only shown at creation. Sensitive
telemetry attributes are redacted before persistence. Production disables the old
seed/demo API surface and enforces same-origin cookie mutations.

## Services and API

The browser uses `/api/v1`; collectors send OTLP/HTTP JSON or protobuf to
`/v1/traces` and `/v1/logs`. Analysis jobs expose durable status plus an SSE event
stream. Health endpoints are `/health/live` and `/health/ready`.

The legacy in-memory seed and import routes remain available only in development
for product demonstrations and evaluation.

## Verification

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest

cd ../frontend
npm ci
npm run build

cd ..
docker build -t causality .
```

CI runs all three checks on pull requests and `main`.

## Railway deployment

The repository contains separate Railway configurations for the web process,
worker, and daily retention cleanup. Follow [docs/railway.md](docs/railway.md) for
provisioning, required environment variables, migrations, and the staging
checklist. The processes use portable URLs and environment variables so the same
application can later move to Render without code changes.

## Open-core development

The shared product is MIT-licensed. Paid source must live in a separate private
repository—not a branch of this public repository—and integrate through the
optional backend extension contract. See [docs/open-core.md](docs/open-core.md)
for ownership, CI, packaging, and security boundaries.

## Retention and beta limits

Telemetry expires after seven days. Incidents, analyses, hypotheses, and audit
history expire after 90 days through the cleanup job. Default design-partner beta
limits are three environments, ten members, ten million telemetry records per
month, and 200 analyses per month; all are configurable per workspace.
