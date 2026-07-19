# Knowledge Assistant — Capstone

A 30-week build of a Q&A assistant over a small document corpus (Agentic AI & RAG Engineering).
This repo has **two tracks**. Knowing which track a file belongs to is the whole discipline.

---

## The two tracks

```
<name>-capstone/
│
├── practice_examples/        ← LEARNING TRACK  (throwaway demos, by week)
│   ├── week01/               how does one LLM call work?
│   │   ├── hello_llm.py
│   │   └── system_prompt_demo.py
│   └── week02/               how do Pydantic / async / patterns work?
│       ├── pydantic_demo.py   booking.py
│       ├── napper.py          speed_demo.py
│       ├── gather_demo.py     batch_demo.py
│       ├── retry_demo.py      sqlite_demo.py
│
├── src/                      ← APPLICATION TRACK  (the real system, kept & grown)
│   └── pipeline/
│       ├── __init__.py
│       ├── settings.py         (typed config — Pydantic)
│       ├── logging_config.py   (JSON logger — feeds the KPI scoreboard)
│       ├── fake_llm.py         (offline model for tests/dev)
│       ├── pipeline.py         (async batched pipeline: gather + retry + logging)
│       ├── store.py            (SQLite persistence)
│       └── query_results.py    (query saved runs)
│
├── data/                     ← inputs (questions.csv now → your corpus later)
├── docs/
│   ├── adr/                  ← design decisions, the "why" (0001, 0002, …)
│   └── runs/                 ← saved evidence
├── requirements.txt
├── .gitignore               ← keeps .env and generated files out of git
└── README.md
```

**`practice_examples/`** = how a concept *works*. Messy is fine. You would never ship it.
**`src/`** = the real application. Written to a keep-it standard. This is the product.

---

## The one rule (where does a file go?)

> **"Would this file be part of the final product?"**
> **No →** `practice_examples/weekNN/`  ·  **Yes →** `src/`

---

## The weekly workflow (every week, same ritual)

1. **Pull** — start from the latest: `git pull`
2. **Make this week's practice folder** — `mkdir -p practice_examples/weekNN`
3. **Learn (hands-on first)** — write/run small demos in `practice_examples/weekNN/`.
   *Question: how does this work?*
4. **Apply** — take what you learned and add/change real code in `src/`.
   *Question: now build the real thing with it.*
5. **Document** — add an ADR in `docs/adr/` when you make a real design choice.
6. **Commit & push** — save the whole repo (both tracks) to GitHub.

Both tracks travel together, so your repo becomes a clean story of *what you learned* and
*what you built* — exactly what a teammate or an employer wants to see.

---

## How to run things

```bash
# A practice demo (learning track) — run from the repo root:
python practice_examples/week02/napper.py
python practice_examples/week02/pydantic_demo.py bad

# The application (fake mode — no API key needed):
python -m src.pipeline.pipeline

# The application against the REAL API: set use_fake=False (see src/pipeline/settings.py)
# and put your key in a .env file:  OPENAI_API_KEY=sk-...
```

## Setup (once)

```bash
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt                        # add --break-system-packages on Vocareum
echo "OPENAI_API_KEY=sk-your-key" > .env               # never commit this file
```
