"""Local RAG pipeline over the capstone corpus.

This is the endpoint-level pipeline used by the Streamlit UI. It loads the
same corpus from ``docs/corpus/``, chunks it, embeds the chunks, retrieves the
top matches for a question, and then generates a grounded answer.
"""

from __future__ import annotations

import asyncio
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .chunker import Chunk, chunk_corpus
from .embeddings_local import embed, embed_batch


DEFAULT_CORPUS_DIR = Path("docs/corpus")
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 3
DEFAULT_MODEL = "gpt-4o-mini"

PRICE_INPUT_PER_1M = {"gpt-4o-mini": 0.15, "gpt-4o": 2.50}
PRICE_OUTPUT_PER_1M = {"gpt-4o-mini": 0.60, "gpt-4o": 10.00}

DEFAULT_SYSTEM = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context. If the context does not contain the answer, say so "
    "plainly. Cite the source id in square brackets after any fact you use."
)


class RagAnswer(BaseModel):
    """Structured output from the RAG pipeline."""

    question: str
    content: str
    sources: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    retries: int = 0
    retrieved: list[dict[str, Any]] = Field(default_factory=list)


def _use_fake() -> bool:
    """Default to local offline mode unless explicitly disabled."""
    return os.getenv("RAG_USE_FAKE", "1").lower() not in {"0", "false", "no"}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


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
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Chunk the corpus and attach embeddings to every chunk."""
    chunks = chunk_corpus(corpus_dir, size=chunk_size, overlap=chunk_overlap)
    vectors = embed_batch([chunk.text for chunk in chunks])
    for chunk, vec in zip(chunks, vectors):
        chunk.vector = vec
    return chunks


@lru_cache(maxsize=4)
def _cached_index(corpus_dir: str, chunk_size: int, chunk_overlap: int) -> tuple[Chunk, ...]:
    """Cached index builder keyed by corpus and chunking settings."""
    return tuple(
        build_index(
            corpus_dir=corpus_dir,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    )


def get_index(
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Return the cached chunk index for the default corpus."""
    corpus_dir = str(Path(corpus_dir).resolve())
    return list(_cached_index(corpus_dir, chunk_size, chunk_overlap))


def retrieve(
    query: str,
    index: list[Chunk],
    *,
    k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Embed the query, rank chunks, and return the top matches."""
    q_vec = embed(query)
    scored: list[tuple[float, Chunk]] = []
    for chunk in index:
        vec = chunk.vector if chunk.vector is not None else embed(chunk.text)
        scored.append((_cosine(q_vec, vec), chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "text": chunk.text,
            "score": score,
        }
        for score, chunk in scored[:k]
    ]


def build_prompt(question: str, retrieved: list[dict[str, Any]], system: str = DEFAULT_SYSTEM) -> tuple[str, str]:
    """Return the system and user messages for the generator."""
    context = "\n\n".join(
        f"[{hit['chunk_id']}]\n{hit['text']}"
        for hit in retrieved
    )
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


def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate = PRICE_INPUT_PER_1M.get(model, 0.0)
    output_rate = PRICE_OUTPUT_PER_1M.get(model, 0.0)
    return (
        prompt_tokens * input_rate / 1_000_000
        + completion_tokens * output_rate / 1_000_000
    )


async def ask_rag(
    question: str,
    *,
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    top_k: int = DEFAULT_TOP_K,
    model: str = DEFAULT_MODEL,
) -> RagAnswer:
    """Run retrieval and answer generation over the capstone corpus."""
    index = get_index(corpus_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    retrieved = retrieve(question, index, k=top_k)
    sources = [hit["chunk_id"] for hit in retrieved]

    if _use_fake():
        content = _extractive_answer(question, retrieved)
        return RagAnswer(
            question=question,
            content=content,
            sources=sources,
            cost_usd=0.0,
            retries=0,
            retrieved=retrieved,
        )

    from dotenv import load_dotenv
    from openai import AsyncOpenAI

    load_dotenv()
    client = AsyncOpenAI()
    system_msg, user_msg = build_prompt(question, retrieved)
    resp = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    cost_usd = _compute_cost(model, prompt_tokens, completion_tokens)

    return RagAnswer(
        question=question,
        content=content,
        sources=sources,
        cost_usd=cost_usd,
        retries=0,
        retrieved=retrieved,
    )

