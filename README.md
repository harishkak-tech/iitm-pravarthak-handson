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

# The Streamlit UI:
streamlit run api/main.py --server.port 8501

# Run the local golden-set evaluation:
python scripts/run_golden_set.py

# The live gpt-4o judge runs by default. To use the local fake judge instead:
# set JUDGE_USE_FAKE=1

# The application against the REAL API: set use_fake=False (see src/pipeline/settings.py)
# and put your key in a .env file:  OPENAI_API_KEY=sk-...
```

The current golden set is `docs/goldenset/golden_set.jsonl`: 126 questions covering
all 14 corpus documents, with source evidence for answerable entries. See
[the golden-set notes](docs/goldenset/README.md) for coverage and snapshot details.
Validate it locally with `python scripts/validate_golden_set.py`.

Completed golden evaluations also append to `results.db`. The `golden_runs`
table stores the generation model, full settings snapshot, judge configuration,
input paths, UTC timestamps, and summary. The `golden_results` table stores each
question's answer, scores, and complete evaluation row, linked by `run_id`.
Existing JSON outputs are still written. Use
`python scripts/run_golden_set.py --db-path docs/runs/golden_runs.db`
to choose a different database. Historical JSON files are not automatically
imported because their original settings are not recorded.

To browse saved results locally, run:

```powershell
python -m streamlit run api/results_viewer.py --server.port 8502
```

Open `http://localhost:8502`. The read-only viewer shows golden-run settings,
model and score history, searchable failed answers and judge reasoning, plus
older batch runs. Use **Refresh results** after a golden run finishes. It does
not need an OpenAI API key or Qdrant connection.

## Batch RAG API

To ask questions in the results UI, start these in two terminals from the project
directory:

```powershell
python -m uvicorn api.main:app --reload --port 8000
```

```powershell
python -m streamlit run api/results_viewer.py --server.port 8502
```

Open `http://localhost:8502` and choose the **Ask questions** tab. Enter a
question and select **Ask** to see the answer, source chunk IDs, and generation
cost, plus expandable retrieved chunk text. The UI calls `/ask_rag` with
`{"question": "..."}` and uses the current RAG
settings. The Q&A view works independently of the results database. Set the API
base URL in the sidebar if the API runs elsewhere.

Golden summaries include run totals: `total_retrieval_seconds` (index loading,
retrieval and reranking), `total_generation_seconds` (prompt preparation and LLM
answering), and `total_judge_seconds`. Each total measures elapsed time with at
least one call in that stage; overlapping calls within a stage count once.
Stages can overlap with each other, so these totals need not sum to run wall time.
Totals appear in console output, the results history, summary JSON and database,
and a `golden_run_metrics` record in `logs/pipeline.log`. Older results have no totals.

Python callers can also pass a list directly to `ask_rag`:

```python
answers = await ask_rag(["Who is eligible for PM-KISAN?", "What support is available?"], concurrency=5)
for answer in answers:
    print(answer.question, answer.content)
```

A string still returns one `RagAnswer`; a list returns an ordered list of answers.
An empty list returns `[]`. Shared retrieval options apply to every question.
The golden-set runner calls `ask_rag` with ten questions at a time and concurrency
of ten. The final batch may be smaller. Judges run concurrently for each batch,
with results and logs saved in input order. The next batch starts after judging
finishes. Per-row elapsed time is the RAG batch wall time divided by its question
count; this excludes judge time.

Start the API with `uvicorn api.main:app --reload --port 8000`.
Send `POST /ask_batched` with this JSON body:

```json
{
  "questions": ["Who is eligible for PM-KISAN?", "What support is available?"],
  "concurrency": 5
}
```

The response is `{"answers": [...]}` in the same order as the input. Each item
contains `question`, `content`, `sources`, `cost_usd`, and `retries`. Each question
runs through RAG independently; the full response arrives after all answers finish.
Accepts 1–100 nonblank questions, with concurrency from 1–20 (default 5).
If a pipeline call fails, the request fails; partial answers are not returned.
This replaces the old single-question `/ask_batched` format. `/ask` still accepts
`{"question": "..."}` for a single streamed answer.

## Setup (once)

```bash
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt                        # add --break-system-packages on Vocareum
echo "OPENAI_API_KEY=sk-your-key" > .env               # never commit this file
```
