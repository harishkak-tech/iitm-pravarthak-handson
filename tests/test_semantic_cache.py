import asyncio
import json
import sqlite3
import subprocess
import sys

import pytest

from src.pipeline import pipeline
from src.pipeline.semantic_cache import SemanticCache
from src.pipeline.settings import RagSettings


def test_cache_scope_threshold_expiry_and_eviction(monkeypatch, tmp_path):
    clock = [100.0]
    monkeypatch.setattr("src.pipeline.semantic_cache.time.time", lambda: clock[0])
    cache = SemanticCache(tmp_path / "cache.db")
    cache.store("kb1", "q", [1., 0.], {"content": "answer"}, max_entries=2)
    lookup = lambda scope, vector: cache.lookup(scope, "paraphrase", vector, threshold=.95, ttl=10)
    answer, score = lookup("kb1", [1., .01])
    assert answer == {"content": "answer"} and score > .95
    answer["content"] = "changed"
    assert lookup("kb1", [1., 0.])[0]["content"] == "answer"
    assert lookup("kb2", [1., 0.])[0] is None
    assert lookup("kb1", [0., 1.])[0] is None
    clock[0] += 10
    assert lookup("kb1", [1., 0.])[0] is None
    for i in range(3):
        cache.store(str(i), "q", [1., 0.], {}, max_entries=2)
    assert lookup("0", [1., 0.])[0] is None


def test_pipeline_reuses_answer_and_invalidates_settings_and_corpus(monkeypatch, tmp_path):
    rag = RagSettings()
    rag.semantic_cache.db_path = tmp_path / "cache.db"
    rag.retrieval.query_rewrite_enabled = False
    rag.retrieval.rerank_enabled = False
    rag.retrieval.use_qdrant = False
    chunks = [pipeline.Chunk("a", "a", "Approved.", [1., 0.])]
    calls = []
    monkeypatch.setattr(pipeline, "get_index", lambda *a, **kw: chunks)
    monkeypatch.setattr(pipeline, "embed", lambda *a, **kw: [1., 0.])
    monkeypatch.setattr(pipeline, "_use_fake_rag", lambda: True)
    monkeypatch.setattr(pipeline, "token_accounting", lambda *a: {})
    def retrieve(*args, **kwargs):
        calls.append(args[0])
        return [{"chunk_id": "a", "source": "a", "text": chunks[0].text, "score": 1.}]
    monkeypatch.setattr(pipeline, "retrieve", retrieve)
    async def run():
        first = await pipeline.ask_rag("Is this approved?", rag_settings=rag)
        second = await pipeline.ask_rag("Has this been approved?", rag_settings=rag)
        assert not first.cache_hit and second.cache_hit
        assert second.question == "Has this been approved?"
        assert second.content == first.content and second.evidence == first.evidence
        assert second.cost_usd == second.generation_seconds == 0
        assert len(calls) == 1
        rag.retrieval.metadata_filters = {"language": "en"}
        assert not (await pipeline.ask_rag("Is this approved?", rag_settings=rag)).cache_hit
        chunks[0].text = "Updated policy."
        assert not (await pipeline.ask_rag("Is this approved?", rag_settings=rag)).cache_hit
        rag.semantic_cache.enabled = False
        assert not (await pipeline.ask_rag("Is this approved?", rag_settings=rag)).cache_hit
    asyncio.run(run())


def test_cache_settings_validate():
    with pytest.raises(ValueError):
        RagSettings(semantic_cache={"similarity_threshold": 1.1})


def test_cache_survives_new_process_and_records_hits(tmp_path):
    path = tmp_path / "persistent.db"
    cache = SemanticCache(path)
    cache.store("scope", "Question?", [1., 0.], {"content": "Saved answer"}, max_entries=5)
    script = (
        "import json, sys; from src.pipeline.semantic_cache import SemanticCache; "
        "print(json.dumps(SemanticCache(sys.argv[1]).lookup("
        "'scope', 'Paraphrase?', [1., 0.], threshold=.95, ttl=3600)))"
    )
    result = subprocess.run([sys.executable, "-c", script, str(path)],
                            check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)[0]["content"] == "Saved answer"
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT hit_count, last_hit_ts FROM query_cache").fetchone()[0] == 1
    assert cache.clear() == 1
    assert cache.lookup("scope", "q", [1., 0.], threshold=.95, ttl=3600) == (None, None)


def test_cache_write_failure_does_not_discard_answer(monkeypatch, tmp_path):
    rag = RagSettings()
    rag.semantic_cache.db_path = tmp_path / "cache.db"
    rag.retrieval.query_rewrite_enabled = False
    rag.retrieval.rerank_enabled = False
    rag.retrieval.use_qdrant = False
    monkeypatch.setattr(pipeline, "get_index", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "embed", lambda *a, **kw: [1., 0.])
    monkeypatch.setattr(pipeline, "_use_fake_rag", lambda: True)
    monkeypatch.setattr(pipeline, "token_accounting", lambda *a: {})
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **kw: [
        {"chunk_id": "a", "source": "a", "text": "Approved.", "score": 1.}])
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("locked")
    monkeypatch.setattr(SemanticCache, "store", fail)
    result = asyncio.run(pipeline.ask_rag("Approved?", rag_settings=rag))
    assert result.content == "Approved. [a]" and not result.cache_hit
