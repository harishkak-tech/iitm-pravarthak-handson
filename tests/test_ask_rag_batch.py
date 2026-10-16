import asyncio
from unittest.mock import AsyncMock

import pytest

from src.pipeline import pipeline


def test_single_question_keeps_single_result_and_forwards_options(monkeypatch):
    answer = pipeline.RagAnswer(question="question", content="answer")
    single = AsyncMock(return_value=answer)
    monkeypatch.setattr(pipeline, "_ask_rag_single", single)
    result = asyncio.run(pipeline.ask_rag("question", top_k=3, use_qdrant=False))
    assert result is answer
    assert result.rag_seconds >= 0
    single.assert_awaited_once_with(
        "question", corpus_dir=None, top_k=3, model=None,
        rag_settings=None, use_qdrant=False,
    )


def test_empty_batch_returns_empty_list(monkeypatch):
    single = AsyncMock()
    monkeypatch.setattr(pipeline, "_ask_rag_single", single)
    assert asyncio.run(pipeline.ask_rag([])) == []
    single.assert_not_awaited()


@pytest.mark.parametrize("question,concurrency,error", [
    (["valid", " "], 5, ValueError),
    (["valid", 1], 5, TypeError),
    (None, 5, TypeError),
    ("question", 0, ValueError),
    (["question"], 21, ValueError),
    (["question"], True, ValueError),
])
def test_invalid_input_does_not_start_pipeline(monkeypatch, question, concurrency, error):
    single = AsyncMock()
    monkeypatch.setattr(pipeline, "_ask_rag_single", single)
    with pytest.raises(error):
        asyncio.run(pipeline.ask_rag(question, concurrency=concurrency))
    single.assert_not_awaited()


def test_batch_propagates_pipeline_failure(monkeypatch):
    single = AsyncMock(side_effect=RuntimeError("retrieval failed"))
    monkeypatch.setattr(pipeline, "_ask_rag_single", single)
    with pytest.raises(RuntimeError, match="retrieval failed"):
        asyncio.run(pipeline.ask_rag(["question"]))
