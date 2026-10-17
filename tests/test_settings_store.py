import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.settings_store import SettingsConflict, load_settings, save_settings, settings_record


def test_saved_settings_validate_persist_and_reject_stale_edits(tmp_path):
    path = tmp_path / "settings.db"
    first = settings_record(path)
    assert first["settings"].rag.retrieval.top_k == 8
    data = first["settings"].model_dump(mode="json")
    data["rag"]["retrieval"]["top_k"] = 4
    second = save_settings(data, expected_revision=first["revision"], db_path=path)
    assert second["revision"] == 2 and second["updated_by"] == "admin"
    assert load_settings(path).rag.retrieval.top_k == 4
    with pytest.raises(SettingsConflict):
        save_settings(data, expected_revision=1, db_path=path)
    data["rag"]["retrieval"]["top_k"] = 0
    with pytest.raises(ValidationError):
        save_settings(data, expected_revision=2, db_path=path)
    assert load_settings(path).rag.retrieval.top_k == 4
    assert settings_record(path)["revision"] == 2


def test_new_questions_load_saved_configuration_without_restart(tmp_path, monkeypatch):
    from src.pipeline import pipeline
    path = tmp_path / "settings.db"
    monkeypatch.setenv("APP_SETTINGS_DB", str(path))
    record = settings_record(path)
    record["settings"].rag.retrieval.top_k = 3
    save_settings(record["settings"], expected_revision=record["revision"], db_path=path)
    single = AsyncMock(return_value=pipeline.RagAnswer(question="q", content="answer"))
    monkeypatch.setattr(pipeline, "_ask_rag_single", single)
    asyncio.run(pipeline.ask_rag("q"))
    assert single.call_args.kwargs["rag_settings"].retrieval.top_k == 3
    record = settings_record(path)
    record["settings"].rag.retrieval.top_k = 6
    save_settings(record["settings"], expected_revision=record["revision"], db_path=path)
    asyncio.run(pipeline.ask_rag("q"))
    assert single.call_args.kwargs["rag_settings"].retrieval.top_k == 6


def test_worker_implicit_settings_read_uses_immutable_job_snapshot(tmp_path, monkeypatch):
    from src.eval.jobs import initialize_jobs
    path = tmp_path / "settings.db"
    record = settings_record(path)
    original = record["settings"].model_dump_json()
    initialize_jobs(path)
    with sqlite3.connect(path) as con:
        con.execute("INSERT INTO admin_golden_jobs (id,status,settings_revision,settings_json,created_at,heartbeat_at,artifacts_dir) "
                    "VALUES ('job','queued',1,?,'now','now','artifacts')", (original,))
    record["settings"].rag.retrieval.top_k = 2
    save_settings(record["settings"], expected_revision=1, db_path=path)
    monkeypatch.setenv("APP_SETTINGS_DB", str(path))
    monkeypatch.setenv("APP_SETTINGS_JOB_ID", "job")
    assert load_settings().rag.retrieval.top_k == json.loads(original)["rag"]["retrieval"]["top_k"]
    assert load_settings(path).rag.retrieval.top_k == 2
