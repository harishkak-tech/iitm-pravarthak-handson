"""Ask one question against the local RAG pipeline.

Examples:
    python scripts/ask_rag.py "Which groups are intended to benefit from farmer-welfare programmes?"
    python scripts/ask_rag.py --top-k 7 "What does the corpus say about district verification?"
"""

from __future__ import annotations

import argparse
import asyncio
from numbers import Number
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.pipeline import ask_rag


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Ask one question using the RAG pipeline.")
    parser.add_argument("question", help="Question to ask the RAG system.")
    parser.add_argument("--top-k", type=int, default=None, help="Override retrieval top_k.")
    parser.add_argument(
        "--show-retrieved",
        action="store_true",
        help="Print retrieved chunk IDs and scores after the answer.",
    )
    args = parser.parse_args()

    answer = await ask_rag(args.question, top_k=args.top_k)

    print("\nAnswer:\n")
    print(answer.content.strip())
    print("\nSources:")
    for source in answer.sources:
        print(f"- {source}")
    print(f"\nCost: ${answer.cost_usd:.6f}")

    if args.show_retrieved:
        print("\nRetrieved chunks:")
        for hit in answer.retrieved:
            score = hit.get("score")
            score_text = f"{float(score):.5f}" if isinstance(score, Number) else "n/a"
            print(f"- {hit.get('chunk_id')} | score={score_text} | source={hit.get('source')}")


if __name__ == "__main__":
    asyncio.run(_main())
