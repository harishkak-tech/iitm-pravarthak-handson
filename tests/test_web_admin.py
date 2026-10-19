"""React API authorization, settings concurrency, and API compatibility."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api import web_admin
from src.admin_auth import create_admin


@pytest.fixture
def web(tmp_path, monkeypatch):
    path = tmp_path / "web.db"
    monkeypatch.setenv("APP_RESULTS_DB", str(path))
    monkeypatch.setenv("APP_AUTH_DB", str(path))
    monkeypatch.setenv("APP_SETTINGS_DB", str(path))
    create_admin(path, "test-password")
    web_admin._sessions.clear()
    web_admin._attempts.clear()
    with TestClient(app) as client:
        yield client


def sign_in(client):
    response = client.post("/api/admin/login", json={"username": "admin", "password": "test-password"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest.mark.parametrize("path", ["history", "settings", "jobs", "runs/1"])
def test_admin_reads_require_login(web, path):
    assert web.get("/api/admin/" + path).status_code == 401


def test_admin_mutations_require_login(web):
    assert web.put("/api/admin/settings", json={"settings": {}, "expected_revision": 1}).status_code == 401
    assert web.post("/api/admin/jobs", json={"expected_revision": 1}).status_code == 401


def test_login_logout_and_expiration(web):
    assert web.post("/api/admin/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    headers = sign_in(web)
    assert web.get("/api/admin/history", headers=headers).json() == {"golden_runs": [], "runs": []}
    assert web.post("/api/admin/logout", headers=headers).status_code == 200
    assert web.get("/api/admin/settings", headers=headers).status_code == 401
    headers = sign_in(web)
    web_admin._sessions[headers["Authorization"].removeprefix("Bearer ")] = 0
    assert web.get("/api/admin/settings", headers=headers).status_code == 401


def test_settings_save_rejects_stale_and_invalid_edits(web):
    headers = sign_in(web)
    record = web.get("/api/admin/settings", headers=headers).json()
    assert "$defs" in record["schema"]
    value = {"settings": record["settings"], "expected_revision": record["revision"]}
    response = web.put("/api/admin/settings", json=value, headers=headers)
    assert response.status_code == 200
    assert response.json()["revision"] == record["revision"] + 1
    assert web.put("/api/admin/settings", json=value, headers=headers).status_code == 409
    value["expected_revision"] += 1
    value["settings"]["rag"]["retrieval"]["top_k"] = -1
    assert web.put("/api/admin/settings", json=value, headers=headers).status_code == 422


def test_job_launch_uses_saved_revision(web, monkeypatch):
    headers = sign_in(web)
    called = []
    monkeypatch.setattr(web_admin, "start_job", lambda **kwargs: called.append(kwargs) or "job-id")
    response = web.post("/api/admin/jobs", json={"expected_revision": 7}, headers=headers)
    assert response.json() == {"id": "job-id"}
    assert called == [{"expected_revision": 7}]


def test_login_attempts_are_limited(web):
    for _ in range(5):
        assert web.post("/api/admin/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert web.post("/api/admin/login", json={"username": "admin", "password": "wrong"}).status_code == 429


def test_public_react_route_keeps_answer_contract(web, monkeypatch):
    from api import main
    from src.pipeline.pipeline import RagAnswer
    answer = RagAnswer(question="My question", content="Supported answer.", sources=["source#1"], cost_usd=0, retries=0)
    mock = AsyncMock(return_value=answer)
    monkeypatch.setattr(main, "_ask_rag", mock)
    response = web.post("/api/ask_rag", json={"question": " My question "})
    assert response.status_code == 200
    assert response.json()["content"] == "Supported answer."
    assert response.json()["sources"] == ["source#1"]
    mock.assert_awaited_once_with("My question")
    assert web.get("/api/health").json() == {"status": "ok"}
    assert web.post("/api/ask_rag", json={"question": "  "}).status_code == 422
