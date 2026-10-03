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
import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .logging_config import get_logger
from .settings import RunSummary, Settings


log = get_logger()

RATES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}

DEFAULT_CORPUS_DIR = Path("docs/corpus")
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 3
DEFAULT_BM25_WEIGHT = 0.45
DEFAULT_MAX_CONTEXT_CHARS = 2000
DEFAULT_MODEL = "gpt-4o-mini"

PRICE_INPUT_PER_1M = {"gpt-4o-mini": 0.15, "gpt-4o": 2.50}
PRICE_OUTPUT_PER_1M = {"gpt-4o-mini": 0.60, "gpt-4o": 10.00}

DEFAULT_SYSTEM = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "provided context. If the context does not contain the answer, say so "
    "plainly. Cite the source id in square brackets after any fact you use."
)


_settings_for_import = Settings()

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


def load_corpus_documents(corpus_dir: str | Path) -> list[dict[str, str]]:
    """Load corpus documents from a directory of ``.txt`` files."""
    corpus_dir = Path(corpus_dir)
    documents: list[dict[str, str]] = []
    for path in sorted(corpus_dir.glob("*.txt")):
        documents.append({"id": path.name, "text": path.read_text(encoding="utf-8")})
    return documents


def chunk_corpus(corpus_dir: str | Path, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[Chunk]:
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


_embed_model = None
_EMBED_DIM = 384


@lru_cache(maxsize=1)
def _get_embed_model():
    """Load and cache the sentence-transformers model if installed."""
    global _embed_model
    if _embed_model is not None:
        return _embed_model
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        _embed_model = None
        return None
    _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _fallback_embed(text: str, dim: int = _EMBED_DIM) -> list[float]:
    """Deterministic local embedding based on hashed token counts."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    vector = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def embed(text: str) -> list[float]:
    """Embed a single string. Returns a normalized vector."""
    model = _get_embed_model()
    if model is None:
        return _fallback_embed(text)
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings in one call."""
    model = _get_embed_model()
    if model is None:
        return [_fallback_embed(text) for text in texts]
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()


def _use_fake_rag() -> bool:
    """Default to local offline mode unless explicitly disabled."""
    return os.getenv("RAG_USE_FAKE", "0").lower() not in {"0", "false", "no"}


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


def _normalize_scores(scores: list[float]) -> list[float]:
    """Scale scores to [0, 1] so lexical and semantic ranks can be combined."""
    if not scores:
        return []
    low = min(scores)
    high = max(scores)
    if math.isclose(low, high):
        return [1.0 if high else 0.0 for _ in scores]
    return [(score - low) / (high - low) for score in scores]


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
    """Return the cached chunk index for the corpus."""
    corpus_dir = str(Path(corpus_dir).resolve())
    return list(_cached_index(corpus_dir, chunk_size, chunk_overlap))


def retrieve(
    query: str,
    index: list[Chunk],
    *,
    k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Rank chunks with a hybrid of semantic similarity and BM25 lexical matching."""
    q_vec = embed(query)
    semantic_scores = [
        _cosine(q_vec, chunk.vector if chunk.vector is not None else embed(chunk.text))
        for chunk in index
    ]
    lexical_scores = bm25_scores(query, index)
    normalized_semantic = _normalize_scores(semantic_scores)
    normalized_lexical = _normalize_scores(lexical_scores)
    scored = [
        (
            (1 - DEFAULT_BM25_WEIGHT) * semantic + DEFAULT_BM25_WEIGHT * lexical,
            semantic_scores[position],
            lexical_scores[position],
            chunk,
        )
        for position, (chunk, semantic, lexical) in enumerate(
            zip(index, normalized_semantic, normalized_lexical)
        )
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "text": chunk.text,
            "score": score,
            "semantic_score": semantic_score,
            "bm25_score": bm25_score,
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
    corpus_dir: str | Path = DEFAULT_CORPUS_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    top_k: int = DEFAULT_TOP_K,
    model: str = DEFAULT_MODEL,
) -> RagAnswer:
    """Run retrieval and answer generation over the local corpus."""
    index = get_index(corpus_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    retrieved = retrieve(question, index, k=top_k)
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

    system_msg, user_msg = build_prompt(question, retrieved)
    resp = await _client.chat.completions.create(
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
    cost_usd = _compute_rag_cost(model, prompt_tokens, completion_tokens)

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
