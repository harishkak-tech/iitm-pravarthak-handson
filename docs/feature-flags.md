# RAG feature switches and re-ingestion

Edit defaults in `src/pipeline/settings.py` and restart the API/evaluation process.
Python callers can also pass a configured `Settings().rag` to `ask_rag`.
These are typed Python settings, not automatically loaded environment variables.
No answer, semantic, or embedding caching has been added.

Paths below start at `Settings()`. The defaults preserve the Week 10–12 behavior.

| Implementation | Setting / disable value | Default | Re-ingestion needed? |
|---|---|---|---|
| Versioned snapshots, history retention, tombstones, readiness filtering and payload indexes | `rag.qdrant.versioned_ingestion_enabled = False` | `True` | Yes for the initial upgrade or a mode whose collection has not been populated |
| Detect changed PDF contents before reusing the existing local index | `rag.corpus_change_detection_enabled = False` | `True` | No for the flag; actual PDF changes require re-ingestion |
| Complete-chunk context selection within character/token budgets | `rag.retrieval.context_budget_enabled = False` | `True` | No |
| Context limits | `rag.retrieval.max_context_chars`; `max_context_tokens = None` disables the optional token limit | `5000`; `None` | No |
| Raw cross-encoder score filtering | `rag.retrieval.rerank_score_threshold = None` | `None` (off) | No; a numeric threshold requires `rerank_enabled = True` |
| Metadata query filters | `rag.retrieval.metadata_filters = {}` | `{}` (off) | No for existing indexed fields; new payload fields require ingestion/index creation |
| Additional per-sentence citation/evidence instructions | `rag.citation_prompt_enabled = False` | `True` | No |
| Reject answers with missing/invalid/malformed citation IDs | `rag.validate_answer_citations = False` | `True` | No |
| Normalize visible source labels and grouped citations to actual evidence IDs | `rag.normalize_answer_citations = False` | `True` | No |
| Skip generation and abstain when selected evidence is empty | `rag.empty_evidence_abstention_enabled = False` | `True` | No |
| Debug trace: raw model response, discarded IDs, prompt-token breakdown | `rag.trace_enabled = False` | `True` | No |
| Four RAGAS metrics: faithfulness, answer relevance, context precision, context recall | `evaluation.metrics_mode = "off"` | `"off"` | No; enable with `"live"` or `"offline-proxy"` |
| Task, citation, abstention, groundedness, hallucination, latency and cost KPIs | `evaluation.kpis_enabled = False` | `True` | No |
| Evaluate optional min/max quality thresholds and fail the run when breached | `evaluation.thresholds_enabled = False` | `True`; inactive without `--thresholds FILE` | No |
| Semantic judge checks cited evidence and sentence citation coverage | `evaluation.citation_grounding_enabled = True` enables the stricter rubric | `False` | No |

`citation_prompt_enabled` controls the additional strict prompt; the normal
`generation.system_prompt` remains independently configurable. Citation validity
is still calculated for source attribution when enforcement is off. Disabling
the empty-evidence gate allows a generation call, but enabled citation enforcement
can still reject its answer. Core evidence, KB version, and validation provenance
remain available with debug tracing off, so evaluation can use the real context.
The semantic citation judge shares the existing judge call; it is not a separate
generation-time gate. Offline/proxy judges do not establish semantic entailment.
The stricter judge is opt-in to keep historical pass-rate comparisons meaningful.
Normalization expands a visible `GOV-...` label into every supplied chunk carrying
that label; comma/semicolon groups expand only when all references are known.
Unseen labels remain invalid. The original model text remains in the debug trace.

The lifecycle switch also selects the collection: disabled mode uses an
`_unversioned` suffix, bypasses snapshot filters, and replaces that isolated
collection on ingestion. It never overwrites the versioned history collection.
Re-enable lifecycle mode to select the versioned collection again; if it already
contains the current snapshot, no additional ingestion is necessary. Explicit
custom collection names must follow this suffix convention. Unversioned mode
does not retain old chunks or protect readers from interrupted replacement.

The RAGAS CLI `--metrics off|offline-proxy|live` overrides the settings default.
Live metrics require `pip install -r requirements-eval.txt`. Threshold files must
refer to enabled metrics; values and thresholds should be calibrated on this
corpus. Dashboard panels appear automatically when the saved run contains metrics
or KPIs. Turning evaluation off does not remove historical saved results.

## What requires re-ingestion

Run from the application directory:

```powershell
python scripts/ingest_qdrant.py
```

Run it once for the versioned-lifecycle upgrade and whenever PDFs are added,
edited, or removed. Also ingest after changing chunking strategy/parameters,
embedding model, metadata attached during ingestion, source-ID conventions,
corpus location/glob, or collection selection. Already populated matching
collections can be reused. Switching local retrieval to Qdrant requires a matching
remote index; local-only retrieval does not need Qdrant ingestion.

Citation controls, reranking and its threshold/model, top-k/RRF parameters, query
rewriting/HyDE, generation model/prompt, context limits, tracing, and evaluation
settings do not change stored embeddings and do not require re-ingestion.

Existing Week 9 toggles remain `rag.retrieval.rerank_enabled`,
`query_rewrite_enabled`, `hypothetical_retrieval_enabled`, `use_qdrant`, and
`strategy` (`semantic`/`hybrid`). These are independent of the new feature flags.
