# ADR 0002 — Async Batch Pipeline as the Foundation

- **Status:** Accepted
- **Date:** Week 2
- **Deciders:** <your name>

## Context
Before retrieval, we need to make many LLM calls reliably, fast, and observably. This same
capability becomes the document-ingestion engine in Week 8.

## Decision
Build a minimal, production-shaped async pipeline in `src/pipeline/`:
typed `Settings` (Pydantic), JSON logging, CSV-driven input, **async batched** parallel calls
(`asyncio.gather` in paced chunks), **retry with exponential backoff**, a `RunSummary` per run,
and **SQLite** persistence. Fake/real LLM is switchable via `Settings.use_fake`.

## Consequences
- Many calls run in parallel (minutes, not hours) and survive transient failures.
- Structured JSON logs become the raw data for the KPI scoreboard from Week 6.
- We deliberately avoid heavier orchestration (job queues / DAGs) — the simple stack is
  genuinely production-shaped for our scale.
