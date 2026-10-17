"""Validated singleton application settings, shared by the UI, API and CLI."""
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from .pipeline.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL,
    settings_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
"""


class SettingsConflict(ValueError):
    pass


def settings_database() -> Path:
    return Path(os.getenv("APP_SETTINGS_DB", os.getenv("APP_RESULTS_DB", str(ROOT / "results.db")))).resolve()


def _connect(path):
    return sqlite3.connect(path, timeout=30)


def initialize_settings(db_path=None) -> None:
    path = Path(db_path) if db_path is not None else settings_database()
    with closing(_connect(path)) as con, con:
        con.executescript(SCHEMA)
        con.execute("INSERT OR IGNORE INTO app_settings VALUES (1, 1, ?, ?, 'initial configuration')",
                    (Settings().model_dump_json(), datetime.now(timezone.utc).isoformat()))


def settings_record(db_path=None) -> dict:
    path = Path(db_path) if db_path is not None else settings_database()
    try:
        with closing(_connect(path)) as con:
            row = con.execute("SELECT revision, settings_json, updated_at, updated_by FROM app_settings WHERE id=1").fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        row = None
    if row is None:
        initialize_settings(path)
        return settings_record(path)
    return dict(revision=row[0], settings=Settings.model_validate_json(row[1]), updated_at=row[2], updated_by=row[3])


def load_settings(db_path=None) -> Settings:
    # Background evaluations pin all implicit reads to their launch snapshot.
    job_id = os.getenv("APP_SETTINGS_JOB_ID") if db_path is None else None
    if job_id:
        with closing(_connect(settings_database())) as con:
            row = con.execute("SELECT settings_json FROM admin_golden_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Evaluation settings snapshot was not found")
        return Settings.model_validate_json(row[0])
    return settings_record(db_path)["settings"]


def save_settings(value, *, expected_revision: int, db_path=None) -> dict:
    validated = Settings.model_validate(value)
    path = Path(db_path) if db_path is not None else settings_database()
    with closing(_connect(path)) as con, con:
        result = con.execute(
            "UPDATE app_settings SET settings_json=?, revision=revision+1, updated_at=?, updated_by='admin' "
            "WHERE id=1 AND revision=?",
            (validated.model_dump_json(), datetime.now(timezone.utc).isoformat(), expected_revision),
        )
        if result.rowcount != 1:
            raise SettingsConflict("Settings were changed in another session. Reload the saved settings before saving.")
    return settings_record(path)
