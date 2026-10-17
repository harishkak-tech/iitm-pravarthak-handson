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

from src.pipeline.pipeline import get_index, index_corpus_in_qdrant
from src.pipeline.lifecycle import snapshot_version
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
    chunks = get_index(rag_settings.corpus.directory, chunking=rag_settings.chunking,
                       metadata=rag_settings.metadata, corpus_settings=rag_settings.corpus,
                       embedding=rag_settings.embedding,
                       detect_corpus_changes=rag_settings.corpus_change_detection_enabled)
    if rag_settings.qdrant.versioned_ingestion_enabled:
        print(f"Published knowledge-base version: {snapshot_version(chunks)}")
    else:
        print("Unversioned mode: this collection retains only the current ingestion.")


if __name__ == "__main__":
    main()

