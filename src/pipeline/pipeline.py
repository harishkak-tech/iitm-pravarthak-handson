"""Canonical pipeline module for batch QA and local RAG.

This module now owns the full implementation that used to be split across
multiple modules:

* batch question answering over ``data/questions.csv``
* retry/backoff and run summaries
* local corpus chunking, embedding, retrieval, and grounded answer generation

The RAG path remains available through ``ask_rag`` and is used by the API and
golden-set evaluation code.
"""

from __future__ import annotations

import asyncio
import csv
from collections import Counter
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .logging_config import get_logger
from .settings import (
    ChunkingSettings,
    CorpusSettings,
    EmbeddingSettings,
    MetadataSettings,
    RagSettings,
    RunSummary,
    Settings,
)


log = get_logger()

RATES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}

_settings_for_import = Settings()
_default_rag_settings = _settings_for_import.rag

# Compatibility aliases derived from the single source of truth in settings.py.
DEFAULT_CORPUS_DIR = _default_rag_settings.corpus.directory
DEFAULT_CHUNK_SIZE = _default_rag_settings.chunking.fixed.chunk_size
DEFAULT_CHUNK_OVERLAP = _default_rag_settings.chunking.fixed.chunk_overlap
DEFAULT_TOP_K = _default_rag_settings.retrieval.top_k
DEFAULT_MAX_CONTEXT_CHARS = _default_rag_settings.retrieval.max_context_chars
DEFAULT_MODEL = _default_rag_settings.generation.model
DEFAULT_QDRANT_COLLECTION = _default_rag_settings.collection_name()

PRICE_INPUT_PER_1M = {"gpt-4o-mini": 0.15, "gpt-4o": 2.50}
PRICE_OUTPUT_PER_1M = {"gpt-4o-mini": 0.60, "gpt-4o": 10.00}

DEFAULT_SYSTEM = _default_rag_settings.generation.system_prompt

if _settings_for_import.use_fake:
    from .fake_llm import Answer, FakeLLMError, Question, fake_ask_llm
else:
    from dotenv import load_dotenv
    from openai import AsyncOpenAI
    from openai.types import CompletionUsage
    import tiktoken

    load_dotenv()
    _client = AsyncOpenAI()

    class Question(BaseModel):
        text: str

    class Answer(BaseModel):
        question: str
        text: str
        cost_usd: float
        retries: int = 0
        finish_reason: str
        usage: CompletionUsage


class RagAnswer(BaseModel):
    """Structured output from the local RAG pipeline."""

    question: str
    content: str
    sources: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    retries: int = 0
    retrieved: list[dict[str, Any]] = Field(default_factory=list)


@dataclass
class Chunk:
    """One chunk of source text from the local corpus."""

    chunk_id: str
    source: str
    text: str
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_text(text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character chunks."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be in [0, size)")

    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _chunk_recursively(text: str, max_size: int) -> list[str]:
    """Prefer paragraph and sentence boundaries before a hard size split."""
    chunks: list[str] = []
    for paragraph in (part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()):
        paragraph = re.sub(r"\s+", " ", paragraph)
        if len(paragraph) <= max_size:
            chunks.append(paragraph)
            continue
        current = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if len(sentence) > max_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(chunk_text(sentence, size=max_size, overlap=0))
            elif not current or len(current) + len(sentence) + 1 <= max_size:
                current = f"{current} {sentence}".strip()
            else:
                chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)
    return chunks


def _load_pdf_documents(
    corpus_dir: str | Path,
    *,
    corpus_settings: CorpusSettings,
) -> list[dict[str, Any]]:
    """Extract styled PDFs with page text plus font-aware line metadata."""
    corpus_dir = Path(corpus_dir)
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF corpus ingestion requires PyMuPDF.") from exc

    paths = sorted(corpus_dir.glob(corpus_settings.file_glob))
    if not paths:
        raise ValueError(f"No PDF files found in corpus directory: {corpus_dir}")

    documents: list[dict[str, Any]] = []
    for path in paths:
        pages: list[dict[str, Any]] = []
        with pymupdf.open(path) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if not text:
                    continue
                lines: list[dict[str, Any]] = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        line_text = "".join(str(span["text"]) for span in spans).strip()
                        if line_text:
                            lines.append(
                                {
                                    "text": line_text,
                                    "font_size": max(float(span["size"]) for span in spans),
                                    "bold": any("bold" in str(span["font"]).lower() for span in spans),
                                }
                            )
                pages.append({"number": page_number, "text": text, "lines": lines})
        if not pages:
            raise ValueError(f"No extractable text found in PDF corpus document: {path}")
        documents.append({"id": f"{path.stem}{corpus_settings.source_id_extension}", "pages": pages})
    return documents


