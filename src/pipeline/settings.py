"""Typed configuration + run summary — Pydantic v2 models.

Two models with different roles:
  - Settings:    config (same every run; loaded at module init)
  - RunSummary:  observation (one row per execution; produced at run end)
"""
from __future__ import annotations
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


class RetrievalSettings(BaseModel):
    """Select semantic-only or semantic-plus-BM25 retrieval."""

    # Possible values: "semantic", "hybrid".
    strategy: Literal["semantic", "hybrid"] = "hybrid"
    use_qdrant: bool = True
    collection_name: str = "public_policy_corpus"
    top_k: int = Field(8, gt=0)
    rrf_k: int = Field(20, gt=0)
    max_context_chars: int = Field(5000, gt=0)
    # Possible values: True (cross-encoder reranking) or False (first-stage retrieval only).
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_candidate_k: int = Field(10, gt=0)


class RagSettings(BaseModel):
    """All RAG strategy settings, grouped in one place."""

    corpus_dir: Path = Path("docs/corpus_pdf_styled")
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)


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
