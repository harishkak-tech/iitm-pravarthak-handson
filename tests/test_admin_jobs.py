from datetime import datetime, timedelta, timezone
import json
import sqlite3
from unittest.mock import Mock
from unittest.mock import AsyncMock
from types import SimpleNamespace
import sys

import pytest

from src.eval import jobs
from src.settings_store import SettingsConflict, save_settings, settings_record


@pytest.fixture
def queued(tmp_path, monkeypatch):
    path = tmp_path / "results.db"
    record = settings_record(path)
    golden = tmp_path / "golden.jsonl"
    golden.write_text('{}\n', encoding="utf-8")
    record["settings"].golden.golden_path = golden
    record["settings"].rag.corpus.directory = tmp_path
    record["settings"].rag.retrieval.top_k = 4
    saved = save_settings(record["settings"], expected_revision=1, db_path=path)
    process = Mock(pid=12345)
    popen = Mock(return_value=process)
    monkeypatch.setattr(jobs.subprocess, "Popen", popen)
    job_id = jobs.start_job(db_path=path, expected_revision=saved["revision"], artifacts_root=tmp_path / "jobs")
    return path, job_id, popen


def test_launch_snapshots_settings_and_prevents_duplicate_workers(queued):
    path, job_id, popen = queued
    job = jobs.get_job(path, job_id)
    assert job["status"] == "queued"
    assert json.loads(job["settings_json"])["rag"]["retrieval"]["top_k"] == 4
    kwargs = popen.call_args.kwargs
    assert kwargs["env"]["APP_SETTINGS_JOB_ID"] == job_id
    assert kwargs["env"]["APP_SETTINGS_DB"] == str(path.resolve())
    assert kwargs.get("shell", False) is False
    with pytest.raises(ValueError, match="already queued or running"):
        jobs.start_job(db_path=path)
    popen.assert_called_once()
    with pytest.raises(SettingsConflict):
        jobs.start_job(db_path=path, expected_revision=1)


def test_worker_progress_success_and_launch_settings_survive_later_edits(queued):
    path, job_id, _ = queued
    record = settings_record(path)
    record["settings"].rag.retrieval.top_k = 7
    save_settings(record["settings"], expected_revision=record["revision"], db_path=path)
    calls = []

    async def fake_runner(**kwargs):
        calls.append(kwargs)
        kwargs["progress_callback"](1, 2)
        kwargs["progress_callback"](2, 2)
        return 42

    assert jobs.execute_job(path, job_id, runner=fake_runner) == 0
    job = jobs.get_job(path, job_id)
    assert job["status"] == "completed" and job["run_id"] == 42
    assert job["completed_questions"] == job["total_questions"] == 2
    assert calls[0]["settings"].rag.retrieval.top_k == 4
    assert calls[0]["rows_out"] != calls[0]["summary_out"]
    with pytest.raises(ValueError, match="already been claimed"):
        jobs.execute_job(path, job_id, runner=fake_runner)


def test_worker_failure_is_saved_and_allows_a_new_run(queued, tmp_path):
    path, job_id, _ = queued

    async def failing(**kwargs):
        raise RuntimeError("Qdrant connection unavailable")

    assert jobs.execute_job(path, job_id, runner=failing) == 1
    job = jobs.get_job(path, job_id)
    assert job["status"] == "failed" and "Qdrant" in job["error"]
    assert jobs.start_job(db_path=path, artifacts_root=tmp_path / "jobs") != job_id


def test_stopped_worker_is_not_left_running_forever(queued):
    path, job_id, _ = queued
    expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with sqlite3.connect(path) as con:
        con.execute("UPDATE admin_golden_jobs SET status='running', heartbeat_at=? WHERE id=?", (expired, job_id))
    assert jobs.latest_jobs(path)[0]["status"] == "failed"


def test_worker_uses_real_runner_and_persists_results_with_its_snapshot(queued, monkeypatch):
    from scripts import run_golden_set
    from src.eval.golden import GoldenEntry
    from src.eval.judge import JudgeScore
    from src.eval.results_reader import read_history, read_results
    path, job_id, _ = queued
    entry = GoldenEntry(id="q1", question="What is the policy?", expected_behavior="Approved policy",
                        answerability="answerable", evaluation_type="retrieval", document="policy")
    answer = SimpleNamespace(content="Approved policy", retrieved=[], cost_usd=0.0)
    answer_fn = AsyncMock(return_value=[answer])
    monkeypatch.setitem(sys.modules, "src.pipeline.pipeline", SimpleNamespace(ask_rag=answer_fn))
    monkeypatch.setattr(run_golden_set, "load_golden_set", lambda _: [entry])
    monkeypatch.setattr(run_golden_set, "load_corpus_documents", lambda _: {})
    monkeypatch.setattr("src.eval.golden.judge_answer", AsyncMock(return_value=JudgeScore(
        accuracy=4, groundedness=4, format=4, overall=4, passed=True, reasoning="Supported")))
    assert jobs.execute_job(path, job_id) == 0
    job = jobs.get_job(path, job_id)
    history = read_history(path)["golden_runs"]
    assert len(history) == 1 and history[0]["id"] == job["run_id"]
    assert history[0]["settings"]["rag"]["retrieval"]["top_k"] == 4
    assert read_results(path, job["run_id"])[0]["id"] == "q1"
    assert job["completed_questions"] == job["total_questions"] == 1
