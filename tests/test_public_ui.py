from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from src.admin_auth import create_admin


APP = Path(__file__).resolve().parents[1] / "api/results_viewer.py"


@pytest.fixture
def ui(tmp_path, monkeypatch):
    path = tmp_path / "results.db"
    create_admin(path, "test-admin-password")
    monkeypatch.setenv("APP_AUTH_DB", str(path))
    monkeypatch.setenv("APP_RESULTS_DB", str(path))
    return AppTest.from_file(str(APP), default_timeout=30).run()


def button(ui, label):
    return next(w for w in ui.button if w.label == label)


def test_home_only_shows_question_answer_and_admin_link(ui, monkeypatch):
    assert not ui.exception
    assert len(ui.title) == 1 and len(ui.text_area) == 1
    assert not ui.sidebar.text_input and not ui.tabs and not ui.dataframe
    assert [w.label for w in ui.button] == ["Admin login", "Ask"]
    response = Mock()
    response.json.return_value = {"content": "A supported answer [source#1].", "sources": ["source#1"],
                                  "retrieved": [{"chunk_id": "secret-debug", "text": "private diagnostic"}],
                                  "cost_usd": 1.0}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    ui.text_area[0].set_value("My policy question")
    button(ui, "Ask").click().run()
    assert not ui.exception
    assert any(w.value == "A supported answer." for w in ui.markdown)
    assert not ui.expander and not ui.json
    assert not any("cost" in w.value.lower() for w in ui.caption)
    assert post.call_args.kwargs["json"] == {"question": "My policy question"}
    assert ui.session_state["rag_last_answer"]["content"] == "A supported answer [source#1]."


def test_admin_route_requires_valid_login_and_logout_revokes_access(ui):
    # Navigating directly to the admin URL must not grant access.
    ui.query_params["view"] = "admin"
    ui.run()
    assert not ui.sidebar.text_input and not ui.dataframe and not ui.tabs
    next(w for w in ui.text_input if w.label == "Password").set_value("wrong")
    button(ui, "Log in").click().run()
    assert any("Invalid username or password" in w.value for w in ui.error)
    assert not ui.sidebar.text_input
    next(w for w in ui.text_input if w.label == "Password").set_value("test-admin-password")
    button(ui, "Log in").click().run()
    assert not ui.exception and not ui.error
    assert [w.label for w in ui.tabs] == ["Settings and runs", "Golden evaluations", "Answer diagnostics"]
    assert any(w.label == "Database path" for w in ui.sidebar.text_input)
    button(ui, "Log out").click().run()
    assert not ui.tabs and not ui.sidebar.text_input
    ui.query_params["view"] = "admin"
    ui.run()
    assert any(w.label == "Password" for w in ui.text_input)
    assert not ui.tabs


def test_blank_question_does_not_call_api(ui, monkeypatch):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    button(ui, "Ask").click().run()
    post.assert_not_called()
    assert ui.warning


def test_legacy_streamlit_entrypoint_uses_same_home():
    app = APP.parent / "main.py"
    ui = AppTest.from_file(str(app), default_timeout=30).run()
    assert not ui.exception
    assert ui.title[0].value == "Government Policy Knowledge Assistant"
    assert len(ui.text_area) == 1 and not ui.tabs
    assert not ui.sidebar.text_input
    assert [w.label for w in ui.button] == ["Admin login", "Ask"]
