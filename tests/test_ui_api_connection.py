from unittest.mock import Mock

import pytest
import requests

from api import ask_ui


def test_ui_reads_project_dotenv_and_preserves_environment_override(tmp_path, monkeypatch):
    monkeypatch.setattr(ask_ui, "ROOT", tmp_path)
    monkeypatch.delenv("RAG_API_BASE_URL", raising=False)
    (tmp_path / ".env").write_text("RAG_API_BASE_URL=http://127.0.0.1:8010/\n", encoding="utf-8")
    assert ask_ui.api_base_url() == "http://127.0.0.1:8010"
    monkeypatch.setenv("RAG_API_BASE_URL", "http://api.example.com:8000")
    assert ask_ui.api_base_url() == "http://api.example.com:8000"


@pytest.mark.parametrize("base,local", [("http://127.0.0.1:8000", True),
                                       ("http://localhost:8000", True),
                                       ("http://[::1]:8000", True),
                                       ("http://backend.example.com:8000", False)])
def test_loopback_bypasses_proxies_while_remote_respects_environment(base, local, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example.com:3128")
    monkeypatch.setenv("NO_PROXY", "")
    observed = []

    def send(session, request, **kwargs):
        observed.append((request, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"content":"answer"}'
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    response = ask_ui.post_question("question", base)
    assert response.status_code == 200
    request, kwargs = observed[0]
    assert request.url == base + "/ask_rag"
    assert bool(kwargs["proxies"]) is not local
    assert kwargs["timeout"] == (10, 300)


def test_http_error_status_logged_without_question_credentials_or_body(monkeypatch):
    response = requests.Response()
    response.status_code = 403
    response._content = b"private-response"
    monkeypatch.setattr(requests.Session, "post", Mock(return_value=response))
    log = Mock()
    monkeypatch.setattr(ask_ui, "log", log)
    assert ask_ui.post_question("private-question", "http://user:secret@localhost:8000") is response
    calls = str(log.mock_calls)
    assert "403" in calls and "localhost:8000" in calls
    assert not any(value in calls for value in ["secret", "private-question", "private-response"])


def test_connection_failure_is_logged_and_propagated(monkeypatch):
    monkeypatch.setattr(requests.Session, "post", Mock(side_effect=requests.ConnectionError("private detail")))
    log = Mock()
    monkeypatch.setattr(ask_ui, "log", log)
    with pytest.raises(requests.ConnectionError):
        ask_ui.post_question("private-question", "http://127.0.0.1:8000")
    assert "ConnectionError" in str(log.error.call_args)
    assert "private" not in str(log.mock_calls)