def load_corpus_documents(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    *,
    corpus_settings: CorpusSettings | None = None,
) -> list[dict[str, str]]:
    """Load the styled PDF corpus as text documents for inspection or evaluation."""
    return [
        {"id": str(document["id"]), "text": "\n\n".join(page["text"] for page in document["pages"])}
        for document in _load_pdf_documents(
            corpus_dir,
            corpus_settings=corpus_settings or _default_rag_settings.corpus,
        )
    ]


def _chunk_metadata(
    source: str,
    page_number: int,
    section_path: str,
    settings: MetadataSettings,
) -> dict[str, Any]:
    if not settings.enabled:
        return {}
    return {
        "doc_type": "pdf",
        "section_path": section_path,
        "page": page_number,
        "language": settings.language,
        "version": settings.version,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def chunk_corpus(
    corpus_dir: str | Path,
    *,
    chunking: ChunkingSettings,
    metadata: MetadataSettings,
    corpus_settings: CorpusSettings,
    embedding: EmbeddingSettings,
) -> list[Chunk]:
    """Chunk configured PDF documents using the selected strategy."""
    chunks: list[Chunk] = []
    for document in _load_pdf_documents(corpus_dir, corpus_settings=corpus_settings):
        source = str(document["id"])
        section_path: list[str] = []
        for page in document["pages"]:
            page_number = int(page["number"])
            if chunking.strategy == "fixed":
                text_chunks = [("", text) for text in chunk_text(
                    page["text"],
                    size=chunking.fixed.chunk_size,
                    overlap=chunking.fixed.chunk_overlap,
                )]
            elif chunking.strategy == "structure_aware":
                text_chunks: list[tuple[str, str]] = []
                section_lines: list[str] = []

                def flush_section() -> None:
                    if not section_lines:
                        return
                    path = " > ".join(section_path)
                    body = "\n".join(section_lines)
                    for value in _chunk_recursively(body, chunking.structure_aware.max_chunk_size):
                        text_chunks.append((path, f"{path}\n\n{value}".strip()))
                    section_lines.clear()

                for line in page["lines"]:
                    is_heading = bool(line["bold"]) and (
                        float(line["font_size"])
                        >= chunking.structure_aware.heading_font_size
                    )
                    if is_heading:
                        flush_section()
                        if float(line["font_size"]) >= chunking.structure_aware.title_font_size:
                            section_path = [str(line["text"])]
                        else:
                            section_path = [*section_path[:1], str(line["text"])]
                    else:
                        section_lines.append(str(line["text"]))
                flush_section()
            else:
                text_chunks = [
                    ("", text)
                    for text in _chunk_semantically(
                        page["text"],
                        max_size=chunking.semantic.max_chunk_size,
                        similarity_threshold=chunking.semantic.similarity_threshold,
                        embedding_model=embedding.model_name,
                        embedding_batch_size=embedding.batch_size,
                    )
                ]

            for chunk_number, (path, text) in enumerate(text_chunks):
                chunks.append(
                    Chunk(
                        chunk_id=f"{source}#page-{page_number}-chunk-{chunk_number}",
                        source=source,
                        text=text,
                        metadata=_chunk_metadata(source, page_number, path, metadata),
                    )
                )
    return chunks


_embed_models: dict[str, Any] = {}
_cross_encoder_models: dict[str, Any] = {}


def _get_embed_model(model_name: str | None = None) -> Any:
    """Load and cache the required sentence-transformers embedding model."""
    model_name = model_name or _default_rag_settings.embedding.model_name
    if model_name in _embed_models:
        return _embed_models[model_name]
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Embedding requires sentence-transformers and the all-MiniLM-L6-v2 model. "
            "Install project dependencies before running ingestion or retrieval."
        ) from exc
    _embed_models[model_name] = SentenceTransformer(model_name)
    return _embed_models[model_name]


