"""Coverage for configurable chunking, metadata, and retrieval strategies."""

from __future__ import annotations

from src.pipeline import pipeline
from src.pipeline.pipeline import (
    Chunk,
    _chunk_semantically,
    chunk_corpus,
    rerank_with_cross_encoder,
    retrieve,
)
from src.pipeline.settings import ChunkingSettings, MetadataSettings, Settings


def test_structure_aware_pdf_chunks_include_section_metadata() -> None:
    chunks = chunk_corpus(
        "docs/corpus_pdf_styled",
        chunking=ChunkingSettings(strategy="structure_aware"),
        metadata=MetadataSettings(language="en", version="test"),
    )

    assert chunks
    assert any(chunk.metadata["section_path"] for chunk in chunks)
    assert all(chunk.metadata["doc_type"] == "pdf" for chunk in chunks)
    assert all(chunk.metadata["version"] == "test" for chunk in chunks)


def test_semantic_retrieval_does_not_add_bm25_score(monkeypatch) -> None:
    index = [
        Chunk("one", "policy.txt", "SRR-12 contains required fields.", vector=[1.0, 0.0]),
        Chunk("two", "policy.txt", "A general policy statement.", vector=[0.0, 1.0]),
    ]
    monkeypatch.setattr(pipeline, "embed", lambda _text: [1.0, 0.0])

    results = retrieve("SRR-12", index, k=1, strategy="semantic")

    assert results[0]["chunk_id"] == "one"
    assert results[0]["bm25_score"] == 0.0


def test_semantic_chunking_splits_on_similarity_drop(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "embed_batch",
        lambda _: [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
    )

    chunks = _chunk_semantically(
        "Leave requests need approval. Leave balances carry forward. Ports require dredging.",
        max_size=500,
        similarity_threshold=0.55,
    )

    assert chunks == [
        "Leave requests need approval. Leave balances carry forward.",
        "Ports require dredging.",
    ]


def test_cross_encoder_reranking_orders_candidates(monkeypatch) -> None:
    class FakeCrossEncoder:
        def predict(self, pairs):
            return [0.1 if "general" in text else 0.9 for _, text in pairs]

    monkeypatch.setattr(pipeline, "_get_cross_encoder", lambda _: FakeCrossEncoder())
    candidates = [
        {"chunk_id": "one", "text": "general policy text"},
        {"chunk_id": "two", "text": "exact operational policy text"},
    ]

    reranked = rerank_with_cross_encoder(
        "Which operational policy applies?",
        candidates,
        top_k=1,
        model_name="test-cross-encoder",
    )

    assert reranked[0]["chunk_id"] == "two"
    assert reranked[0]["rerank_score"] == 0.9


def test_rag_settings_group_strategies() -> None:
    settings = Settings()

    assert settings.rag.chunking.strategy == "fixed"
    assert settings.rag.retrieval.strategy == "hybrid"
    assert settings.rag.retrieval.rerank_enabled is True
