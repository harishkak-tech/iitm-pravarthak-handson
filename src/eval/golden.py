"""Golden-set loading and evaluation helpers.

The golden set lives in ``docs/goldenset/golden_set_60.jsonl`` and the source
corpus lives in ``docs/corpus_pdf_styled/``. This module keeps the schema, document
loading, retrieval heuristic, and evaluation loop in one place.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

from .judge import JudgeScore, judge_answer


class GoldenEntry(BaseModel):
    """One row from the golden-set JSONL file."""

    id: str = Field(min_length=1)
    document: str | None = None
    source_documents: list[str] = Field(default_factory=list)
    question: str = Field(min_length=1)
    expected_behavior: str = Field(min_length=1)
    answerability: Literal["answerable", "unanswerable"]
    evaluation_type: str = Field(min_length=1)


class GoldenEvalRow(BaseModel):
    """One evaluated question with the model response and local checks."""

    id: str
    document: str | None = None
    source_documents: list[str] = Field(default_factory=list)
    question: str
    expected_behavior: str
    answerability: Literal["answerable", "unanswerable"]
    evaluation_type: str
    selected_document: str | None = None
    retrieval_hit: bool = False
    abstained: bool = False
    answer_text: str
    cost_usd: float = 0.0
    retries: int = 0
    elapsed_seconds: float = Field(ge=0.0)
    pass_fail: bool = False
    judge_accuracy: int | None = Field(default=None, ge=1, le=4)
    judge_groundedness: int | None = Field(default=None, ge=1, le=4)
    judge_format: int | None = Field(default=None, ge=1, le=4)
    judge_reasoning: str | None = None
    judge_overall: float | None = Field(default=None, ge=1.0, le=4.0)
    judge_pass: bool | None = None


class GoldenEvalSummary(BaseModel):
    """Aggregate results for a whole golden-set run."""

    total: int
    answerable: int
    unanswerable: int
    retrieval_hits: int
    retrieval_hit_rate: float
    abstentions: int
    abstention_rate: float
    passed: int
    pass_rate: float
    answerable_passed: int
    answerable_pass_rate: float
    unanswerable_passed: int
    unanswerable_pass_rate: float
    total_cost_usd: float
    total_elapsed_seconds: float
    by_eval_type: dict[str, int]
    judge_accuracy_avg: float
    judge_groundedness_avg: float
    judge_format_avg: float
    judge_overall_avg: float
    judge_passed: int
    judge_pass_rate: float
    judge_log_path: str


def load_golden_set(path: str | Path) -> list[GoldenEntry]:
    """Read and validate a JSONL golden set."""
    out: list[GoldenEntry] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(GoldenEntry.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"invalid golden entry on line {line_no}: {exc}") from exc
    return out


def load_corpus_documents(corpus_dir: str | Path) -> dict[str, str]:
    """Extract styled PDF corpus files into memory keyed by original text IDs."""
    corpus_dir = Path(corpus_dir)
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError(
            "Golden-set evaluation requires PyMuPDF for the styled PDF corpus."
        ) from exc

    docs: dict[str, str] = {}
    for path in sorted(corpus_dir.glob("*.pdf")):
        with pymupdf.open(path) as pdf:
            text = "\n\n".join(page.get_text("text").strip() for page in pdf).strip()
        if text:
            docs[f"{path.stem}.txt"] = text
    return docs


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_document(question: str, filename: str, text: str) -> float:
    """Simple lexical scorer for document retrieval.

    The filename carries the strongest signal because the golden set names the
    target document explicitly. The body text is used as a weak tie-breaker.
    """
    question_tokens = _tokenize(question)
    name_tokens = _tokenize(Path(filename).stem.replace("_", " "))
    body_tokens = _tokenize(text[:4000])
    return (5.0 * len(question_tokens & name_tokens)) + len(question_tokens & body_tokens)


def select_document(question: str, corpus_docs: dict[str, str]) -> tuple[str | None, str | None]:
    """Pick the most relevant corpus document with a light lexical heuristic."""
    best_name: str | None = None
    best_score = 0.0
    for filename, text in corpus_docs.items():
        score = _score_document(question, filename, text)
        if score > best_score:
            best_name = filename
            best_score = score
    if best_name is None:
        return None, None
    return best_name, corpus_docs[best_name]


def build_grounded_prompt(
    entry: GoldenEntry,
    retrieved: list[dict[str, Any]],
    *,
    max_context_chars: int = 1000,
) -> str:
    """Build an evaluation prompt from retrieved chunks, never a full document."""
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive")

    context_parts: list[str] = []
    remaining = max_context_chars
    for hit in retrieved:
        chunk_id = str(hit.get("chunk_id", "unknown"))
        text = str(hit.get("text", "")).strip()
        if not text or remaining <= 0:
            continue

        separator = "\n\n" if context_parts else ""
        available = remaining - len(separator)
        prefix = f"[{chunk_id}]\n"
        if len(prefix) >= available:
            break
        part = prefix + text[: available - len(prefix)]
        context_parts.append(part)
        remaining -= len(separator) + len(part)

    context = "\n\n".join(context_parts)
    return (
        "You are a careful question-answering system.\n"
        "Use only the document content below. If the answer is not supported by\n"
        "the document, say that the answer is not available in the corpus.\n\n"
        f"Document: {entry.document or 'unknown'}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {entry.question}\n"
        "Answer:"
    )


_ABSTAIN_PHRASES = (
    "not available in the corpus",
    "not available",
    "not in the corpus",
    "cannot determine",
    "cannot answer",
    "don't know",
    "do not know",
    "insufficient information",
    "please contact hr",
    "no answer",
)


def is_abstention(answer_text: str) -> bool:
    """Return True when the answer clearly refuses to invent facts."""
    lowered = answer_text.lower()
    return any(phrase in lowered for phrase in _ABSTAIN_PHRASES)


async def evaluate_golden_set(
    golden_entries: list[GoldenEntry],
    corpus_docs: dict[str, str],
    answer_fn: Callable[[str], Awaitable[Any]],
    *,
    max_entries: int | None = None,
    judge_log_path: str | Path | None = None,
) -> tuple[list[GoldenEvalRow], GoldenEvalSummary]:
    """Run a golden-set evaluation loop against an async question-answer function."""
    rows: list[GoldenEvalRow] = []
    entries = golden_entries[:max_entries] if max_entries is not None else golden_entries
    if judge_log_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        judge_log_path = Path("docs/runs/judge_logs") / f"golden_eval_{timestamp}.jsonl"
    judge_log_path = Path(judge_log_path)
    judge_log_path.parent.mkdir(parents=True, exist_ok=True)
    total_elapsed = 0.0
    total_cost = 0.0
    judge_accuracy_total = 0.0
    judge_groundedness_total = 0.0
    judge_format_total = 0.0
    judge_overall_total = 0.0
    judge_passed = 0

    with judge_log_path.open("w", encoding="utf-8") as judge_log:
        for entry in entries:
            selected_name, selected_text = select_document(entry.question, corpus_docs)
            if entry.document and entry.document in corpus_docs:
                expected_text = corpus_docs[entry.document]
            else:
                expected_text = None

            started = time.perf_counter()
            answer = await answer_fn(entry.question)
            elapsed = time.perf_counter() - started

            answer_text = getattr(answer, "content", getattr(answer, "text", str(answer)))
            cost_usd = float(getattr(answer, "cost_usd", 0.0) or 0.0)
            retries = int(getattr(answer, "retries", 0) or 0)
            abstained = is_abstention(answer_text)
            retrieved = getattr(answer, "retrieved", [])
            expected_sources = entry.source_documents or ([entry.document] if entry.document else [])
            retrieved_sources = {str(hit.get("source", "")) for hit in retrieved}
            retrieval_hit = bool(expected_sources) and set(expected_sources).issubset(retrieved_sources)
            source_context = "\n\n".join(
                f"[{hit['chunk_id']}]\n{hit['text']}"
                for hit in retrieved
            )
            judge: JudgeScore = await judge_answer(
                question=entry.question,
                expected_behavior=entry.expected_behavior,
                source_context=source_context,
                candidate_answer=answer_text,
                answerability=entry.answerability,
                evaluation_type=entry.evaluation_type,
            )
            passed = judge.passed
            judge_accuracy_total += judge.accuracy
            judge_groundedness_total += judge.groundedness
            judge_format_total += judge.format
            judge_overall_total += judge.overall
            if judge.passed:
                judge_passed += 1

            judge_log.write(
                json.dumps(
                    {
                        "id": entry.id,
                        "question": entry.question,
                        "expected_behavior": entry.expected_behavior,
                        "llm_response": answer_text,
                        "judge_pass": judge.passed,
                        "judge_accuracy": judge.accuracy,
                        "judge_groundedness": judge.groundedness,
                        "judge_format": judge.format,
                        "judge_reasoning": judge.reasoning,
                    }
                )
                + "\n"
            )

            rows.append(
                GoldenEvalRow(
                    id=entry.id,
                    document=entry.document,
                    source_documents=entry.source_documents,
                    question=entry.question,
                    expected_behavior=entry.expected_behavior,
                    answerability=entry.answerability,
                    evaluation_type=entry.evaluation_type,
                    selected_document=selected_name,
                    retrieval_hit=retrieval_hit,
                    abstained=abstained,
                    answer_text=answer_text,
                    cost_usd=cost_usd,
                    retries=retries,
                    elapsed_seconds=elapsed,
                    pass_fail=passed,
                    judge_accuracy=judge.accuracy,
                    judge_groundedness=judge.groundedness,
                    judge_format=judge.format,
                    judge_reasoning=judge.reasoning,
                    judge_overall=judge.overall,
                    judge_pass=judge.passed,
                )
            )
            total_elapsed += elapsed
            total_cost += cost_usd

    answerable = sum(1 for row in rows if row.answerability == "answerable")
    unanswerable = len(rows) - answerable
    answerable_rows = [row for row in rows if row.answerability == "answerable"]
    unanswerable_rows = [row for row in rows if row.answerability == "unanswerable"]
    retrieval_hits = sum(1 for row in answerable_rows if row.retrieval_hit)
    abstentions = sum(1 for row in rows if row.abstained)
    passed = sum(1 for row in rows if row.pass_fail)
    answerable_passed = sum(1 for row in answerable_rows if row.pass_fail)
    unanswerable_passed = sum(1 for row in unanswerable_rows if row.pass_fail)
    by_eval_type = dict(Counter(row.evaluation_type for row in rows))

    summary = GoldenEvalSummary(
        total=len(rows),
        answerable=answerable,
        unanswerable=unanswerable,
        retrieval_hits=retrieval_hits,
        retrieval_hit_rate=(retrieval_hits / max(answerable, 1)),
        abstentions=abstentions,
        abstention_rate=(abstentions / max(len(rows), 1)),
        passed=passed,
        pass_rate=(passed / max(len(rows), 1)),
        answerable_passed=answerable_passed,
        answerable_pass_rate=(answerable_passed / max(answerable, 1)),
        unanswerable_passed=unanswerable_passed,
        unanswerable_pass_rate=(unanswerable_passed / max(unanswerable, 1)),
        total_cost_usd=total_cost,
        total_elapsed_seconds=total_elapsed,
        by_eval_type=by_eval_type,
        judge_accuracy_avg=(judge_accuracy_total / max(len(rows), 1)),
        judge_groundedness_avg=(judge_groundedness_total / max(len(rows), 1)),
        judge_format_avg=(judge_format_total / max(len(rows), 1)),
        judge_overall_avg=(judge_overall_total / max(len(rows), 1)),
        judge_passed=judge_passed,
        judge_pass_rate=(judge_passed / max(len(rows), 1)),
        judge_log_path=str(judge_log_path),
    )
    return rows, summary


def write_eval_artifacts(
    rows: list[GoldenEvalRow],
    summary: GoldenEvalSummary,
    *,
    rows_path: str | Path,
    summary_path: str | Path,
) -> None:
    """Persist the evaluation output as JSONL plus a summary JSON file."""
    rows_path = Path(rows_path)
    summary_path = Path(summary_path)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with rows_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json() + "\n")

    summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
