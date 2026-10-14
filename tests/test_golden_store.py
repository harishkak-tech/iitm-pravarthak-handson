"""Golden history preserves run settings and writes results atomically."""

import asyncio
import json
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import run_golden_set
from src.eval.golden import GoldenEntry, evaluate_golden_set
from src.eval.judge import JudgeScore
from src.eval.store import save_golden_run
from src.pipeline.settings import Settings


def test_history_snapshots_and_atomic_results(tmp_path, monkeypatch):
    entry = GoldenEntry(
        id="q1", question="What is the policy?", expected_behavior="State policy",
        answerability="answerable", evaluation_type="retrieval", document="policy.txt",
    )
    judge = AsyncMock(return_value=JudgeScore(
        accuracy=4, groundedness=4, format=4, reasoning="Supported", overall=4, passed=True,
    ))
    monkeypatch.setattr("src.eval.golden.judge_answer", judge)
    answer = AsyncMock(return_value=SimpleNamespace(content="Policy answer", retrieved=[]))
    rows, summary = asyncio.run(evaluate_golden_set(
        [entry], {}, answer, judge_log_path=tmp_path / "judge.jsonl",
    ))
    db_path = tmp_path / "history" / "results.db"
    settings = Settings()
    settings.rag.generation.model = "gpt-4.1"
    kwargs = dict(
        settings=settings, judge_settings={"model": "judge", "use_fake": True},
        started_at="2026-10-10T10:00:00+00:00", completed_at="2026-10-10T10:01:00+00:00",
        golden_path=tmp_path / "golden.jsonl", corpus_dir=tmp_path / "corpus", limit=1,
    )
    first = save_golden_run(db_path, rows, summary, **kwargs)
    settings.rag.generation.model = "other-model"
    settings.rag.retrieval.top_k = 2
    settings.rag.retrieval.rerank_candidate_k = 10
    second = save_golden_run(db_path, rows, summary, **kwargs)
    assert first != second
    with pytest.raises(sqlite3.IntegrityError):
        save_golden_run(db_path, rows + rows, summary, **kwargs)
    with sqlite3.connect(db_path) as con:
        runs = con.execute("SELECT model, settings_json, summary_json FROM golden_runs ORDER BY id").fetchall()
        results = con.execute("SELECT run_id, result_json FROM golden_results ORDER BY id").fetchall()
    assert len(runs) == len(results) == 2
    assert runs[0][0] == "gpt-4.1"
    assert json.loads(runs[0][1])["rag"]["retrieval"]["top_k"] == 8
    assert json.loads(runs[1][1])["rag"]["retrieval"]["top_k"] == 2
    assert json.loads(runs[0][1])["rag"]["retrieval"]["rerank_candidate_k"] == 50
    assert json.loads(runs[1][1])["rag"]["retrieval"]["rerank_candidate_k"] == 10
    assert json.loads(runs[0][2]) == summary.model_dump(mode="json")
    assert json.loads(results[0][1]) == rows[0].model_dump(mode="json")

    # Exercise the actual runner without network calls or PDF extraction.
    monkeypatch.setattr(run_golden_set, "load_golden_set", lambda _: [entry])
    monkeypatch.setattr(run_golden_set, "load_corpus_documents", lambda _: {})
    monkeypatch.setenv("JUDGE_USE_FAKE", "1")
    monkeypatch.setitem(sys.modules, "src.pipeline.pipeline", SimpleNamespace(ask_rag=answer))
    asyncio.run(run_golden_set._run(
        golden_path=tmp_path / "golden.jsonl", corpus_dir=tmp_path / "custom-corpus",
        limit=1, rows_out=tmp_path / "rows.jsonl", summary_out=tmp_path / "summary.json",
        db_path=db_path,
    ))
    actual_settings = answer.call_args.kwargs["rag_settings"]
    assert actual_settings.corpus.directory == (tmp_path / "custom-corpus").resolve()
    with sqlite3.connect(db_path) as con:
        saved = con.execute("SELECT settings_json, judge_settings_json FROM golden_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert json.loads(saved[0])["rag"] == actual_settings.model_dump(mode="json")
    assert json.loads(saved[1])["use_fake"] is True
