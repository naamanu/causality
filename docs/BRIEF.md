# CLAUDE.md — Causality

> Handoff brief from a planning session. This is a **weekend portfolio project**. Read this fully before starting; it defines scope, stack, and the build order. Optimize for a polished, demo-able result over completeness.

## What we're building

**Causality** — an AI incident root-cause copilot for on-call engineers. You feed it a window of logs + traces from a failing service; it returns a **ranked set of root-cause hypotheses**, each backed by the specific spans/log lines that support it, with an interactive trace timeline you can drill into. Think "Linear-grade interface for the on-call moment."

## Why this project (portfolio goals — keep these in view)

This is a portfolio centerpiece meant to land senior roles across four lenses, in priority order:

1. **Design engineering (top priority)** — the craft is the point: trace waterfall, scrubable timeline, hypothesis cards that stream in and animate to ranked positions, keyboard-first command palette, immaculate empty/loading/error states, monospace-meets-editorial typography.
2. **Product engineering** — clear ICP (on-call engineers), a felt problem, and a value metric (MTTR). The demo should make the "time-to-root-cause" win obvious.
3. **Full-stack engineering** — real ingest endpoint, sane trace/span data model, streaming to client, a query layer the AI can call.
4. **AI engineering** — structured/function-calling output for hypotheses, retrieval over log/trace context, an agentic "query the data to test a hypothesis" loop, and a small eval harness. Bonus: instrument the LLM itself (tokens, latency, tool-calls) and surface it in the UI — observability _of_ the AI, inside an observability product.

## Scope guardrails (do NOT violate without asking)

- **Synthetic data only.** Ship 3–4 canned failing-service scenarios (slow DB query, cascading timeout, bad deploy, noisy-neighbor). No real ingestion at scale — one clean ingest endpoint + great seed data.
- **Demo-first.** The live demo must pre-load a scenario so a reviewer gets the "wow" in ~10 seconds with zero setup.
- **Weekend-scoped.** If something threatens the timeline, cut it and note it in a `FUTURE.md`. Polish on the happy path beats breadth.

## Recommended stack (swap if you have a strong preference)

- **Frontend:** React + TypeScript + Vite. Styling: Tailwind. Animation: Framer Motion (hypothesis re-ranking, timeline). This is where the craft budget goes.
- **Backend + AI:** Python + FastAPI (fastest path for streaming + LLM structured output). _Note: Go is also on the table and plays to the CV's "Go tracing pipeline" story — decide on Saturday morning, don't dither._
- **AI:** Anthropic API, Claude Sonnet (current model string `claude-sonnet-4-6`) for the hypothesis engine. Use tool-calling / structured output for the hypothesis schema. Stream results to the client.
- **Data:** in-memory or SQLite for the weekend — do not over-engineer persistence.

## Data model (starting sketch — refine as needed)

- `Trace` — id, service, start/end, status
- `Span` — id, trace_id, parent_id, name, service, start/end, status, attributes{}
- `LogLine` — id, trace_id?, span_id?, ts, level, message, attributes{}
- `Incident` — id, title, scenario_key, trace_ids[], summary
- `Hypothesis` — id, incident_id, rank, confidence, title, explanation, evidence_span_ids[], evidence_log_ids[]

## AI pipeline

1. **Context assembly** — given an incident window, gather candidate spans/logs (retrieval: rank by error status, latency outliers, temporal proximity to first failure).
2. **Hypothesis generation** — single structured-output call returning a list of `Hypothesis` objects (title, explanation, confidence, evidence references). Enforce the schema via tool-calling.
3. **Agentic verification loop (stretch)** — let the model call a `query_traces(filter)` tool to test a hypothesis against the data before finalizing rank.
4. **Eval harness** — each canned scenario has a known root cause; score whether the top hypothesis matches. Print a tiny scorecard. This is a strong AI-eng signal — don't skip it.
5. **Self-instrumentation** — log token count, latency, and tool-calls per request; expose via an endpoint the UI can render.

## Frontend component breakdown

- `IncidentTimeline` — scrubable, marks first-failure, hover to highlight related spans
- `TraceWaterfall` — span bars by depth, error spans flagged, click to inspect
- `HypothesisList` — cards stream in, animate to ranked order, confidence indicator, expand to show evidence (jumps to the spans/logs)
- `CommandPalette` — keyboard-first (Cmd-K): jump to incident, filter, re-run analysis
- `AIMetricsBar` — tokens / latency / tool-calls for the last run (the meta-flex)
- States — design the empty, loading (streaming skeleton), and error states deliberately; reviewers notice these.

## Build sequence

**Saturday**

1. Repo + stack decision (Python vs Go) — 15 min, then commit.
2. Data model + 3–4 seed scenarios.
3. Ingest endpoint + query layer.
4. AI hypothesis pipeline with structured output + streaming, validated against seeds.
5. Eval harness + scorecard.

**Sunday**

1. Frontend shell + data fetching/streaming.
2. TraceWaterfall + IncidentTimeline.
3. HypothesisList with streaming + re-rank animation.
4. CommandPalette + AIMetricsBar.
5. Polish pass: states, motion, typography, keyboard nav.
6. Deploy a live demo with a scenario pre-loaded. Write the case-study README (problem → ICP → MTTR framing → what each lens demonstrates).

## Definition of done

A deployed link where a stranger can, within 10 seconds and no setup, see a failing incident, watch ranked hypotheses stream in, drill into the evidence, and notice the craft. README frames it as a product with a metric.