def embed(text: str, *, model_name: str | None = None) -> list[float]:
    """Embed a single string. Returns a normalized vector."""
    model = _get_embed_model(model_name)
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(
    texts: list[str],
    *,
    batch_size: int | None = None,
    model_name: str | None = None,
) -> list[list[float]]:
    """Embed texts in bounded batches so large corpus ingestion remains memory-safe."""
    batch_size = batch_size or _default_rag_settings.embedding.batch_size
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    model = _get_embed_model(model_name)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        encoded = model.encode(
            batch,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors.extend(encoded.tolist())
    return vectors


def _get_cross_encoder(model_name: str) -> Any:
    """Load and cache the configured cross-encoder reranker."""
    if model_name in _cross_encoder_models:
        return _cross_encoder_models[model_name]
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "Cross-encoder reranking requires sentence-transformers. "
            "Install project dependencies before running RAG."
        ) from exc
    try:
        model = CrossEncoder(model_name)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load cross-encoder model '{model_name}'. "
            "Ensure the model is available locally or can be downloaded."
        ) from exc
    _cross_encoder_models[model_name] = model
    return model


def rerank_with_cross_encoder(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int,
    model_name: str,
) -> list[dict[str, Any]]:
    """Score retrieved candidates with a cross-encoder and return the strongest ones."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not candidates:
        return []

    model = _get_cross_encoder(model_name)
    scores = model.predict([(query, str(candidate["text"])) for candidate in candidates])
    scored = [
        {**candidate, "rerank_score": float(score)}
        for candidate, score in zip(candidates, scores)
    ]
    scored.sort(key=lambda candidate: candidate["rerank_score"], reverse=True)
    return scored[:top_k]


def _chunk_semantically(
    text: str,
    *,
    max_size: int,
    similarity_threshold: float,
    embedding_model: str | None = None,
    embedding_batch_size: int | None = None,
) -> list[str]:
    """Group consecutive sentences until their semantic similarity drops."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    if not -1.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be in [-1, 1]")

    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if not sentences:
        return []
    if len(sentences) == 1:
        return chunk_text(sentences[0], size=max_size, overlap=0)

    vectors = embed_batch(
        sentences,
        batch_size=embedding_batch_size,
        model_name=embedding_model,
    )
    chunks: list[str] = []
    current_sentences = [sentences[0]]
    current_length = len(sentences[0])

    for position in range(1, len(sentences)):
        sentence = sentences[position]
        similarity = _cosine(vectors[position - 1], vectors[position])
        exceeds_limit = current_length + len(sentence) + 1 > max_size
        if similarity < similarity_threshold or exceeds_limit:
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentence]
            current_length = len(sentence)
        else:
            current_sentences.append(sentence)
            current_length += len(sentence) + 1

    if current_sentences:
        chunks.append(" ".join(current_sentences))
    return [
        piece
        for chunk in chunks
        for piece in chunk_text(chunk, size=max_size, overlap=0)
    ]


