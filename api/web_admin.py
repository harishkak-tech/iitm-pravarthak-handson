"""HTTP boundary for the React administration screens."""
from pathlib import Path
import os
import secrets
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError

from src.admin_auth import authenticate_admin
from src.eval.jobs import latest_jobs, start_job
from src.eval.results_reader import read_history, read_results
from src.pipeline.settings import Settings
from src.settings_store import ROOT, SettingsConflict, save_settings, settings_database, settings_record

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer(auto_error=False)
_sessions: dict[str, float] = {}
_attempts: dict[str, list[float]] = {}
_lock = threading.Lock()


def results_database():
    return Path(os.getenv("APP_RESULTS_DB", str(ROOT / "results.db"))).resolve()


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    with _lock:
        now = time.monotonic()
        for token in list(_sessions):
            if _sessions[token] <= now:
                del _sessions[token]
        if credentials is None or credentials.credentials not in _sessions:
            raise HTTPException(401, "Please sign in as administrator.")
    return credentials.credentials


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1024)


@router.post("/login")
def login(value: Login, request: Request):
    host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        for key in list(_attempts):
            _attempts[key] = [t for t in _attempts[key] if now - t < 60]
            if not _attempts[key]:
                del _attempts[key]
        attempts = _attempts.setdefault(host, [])
        if len(attempts) >= 5:
            raise HTTPException(429, "Too many login attempts. Try again in one minute.")
        attempts.append(now)
    auth_db = Path(os.getenv("APP_AUTH_DB", str(results_database())))
    if not authenticate_admin(auth_db, value.username, value.password):
        raise HTTPException(401, "Invalid username or password.")
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = now + 8 * 60 * 60
    return {"token": token}


@router.post("/logout")
def logout(token: str = Depends(require_admin)):
    with _lock:
        _sessions.pop(token, None)
    return {"status": "ok"}


@router.get("/history", dependencies=[Depends(require_admin)])
def history():
    try:
        return read_history(results_database())
    except FileNotFoundError:
        return {"golden_runs": [], "runs": []}


@router.get("/runs/{run_id}", dependencies=[Depends(require_admin)])
def results(run_id: int, golden: bool = True):
    try:
        return read_results(results_database(), run_id, golden=golden)
    except FileNotFoundError:
        return []


def serialize_record(record):
    return {**record, "settings": record["settings"].model_dump(mode="json"), "schema": Settings.model_json_schema()}


@router.get("/settings", dependencies=[Depends(require_admin)])
def get_settings():
    return serialize_record(settings_record())


class SettingsUpdate(BaseModel):
    settings: dict
    expected_revision: int = Field(ge=1)


@router.put("/settings", dependencies=[Depends(require_admin)])
def update_settings(value: SettingsUpdate):
    try:
        return serialize_record(save_settings(value.settings, expected_revision=value.expected_revision))
    except SettingsConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/jobs", dependencies=[Depends(require_admin)])
def jobs():
    return latest_jobs(settings_database())


class Launch(BaseModel):
    expected_revision: int = Field(ge=1)


@router.post("/jobs", dependencies=[Depends(require_admin)])
def launch(value: Launch):
    try:
        return {"id": start_job(expected_revision=value.expected_revision)}
    except SettingsConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(400, str(exc)) from exc
