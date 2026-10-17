from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from src.admin_auth import create_admin
from src.eval import jobs
from src.settings_store import load_settings, settings_record


APP = Path(__file__).resolve().parents[1] / "api/results_viewer.py"


def button(ui, label):
    return next(w for w in ui.button if w.label == label)


def login(path, monkeypatch):
    monkeypatch.setenv("APP_AUTH_DB", str(path))
    monkeypatch.setenv("APP_RESULTS_DB", str(path))
    monkeypatch.setenv("APP_SETTINGS_DB", str(path))
    ui = AppTest.from_file(str(APP), default_timeout=30).run()
    button(ui, "Admin login").click().run()
    next(w for w in ui.text_input if w.label == "Password").set_value("test-password")
    button(ui, "Log in").click().run()
    assert not ui.exception
    return ui


def test_editor_displays_database_values_and_saves_validated_changes(tmp_path, monkeypatch):
    path = tmp_path / "results.db"
    create_admin(path, "test-password")
    ui = login(path, monkeypatch)
    next(w for w in ui.number_input if w.label == "Retrieved chunks (k)").set_value(6)
    next(w for w in ui.checkbox if w.label == "Enable reranking").check()
    button(ui, "Save settings").click().run()
    assert not ui.exception and not ui.error
    settings = load_settings(path)
    assert settings.rag.retrieval.top_k == 6 and settings.rag.retrieval.rerank_enabled
    ui = login(path, monkeypatch)
    assert next(w for w in ui.number_input if w.label == "Retrieved chunks (k)").value == 6
    assert next(w for w in ui.checkbox if w.label == "Enable reranking").value
    revision = settings_record(path)["revision"]
    next(w for w in ui.number_input if w.label == "Retrieved chunks (k)").set_value(0)
    button(ui, "Save settings").click().run()
    assert ui.error and not ui.exception
    assert settings_record(path)["revision"] == revision
    assert load_settings(path).rag.retrieval.top_k == 6


def test_ui_can_launch_saved_settings_and_show_durable_job_state(tmp_path, monkeypatch):
    path = tmp_path / "results.db"
    create_admin(path, "test-password")
    # Do not start real external evaluations in a UI test.
    popen = Mock(return_value=Mock(pid=12345))
    monkeypatch.setattr(jobs.subprocess, "Popen", popen)
    start = jobs.start_job
    monkeypatch.setattr("api.admin_settings.start_job", lambda **kwargs: start(artifacts_root=tmp_path / "jobs", **kwargs))
    ui = login(path, monkeypatch)
    next(w for w in ui.number_input if w.label == "Retrieved chunks (k)").set_value(7)
    button(ui, "Save and run golden set").click().run()
    assert not ui.exception and not ui.error
    assert load_settings(path).rag.retrieval.top_k == 7
    job = jobs.latest_jobs(path)[0]
    assert job["status"] == "queued"
    popen.assert_called_once()
    assert button(ui, "Save and run golden set").disabled
    ui = login(path, monkeypatch)
    assert button(ui, "Save and run golden set").disabled
    assert any("queued" in w.value.lower() for w in ui.info)

    async def finish(**kwargs):
        kwargs["progress_callback"](1, 1)
        return 123

    jobs.execute_job(path, job["id"], runner=finish)
    ui.run()
    assert not ui.exception
    assert any("run 123" in w.value.lower() for w in ui.success)
    assert not button(ui, "Save and run golden set").disabled
