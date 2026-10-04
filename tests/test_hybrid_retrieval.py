from src.pipeline import pipeline
from src.pipeline.pipeline import Chunk, bm25_scores, retrieve, rrf_fuse


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
    monkeypatch.setattr(pipeline, "embed", lambda _text: [1.0, 0.0])

    results = retrieve("Which SRR-12 fields are required?", index, k=1)

    assert results[0]["chunk_id"] == "water.txt#0"
    assert results[0]["bm25_score"] > 0.0

