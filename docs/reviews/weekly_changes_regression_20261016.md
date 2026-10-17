# Weekly changes: pass-rate regression investigation

Compared completed SQLite runs 15 (before weekly changes) and 16 (after).
Both used k=8, hybrid retrieval, query rewriting, no reranking, and a 5000-character
context budget. This comparison predates the user's subsequent k=5 change.

| Measure | Run 15 | Run 16 |
|---|---:|---:|
| Retrieval hits, answerable | 95/98 (96.94%) | 95/98 (96.94%) |
| Passes | 114/126 (90.48%) | 106/126 (84.13%) |

No per-question retrieval-hit flags changed. No selected chunks were discarded
by the new context-budget selection in run 16. Thus these saved runs establish
a pass-rate regression, not a retrieval-hit regression. No completed k=5 run
after the update was available in the database at investigation time.

Ten previously passing questions failed, and two previously failing questions
passed. Five answers were replaced with abstentions by citation-ID validation;
four of these had passed in run 15. The rejected raw responses cited visible
GOV source labels or grouped actual chunk IDs with semicolons. The exact-ID
validator rejected these formatting conventions even though the referenced
labels/IDs existed in supplied evidence. This explains avoidable abstentions;
it does not establish that all those raw responses were semantically correct.

Other failures include omitted details and genuine generation errors. In
addition, the update changed the judge rubric and narrowed its context to cited
chunks. These changes confound a direct comparison with the historical pass
rate; this was not a controlled A/B experiment and does not isolate prompt/model
variation from evaluator changes.

## Corrections

- Normalize visible GOV labels to actual supplied chunk IDs before validating.
  Labels spanning multiple visible chunks cite every matching chunk; no single
  chunk is guessed. Normalize grouped IDs only if every reference is known.
  Unknown IDs remain rejected, and raw model text is retained separately.
- Add `rag.normalize_answer_citations` (default true) to control this behavior.
- Default `evaluation.citation_grounding_enabled` to false, so the stricter
  per-sentence citation rubric/context restriction is opt-in. The original
  accuracy/groundedness/format judge remains active and uses generation evidence.
- Preserve k=5 as requested. No changes to stored embeddings or remote data.

Offline replay of all five saved citation-rejected responses now passes citation
reference validation. This is not a new semantic judge result or an estimated
pass rate. A fresh live evaluation is needed to measure end-to-end quality.
For a controlled comparison with run 15, explicitly use k=8, the same corpus and
generation settings, and the baseline judge; compare k=5 separately.

No re-ingestion is required for these corrections. Historical rows and metrics
are retained unchanged.
