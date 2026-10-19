# Knowledge Assistant — Capstone

Weeks 10–12 now add versioned KB ingestion, citation-ID validation, optional
reranker score filtering, and evaluation KPIs. See
[the implementation and migration notes](docs/adr/0003-versioned-evidence-and-evaluation.md).
Run `python scripts/ingest_qdrant.py` once to publish the new snapshot payloads.
No answer or embedding caching is added.
All new features have configurable switches; see the
[feature flags and re-ingestion table](docs/feature-flags.md).

Use `python scripts/run_golden_set.py --metrics offline-proxy` for explicitly
labeled wiring checks, or install `requirements-eval.txt` and use `--metrics live`
for the four RAGAS metrics. Evaluation evidence and KPIs appear in the results UI.

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

# React UI (Node.js 22.12+; start the API in a separate terminal):
python -m uvicorn api.main:app --reload --port 8000
# In the other terminal:
cd frontend
npm install
npm run dev
# Open http://localhost:5173

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

To browse saved results locally, start the FastAPI backend and React frontend
using the commands above. The React frontend replaces Streamlit as the default UI.
For production, build once and start FastAPI from the project directory:

```powershell
cd frontend
npm install
npm run build
cd ..
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` (production) or `http://localhost:5173` (development).
The public page contains the application name,
question form and answer. Use **Admin login** in the top-right corner to sign in
as `admin` with the configured password. The admin dashboard contains golden-run
settings, score history, failed answers, judge reasoning and answer diagnostics.
Use **Refresh results** after a golden run finishes. Browsing saved evaluations
does not need an OpenAI API key or Qdrant connection.

In **Settings and runs**, the editor shows the configuration saved in the
`app_settings` table. Change values and select **Save settings**, or **Save and
run golden set** to save and launch a background evaluation. Controls include
retrieval k, reranking, query rewriting, answer generation, Qdrant provider and
timeouts, corpus/chunking/embedding options, judge model, question limit and
concurrency. Invalid settings are rejected; stale edits from another session
cannot overwrite newer saved values.

The API reads saved settings for each new question; ingestion and the CLI golden
runner read them too. Code defaults only initialize the database once. Credentials
remain in environment variables or `.env`, not in the settings table.
`APP_SETTINGS_DB` overrides the configuration database; otherwise it follows
`APP_RESULTS_DB`, or defaults to the project's `results.db`.

Each background job keeps an immutable configuration snapshot and revision in
`admin_golden_jobs`. The admin UI polls progress every five seconds and displays
completion/failure details. Jobs continue when the browser disconnects; only one
UI evaluation can be active at a time. A stopped worker is marked failed after
five minutes without a heartbeat. Completed evaluations appear in **Golden
evaluations** with their original settings and question results. Per-job logs
and JSON exports are written under `docs/runs/admin_jobs/<job-id>/`.
Runs use the dashboard's Python environment, so install the project dependencies
there. Changing indexing settings requires ingesting the matching corpus before
evaluating; saving settings does not trigger ingestion automatically.

The single admin account is stored in `results.db` as a salted PBKDF2 password
hash. There is no registration, password reset or forgot-password page. On a new
deployment, provision it once with `python scripts/create_admin.py`; the password
prompt does not echo, and an existing account is never overwritten. Back up the
database to preserve both the account and evaluation history. `APP_AUTH_DB` can
select a different authentication database; `APP_RESULTS_DB` selects the initial
database used for evaluation history. Both default to the project's `results.db`.
The React UI does not expose arbitrary server database paths to the browser.

Admin requests use an eight-hour bearer session held in browser memory. Reloading
the page requires signing in again; signing out revokes the session. Sessions are
kept in the API process, so run a single Uvicorn worker. Restarting it invalidates
all sessions. Use HTTPS when deploying beyond localhost.

The old Streamlit entrypoints remain available for migration and their existing
tests. They are not needed to run React. `streamlit` remains in the Python
requirements only for these legacy screens.

## Batch RAG API

To ask questions in the results UI, start these in two terminals from the project
directory:

```powershell
python -m uvicorn api.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Enter a question and select **Ask assistant** to see the
answer. Retrieval details, generation costs and evaluation results are available
only in the authenticated admin view. The UI calls `/api/ask_rag` with
`{"question": "..."}` and uses the current RAG
settings from the configuration database. The public page requires no login. Set the API
base URL through the `RAG_API_BASE_URL` environment variable in the Vite terminal
if the API runs elsewhere. Vite proxies `/api` requests to the backend, which
defaults to `http://127.0.0.1:8000`. For example, in PowerShell:
`$env:RAG_API_BASE_URL = "http://127.0.0.1:9000"` before `npm run dev`.
The production build is served directly by FastAPI with same-origin API requests;
no CORS configuration is required. Existing `/ask_rag`, `/ask_batched`, `/ask` and
`/health` routes remain available for scripts and existing clients.

Frontend checks: `cd frontend`, then `npm test` and `npm run build`.
Backend HTTP checks: `python -m pytest tests/test_web_admin.py tests/test_api.py tests/test_api_batch.py`.

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

Choose the Qdrant server from **Admin → Settings and runs → Qdrant connection**:
set `provider` to `"oci"` (current default) or `"remote"`, then save settings.
OCI reads `OCI_QDRANT_URL` and optional `OCI_QDRANT_API_KEY` from the environment
or `.env`; the local SSH tunnel uses `http://127.0.0.1:6335` and must stay open.
Remote reads the existing `QDRANT_URL` and `QDRANT_API_KEY` instead.
Clients and HTTP connections are reused within each app process, including for
the localhost SSH tunnel. They close at API shutdown or normal process exit.
`QdrantSettings.timeout_seconds` defaults to 30 seconds per request;
`read_retries` defaults to 1 additional attempt for transient read timeouts or
network failures. A failed read can therefore take roughly 60 seconds before
surfacing an error. Ingestion writes are not automatically retried.
The selection applies to both ingestion and retrieval. Each server needs its own
corpus ingestion; changing providers does not copy collections.

```bash
python -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt                        # add --break-system-packages on Vocareum
echo "OPENAI_API_KEY=sk-your-key" > .env               # never commit this file
```
