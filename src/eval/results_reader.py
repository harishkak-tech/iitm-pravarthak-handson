"""Read evaluation history without importing the pipeline or opening API clients."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3


def _connect(path: str | Path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


def read_history(path: str | Path) -> dict[str, list[dict]]:
    with closing(_connect(path)) as con:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        history = {"golden_runs": [], "runs": []}
        for table in history:
            if table in tables:
                history[table] = [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY id DESC")]
        for run in history["golden_runs"]:
            for key in ("settings", "judge_settings", "summary"):
                run[key] = json.loads(run.pop(key + "_json"))
        return history


def read_results(path: str | Path, run_id: int, *, golden: bool = True) -> list[dict]:
    table = "golden_results" if golden else "answers"
    with closing(_connect(path)) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return []
        rows = [dict(row) for row in con.execute(f"SELECT * FROM {table} WHERE run_id=? ORDER BY id", (run_id,))]
    if golden:
        return [json.loads(row["result_json"]) for row in rows]
    return rows
