# CLAUDE.md — Causality

Portfolio centerpiece for a senior-role job hunt. The full original planning brief lives at
`docs/BRIEF.md` (historical — the project is now built; the code is the source of truth for
stack, data model, and components).

## Portfolio goals (why decisions get made the way they do)

Four lenses, in priority order: **design engineering first** (the craft — motion, states,
typography — is the point), then product engineering (ICP: on-call engineers; metric: MTTR),
full-stack, and AI engineering (structured output, agentic verification, eval harness,
observability *of* the LLM in the UI).

## Scope guardrails (do NOT violate without asking)

- **Synthetic data only** — canned failing-service scenarios, no real ingestion at scale.
- **Demo-first** — the live demo must pre-load a scenario; a reviewer gets the "wow" in
  ~10 seconds with zero setup.
- **Cut before overrunning** — anything that threatens polish gets cut and noted in `FUTURE.md`.
  Polish on the happy path beats breadth.

## Definition of done

A deployed link where a stranger can, within 10 seconds and no setup, see a failing incident,
watch ranked hypotheses stream in, drill into the evidence, and notice the craft. README frames
it as a product with a metric.
