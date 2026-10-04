"""Ingest the styled PDF policy corpus into Qdrant.

Examples:
    python scripts/ingest_qdrant.py
    python scripts/ingest_qdrant.py --collection policy_corpus_v2
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.pipeline import index_corpus_in_qdrant
from src.pipeline.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk, embed, and persist the corpus in Qdrant.")
    parser.add_argument("--corpus-dir", type=Path, default=None, help="Override rag.corpus.directory")
    parser.add_argument("--collection", default=None)
    args = parser.parse_args()
    rag_settings = Settings().rag
    if args.corpus_dir:
        rag_settings = rag_settings.model_copy(deep=True)
        rag_settings.corpus.directory = args.corpus_dir
    collection_name = args.collection or rag_settings.collection_name()

    count = index_corpus_in_qdrant(
        rag_settings.corpus.directory,
        collection_name=collection_name,
        rag_settings=rag_settings,
    )
    print(f"Stored {count} chunks in Qdrant collection '{collection_name}'.")


if __name__ == "__main__":
    main()

