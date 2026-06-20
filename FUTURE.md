# FUTURE — deferred / cut to protect the weekend timeline

Things intentionally left out so the happy-path demo ships polished. Per CLAUDE.md:
cut anything that threatens the timeline and note it here.

## Deferred this weekend
- **SQLite persistence** — in-memory only for now; `Store` is structured so a swap is mechanical.
- **Real ingestion at scale / OTLP** — single `/ingest` endpoint + great seed data instead.
- **Agentic verification loop** (pipeline step 3, stretch) — `query_traces` tool exists in the store (`query_spans`/`query_logs`); wiring it into a model loop is post-MVP.
- **Multi-trace incidents** — scenarios are single-trace today; the model (`Incident.trace_ids`) already supports many.
- **Auth / multi-tenant** — none; it's a demo.

## Pipeline stretch
- **Per-card incremental streaming** — today `/analyze` streams one SSE `hypothesis` event per card, but all cards are produced by one structured call before emitting. True token-by-token card streaming (parsing `input_json_delta` as each hypothesis object completes) would let cards literally type in. Deferred — fragile partial-JSON parsing vs. weekend budget.
- **Stream the agentic loop's intermediate steps** — `?verify=true` runs the `query_traces` loop server-side but only streams the final hypotheses. Surfacing each `query_traces` call as an SSE event would make the agent's reasoning visible in the UI (great demo material).

## Nice-to-haves if time remains
- More scenarios (memory leak / OOM, retry storm, clock skew, partial outage).
- Self-instrumentation persistence + historical AI-metrics view (beyond last-run bar).
- Shareable incident permalinks for the case study.

## Known shortcuts
- Seed timestamps are pinned to a fixed base epoch for reproducible demos.
- Eval matching is fuzzy (keyword + evidence overlap), not semantic.
