"""Equivalent corpus paths must reuse the ingested Qdrant collection."""

import hashlib
import json
from pathlib import Path

from src.pipeline.settings import RagSettings


def test_absolute_and_relative_corpus_paths_reuse_existing_collection():
    base = RagSettings()
    existing_hash = hashlib.sha256(json.dumps(
        base.indexing_settings(), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()[:12]
    assert base.collection_name().endswith(existing_hash)
    absolute = base.model_copy(deep=True)
    absolute.corpus.directory = Path(__file__).resolve().parents[1] / base.corpus.directory
    assert absolute.collection_name() == base.collection_name()


def test_runtime_settings_reuse_collection():
    base = RagSettings()
    changed = base.model_copy(deep=True)
    changed.generation.model = "another-model"
    changed.retrieval.top_k = 2
    changed.retrieval.rerank_enabled = False
    changed.retrieval.rrf_k = 60
    assert changed.collection_name() == base.collection_name()


def test_index_settings_change_collection():
    base = RagSettings()
    for group, field, value in [
        ("chunking", "strategy", "fixed"),
        ("embedding", "model_name", "another-embedding"),
        ("metadata", "version", "v2"),
        ("corpus", "directory", Path("docs/other-corpus")),
    ]:
        changed = base.model_copy(deep=True)
        setattr(getattr(changed, group), field, value)
        assert changed.collection_name() != base.collection_name()
