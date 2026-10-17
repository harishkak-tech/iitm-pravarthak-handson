"""Run one database-queued admin evaluation in a separate Python process."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    os.environ["APP_SETTINGS_DB"] = str(args.db_path.resolve())
    os.environ["APP_SETTINGS_JOB_ID"] = args.job_id
    from src.eval.jobs import execute_job
    raise SystemExit(execute_job(args.db_path, args.job_id))
