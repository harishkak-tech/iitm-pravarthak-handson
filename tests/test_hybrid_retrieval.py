from src.pipeline import pipeline
from src.pipeline.pipeline import Chunk, bm25_scores, retrieve, rrf_fuse


def test_qdrant_connection_error_preserves_cause_without_demanding_ingestion():
    from unittest.mock import patch

    failure = ConnectionError("[WinError 10054] connection forcibly closed")
    index = [Chunk("one", "policy.txt", "A policy passage.", vector=[1.0, 0.0])]
    with patch.object(pipeline, "retrieve_from_qdrant", side_effect=failure):
        try:
            pipeline._retrieve_with_qdrant_hybrid(
                "What is the policy?", index, k=1, rrf_k=20,
                collection_name="existing_collection", rag_settings=pipeline.Settings().rag,
            )
        except RuntimeError as exc:
            assert "existing_collection" in str(exc)
            assert "WinError 10054" in str(exc)
            assert "Re-ingest only if" in str(exc)
            assert "Run `python scripts/ingest_qdrant.py`" not in str(exc)
            assert exc.__cause__ is failure
        else:
            raise AssertionError("The connection failure was silently ignored")


def test_rrf_fusion_scores_by_rank_across_retrievers() -> None:
    scores = rrf_fuse(
        [["doc_A", "doc_B", "doc_C"], ["doc_C", "doc_A", "doc_D"]],
        rrf_k=60,
    )

    assert scores["doc_A"] == (1 / 61) + (1 / 62)
    assert scores["doc_A"] > scores["doc_B"]


def test_bm25_scores_exact_operational_identifier() -> None:
    index = [
        Chunk(
            chunk_id="water.txt#0",
            source="water.txt",
            text="The SRR-12 record lists a source failure, fallback supply, and restoration date.",
        ),
        Chunk(
            chunk_id="water.txt#1",
            source="water.txt",
            text="A household connection requires regular verification of service quality.",
        ),
    ]

    scores = bm25_scores("Which SRR-12 fields are required?", index)

    assert scores[0] > scores[1]


def test_hybrid_retrieval_uses_bm25_when_semantic_scores_tie(monkeypatch) -> None:
    index = [
        Chunk(
            chunk_id="water.txt#0",
            source="water.txt",
            text="The SRR-12 record lists a source failure, fallback supply, and restoration date.",
            vector=[1.0, 0.0],
        ),
        Chunk(
            chunk_id="water.txt#1",
            source="water.txt",
            text="A household connection requires regular verification of service quality.",
            vector=[1.0, 0.0],
        ),
    ]
    monkeypatch.setattr(pipeline, "embed", lambda _text, **_: [1.0, 0.0])

    results = retrieve("Which SRR-12 fields are required?", index, k=1, strategy="hybrid")

    assert results[0]["chunk_id"] == "water.txt#0"
    assert results[0]["bm25_score"] > 0.0


def test_retrieval_applies_metadata_filters_before_ranking(monkeypatch) -> None:
    index = [
        Chunk(
            chunk_id="old.txt#0",
            source="old.txt",
            text="The SRR-12 record lists a source failure.",
            vector=[1.0, 0.0],
            metadata={"doc_type": "pdf", "version": "old", "page": 1},
        ),
        Chunk(
            chunk_id="latest.txt#0",
            source="latest.txt",
            text="A household connection requires regular verification.",
            vector=[1.0, 0.0],
            metadata={"doc_type": "pdf", "version": "latest", "page": 3},
        ),
    ]
    monkeypatch.setattr(pipeline, "embed", lambda _text, **_: [1.0, 0.0])

    results = retrieve(
        "Which SRR-12 fields are required?",
        index,
        k=1,
        metadata_filters={"version": "latest", "page": {"gte": 2}},
    )

    assert [hit["chunk_id"] for hit in results] == ["latest.txt#0"]

