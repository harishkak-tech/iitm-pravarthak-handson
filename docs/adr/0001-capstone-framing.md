# ADR 0001 — Capstone Framing: Knowledge Assistant

- **Status:** Accepted
- **Date:** Week 1
- **Deciders:** <your name>

## Context
We are building a Q&A assistant over a small document corpus. The knowledge lives in
documents that can change, answers must be trustworthy, and we must be able to show where
each answer came from. We are building it one piece at a time over 30 weeks.

## Decision
We will build a **Retrieval-Augmented Generation (RAG)** system, framed by the Solution
Framing Canvas:

| Field | Choice (v1) |
|-------|-------------|
| Inputs | Document corpus + user questions |
| Tools | Retrieval + a single LLM call |
| Memory | None in v1 (added later) |
| Outputs | A grounded answer with citations |
| Autonomy | Suggest only — no destructive actions |
| Decision boundaries | Answer only from the provided documents |
| Success metrics | Grounded response · hallucination rate · task success |

## Consequences
- Fresh, private, *citable* answers without retraining a model.
- v1 is deliberately small and safe: suggest-only, answers only from our documents.
- We are *not* fine-tuning (facts change) and *not* using long-context at scale (cost).
