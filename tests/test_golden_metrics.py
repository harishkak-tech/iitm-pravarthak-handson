"""Regression tests for golden-set summary metrics."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from src.eval.golden import GoldenEntry, evaluate_golden_set
from src.eval.judge import JudgeScore


def test_retrieval_hit_rate_excludes_unanswerable_rows() -> None:
    entries = [
        GoldenEntry(
            id="answerable",
            document="policy.txt",
            question="What is the policy?",
            expected_behavior="State the policy.",
            answerability="answerable",
            evaluation_type="retrieval",
        ),
        GoldenEntry(
            id="unanswerable",
            document="policy.txt",
            question="What is the unsupported detail?",
            expected_behavior="Abstain.",
            answerability="unanswerable",
            evaluation_type="hallucination / abstention",
        ),
    ]

    async def answer_fn(_: str):
        return SimpleNamespace(
            content="A supported answer.",
            retrieved=[{"chunk_id": "policy.txt#0", "source": "policy.txt", "text": "Policy text."}],
        )

    async def judge_answer(**_: object) -> JudgeScore:
        return JudgeScore(
            accuracy=4,
            groundedness=4,
            format=4,
            reasoning="Pass.",
            overall=4.0,
            passed=True,
        )

    with TemporaryDirectory() as temp_dir, patch("src.eval.golden.judge_answer", judge_answer):
        judge_log_path = f"{temp_dir}/judge_trace.jsonl"
        _, summary = asyncio.run(
            evaluate_golden_set(
                entries,
                {"policy.txt": "Policy text."},
                answer_fn,
                judge_log_path=judge_log_path,
            )
        )
        with open(judge_log_path, encoding="utf-8") as judge_log:
            trace_rows = [json.loads(line) for line in judge_log]

    assert summary.retrieval_hits == 1
    assert summary.retrieval_hit_rate == 1.0
    assert summary.answerable_pass_rate == 1.0
    assert summary.unanswerable_pass_rate == 1.0
    assert summary.judge_log_path == str(Path(judge_log_path))
    assert trace_rows[0]["question"] == "What is the policy?"
    assert trace_rows[0]["expected_behavior"] == "State the policy."
    assert trace_rows[0]["llm_response"] == "A supported answer."
