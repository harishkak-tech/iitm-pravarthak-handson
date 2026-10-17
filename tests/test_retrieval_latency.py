"""Latency optimizations must preserve filtering, diagnostics and rewrite fusion."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pipeline import pipeline
from src.pipeline.settings import RagSettings


@pytest.mark.parametrize("has_hits,snapshot_count", [(True, 1), (False, 1), (False, 0)])
def test_snapshot_check_only_needed_for_empty_search(monkeypatch, has_hits, snapshot_count):
    hit = SimpleNamespace(payload={"chunk_id": "a", "source": "policy", "text": "answer"}, score=0.9)
    client = Mock()
    client.query_points.return_value.points = [hit] if has_hits else []
    client.count.return_value.count = snapshot_count
    monkeypatch.setattr(pipeline, "get_qdrant_client", lambda _: client)
    monkeypatch.setattr(pipeline, "embed", lambda *args, **kwargs: [1.0, 0.0])
    kwargs = dict(rag_settings=RagSettings(), metadata_filters={"kb_version": "v1", "language": "en"})
    if not has_hits and not snapshot_count:
        with pytest.raises(RuntimeError, match="snapshot is not published"):
            pipeline.retrieve_from_qdrant("question", **kwargs)
    else:
        hits = pipeline.retrieve_from_qdrant("question", **kwargs)
        assert len(hits) == int(has_hits)
    query_filter = str(client.query_points.call_args.kwargs["query_filter"])
    assert "v1" in query_filter and "en" in query_filter and "deleted_at" in query_filter
    assert client.count.call_count == int(not has_hits)
    client.close.assert_not_called()


def test_original_search_overlaps_rewrite_and_preserves_fusion(monkeypatch):
    started = threading.Event()
    released = threading.Event()
    calls = []

    def search(query, *args, **kwargs):
        calls.append(query)
        if query == "original":
            started.set()
            assert released.wait(timeout=5), "Original search did not overlap rewriting"
        return [{"chunk_id": "shared", "text": "answer"}, {"chunk_id": query, "text": query}]

    async def rewrite(*args, **kwargs):
        try:
            assert await asyncio.to_thread(started.wait, 5)
            return ["rewrite one", "rewrite two"], 0.01
        finally:
            released.set()

    monkeypatch.setattr(pipeline, "retrieve", search)
    monkeypatch.setattr(pipeline, "_generate_query_rewrites", rewrite)
    hits, rewrites, cost = asyncio.run(pipeline._retrieve_with_query_rewriting(
        "original", [], k=4, use_qdrant=True, strategy="hybrid", rrf_k=20,
        collection_name="policies", rag_settings=RagSettings(), metadata_filters={},
    ))
    assert calls == ["original", "rewrite one", "rewrite two"]
    assert [hit["chunk_id"] for hit in hits] == ["shared", *calls]
    assert hits[0]["matched_query"] == "original"
    assert hits[0]["score"] == pytest.approx(3 / 21)
    assert rewrites == ["rewrite one", "rewrite two"] and cost == 0.01
