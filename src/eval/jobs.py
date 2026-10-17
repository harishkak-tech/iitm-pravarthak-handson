"""Durable background evaluation jobs with immutable settings snapshots."""
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import traceback
import uuid

from src.pipeline.settings import Settings
from src.settings_store import ROOT, SettingsConflict, settings_database, settings_record


SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_golden_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    settings_revision INTEGER NOT NULL,
    settings_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    heartbeat_at TEXT NOT NULL,
    completed_questions INTEGER NOT NULL DEFAULT 0,
    total_questions INTEGER NOT NULL DEFAULT 0,
    run_id INTEGER,
    pid INTEGER,
    artifacts_dir TEXT NOT NULL,
    error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_golden_job
    ON admin_golden_jobs ((1)) WHERE status IN ('queued','running');
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize_jobs(db_path):
    with closing(sqlite3.connect(db_path, timeout=30)) as con, con:
        con.executescript(SCHEMA)


def _update(db_path, job_id, **values):
    allowed = {"status", "started_at", "finished_at", "heartbeat_at", "completed_questions",
               "total_questions", "run_id", "pid", "error"}
    if not values or not set(values).issubset(allowed):
        raise ValueError("Invalid job update")
    with closing(sqlite3.connect(db_path, timeout=30)) as con, con:
        con.execute("UPDATE admin_golden_jobs SET " + ", ".join(f"{key}=?" for key in values) + " WHERE id=?",
                    (*values.values(), job_id))


def latest_jobs(db_path=None, limit=10):
    path = Path(db_path) if db_path is not None else settings_database()
    initialize_jobs(path)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with closing(sqlite3.connect(path, timeout=30)) as con, con:
        con.row_factory = sqlite3.Row
        # A crashed/killed worker cannot leave the launch button locked forever.
        con.execute("UPDATE admin_golden_jobs SET status='failed', finished_at=?, "
                    "error='The evaluation worker stopped reporting progress. Start a new run.' "
                    "WHERE status IN ('queued','running') AND heartbeat_at < ?", (now(), cutoff))
        return [dict(row) for row in con.execute(
            "SELECT * FROM admin_golden_jobs ORDER BY created_at DESC LIMIT ?", (limit,))]


def get_job(db_path, job_id):
    with closing(sqlite3.connect(db_path, timeout=30)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM admin_golden_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Evaluation job not found")
    return dict(row)


def start_job(*, db_path=None, expected_revision=None, artifacts_root=None) -> str:
    path = (Path(db_path) if db_path is not None else settings_database()).resolve()
    settings_record(path)
    latest_jobs(path)
    job_id = uuid.uuid4().hex
    artifacts = (Path(artifacts_root) if artifacts_root else ROOT / "docs/runs/admin_jobs") / job_id
    with closing(sqlite3.connect(path, timeout=30)) as con, con:
        con.execute("BEGIN IMMEDIATE")
        revision, payload = con.execute("SELECT revision, settings_json FROM app_settings WHERE id=1").fetchone()
        if expected_revision is not None and revision != expected_revision:
            raise SettingsConflict("Saved settings changed before launch. Reload them and try again.")
        settings = Settings.model_validate_json(payload)
        golden_path = ROOT / settings.golden.golden_path
        corpus_dir = ROOT / settings.rag.corpus.directory
        if not golden_path.is_file() or not corpus_dir.is_dir():
            raise ValueError("The saved golden-set file and corpus directory must exist before launching.")
        try:
            con.execute("INSERT INTO admin_golden_jobs "
                        "(id,status,settings_revision,settings_json,created_at,heartbeat_at,artifacts_dir) "
                        "VALUES (?,'queued',?,?,?,?,?)",
                        (job_id, revision, payload, now(), now(), str(artifacts.resolve())))
        except sqlite3.IntegrityError as exc:
            raise ValueError("A golden-set evaluation is already queued or running.") from exc
    try:
        artifacts.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["APP_SETTINGS_DB"] = str(path)
        env["APP_SETTINGS_JOB_ID"] = job_id
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        with (artifacts / "worker.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "scripts/run_admin_golden.py"),
                 "--db-path", str(path), "--job-id", job_id],
                cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, **options,
            )
        _update(path, job_id, pid=process.pid)
        # Reap the child without tying job lifetime to a Streamlit session.
        threading.Thread(target=process.wait, daemon=True).start()
    except Exception as exc:
        _update(path, job_id, status="failed", error=str(exc), finished_at=now())
        raise
    return job_id


def execute_job(db_path, job_id, runner=None) -> int:
    """Worker entrypoint. The optional runner is used for offline integration tests."""
    path = Path(db_path).resolve()
    job = get_job(path, job_id)
    with closing(sqlite3.connect(path, timeout=30)) as con, con:
        claimed = con.execute("UPDATE admin_golden_jobs SET status='running', started_at=?, heartbeat_at=?, pid=? "
                              "WHERE id=? AND status='queued'", (now(), now(), os.getpid(), job_id))
        if claimed.rowcount != 1:
            raise ValueError("This job has already been claimed or finished")
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(10):
            try:
                _update(path, job_id, heartbeat_at=now())
            except sqlite3.Error:
                traceback.print_exc()

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        settings = Settings.model_validate_json(job["settings_json"])
        if runner is None:
            from scripts.run_golden_set import _run
            runner = _run

        def progress(completed, total):
            _update(path, job_id, completed_questions=completed, total_questions=total, heartbeat_at=now())

        artifacts = Path(job["artifacts_dir"])
        artifacts.mkdir(parents=True, exist_ok=True)
        run_id = asyncio.run(runner(
            golden_path=ROOT / settings.golden.golden_path, corpus_dir=ROOT / settings.rag.corpus.directory,
            limit=settings.golden.question_limit, rows_out=artifacts / "results.jsonl",
            summary_out=artifacts / "summary.json", db_path=path, settings=settings,
            progress_callback=progress,
        ))
        _update(path, job_id, status="completed", run_id=run_id, finished_at=now(), heartbeat_at=now())
        return 0
    except (Exception, SystemExit) as exc:
        traceback.print_exc()
        _update(path, job_id, status="failed", error=f"{type(exc).__name__}: {exc}", finished_at=now())
        return 1
    finally:
        stop.set()
        thread.join(timeout=1)
