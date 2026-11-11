# Semantic answer cache

Supersedes the no-answer-cache decision in ADR 0003. The shared `ask_rag`
pipeline now checks a persistent SQLite semantic cache after resolving the current
index snapshot and before query rewriting, HyDE, retrieval, reranking or generation.
The lookup uses the configured sentence-transformer embedding and cosine similarity.

`rag.semantic_cache` settings (persisted through the existing settings store):

- `enabled`: true; set false for cold-cache evaluations or to bypass reuse.
- `db_path`: `data/semantic_cache.db`; keep the same file across runs to reuse answers.
- `similarity_threshold`: 0.95; higher values make reuse more conservative.
- `ttl_seconds`: 3600.
- `max_entries`: 500 per database, oldest entries evicted first.

Entries are isolated by KB content version, all RAG settings (including metadata
filters and prompts), effective request overrides, corpus path and fake/live mode.
Only non-abstaining answers with valid citations are stored. Returned answers are
deep copies with the current question, original supporting evidence, `cache_hit`
and `cache_similarity`. Hits have zero new LLM cost and zero generation/retrieval
stage durations; total request time still includes snapshot checking and lookup.
Embedding/cache lookup failures log a warning and continue through normal RAG.
Cache write failures return the generated answer without failing the request.

Following `wk10_pipeline.py`, the `query_cache` table stores the question,
embedding, answer, creation time, hit count and last-hit time. Embeddings and the
full structured answer (including evidence) are serialized as JSON. Connections
are opened per operation so threads and processes can share the database safely;
SQLite transactions serialize writes. Unlike the teaching notebook, application
startup does not delete the database. `SemanticCache(db_path).clear()` explicitly
clears it. Version/settings scopes prevent reuse after a corpus or settings change
without deleting other valid scopes. Expired entries are removed during lookup.

Separate golden-set runs reuse entries when they use the same database, corpus,
settings and fake/live mode, within the TTL. Golden result JSONL rows include
`cache_hit` and `cache_similarity`. The evaluation judge still runs on cached
answers; answer reuse skips RAG generation, not evaluation.

This cache survives process restarts and is shared by workers using the same file.
Simultaneous misses may each generate an answer.
Cosine similarity is an approximation: tune the threshold against domain-specific
paraphrases and near-miss questions before lowering it. Index resolution still runs
on hits so corpus updates invalidate answers even before the TTL expires.
