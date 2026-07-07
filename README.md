# Causality

**An AI incident root-cause copilot for on-call engineers.** Feed it a window of
logs + traces from a failing service; it returns a **ranked set of root-cause
hypotheses**, each backed by the specific spans and log lines that support it,
over an interactive trace timeline you can drill into.

> Weekend portfolio project. Demo-first, synthetic data only. See `../CLAUDE.md`
> for the full brief and `../master-plan.md` for where it fits the job sprint.

## Stack

- **Backend + AI:** Python + FastAPI · Anthropic `claude-sonnet-4-6` (tool-calling for the hypothesis schema) — _fastest path to streaming + structured output._
- **Frontend (Sunday):** React + TypeScript + Vite · Tailwind · Framer Motion.
- **Data:** in-memory; SQLite optional. Synthetic seeds only.

## Status

| Area | State |
| --- | --- |
| Data model (`app/models.py`) | ✅ done |
| 4 seed scenarios (`app/seeds/`) | ✅ done |
| Ingest + query layer (`app/store.py`, `/ingest`, `/spans`) | ✅ done |
| API serving seeds (`app/main.py`) | ✅ done |
| AI hypothesis pipeline (structured output + SSE streaming) | ✅ done (`app/pipeline.py`, `POST /incidents/{id}/analyze`) |
| Self-instrumentation (tokens / latency / tool-calls) | ✅ done (`AIMetrics`, `GET /incidents/{id}/metrics`) |
| Eval harness + scorecard (`app/eval.py`) | ✅ done (seed validation; scores the engine when `ANTHROPIC_API_KEY` is set) |
| Agentic verification loop (`query_traces`) | ✅ done (`POST /incidents/{id}/analyze?verify=true`) |
| Frontend | ⛔ not started (Sunday) |

## Seed scenarios

Each ships with a hidden ground-truth root cause for the eval harness:

1. **slow-db-query** — unindexed, lock-contended `SELECT ... FOR UPDATE` blows the checkout latency budget (no errors, latency only).
2. **cascading-timeout** — redis outage → profile-svc bypasses cache → recommendations timeout → gateway 504.
3. **bad-deploy** — order-svc v2.4.0 introduces a null deref in a new discount path; error rate spikes at the deploy boundary.
4. **noisy-neighbor** — analytics batch hogs the shared DB connection pool; api-svc stalls acquiring a connection despite fast queries.

## Run

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # fish: source .venv/bin/activate.fish
pip install -r requirements.txt

uvicorn app.main:app --reload         # API on http://localhost:8000  (/docs for Swagger)
python -m app.eval                    # seed integrity + scorecard skeleton
```

Set `ANTHROPIC_API_KEY` to enable the hypothesis engine (`claude-sonnet-4-6`,
override with `CAUSALITY_MODEL`). Without a key, `/analyze` streams a clean
`error` event and the eval harness stops after seed validation.

Key endpoints: `GET /scenarios`, `GET /incidents/{id}`, `GET /incidents/{id}/spans`,
`GET /incidents/{id}/logs`, `POST /incidents/{id}/analyze` (SSE: `hypothesis`* →
`metrics` → `done`; add `?verify=true` for the agentic loop),
`GET /incidents/{id}/metrics`, `GET /incidents/{id}/hypotheses`.
