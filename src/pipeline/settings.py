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
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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
    version: str = "corpus-v2"


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
    # None omits temperature for reasoning models that do not support it.
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    system_prompt: str = (
        "You are a careful Indian Government Policy assistant. Answer the user's question using "
        "ONLY the provided context. First consider all retrieved chunks, including "
        "chunks from different documents, and synthesize every relevant fact needed "
        "for a complete answer. Keep distinct lifecycle stages, records, statuses, "
        "exceptions, verification steps, and outcomes separate; do not collapse "
        "them into one generic answer. If the question has some terms and if the"
        "context has explaination of those terms , then see if the explaination of" 
        "those terms is needed for giving an accurate answer For example if family is the word used , "
        "then also see if you have a chunk which explain who all are considered part of family.If the context supports" 
        "only part of the answer, say what is supported and what is not available in the context. "
        "If the context does not contain the answer, say that you don't the answer for it. Cite the "
        "source id in square brackets after any fact you use. If some one asks you general questions which are not related to indian goivernment policies," 
        "then inform then that are you are supposed to answer only the questions related to policies of Indian government."
    )


class QdrantSettings(BaseModel):
    """Remote Qdrant connection and collection lifecycle settings."""

    provider: Literal["oci", "remote"] = "oci"
    url_env_var: str = "QDRANT_URL"
    api_key_env_var: str = "QDRANT_API_KEY"
    oci_url_env_var: str = "OCI_QDRANT_URL"
    oci_api_key_env_var: str = "OCI_QDRANT_API_KEY"
    timeout_seconds: int = Field(30, gt=0)
    read_retries: int = Field(1, ge=0, le=3)
    collection_prefix: str = "rag"
    upsert_batch_size: int = Field(128, gt=0)
    versioned_ingestion_enabled: bool = True


class RetrievalSettings(BaseModel):
    """Select semantic-only or semantic-plus-BM25 retrieval."""

    # Possible values: "semantic", "hybrid".
    strategy: Literal["semantic", "hybrid"] = "hybrid"
    use_qdrant: bool = True
    top_k: int = Field(8, gt=0)
    # Used only when hybrid retrieval or multi-query rewriting is enabled.
    rrf_k: int = Field(20, gt=0)
    max_context_chars: int = Field(5000, gt=0)
    context_budget_enabled: bool = True
    max_context_tokens: int | None = Field(None, gt=0)
    rerank_score_threshold: float | None = Field(None, allow_inf_nan=False)
    # Optional hard filters applied before retrieval/ranking, using Qdrant payload fields
    # and local chunk metadata. Examples: {"doc_type": "pdf"}, {"page": {"gte": 2}}.
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    # Week 9 multi-query rewrite: original query + LLM rewrites, then RRF-fuse results.
    query_rewrite_enabled: bool = True
    query_rewrite_n: int = Field(3, gt=0, le=10)
    query_rewrite_model: str = "gpt-4o-mini"
    query_rewrite_temperature: float = Field(0.4, ge=0.0, le=2.0)
    # Week 9 HyDE: draft a hypothetical answer and use it as the retrieval query.
    hypothetical_retrieval_enabled: bool = False
    hypothetical_retrieval_model: str = "gpt-4o-mini"
    hypothetical_retrieval_temperature: float = Field(0.3, ge=0.0, le=2.0)
    # Possible values: True (cross-encoder reranking) or False (first-stage retrieval only).
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    rerank_candidate_k: int = Field(15, gt=0)

    @model_validator(mode="after")
    def validate_score_gate(self):
        if self.rerank_score_threshold is not None and not self.rerank_enabled:
            raise ValueError("rerank_score_threshold requires rerank_enabled=True")
        return self


class RagSettings(BaseModel):
    """All RAG strategy settings, grouped in one place."""

    corpus: CorpusSettings = Field(default_factory=CorpusSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    validate_answer_citations: bool = True
    normalize_answer_citations: bool = True
    corpus_change_detection_enabled: bool = True
    citation_prompt_enabled: bool = True
    empty_evidence_abstention_enabled: bool = True
    trace_enabled: bool = True

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
        indexing = self.indexing_settings()
        # The golden runner uses absolute paths; ingestion normally uses relative
        # paths. Equivalent corpus folders must select the same collection.
        project_root = Path(__file__).resolve().parents[2]
        directory = self.corpus.directory
        resolved = (project_root / directory).resolve()
        try:
            canonical_directory = str(resolved.relative_to(project_root))
        except ValueError:
            canonical_directory = str(resolved)
        indexing["corpus"]["directory"] = canonical_directory
        payload = json.dumps(indexing, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        corpus_name = re.sub(r"[^a-z0-9_]+", "_", self.corpus.directory.name.lower()).strip("_")
        name = f"{self.qdrant.collection_prefix}_{corpus_name}_{self.chunking.strategy}_{fingerprint}"
        return name if self.qdrant.versioned_ingestion_enabled else f"{name}_unversioned"


class EvaluationSettings(BaseModel):
    """Evaluation switches; CLI options override these defaults."""

    kpis_enabled: bool = True
    metrics_mode: Literal["off", "offline-proxy", "live"] = "off"
    thresholds_enabled: bool = True
    # Opt in explicitly: this changes the rubric versus historical golden runs.
    citation_grounding_enabled: bool = False
    judge_model: str = "gpt-4o"
    # None keeps the existing JUDGE_USE_FAKE environment setting.
    judge_use_fake: bool | None = None


class GoldenSettings(BaseModel):
    """Defaults for evaluations launched from the UI or command line."""

    golden_path: Path = Path("docs/goldenset/golden_set.jsonl")
    question_limit: int | None = Field(None, gt=0)
    concurrency: int = Field(10, gt=0, le=20)
    batch_size: int = Field(10, gt=0, le=20)


class Settings(BaseModel):
    """Configuration schema and first-run defaults; runtime values live in SQLite."""

    questions_csv: Path  = Path("data/questions.csv")
    results_json:  Path  = Path("results.json")
    results_db:    Path  = Path("results.db")
    batch_size:    int   = Field(5,   gt=0, le=20)
    fail_rate:     float = Field(0.0, ge=0.0, le=1.0)
    model:         str   = "gpt-4o-mini"
    use_fake:      bool  = False
    rag:           RagSettings = Field(default_factory=RagSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    golden: GoldenSettings = Field(default_factory=GoldenSettings)


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
