import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api import main


def test_single_question_returns_chunk_text(monkeypatch):
    chunks = [{"chunk_id": "policy.txt#0", "source": "policy.txt", "text": "Policy evidence", "score": 0.5}]
    ask = AsyncMock(return_value=SimpleNamespace(
        content="Policy answer", sources=["policy.txt#0"], cost_usd=0.01,
        retries=0, retrieved=chunks,
    ))
    monkeypatch.setattr(main, "_ask_rag", ask)
    response = TestClient(main.app).post("/ask_rag", json={"question": "Who is eligible?"})
    assert response.status_code == 200
    assert response.json()["retrieved"] == chunks
    ask.assert_awaited_once_with("Who is eligible?")


def test_batch_preserves_order_and_limits_concurrency(monkeypatch):
    active = 0
    peak = 0

    async def fake_ask(question, **_options):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02 if question == "first" else 0)
        active -= 1
        return SimpleNamespace(
            content=f"Answer: {question}", sources=["policy.txt"], cost_usd=0.01, retries=0,
            retrieval_seconds=0.0, rerank_seconds=0.0, generation_seconds=0.0,
            retrieved=[{"chunk_id": "policy.txt#0", "source": "policy.txt", "text": "Policy evidence", "score": 0.5}],
        )

    from src.pipeline import pipeline

    monkeypatch.setattr(pipeline, "_ask_rag_single", fake_ask)
    response = TestClient(main.app).post(
        "/ask_batched", json={"questions": ["first", "second", "first"], "concurrency": 2}
    )
    assert response.status_code == 200
    answers = response.json()["answers"]
    assert [answer["question"] for answer in answers] == ["first", "second", "first"]
    assert [answer["content"] for answer in answers] == [
        "Answer: first", "Answer: second", "Answer: first"
    ]
    assert answers[0]["sources"] == ["policy.txt"]
    assert answers[0]["cost_usd"] == 0.01
    assert answers[0]["retries"] == 0
    assert all("retrieved" not in answer for answer in answers)
    assert peak == 2


@pytest.mark.parametrize("payload", [
    {"questions": []},
    {"questions": [" "]},
    {"questions": ["valid", ""]},
    {"questions": ["question"] * 101},
    {"questions": ["question"], "concurrency": 0},
    {"questions": ["question"], "concurrency": 21},
    {"question": "old single-question format"},
])
def test_batch_rejects_invalid_requests(payload, monkeypatch):
    async def unexpected_call(_):
        raise AssertionError("Invalid requests must not invoke RAG")

    monkeypatch.setattr(main, "_ask_rag", unexpected_call)
    assert TestClient(main.app).post("/ask_batched", json=payload).status_code == 422