def _use_fake_rag() -> bool:
    """Use the configured offline mode for RAG generation."""
    return _settings_for_import.use_fake


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_scores(
    query: str,
    index: list[Chunk],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Return BM25 scores for each chunk, preserving index order."""
    query_terms = _tokenize(query)
    if not index or not query_terms:
        return [0.0] * len(index)

    document_terms = [_tokenize(chunk.text) for chunk in index]
    document_frequency = Counter(
        term for terms in document_terms for term in set(terms)
    )
    average_length = sum(len(terms) for terms in document_terms) / len(document_terms)
    scores: list[float] = []

    for terms in document_terms:
        term_frequency = Counter(terms)
        length_normalizer = k1 * (1 - b + b * len(terms) / max(average_length, 1.0))
        score = 0.0
        for term in set(query_terms):
            frequency = term_frequency.get(term, 0)
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(index) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            score += inverse_frequency * (frequency * (k1 + 1)) / (frequency + length_normalizer)
        scores.append(score)
    return scores


def rrf_fuse(ranked_lists: list[list[str]], *, rrf_k: int = 60) -> dict[str, float]:
    """Fuse ranked chunk IDs with Reciprocal Rank Fusion."""
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")

    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a ** 0.5 * norm_b ** 0.5)


def build_index(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    *,
    chunking: ChunkingSettings | None = None,
    metadata: MetadataSettings | None = None,
    corpus_settings: CorpusSettings | None = None,
    embedding: EmbeddingSettings | None = None,
) -> list[Chunk]:
    """Chunk the corpus and attach embeddings to every chunk."""
    rag = _settings_for_import.rag
    corpus_settings = corpus_settings or rag.corpus
    embedding = embedding or rag.embedding
    chunks = chunk_corpus(
        corpus_dir,
        chunking=chunking or rag.chunking,
        metadata=metadata or rag.metadata,
        corpus_settings=corpus_settings,
        embedding=embedding,
    )
    vectors = embed_batch(
        [chunk.text for chunk in chunks],
        batch_size=embedding.batch_size,
        model_name=embedding.model_name,
    )
    for chunk, vec in zip(chunks, vectors):
        chunk.vector = vec
    return chunks


@lru_cache(maxsize=4)
def _cached_index(corpus_dir: str, settings_json: str) -> tuple[Chunk, ...]:
    """Cached index builder keyed by corpus and chunking settings."""
    payload = json.loads(settings_json)
    return tuple(
        build_index(
            corpus_dir=corpus_dir,
            chunking=ChunkingSettings.model_validate(payload["chunking"]),
            metadata=MetadataSettings.model_validate(payload["metadata"]),
            corpus_settings=CorpusSettings.model_validate(payload["corpus"]),
            embedding=EmbeddingSettings.model_validate(payload["embedding"]),
        )
    )


def get_index(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    *,
    chunking: ChunkingSettings | None = None,
    metadata: MetadataSettings | None = None,
    corpus_settings: CorpusSettings | None = None,
    embedding: EmbeddingSettings | None = None,
) -> list[Chunk]:
    """Return the cached chunk index for the corpus."""
    corpus_dir = str(Path(corpus_dir).resolve())
    rag = _settings_for_import.rag
    corpus_settings = corpus_settings or rag.corpus
    embedding = embedding or rag.embedding
    settings_json = json.dumps(
        {
            "chunking": (chunking or rag.chunking).model_dump(mode="json"),
            "metadata": (metadata or rag.metadata).model_dump(mode="json"),
            "corpus": corpus_settings.model_dump(mode="json"),
            "embedding": embedding.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    return list(_cached_index(corpus_dir, settings_json))


def get_qdrant_client(rag_settings: RagSettings | None = None) -> Any:
    """Return a client for the configured remote Qdrant server."""
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError(
            "Qdrant support requires qdrant-client. Install dependencies before indexing."
        ) from exc

    qdrant_settings = (rag_settings or _default_rag_settings).qdrant
    url = os.getenv(qdrant_settings.url_env_var)
    if not url:
        raise RuntimeError(
            f"{qdrant_settings.url_env_var} is required. Configure a remote Qdrant server before "
            "running ingestion or retrieval."
        )
    api_key = os.getenv(qdrant_settings.api_key_env_var) or None
    return QdrantClient(url=url, api_key=api_key) if api_key else QdrantClient(url=url)


def persist_chunks_to_qdrant(
    chunks: list[Chunk],
    *,
    collection_name: str,
    rag_settings: RagSettings | None = None,
) -> int:
    """Create a new collection or overwrite one with the same index settings."""
    if not chunks:
        return 0
    rag = rag_settings or _default_rag_settings
    upsert_batch_size = rag.qdrant.upsert_batch_size

    try:
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ImportError as exc:
        raise RuntimeError(
            "Qdrant support requires qdrant-client. Install dependencies before indexing."
        ) from exc

    vectors = [
        chunk.vector
        if chunk.vector is not None
        else embed(chunk.text, model_name=rag.embedding.model_name)
        for chunk in chunks
    ]
    client = get_qdrant_client(rag)
    # Qdrant recreates an existing matching configuration collection or creates a new one.
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
    )
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
            vector=vector,
            payload={
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "text": chunk.text,
                "indexing_settings": rag.indexing_settings(),
                "collection_name": collection_name,
                **chunk.metadata,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    for start in range(0, len(points), upsert_batch_size):
        client.upsert(
            collection_name=collection_name,
            points=points[start : start + upsert_batch_size],
        )
    client.close()
    return len(points)


def index_corpus_in_qdrant(
    corpus_dir: str | Path | None = None,
    *,
    collection_name: str | None = None,
    rag_settings: RagSettings | None = None,
) -> int:
    """Build the configured PDF chunk index, then persist it to Qdrant."""
    rag = rag_settings or _settings_for_import.rag
    resolved_collection_name = collection_name or rag.collection_name()
    return persist_chunks_to_qdrant(
        get_index(
            corpus_dir or rag.corpus.directory,
            chunking=rag.chunking,
            metadata=rag.metadata,
            corpus_settings=rag.corpus,
            embedding=rag.embedding,
        ),
        collection_name=resolved_collection_name,
        rag_settings=rag,
    )


def retrieve_from_qdrant(
    query: str,
    *,
    k: int = DEFAULT_TOP_K,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    rag_settings: RagSettings | None = None,
) -> list[dict[str, Any]]:
    """Retrieve dense chunk matches from a previously indexed Qdrant collection."""
    if k <= 0:
        raise ValueError("k must be positive")

    rag = rag_settings or _default_rag_settings
    client = get_qdrant_client(rag)
    try:
        results = client.query_points(
            collection_name=collection_name,
            query=embed(query, model_name=rag.embedding.model_name),
            limit=k,
        ).points
    finally:
        client.close()
    return [
        {
            "chunk_id": str(hit.payload.get("chunk_id", "unknown")),
            "source": str(hit.payload.get("source", "unknown")),
            "text": str(hit.payload.get("text", "")),
            "score": float(hit.score),
            "metadata": {
                key: value
                for key, value in hit.payload.items()
                if key not in {"chunk_id", "source", "text"}
            },
        }
        for hit in results
    ]


def _retrieve_with_qdrant_hybrid(
    query: str,
    index: list[Chunk],
    *,
    k: int,
    rrf_k: int,
    collection_name: str,
    rag_settings: RagSettings,
) -> list[dict[str, Any]]:
    """Fuse Qdrant dense candidates with locally computed BM25 candidates."""
    candidate_limit = max(k * 4, 20)
    try:
        dense_hits = retrieve_from_qdrant(
            query,
            k=candidate_limit,
            collection_name=collection_name,
            rag_settings=rag_settings,
        )
    except Exception as exc:
        raise RuntimeError(
            "Qdrant retrieval is unavailable. Run `python scripts/ingest_qdrant.py` "
            "after installing dependencies, then retry."
        ) from exc

    dense_by_id = {str(hit["chunk_id"]): float(hit["score"]) for hit in dense_hits}
    chunks_by_id = {chunk.chunk_id: chunk for chunk in index}
    lexical_scores = bm25_scores(query, index)
    lexical_ranked = sorted(
        enumerate(lexical_scores),
        key=lambda item: item[1],
        reverse=True,
    )[:candidate_limit]

    lexical_ids = [index[position].chunk_id for position, _ in lexical_ranked]
    rrf_scores = rrf_fuse([list(dense_by_id), lexical_ids], rrf_k=rrf_k)
    if not rrf_scores:
        return []

    lexical_by_id = {chunk.chunk_id: lexical_scores[position] for position, chunk in enumerate(index)}
    scored = [
        (
            rrf_score,
            dense_by_id.get(chunk_id),
            lexical_by_id.get(chunk_id, 0.0),
            chunks_by_id[chunk_id],
        )
        for chunk_id, rrf_score in rrf_scores.items()
        if chunk_id in chunks_by_id
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "text": chunk.text,
            "score": score,
            "rrf_score": score,
            "semantic_score": semantic_score,
            "bm25_score": bm25_score,
            "metadata": chunk.metadata,
        }
        for score, semantic_score, bm25_score, chunk in scored[:k]
    ]


def retrieve(
    query: str,
    index: list[Chunk],
    *,
    k: int = DEFAULT_TOP_K,
    use_qdrant: bool = False,
    strategy: str = "hybrid",
    rrf_k: int = 60,
    collection_name: str = DEFAULT_QDRANT_COLLECTION,
    rag_settings: RagSettings | None = None,
) -> list[dict[str, Any]]:
    """Rank chunks with configured semantic-only or hybrid retrieval."""
    if strategy not in {"semantic", "hybrid"}:
        raise ValueError("strategy must be 'semantic' or 'hybrid'")
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    rag = rag_settings or _default_rag_settings
    if use_qdrant:
        if strategy == "semantic":
            return retrieve_from_qdrant(
                query,
                k=k,
                collection_name=collection_name,
                rag_settings=rag,
            )
        return _retrieve_with_qdrant_hybrid(
            query,
            index,
            k=k,
            rrf_k=rrf_k,
            collection_name=collection_name,
            rag_settings=rag,
        )
    q_vec = embed(query, model_name=rag.embedding.model_name)
    semantic_scores = [
        _cosine(
            q_vec,
            chunk.vector
            if chunk.vector is not None
            else embed(chunk.text, model_name=rag.embedding.model_name),
        )
        for chunk in index
    ]
    if strategy == "semantic":
        scored = [
            (semantic_score, semantic_score, 0.0, chunk)
            for semantic_score, chunk in zip(semantic_scores, index)
        ]
    else:
        candidate_limit = max(k * 4, 20)
        semantic_ranked = sorted(
            range(len(index)), key=lambda position: semantic_scores[position], reverse=True
        )[:candidate_limit]
        lexical_scores = bm25_scores(query, index)
        lexical_ranked = sorted(
            range(len(index)), key=lambda position: lexical_scores[position], reverse=True
        )[:candidate_limit]
        rrf_scores = rrf_fuse(
            [
                [index[position].chunk_id for position in semantic_ranked],
                [index[position].chunk_id for position in lexical_ranked],
            ],
            rrf_k=rrf_k,
        )
        by_id = {chunk.chunk_id: (position, chunk) for position, chunk in enumerate(index)}
        scored = [
            (
                score,
                semantic_scores[by_id[chunk_id][0]],
                lexical_scores[by_id[chunk_id][0]],
                by_id[chunk_id][1],
            )
            for chunk_id, score in rrf_scores.items()
        ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "text": chunk.text,
            "score": score,
            "rrf_score": score if strategy == "hybrid" else None,
            "semantic_score": semantic_score,
            "bm25_score": bm25_score,
            "metadata": chunk.metadata,
        }
        for score, semantic_score, bm25_score, chunk in scored[:k]
    ]


def format_retrieved_context(
    retrieved: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """Format retrieved chunks without allowing a record to flood the prompt."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    sections: list[str] = []
    remaining = max_chars
    for hit in retrieved:
        chunk_id = str(hit.get("chunk_id", "unknown"))
        text = str(hit.get("text", "")).strip()
        if not text or remaining <= 0:
            continue

        separator = "\n\n" if sections else ""
        available = remaining - len(separator)
        prefix = f"[{chunk_id}]\n"
        if len(prefix) >= available:
            break
        section = prefix + text[: available - len(prefix)]
        sections.append(section)
        remaining -= len(separator) + len(section)

    return "\n\n".join(sections)


def build_prompt(
    question: str,
    retrieved: list[dict[str, Any]],
    system: str = DEFAULT_SYSTEM,
    *,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> tuple[str, str]:
    """Return the system and user messages for the generator."""
    context = format_retrieved_context(retrieved, max_chars=max_context_chars)
    user_msg = (
        f"Context:\n{context}\n\n"
        f"---\n\nQuestion: {question}\n"
        "Answer:"
    )
    return system, user_msg


def _sentence_summary(text: str, max_sentences: int = 2) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentence for sentence in sentences[:max_sentences] if sentence)


def _extractive_answer(question: str, retrieved: list[dict[str, Any]]) -> str:
    """Offline answer mode that summarizes the strongest retrieved chunks."""
    if not retrieved:
        return "I could not find enough information in the corpus to answer that."

    top = retrieved[0]
    top_score = float(top.get("score", 0.0))
    if top_score < 0.08:
        return "I could not find enough information in the corpus to answer that."

    summary = _sentence_summary(top["text"], max_sentences=2)
    if len(retrieved) > 1:
        second = _sentence_summary(retrieved[1]["text"], max_sentences=1)
        if second and second not in summary:
            summary = f"{summary} {second}"

    source_ids = ", ".join(hit["chunk_id"] for hit in retrieved)
    return f"{summary} [Sources: {source_ids}]"


def _compute_rag_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate = PRICE_INPUT_PER_1M.get(model, 0.0)
    output_rate = PRICE_OUTPUT_PER_1M.get(model, 0.0)
    return (
        prompt_tokens * input_rate / 1_000_000
        + completion_tokens * output_rate / 1_000_000
    )


async def ask_rag(
    question: str,
    *,
    corpus_dir: str | Path | None = None,
    top_k: int | None = None,
    model: str | None = None,
    rag_settings: RagSettings | None = None,
    use_qdrant: bool | None = None,
) -> RagAnswer:
    """Run RAG using the selected chunking and retrieval settings."""
    rag = rag_settings or _settings_for_import.rag
    retrieval = rag.retrieval
    result_count = top_k or retrieval.top_k
    candidate_count = (
        max(result_count, retrieval.rerank_candidate_k)
        if retrieval.rerank_enabled
        else result_count
    )
    index = get_index(
        corpus_dir or rag.corpus.directory,
        chunking=rag.chunking,
        metadata=rag.metadata,
        corpus_settings=rag.corpus,
        embedding=rag.embedding,
    )
    retrieved = retrieve(
        question,
        index,
        k=candidate_count,
        use_qdrant=retrieval.use_qdrant if use_qdrant is None else use_qdrant,
        strategy=retrieval.strategy,
        rrf_k=retrieval.rrf_k,
        collection_name=rag.collection_name(),
        rag_settings=rag,
    )
    if retrieval.rerank_enabled:
        retrieved = rerank_with_cross_encoder(
            question,
            retrieved,
            top_k=result_count,
            model_name=retrieval.rerank_model,
        )
    sources = [hit["chunk_id"] for hit in retrieved]

    if _use_fake_rag():
        content = _extractive_answer(question, retrieved)
        return RagAnswer(
            question=question,
            content=content,
            sources=sources,
            cost_usd=0.0,
            retries=0,
            retrieved=retrieved,
        )

    system_msg, user_msg = build_prompt(
        question,
        retrieved,
        system=rag.generation.system_prompt,
        max_context_chars=retrieval.max_context_chars,
    )
    resp = await _client.chat.completions.create(
        model=model or rag.generation.model,
        temperature=rag.generation.temperature,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    cost_usd = _compute_rag_cost(model or rag.generation.model, prompt_tokens, completion_tokens)

    return RagAnswer(
        question=question,
        content=content,
        sources=sources,
        cost_usd=cost_usd,
        retries=0,
        retrieved=retrieved,
    )


def load_questions(path: str | Path = "data/questions.csv") -> list[Question]:
    """Read questions from a CSV with a ``text`` column."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Question(text=row["text"]) for row in rows if row.get("text")]


async def ask_llm(q: Question, fail_rate: float = 0.0) -> Answer:
    """One LLM call. Branches on ``Settings.use_fake``."""
    if _settings_for_import.use_fake:
        ans = await fake_ask_llm(q, fail_rate=fail_rate)
    else:
        resp = await _client.chat.completions.create(
            model=_settings_for_import.model,
            messages=[{"role": "user", "content": q.text}],
        )
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or count_tokens(q.text, _settings_for_import.model))
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or count_tokens(content, _settings_for_import.model))
        ans = Answer(
            question=q.text,
            text=content,
            cost_usd=compute_cost(_settings_for_import.model, prompt_tokens, completion_tokens),
            finish_reason=resp.choices[0].finish_reason or "stop",
            usage=usage,
        )
    log.info("asked: %s", q.text[:40])
    return ans


async def ask_llm_with_retry(
    q: Question,
    tries: int = 3,
    fail_rate: float = 0.0,
) -> Answer:
    """Retry up to ``tries`` times with exponential backoff."""
    for attempt in range(tries):
        try:
            ans = await ask_llm(q, fail_rate=fail_rate)
            ans.retries = attempt
            return ans
        except Exception as exc:
            if attempt == tries - 1:
                raise
            log.warning("retry %s for: %s (%s)", attempt + 1, q.text[:40], exc)
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


async def run_batch(
    questions: list[Question],
    fail_rate: float = 0.0,
) -> list[Answer]:
    """Fire every question in parallel via a single ``asyncio.gather``."""
    tasks = [ask_llm_with_retry(q, fail_rate=fail_rate) for q in questions]
    return await asyncio.gather(*tasks)


async def run_in_batches(
    questions: list[Question],
    batch_size: int = 5,
    fail_rate: float = 0.0,
) -> list[Answer]:
    """Fire questions in chunks of ``batch_size`` with a short pause between batches."""
    out: list[Answer] = []
    for i in range(0, len(questions), batch_size):
        chunk = questions[i : i + batch_size]
        log.info("batch %s: %s questions", i // batch_size + 1, len(chunk))
        batch_answers = await asyncio.gather(
            *(ask_llm_with_retry(q, fail_rate=fail_rate) for q in chunk)
        )
        out.extend(batch_answers)
        await asyncio.sleep(0.1)
    return out


def summarise_run(
    answers: list[Answer],
    *,
    started_at: float,
    elapsed: float,
    fail_rate: float,
    use_fake: bool,
) -> RunSummary:
    """Roll a list of answers plus runtime data into a ``RunSummary``."""
    return RunSummary(
        started_at=started_at,
        elapsed_seconds=elapsed,
        n_questions=len(answers),
        n_succeeded=len(answers),
        n_retries_total=sum(a.retries for a in answers),
        total_cost_usd=sum(a.cost_usd for a in answers),
        fail_rate=fail_rate,
        use_fake=use_fake,
    )


def compute_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    """Cost = token counts multiplied by the configured rates."""
    in_rate, out_rate = RATES.get(model, (0.0, 0.0))
    return (in_tokens * in_rate + out_tokens * out_rate) / 1_000_000


def count_tokens(text: str, model: str) -> int:
    try:
        import tiktoken as _tiktoken

        enc = _tiktoken.encoding_for_model(model)
    except Exception:
        import tiktoken as _tiktoken

        enc = _tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def _build_results_payload(summary: RunSummary, answers: list[Answer]) -> dict[str, Any]:
    return {
        "summary": summary.model_dump(mode="json"),
        "answers": [a.model_dump() for a in answers],
    }


def main() -> None:
    """CLI entrypoint used by ``python -m src.pipeline.pipeline``."""
    settings = Settings()
    log.info("config: %s", settings.model_dump(mode="json"))

    questions = load_questions(settings.questions_csv)
    log.info("loaded %s questions", len(questions))

    started = time.time()
    answers = asyncio.run(
        run_in_batches(
            questions,
            batch_size=settings.batch_size,
            fail_rate=settings.fail_rate,
        )
    )
    elapsed = time.time() - started

    summary = summarise_run(
        answers,
        started_at=started,
        elapsed=elapsed,
        fail_rate=settings.fail_rate,
        use_fake=settings.use_fake,
    )
    log.info("summary: %s", summary.model_dump_json())

    settings.results_json.write_text(
        json.dumps(_build_results_payload(summary, answers), indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(answers)} answers to {settings.results_json} in {elapsed:.2f}s")

    from .store import connect, write_answers, write_run

    with connect(settings.results_db) as con:
        run_id = write_run(con, summary)
        n = write_answers(con, run_id, answers)
    log.info("persisted run %s with %s answers to %s", run_id, n, settings.results_db)


if __name__ == "__main__":
    main()
