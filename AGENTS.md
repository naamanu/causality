# Repository Guidelines

## Project Structure & Module Organization

`backend/app/` contains the FastAPI service, telemetry ingestion, analysis pipeline, persistence, authentication, and extension contract. Database migrations live in `backend/alembic/`; backend tests are in `backend/tests/`. The React/Vite application is under `frontend/src/`, with reusable UI in `components/` and API types and clients in `api/`. Seed and import fixtures belong in `data/`, while deployment and architecture notes live in `docs/`. Keep paid features outside this public repository; integrate them through the extension interface described in `docs/open-core.md`.

## Build, Test, and Development Commands

- `cp .env.example .env` creates local configuration. Never commit the resulting `.env`.
- `docker compose up --build` starts the local stack using any Docker-compatible runtime.
- `cd backend && pip install -r requirements.txt -r requirements-dev.txt && pytest` installs Python dependencies and runs backend tests.
- `cd frontend && npm ci && npm run dev` starts Vite with hot reload.
- `cd frontend && npm run build` type-checks TypeScript and creates the production bundle.
- `docker build -t causality .` verifies the production image used by CI and Railway.

## Coding Style & Naming Conventions

Use four-space indentation and `snake_case` for Python functions, modules, and variables; use `PascalCase` for Pydantic models. TypeScript uses two spaces, double quotes, `camelCase` values, and `PascalCase` React components. Keep API paths under `/api/v1` and use explicit boundary types. No automatic formatter is enforced, so follow nearby code and run `npm run typecheck` plus `git diff --check` before committing.

## Testing Guidelines

Pytest is the backend test framework. Name files `test_*.py` and tests `test_*`; place shared fixtures in `backend/tests/conftest.py`. Add regression coverage for API, tenancy, authentication, quota, and telemetry changes. Frontend changes currently rely on TypeScript builds and visual verification; include desktop/mobile screenshots for material UI work. CI requires Backend tests, Frontend build, and Production image checks.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects such as `Add public landing page` or `Fix telemetry redaction`. Branch from `main` with a focused name such as `agent/usage-limits` or `feat/trace-import`. PRs must explain what changed, why, user impact, and validation performed; link related issues and include a Railway preview or screenshots for UI changes. Keep PRs focused, resolve review threads, and do not push directly to protected `main`.

## Security & Configuration

Treat ingestion keys, WorkOS credentials, database URLs, and `ANTHROPIC_API_KEY` as secrets. Preserve workspace scoping on every control-plane and telemetry query. Report vulnerabilities through `SECURITY.md`, not public issues.
