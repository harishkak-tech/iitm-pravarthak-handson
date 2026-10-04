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


DEFAULT_GOLDEN = ROOT / "docs" / "goldenset" / "golden_set_60.jsonl"
DEFAULT_CORPUS = ROOT / "docs" / "corpus_pdf_styled"
DEFAULT_ROWS_OUT = ROOT / "docs" / "runs" / "golden_eval_results.jsonl"
DEFAULT_SUMMARY_OUT = ROOT / "docs" / "runs" / "golden_eval_summary.json"


async def _run(
    *,
    golden_path: Path,
    corpus_dir: Path,
    limit: int | None,
    rows_out: Path,
    summary_out: Path,
) -> None:
    golden_entries = load_golden_set(golden_path)
    corpus_docs = load_corpus_documents(corpus_dir)

    from src.pipeline.pipeline import ask_rag

    async def answer_fn(question: str):
        return await ask_rag(question)

    rows, summary = await evaluate_golden_set(
        golden_entries,
        corpus_docs,
        answer_fn,
        max_entries=limit,
    )

    write_eval_artifacts(rows, summary, rows_path=rows_out, summary_path=summary_out)

    print(f"Loaded {len(golden_entries)} golden entries from {golden_path}")
    print(f"Loaded {len(corpus_docs)} corpus documents from {corpus_dir}")
    print(f"Evaluated {summary.total} entries in {summary.total_elapsed_seconds:.2f}s")
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
    args = parser.parse_args()

    asyncio.run(
        _run(
            golden_path=args.golden_path,
            corpus_dir=args.corpus_dir,
            limit=args.limit,
            rows_out=args.rows_out,
            summary_out=args.summary_out,
        )
    )


if __name__ == "__main__":
    main()
