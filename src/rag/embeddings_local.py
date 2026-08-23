"""Local embeddings for the capstone RAG pipeline.

If sentence-transformers is available, we use MiniLM. Otherwise we fall back
to a deterministic hashed bag-of-words embedding so the repo still runs
offline without extra downloads.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache


_model = None
_EMBED_DIM = 384


@lru_cache(maxsize=1)
def _get_model():
    """Load and cache the sentence-transformers model if installed."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        _model = None
        return None
    _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


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
    model = _get_model()
    if model is None:
        return _fallback_embed(text)
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings in one call."""
    model = _get_model()
    if model is None:
        return [_fallback_embed(text) for text in texts]
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()

