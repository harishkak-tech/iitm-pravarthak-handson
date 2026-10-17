import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.eval.golden import GoldenEntry, evaluate_golden_set
from src.eval.judge import JudgeScore


def test_golden_batches_five_with_limit_and_preserves_alignment(tmp_path, monkeypatch):
    entries = [GoldenEntry(
        id=f"q{i}", question=f"Question {i}", expected_behavior="State policy",
        answerability="answerable", evaluation_type="retrieval",
    ) for i in range(13)]
    active = 0
    peak = 0

    async def fake_judge(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02 if kwargs["question"] == "Question 0" else 0)
        active -= 1
        return JudgeScore(
            accuracy=4, groundedness=4, format=4,
            reasoning=kwargs["question"], overall=4, passed=True,
        )

    judge = AsyncMock(side_effect=fake_judge)
    monkeypatch.setattr("src.eval.golden.judge_answer", judge)
    calls = []

    async def batch_answer(questions):
        assert active == 0
        calls.append(questions)
        return [SimpleNamespace(content=f"Answer to {q}", retrieved=[], cost_usd=0.01,
                                stage_intervals={"retrieval": (0.0, 2.0), "generation": (1.0, 4.0)})
                for q in questions]

    single = AsyncMock(side_effect=AssertionError("Must use batch calls"))
    rows, summary = asyncio.run(evaluate_golden_set(
        entries, {}, single, batch_answer_fn=batch_answer, batch_size=5,
        max_entries=12, judge_log_path=tmp_path / "judge.jsonl",
    ))
    assert calls == [[entry.question for entry in entries[start:start + 5]]
                     for start in (0, 5)] + [[entry.question for entry in entries[10:12]]]
    assert [row.id for row in rows] == [entry.id for entry in entries[:12]]
    assert [row.answer_text for row in rows] == [f"Answer to {e.question}" for e in entries[:12]]
    assert judge.await_count == 12
    assert peak == 5
    assert summary.total_judge_seconds > 0
    # Concurrent overlapping intervals count once, rather than once per question.
    assert summary.total_retrieval_seconds == 2.0
    assert summary.total_generation_seconds == 3.0
    assert [row.judge_reasoning for row in rows] == [e.question for e in entries[:12]]
    single.assert_not_awaited()
    assert summary.total == 12
    assert abs(summary.total_cost_usd - 0.12) < 1e-9
    assert summary.total_elapsed_seconds == pytest.approx(sum(row.elapsed_seconds for row in rows))
