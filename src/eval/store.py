"""Append-only SQLite history for completed golden evaluations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .golden import GoldenEvalRow, GoldenEvalSummary
from ..pipeline.settings import Settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS golden_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    model TEXT NOT NULL,
    golden_path TEXT NOT NULL,
    corpus_dir TEXT NOT NULL,
    entry_limit INTEGER,
    settings_json TEXT NOT NULL,
    judge_settings_json TEXT NOT NULL,
    summary_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS golden_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES golden_runs(id),
    entry_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    pass_fail INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    UNIQUE (run_id, entry_id)
);
"""


def save_golden_run(
    db_path: str | Path,
    rows: list[GoldenEvalRow],
    summary: GoldenEvalSummary,
    *,
    settings: Settings,
    judge_settings: dict[str, object],
    started_at: str,
    completed_at: str,
    golden_path: Path,
    corpus_dir: Path,
    limit: int | None,
) -> int:
    """Save a run and all results atomically; return its database ID."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA)
        with con:
            cursor = con.execute(
                "INSERT INTO golden_runs (started_at, completed_at, model, golden_path, "
                "corpus_dir, entry_limit, settings_json, judge_settings_json, summary_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    started_at, completed_at, settings.rag.generation.model,
                    str(golden_path), str(corpus_dir), limit,
                    settings.model_dump_json(), json.dumps(judge_settings),
                    summary.model_dump_json(),
                ),
            )
            run_id = cursor.lastrowid
            assert run_id is not None
            con.executemany(
                "INSERT INTO golden_results (run_id, entry_id, question, answer_text, "
                "pass_fail, result_json) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (run_id, row.id, row.question, row.answer_text,
                     int(row.pass_fail), row.model_dump_json())
                    for row in rows
                ],
            )
        return run_id
    finally:
        con.close()
