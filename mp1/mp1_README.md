# Week 5 Graded Mini Project – Prompt Lab

## Overview

This project compares four LLM prompting strategies
The task is to extract the following fields from job posting snippets:

- `company`
- `role`
- `years_experience_required`

Four prompting strategies are evaluated:

1. Zero-shot
2. Few-shot
3. Structured / Role-based
4. Chain-of-Thought

The same extraction model (`gpt-4o-mini`) and temperature (`0.0`) are used
for all four strategies. This ensures that the prompting strategy is the
main variable being compared.

---

## Files

- `mp1_prompt_lab.ipynb` — End-to-end implementation
- `mp1_comparison.md` — Generated comparison table containing final metrics
- `mp1_writeup.md` — Reflection and recommendations
- `requirements.txt` — Python package dependencies
- `data/job_snippets.jsonl` — Provided input dataset containing 10 job snippets
- `data/golden_set.jsonl` — Golden reference dataset

---

## Setup

### 1. Install dependencies

# pip install -r requirements.txt


### 2.  The notebook performs the following steps:

Loads 10 job posting snippets and the corresponding golden dataset.
Defines four prompting strategies:
Calls gpt-4o-mini with temperature 0.0 for all extraction tasks.
Uses OpenAI function/tool calling to enforce a structured extraction
Validates extraction results using a Pydantic schema.
Scores each extraction against the golden dataset with a deterministic accuracy score from 0 to 3.
Runs an LLM-as-a-Judge evaluation using gpt-4o.
score from 1 to 25
Aggregates results by prompting strategy and calculates , mean accuracy, parse rate, mean LLM judge score,total cost,p50 latency
Generates mp1_comparison.md containing the final comparison table.