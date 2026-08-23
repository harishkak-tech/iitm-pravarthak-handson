"""Corpus loading and chunking utilities for the local RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    """One chunk of source text."""

    chunk_id: str
    source: str
    text: str
    vector: list[float] | None = None


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
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


def load_corpus_documents(corpus_dir: str | Path) -> list[dict[str, str]]:
    """Load corpus documents from a directory of .txt files."""
    corpus_dir = Path(corpus_dir)
    documents: list[dict[str, str]] = []
    for path in sorted(corpus_dir.glob("*.txt")):
        documents.append({"id": path.name, "text": path.read_text(encoding="utf-8")})
    return documents


def chunk_corpus(corpus_dir: str | Path, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Chunk every corpus document into a flat list with source pointers."""
    chunks: list[Chunk] = []
    for doc in load_corpus_documents(corpus_dir):
        for idx, chunk_text_value in enumerate(chunk_text(doc["text"], size=size, overlap=overlap)):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc['id']}#{idx}",
                    source=doc["id"],
                    text=chunk_text_value,
                )
            )
    return chunks

