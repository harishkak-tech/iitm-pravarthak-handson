"""Content-addressed KB snapshots and non-destructive Qdrant publication."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def corpus_fingerprint(directory, file_glob="*.pdf") -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(directory).glob(file_glob)):
        digest.update(path.name.encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()[:20]


def snapshot_version(chunks) -> str:
    rows = sorted((c.chunk_id, c.source, c.text,
                   {k: v for k, v in c.metadata.items() if k not in {"ingested_at", "deleted_at", "kb_version"}})
                  for c in chunks)
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:20]


def live_filter(metadata_filter=None):
    from qdrant_client.models import FieldCondition, Filter, IsEmptyCondition, MatchValue, PayloadField
    return Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="deleted_at")),
                        FieldCondition(key="snapshot_ready", match=MatchValue(value=True)),
                        *([metadata_filter] if metadata_filter is not None else [])])


def publish_unversioned(client, collection_name, chunks, vectors, indexing_settings, batch_size=128):
    """Legacy replacement behavior, isolated from collections retaining snapshot history."""
    from qdrant_client.models import Distance, PointStruct, VectorParams
    if not collection_name.endswith("_unversioned"):
        raise ValueError("Unversioned ingestion requires a collection ending in _unversioned")
    if not chunks or len(chunks) != len(vectors):
        raise ValueError("Every chunk requires a vector")
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name=collection_name)
    client.create_collection(collection_name=collection_name,
        vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
    points = [PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)), vector=v,
        payload={**c.metadata, "chunk_id": c.chunk_id, "source": c.source, "text": c.text,
                 "indexing_settings": indexing_settings, "collection_name": collection_name})
        for c, v in zip(chunks, vectors)]
    for start in range(0, len(points), batch_size):
        client.upsert(collection_name=collection_name, points=points[start:start + batch_size], wait=True)
    return len(points)


def publish_snapshot(client, collection_name, chunks, vectors, indexing_settings, batch_size=128):
    """Upload before retiring older snapshots. Failed uploads leave the old snapshot intact.

    Callers serialize ingestion per collection. Query-time kb_version filters prevent
    mixing versions even during an interrupted publication.
    """
    from qdrant_client.models import (
        Distance, FieldCondition, Filter, IsEmptyCondition, MatchValue, PayloadField, PayloadSchemaType,
        PointStruct, VectorParams,
    )
    if not chunks:
        raise ValueError("Refusing to publish an empty corpus")
    if len(vectors) != len(chunks) or not vectors or not vectors[0]:
        raise ValueError("Every chunk requires a nonempty vector")
    if batch_size <= 0 or any(len(v) != len(vectors[0]) for v in vectors):
        raise ValueError("Batch size must be positive and vector dimensions must match")
    if len({c.chunk_id for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs in snapshot")
    version = snapshot_version(chunks)
    if not client.collection_exists(collection_name):
        client.create_collection(collection_name=collection_name,
                                 vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE))
    schemas = {"kb_version": PayloadSchemaType.KEYWORD, "source": PayloadSchemaType.KEYWORD,
               "deleted_at": PayloadSchemaType.KEYWORD, "doc_type": PayloadSchemaType.KEYWORD,
               "language": PayloadSchemaType.KEYWORD, "version": PayloadSchemaType.KEYWORD,
               "page": PayloadSchemaType.INTEGER, "section_path": PayloadSchemaType.KEYWORD,
               "snapshot_ready": PayloadSchemaType.BOOL}
    for key, schema in schemas.items():
        client.create_payload_index(collection_name=collection_name, field_name=key,
                                    field_schema=schema, wait=True)
    version_filter = Filter(must=[FieldCondition(key="kb_version", match=MatchValue(value=version))])
    already_published = client.count(collection_name=collection_name, count_filter=live_filter(version_filter), exact=True).count == len(chunks)
    points = [PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{version}:{c.chunk_id}")),
                          vector=v, payload={**c.metadata, "chunk_id": c.chunk_id,
                          "source": c.source, "text": c.text, "kb_version": version,
                          "deleted_at": None, "indexing_settings": indexing_settings,
                          "snapshot_ready": False,
                          "collection_name": collection_name}) for c, v in zip(chunks, vectors)]
    if not already_published:
        for start in range(0, len(points), batch_size):
            client.upsert(collection_name=collection_name, points=points[start:start + batch_size], wait=True)
        client.set_payload(collection_name=collection_name, payload={"snapshot_ready": True},
                           points=version_filter, wait=True)
    client.set_payload(collection_name=collection_name,
                       payload={"deleted_at": datetime.now(timezone.utc).isoformat()},
                       points=Filter(must=[IsEmptyCondition(is_empty=PayloadField(key="deleted_at"))], must_not=[
                           FieldCondition(key="kb_version", match=MatchValue(value=version))]), wait=True)
    return len(points)
