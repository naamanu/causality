# Causality

**An AI incident root-cause copilot for on-call engineers.** Point it at a window
of logs and traces from a failing service; it returns a **ranked set of root-cause
hypotheses** — each one backed by the exact spans and log lines that support it —
next to an interactive trace view you can drill into.

> Weekend portfolio project. Demo-first, synthetic data only. Runs end-to-end with
> one command (see [Quickstart](#quickstart)).

<!-- Portfolio TODO: drop a screencast GIF or screenshot here (docs/demo.gif) and a live link. -->
> **Live demo:** _add deploy link_ · **Screencast:** _add `docs/demo.gif`_

---

## The problem

When a service starts failing at 2am, the on-call engineer's job is not "fix it" —
it's **figure out what's actually wrong** before the clock runs. They page through
dashboards, grep logs, eyeball trace waterfalls, and hold a mental model of which
span caused which. That triage phase is where **MTTR** (mean time to resolution)
goes to die: the fix is often trivial once you *know* the cause.

- **ICP:** the on-call engineer mid-incident, and the SRE/platform teams who own MTTR.
- **The wedge:** collapse "read the telemetry → form a theory → find the evidence"
  from minutes of manual scanning into a ranked, evidence-linked shortlist you can
  confirm or reject in seconds.
- **The value metric:** time-to-root-cause. The demo is designed to make that win
  legible — a failing incident loads, hypotheses stream in ranked, and each card
  jumps you straight to the spans that justify it.

## How it works

1. **Context assembly** — for a given incident, gather the candidate spans/logs and
   rank by signal: error status, latency outliers, and temporal proximity to the
   first failure.
2. **Hypothesis generation** — a single structured-output call (Anthropic tool-calling
   enforces the `Hypothesis` schema) returns a ranked list, each with a title,
   explanation, confidence, and references to the supporting `span_ids` / `log_ids`.
3. **Agentic verification** *(optional, `?verify=true`)* — the model may call a
   `query_traces` tool to test a hypothesis against the data before finalizing rank.
   Tool-calls are counted and surfaced in the metrics.
4. **Self-instrumentation** — every run records model, input/output tokens, latency,
   and tool-calls. It's observability *of* the AI, inside an observability product.
5. **Eval harness** — each seed scenario ships a hidden ground-truth root cause; the
   harness scores whether the top hypothesis matches and prints a scorecard.

Results stream to the client over **Server-Sent Events**: one `hypothesis` event per
ranked card, then a `metrics` event, then `done` (errors arrive as a clean `error`
event rather than a broken stream).

## Quickstart

### Docker — one command

```bash
cp .env.example .env        # add your ANTHROPIC_API_KEY
docker compose up           # frontend → http://localhost:5173 · API → http://localhost:8000
```

Brings up both services with source bind-mounted for hot reload. Stop with
`docker compose down`. The frontend auto-loads the default scenario, so a reviewer
gets the full flow with zero setup.

### Local — backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # fish: source .venv/bin/activate.fish
pip install -r requirements.txt

uvicorn app.main:app --reload         # API on http://localhost:8000  (/docs for Swagger)
python -m app.eval                    # seed integrity check + scorecard
```

### Local — frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (expects the backend on :8000)
npm run build      # tsc --noEmit && vite build
```

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — (required) | Enables the hypothesis engine. Without it, `/analyze` streams a clean `error` event and the eval harness stops after seed validation. |
| `CAUSALITY_MODEL` | `claude-sonnet-4-6` | Override the model. |
| `VITE_API_BASE` | `http://localhost:8000` | Where the browser reaches the API (set for a deployed demo). |

> The backend allow-lists `http://localhost:5173` for CORS; the Docker setup keeps
> the frontend on that origin so it works out of the box.

## API

| Method & path | Description |
| --- | --- |
| `GET /health` | Liveness + loaded incident/span counts. |
| `GET /scenarios` | Demo picker source; flags the default "10-second wow" scenario. |
| `GET /incidents` · `GET /incidents/{id}` | List / fetch incidents. |
| `GET /incidents/{id}/spans` · `.../logs` | Telemetry for an incident. |
| `GET /spans?trace_id=&service=&status=&min_duration_ms=` | Raw query layer — also the surface the AI's `query_traces` tool wraps. |
| `POST /ingest` | One clean ingest endpoint; accepts a full scenario bundle. |
| `POST /incidents/{id}/analyze[?verify=true]` | Run the pipeline, stream SSE: `hypothesis`\* → `metrics` → `done`. |
| `GET /incidents/{id}/metrics` | Self-instrumentation for the most recent run. |
| `GET /incidents/{id}/hypotheses` | Cached hypotheses from the most recent run (non-streaming). |

## Architecture

```
frontend/  React + TypeScript + Vite + Tailwind  ──SSE──▶  backend/  FastAPI
  ScenarioPicker · IncidentHeader                            /analyze streams
  SpanList · HypothesisList (+ metrics footer)               Anthropic tool-calling
                                                             in-memory Store (seeds)
```

**Data model** (`backend/app/models.py`):

- `Trace` — id, service, start/end, status
- `Span` — id, trace_id, parent_id, name, service, start/end, status, attributes
- `LogLine` — id, trace_id?, span_id?, ts, level, message, attributes
- `Incident` — id, title, scenario_key, trace_ids, summary
- `Hypothesis` — id, incident_id, rank, confidence, title, explanation, evidence span/log ids
- `AIMetrics` — model, input/output tokens, latency, tool-calls

Persistence is in-memory for the weekend; the `Store` is structured so a SQLite swap
is mechanical (see `FUTURE.md`).

## Seed scenarios

Each ships with a hidden ground-truth root cause for the eval harness:

1. **slow-db-query** — unindexed, lock-contended `SELECT ... FOR UPDATE` blows the
   checkout latency budget (no errors, latency only).
2. **cascading-timeout** — redis outage → profile-svc bypasses cache → recommendations
   timeout → gateway 504.
3. **bad-deploy** — order-svc v2.4.0 introduces a null deref in a new discount path;
   error rate spikes at the deploy boundary.
4. **noisy-neighbor** — analytics batch hogs the shared DB connection pool; api-svc
   stalls acquiring a connection despite fast queries.

## Frontend

React + TypeScript + Vite + Tailwind, with monospace-meets-editorial typography
(JetBrains Mono for data, Newsreader for headlines). It auto-loads the default
scenario, renders the incident header and a proportional span view, and streams
hypotheses from `/analyze` over SSE — `useAnalyzeStream` parses the event stream by
hand since the endpoint is a POST. Hypothesis cards render as they arrive, with a
metrics footer showing model, tokens, latency, and tool-calls. Empty, loading
(skeleton), and error states are handled deliberately.

## Project structure

```
causality/
├─ docker-compose.yml       # one-command stack
├─ backend/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ app/
│     ├─ main.py            # FastAPI routes + SSE
│     ├─ models.py          # Pydantic data model
│     ├─ store.py           # in-memory store + query layer
│     ├─ pipeline.py        # hypothesis gen, structured output, verify loop
│     ├─ eval.py            # seed validation + scorecard
│     └─ seeds/             # 4 synthetic scenarios + builder
└─ frontend/
   ├─ Dockerfile
   └─ src/
      ├─ App.tsx
      ├─ api/               # client, types, useAnalyzeStream (SSE)
      └─ components/        # ScenarioPicker, IncidentHeader, SpanList, HypothesisList
```

## Status

| Area | State |
| --- | --- |
| Data model, 4 seed scenarios, ingest + query layer | ✅ |
| AI hypothesis pipeline — structured output + SSE streaming | ✅ |
| Agentic verification loop (`query_traces`, `?verify=true`) | ✅ |
| Self-instrumentation (tokens / latency / tool-calls) | ✅ |
| Eval harness + scorecard | ✅ |
| Frontend shell, streaming hypotheses, span view, metrics footer, states | ✅ |
| One-command Docker stack | ✅ |
| Scrubable timeline · full trace waterfall · Cmd-K palette · re-rank motion | 🔜 planned (`FUTURE.md`) |

## What this demonstrates

- **Design engineering** — the on-call moment as a crafted interface: streaming
  hypothesis cards, a proportional span view, evidence that links back to the
  telemetry, and deliberate empty/loading/error states.
- **Product engineering** — a clear ICP and a felt problem, framed around one value
  metric (time-to-root-cause / MTTR).
- **Full-stack engineering** — a real ingest endpoint, a sane trace/span data model,
  a query layer the AI reuses, and SSE streaming to the client.
- **AI engineering** — structured/function-calling output for the hypothesis schema,
  retrieval over log/trace context, an agentic verification loop, a small eval
  harness, and self-instrumentation of the model surfaced in the UI.

## Scope

Synthetic data only, demo-first, weekend-scoped. Anything cut to protect the happy
path is tracked in [`FUTURE.md`](./FUTURE.md).
