"""Typed configuration + run summary — Pydantic v2 models.

Two models with different roles:
  - Settings:    config (same every run; loaded at module init)
  - RunSummary:  observation (one row per execution; produced at run end)
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FixedCharacterChunkingSettings(BaseModel):
    """Settings for sliding-window character chunking."""

    chunk_size: int = Field(500, gt=0)
    chunk_overlap: int = Field(50, ge=0)


class StructureAwareChunkingSettings(BaseModel):
    """Settings for PyMuPDF heading-aware PDF chunking."""

    max_chunk_size: int = Field(500, gt=0)
    heading_font_size: float = Field(12.0, gt=0)
    title_font_size: float = Field(16.0, gt=0)


class SemanticChunkingSettings(BaseModel):
    """Settings for embedding-based consecutive-sentence chunking."""

    max_chunk_size: int = Field(500, gt=0)
    similarity_threshold: float = Field(0.55, ge=-1.0, le=1.0)


class ChunkingSettings(BaseModel):
    """Choose one chunking strategy and configure both strategies together."""

    # Possible values: "fixed", "structure_aware", "semantic".
    strategy: Literal["fixed", "structure_aware", "semantic"] = "structure_aware"
    fixed: FixedCharacterChunkingSettings = Field(default_factory=FixedCharacterChunkingSettings)
    structure_aware: StructureAwareChunkingSettings = Field(
        default_factory=StructureAwareChunkingSettings
    )
    semantic: SemanticChunkingSettings = Field(default_factory=SemanticChunkingSettings)


class MetadataSettings(BaseModel):
    """Metadata attached to every ingested PDF chunk."""

    enabled: bool = True
    language: str = "en"
    version: str = "latest"


class CorpusSettings(BaseModel):
    """Input documents for a reusable PDF corpus."""

    directory: Path = Path("docs/corpus_pdf_styled")
    file_glob: str = "*.pdf"
    # Retain .txt IDs for the existing golden set. Use ".pdf" for a new corpus if preferred.
    source_id_extension: str = ".txt"


class EmbeddingSettings(BaseModel):
    """Embedding model and batching used for indexing and dense retrieval."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = Field(64, gt=0)


class GenerationSettings(BaseModel):
    """LLM settings for grounded RAG answer generation."""

    model: str = "gpt-4o-mini"
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    system_prompt: str = (
        "You are a helpful assistant. Answer the user's question using ONLY the "
        "provided context. If the context does not contain the answer, say so "
        "plainly. Cite the source id in square brackets after any fact you use."
    )


class QdrantSettings(BaseModel):
    """Remote Qdrant connection and collection lifecycle settings."""

    url_env_var: str = "QDRANT_URL"
    api_key_env_var: str = "QDRANT_API_KEY"
    collection_prefix: str = "rag"
    upsert_batch_size: int = Field(128, gt=0)


class RetrievalSettings(BaseModel):
    """Select semantic-only or semantic-plus-BM25 retrieval."""

    # Possible values: "semantic", "hybrid".
    strategy: Literal["semantic", "hybrid"] = "hybrid"
    use_qdrant: bool = True
    top_k: int = Field(8, gt=0)
    rrf_k: int = Field(20, gt=0)
    max_context_chars: int = Field(5000, gt=0)
    # Possible values: True (cross-encoder reranking) or False (first-stage retrieval only).
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_candidate_k: int = Field(10, gt=0)


class RagSettings(BaseModel):
    """All RAG strategy settings, grouped in one place."""

    corpus: CorpusSettings = Field(default_factory=CorpusSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)

    def indexing_settings(self) -> dict[str, object]:
        """Return only settings that change chunk text or vector dimensions."""
        return {
            "corpus": self.corpus.model_dump(mode="json"),
            "chunking": self.chunking.model_dump(mode="json"),
            "metadata": self.metadata.model_dump(mode="json"),
            "embedding": self.embedding.model_dump(mode="json"),
        }

    def collection_name(self) -> str:
        """Derive a stable collection name from index-affecting settings."""
        payload = json.dumps(self.indexing_settings(), sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        corpus_name = re.sub(r"[^a-z0-9_]+", "_", self.corpus.directory.name.lower()).strip("_")
        return f"{self.qdrant.collection_prefix}_{corpus_name}_{self.chunking.strategy}_{fingerprint}"


class Settings(BaseModel):
    """Runtime configuration. Validated at construction."""

    questions_csv: Path  = Path("data/questions.csv")
    results_json:  Path  = Path("results.json")
    results_db:    Path  = Path("results.db")
    batch_size:    int   = Field(5,   gt=0, le=20)
    fail_rate:     float = Field(0.0, ge=0.0, le=1.0)
    model:         str   = "gpt-4o-mini"
    use_fake:      bool  = False
    rag:           RagSettings = Field(default_factory=RagSettings)


class RunSummary(BaseModel):
    """One row per pipeline execution. Persisted to the `runs` table."""

    started_at:       float
    elapsed_seconds:  float = Field(ge=0.0)
    n_questions:      int   = Field(ge=0)
    n_succeeded:      int   = Field(ge=0)
    n_retries_total:  int   = Field(ge=0)
    total_cost_usd:   float = Field(ge=0.0)
    fail_rate:        float = Field(ge=0.0, le=1.0)
    use_fake:         bool
