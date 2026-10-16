"""Run the local golden-set evaluation against the corpus.

Examples:
    python scripts/run_golden_set.py
    python scripts/run_golden_set.py --limit 10

By default the live tool-calling judge is used. Set ``JUDGE_USE_FAKE=1`` to
run the deterministic local judge instead. The live judge requires
``OPENAI_API_KEY``.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.golden import (
    evaluate_golden_set,
    load_corpus_documents,
    load_golden_set,
    write_eval_artifacts,
)
from src.pipeline.settings import Settings
from src.eval.judge import JUDGE_MODEL, RUBRIC, JUDGE_TOOL
from src.eval.store import save_golden_run


DEFAULT_GOLDEN = ROOT / "docs" / "goldenset" / "golden_set.jsonl"
DEFAULT_CORPUS = ROOT / Settings().rag.corpus.directory
DEFAULT_ROWS_OUT = ROOT / "docs" / "runs" / "golden_eval_results.jsonl"
DEFAULT_SUMMARY_OUT = ROOT / "docs" / "runs" / "golden_eval_summary.json"
DEFAULT_DB = ROOT / Settings().results_db


async def _run(
    *,
    golden_path: Path,
    corpus_dir: Path,
    limit: int | None,
    rows_out: Path,
    summary_out: Path,
    db_path: Path = DEFAULT_DB,
) -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    settings = Settings()
    settings.rag.corpus.directory = corpus_dir.resolve()
    golden_entries = load_golden_set(golden_path)
    corpus_docs = load_corpus_documents(corpus_dir)

    from src.pipeline.pipeline import ask_rag

    judge_settings = {
        "model": JUDGE_MODEL,
        "use_fake": os.getenv("JUDGE_USE_FAKE", "0").lower() not in {"0", "false", "no"},
        "rubric": RUBRIC,
        "tool": JUDGE_TOOL,
    }

    async def answer_fn(question: str):
        return await ask_rag(question, rag_settings=settings.rag)

    async def batch_answer_fn(questions: list[str]):
        return await ask_rag(questions, rag_settings=settings.rag, concurrency=10)

    rows, summary = await evaluate_golden_set(
        golden_entries,
        corpus_docs,
        answer_fn,
        max_entries=limit,
        batch_answer_fn=batch_answer_fn,
        batch_size=10,
    )

    run_id = save_golden_run(
        db_path, rows, summary, settings=settings, judge_settings=judge_settings,
        started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(),
        golden_path=golden_path.resolve(), corpus_dir=corpus_dir.resolve(), limit=limit,
    )
    write_eval_artifacts(rows, summary, rows_path=rows_out, summary_path=summary_out)

    print(f"Loaded {len(golden_entries)} golden entries from {golden_path}")
    print(f"Loaded {len(corpus_docs)} corpus documents from {corpus_dir}")
    print(f"Evaluated {summary.total} entries in {summary.total_elapsed_seconds:.2f}s")
    print(f"Total retrieval time (including reranking): {summary.total_retrieval_seconds:.2f}s")
    print(f"Total LLM answer time: {summary.total_generation_seconds:.2f}s")
    print(f"Total judge processing time: {summary.total_judge_seconds:.2f}s")
    print(f"Retrieval hit rate (answerable): {summary.retrieval_hit_rate:.2%}")
    print(f"Abstention rate:    {summary.abstention_rate:.2%}")
    print(f"Pass rate (all):              {summary.pass_rate:.2%}")
    print(f"Pass rate (answerable):       {summary.answerable_pass_rate:.2%}")
    print(f"Pass rate (unanswerable):     {summary.unanswerable_pass_rate:.2%}")
    print(f"Judge avg accuracy:  {summary.judge_accuracy_avg:.2f}")
    print(f"Judge avg grounded:  {summary.judge_groundedness_avg:.2f}")
    print(f"Judge avg format:    {summary.judge_format_avg:.2f}")
    print(f"Judge avg overall:   {summary.judge_overall_avg:.2f}")
    print(f"Judge pass rate:     {summary.judge_pass_rate:.2%}")
    print(f"Judge trace:         {summary.judge_log_path}")
    print(f"Total cost:         ${summary.total_cost_usd:.6f}")
    print(f"Wrote rows to:      {rows_out}")
    print(f"Wrote summary to:   {summary_out}")
    print(f"Saved database run: {run_id} in {db_path}")

    failed = [row for row in rows if not row.pass_fail]
    if failed:
        print()
        print("First failures:")
        for row in failed[:5]:
            print(f"  {row.id} | expected={row.answerability} | selected={row.selected_document}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden-path", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--rows-out", type=Path, default=DEFAULT_ROWS_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    asyncio.run(
        _run(
            golden_path=args.golden_path,
            corpus_dir=args.corpus_dir,
            limit=args.limit,
            rows_out=args.rows_out,
            summary_out=args.summary_out,
            db_path=args.db_path,
        )
    )


if __name__ == "__main__":
    main()
