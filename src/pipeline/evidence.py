"""Evidence selection and reference validation; valid references do not prove support."""
from __future__ import annotations

import math
import re

ABSTENTION = "I don't know."
MARKERS = re.compile(r"\[([^\[\]\n]+)\]")


def normalize_citations(text: str, evidence: list[dict]) -> str:
    """Resolve visible source labels and grouped known IDs.

    Never infer an unseen reference. A label spanning several visible chunks
    expands to all of them, rather than choosing one arbitrarily.
    The original model response is retained separately in the answer trace.
    """
    allowed = {hit["chunk_id"] for hit in evidence}
    aliases: dict[str, list[str]] = {}
    for hit in evidence:
        for label in re.findall(r"\[(GOV-[A-Z0-9-]+)\]", hit.get("text", "")):
            ids = aliases.setdefault(label, [])
            if hit["chunk_id"] not in ids:
                ids.append(hit["chunk_id"])
    def replace(match):
        marker = match.group(1).strip()
        if marker in allowed:
            return f"[{marker}]"
        if marker in aliases:
            return "".join(f"[{chunk_id}]" for chunk_id in aliases[marker])
        parts = [part.strip() for part in re.split(r"[,;]", marker)]
        groups = [[part] if part in allowed else aliases.get(part, []) for part in parts]
        if len(parts) > 1 and all(groups):
            ids = dict.fromkeys(chunk_id for group in groups for chunk_id in group)
            return "".join(f"[{chunk_id}]" for chunk_id in ids)
        return match.group(0)
    return MARKERS.sub(replace, text)


def validate_citations(text: str, evidence: list[dict]) -> dict:
    markers = MARKERS.findall(text)
    allowed = {hit["chunk_id"] for hit in evidence}
    cited = list(dict.fromkeys(marker for marker in markers if marker in allowed))
    invalid = sorted(set(markers) - allowed)
    malformed = text.count("[") != len(markers) or text.count("]") != len(markers)
    return {"valid": bool(cited) and not invalid and not malformed,
            "cited_ids": cited, "invalid_ids": invalid, "malformed": malformed}


def filter_evidence(hits: list[dict], threshold: float | None) -> list[dict]:
    if threshold is None:
        return hits
    if not math.isfinite(threshold):
        raise ValueError("Rerank threshold must be finite")
    return [hit for hit in hits
            if isinstance(hit.get("rerank_score"), (int, float))
            and math.isfinite(hit["rerank_score"]) and hit["rerank_score"] >= threshold]


def select_context(hits: list[dict], max_chars: int, max_tokens: int | None = None) -> list[dict]:
    """Keep complete chunks within the budget, so citations refer to visible evidence."""
    if max_tokens is not None:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
    chosen, sections = [], []
    for hit in hits:
        text = str(hit.get("text", "")).strip()
        if not text:
            continue
        section = f"[{hit['chunk_id']}]\n{text}"
        candidate = "\n\n".join([*sections, section])
        if len(candidate) > max_chars:
            continue
        if max_tokens is not None and len(encoding.encode(candidate)) > max_tokens:
            continue
        chosen.append(hit)
        sections.append(section)
    return chosen


def token_accounting(system: str, context: str, question: str) -> dict:
    """Content tokens, excluding provider-specific chat framing."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        counts = {name: len(enc.encode(value)) for name, value in
                  (("system", system), ("context", context), ("question", question))}
        return {**counts, "total": sum(counts.values()), "mode": "cl100k_base-content"}
    except Exception:
        return {"mode": "unavailable"}
