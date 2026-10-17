# Versioned evidence and evaluation (Weeks 10–12)

## Behavior

No answer, semantic, or embedding cache is introduced. The existing process-local
index cache now includes a hash of input PDF bytes, so a document edit rebuilds
the local index rather than serving old chunks.

Qdrant ingestion publishes content-addressed snapshots in the existing collection.
It creates payload indexes, uploads all chunks with version-specific point IDs,
marks the snapshot ready, then tombstones previous live snapshots. It never
recreates or deletes the collection. Removing a PDF and ingesting again retires
its chunks too. Repeating an already published snapshot skips uploads.
Serialize ingestion per collection. This is a single-writer protocol, not a
transaction across collections or simultaneous writers. A failed upload leaves
the previous published snapshot live. Queries use the local corpus's version;
changed local files require ingestion before that version can be queried remotely.
Readers already using an older version may need to retry after publication.
Historical payloads remain available for audit using a `kb_version` filter
without the default live filter. No automatic history purging is performed.

**Migration:** run `python scripts/ingest_qdrant.py` once after this upgrade.
Legacy chunks have no snapshot version/readiness fields and are retired after
successful publication. No remote ingestion is performed by the code change.

Evidence is selected as complete chunks within the character budget and optional
`retrieval.max_context_tokens` (cl100k_base content tokens). Over-budget chunks
are skipped; an empty context abstains without a generation call. Optional
`retrieval.rerank_score_threshold` requires `rerank_enabled=True` and applies to
finite raw cross-encoder logits, never dense cosine or RRF scores. It defaults
to `None` until calibrated on the policy golden set.

Generated bracket references must match exact IDs of evidence actually supplied
to the model. Unknown, missing, malformed, or combined IDs reject the answer and
return `I don't know.` Sources list only cited IDs. The full raw answer, citation
validation, candidate chunks, evidence, discarded IDs, KB version, and content
token counts are available in the internal result. The API exposes evidence and
validation in `/ask_rag`; the dashboard displays them. Reference validity does
not establish claim entailment or sentence-level citation completeness; those
remain semantic judge checks. The judge sees cited generation evidence rather
than chunks omitted from the prompt, and its rubric explicitly checks each
claim's cited support and sentence-level citation coverage.

## Evaluation

Use the existing golden set and actual generated answers, never the notebooks'
synthetic rows. Evidence and per-row evaluation results are persisted in the
existing JSON payloads/SQLite history without replacing older records.

```
python scripts/run_golden_set.py --metrics offline-proxy
pip install -r requirements-eval.txt
python scripts/run_golden_set.py --metrics live
python scripts/run_golden_set.py --metrics live --thresholds docs/eval/thresholds.json
```

The optional live integration pins RAGAS 0.2.15 and reports faithfulness, answer
relevance, context precision, and context recall. Live failures raise rather than
becoming proxy scores. Offline metrics are explicitly labeled `offline-proxy`:
token overlap checks wiring, not answer quality. Unanswerable and abstained rows
are excluded from these metrics; correct/false abstention rates are separate.
Metric mode defaults to `off` to avoid adding paid judge calls automatically.

KPIs include task success, citation-ID validity, correct/false abstention,
judge-grounded response rate, p50/p95 latency, and mean generation cost. Empty
denominators are null. Latency uses each answer's observed RAG wall time when
available; older/custom rows fall back to the allocated share of evaluation
batch wall time, labeled explicitly. Judge/evaluation cost is excluded from
generation cost. No unsupported tool-success KPI is invented.

Optional threshold JSON maps KPI or RAG metric names to `{ "min": 0.8 }` or
`{ "max": 2.0 }`. Threshold failures exit nonzero **after** saving artifacts and
database history. Set thresholds from a measured live baseline; none are invented
for the current corpus. The dashboard displays the saved metrics and KPIs.

References: [Qdrant filtering](https://qdrant.tech/documentation/search/filtering/),
[RAGAS metrics](https://docs.ragas.io/en/v0.2.1/references/metrics/).
