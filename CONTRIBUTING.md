# Contributing to Causality

Thanks for your interest in contributing.

Causality is an incident root-cause copilot: it takes a window of logs and traces from a
failing service and returns ranked hypotheses, each backed by the spans and log lines
that support it.

## Where to start

[`FUTURE.md`](FUTURE.md) is the honest backlog — everything deliberately deferred, and
why. Most open issues come from it. If you want a self-contained first contribution,
adding a new failure scenario under `backend/app/seeds/scenarios.py` needs no API key
and no frontend work.

## Prerequisites

- Docker, or Python 3 and Node
- An `ANTHROPIC_API_KEY` for the analysis pipeline. Seed data and the UI work without
  one; only `/analyze` needs it.

## Getting started

The fastest path:

```bash
cp .env.example .env        # add your ANTHROPIC_API_KEY
docker compose up           # frontend → http://localhost:5173 · API → http://localhost:8000
```

Source is bind-mounted, so both services hot-reload. Or run the backend directly:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://localhost:8000, Swagger at /docs
```

## Project structure

```
backend/app/main.py          # FastAPI app and SSE endpoints
backend/app/pipeline.py      # Hypothesis generation
backend/app/store.py         # In-memory store (see FUTURE.md — SQLite swap is planned)
backend/app/models.py        # Incident / hypothesis models
backend/app/seeds/           # Scenario builders and seed data
backend/app/eval.py          # Eval harness
backend/app/importer.py      # OTLP import
frontend/src/                # React UI and trace view
```

## Things worth knowing before you change behaviour

- **The store is in-memory.** `Store` is structured so a SQLite swap is mechanical;
  please keep that boundary clean rather than reaching into internals.
- **Seed timestamps are pinned to a fixed base epoch** so demos are reproducible. Don't
  replace them with `now()`.
- **Eval matching is fuzzy** (keyword + evidence overlap), not semantic. Improvements
  welcome, but say what you changed and how it moves eval scores.
- **Hypotheses must cite evidence.** A hypothesis without the spans and log lines that
  back it defeats the point of the tool.

## Before you open a PR

There is no test suite yet — adding one is itself a welcome contribution. Until then,
please verify by hand and say what you checked:

```bash
docker compose up
# load the default scenario, run an analysis, confirm cards cite evidence
```

## Making changes

1. Branch off `main`: `git checkout -b feat/your-change`
2. If you defer part of the work, add it to `FUTURE.md` rather than leaving a bare TODO.
3. Open a PR against `main`, linking any related issue.

## Reporting issues

Please include:

- The scenario you loaded (or the OTLP payload you imported)
- Whether you ran with `?verify=true`
- What the hypotheses said versus what you expected

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
