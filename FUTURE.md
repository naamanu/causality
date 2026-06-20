# FUTURE — deferred / cut to protect the weekend timeline

Things intentionally left out so the happy-path demo ships polished. Per CLAUDE.md:
cut anything that threatens the timeline and note it here.

## Deferred this weekend
- **SQLite persistence** — in-memory only for now; `Store` is structured so a swap is mechanical.
- **Real ingestion at scale / OTLP** — single `/ingest` endpoint + great seed data instead.
- **Agentic verification loop** (pipeline step 3, stretch) — `query_traces` tool exists in the store (`query_spans`/`query_logs`); wiring it into a model loop is post-MVP.
- **Multi-trace incidents** — scenarios are single-trace today; the model (`Incident.trace_ids`) already supports many.
- **Auth / multi-tenant** — none; it's a demo.

## Nice-to-haves if time remains
- More scenarios (memory leak / OOM, retry storm, clock skew, partial outage).
- Self-instrumentation persistence + historical AI-metrics view (beyond last-run bar).
- Shareable incident permalinks for the case study.

## Known shortcuts
- Seed timestamps are pinned to a fixed base epoch for reproducible demos.
- Eval matching is fuzzy (keyword + evidence overlap), not semantic.
