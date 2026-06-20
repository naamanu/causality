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
| AI hypothesis pipeline (structured output + streaming) | ⏳ stubbed (`/incidents/{id}/analyze`) |
| Eval harness + scorecard (`app/eval.py`) | ⏳ skeleton + seed validation |
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

Key endpoints: `GET /scenarios`, `GET /incidents/{id}`, `GET /incidents/{id}/spans`,
`GET /incidents/{id}/logs`, `POST /incidents/{id}/analyze` (stub).
