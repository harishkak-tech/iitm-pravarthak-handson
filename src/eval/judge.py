"""LLM-as-judge helpers for the capstone evaluation flow.

The notebook demo uses a strong judge model with a rubric. This module keeps
that shape, but defaults to a deterministic local judge so the repo remains
fully runnable offline.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field


JUDGE_MODEL = "gpt-4o"

RUBRIC = """You are a strict, fair evaluator of answers from a question-answering assistant.
Score the CANDIDATE answer against the SOURCE CONTEXT and the EXPECTED BEHAVIOR on three dimensions, each 1-4:

- accuracy    : are the facts correct and complete versus the expected behavior?
- groundedness: is it supported by the source context, with nothing invented or contradictory?
- format      : is it clear, appropriately concise, and well-structured?

Scale: 1 = Poor, 2 = OK, 3 = Good, 4 = Excellent.
Be strict on accuracy: an answer that omits a key fact or contradicts the source cannot score above 2.
Return your scores and a short reasoning that names specific facts."""

JUDGE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_scores",
        "description": "Submit rubric scores and reasoning for the candidate answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "accuracy": {"type": "integer", "minimum": 1, "maximum": 4},
                "groundedness": {"type": "integer", "minimum": 1, "maximum": 4},
                "format": {"type": "integer", "minimum": 1, "maximum": 4},
                "reasoning": {"type": "string"},
            },
            "required": ["accuracy", "groundedness", "format", "reasoning"],
        },
    },
}


class JudgeScore(BaseModel):
    """Rubric output for a single candidate answer."""

    accuracy: int = Field(ge=1, le=4)
    groundedness: int = Field(ge=1, le=4)
    format: int = Field(ge=1, le=4)
    reasoning: str = Field(min_length=1)
    overall: float = Field(ge=1.0, le=4.0)
    passed: bool


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _content_terms(text: str) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "that",
        "this",
        "what",
        "which",
        "when",
        "where",
        "how",
        "why",
        "are",
        "was",
        "were",
        "can",
        "you",
        "your",
        "their",
        "about",
        "using",
        "using",
        "answer",
        "document",
        "policy",
        "programme",
        "program",
        "section",
        "question",
        "expected",
        "behavior",
        "behavior",
    }
    return [t for t in _tokenize(text) if len(t) >= 4 and t not in stopwords]


def _looks_like_abstention(answer_text: str) -> bool:
    lowered = answer_text.lower()
    phrases = (
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
        "not enough information",
    )
    return any(phrase in lowered for phrase in phrases)


def _build_messages(
    question: str,
    expected_behavior: str,
    source_context: str,
    candidate_answer: str,
) -> list[dict[str, str]]:
    user = (
        f"QUESTION:\n{question}\n\n"
        f"EXPECTED BEHAVIOR:\n{expected_behavior}\n\n"
        f"SOURCE CONTEXT:\n{source_context}\n\n"
        f"CANDIDATE ANSWER:\n{candidate_answer}"
    )
    return [{"role": "system", "content": RUBRIC}, {"role": "user", "content": user}]


def _fake_judge(
    question: str,
    expected_behavior: str,
    source_context: str,
    candidate_answer: str,
    answerability: Literal["answerable", "unanswerable"],
    evaluation_type: str,
) -> JudgeScore:
    candidate = candidate_answer.lower()
    context_terms = set(_content_terms(source_context))
    behavior_terms = _content_terms(expected_behavior)
    question_terms = _content_terms(question)
    key_terms = [term for term in behavior_terms if term in context_terms or term in question_terms]
    hits = [term for term in key_terms if term in candidate]
    abstains = _looks_like_abstention(candidate_answer)

    contradictory = any(
        phrase in candidate
        for phrase in (
            "no limit",
            "unlimited",
            "whenever you like",
            "any day",
            "always",
            "never restricted",
            "not restricted",
        )
    )

    if answerability == "unanswerable":
        if abstains:
            accuracy = groundedness = format_score = 4
            reasoning = "Correctly abstains instead of inventing unsupported facts."
        else:
            accuracy = groundedness = 1
            format_score = 3 if len(candidate_answer.split()) <= 60 else 2
            reasoning = "Fails to abstain on an unanswerable question and invents an answer."
    else:
        coverage = len(hits) / max(len(key_terms), 1)
        if contradictory:
            accuracy = groundedness = 1
            reasoning = "Contradicts the source context."
        elif abstains:
            accuracy = groundedness = 1
            reasoning = "Abstains even though the question is answerable from the source."
        elif coverage >= 0.8:
            accuracy = 4
            groundedness = 4 if hits else 3
            reasoning = f"Covers the key source facts: {', '.join(hits[:5])}."
        elif coverage >= 0.5:
            accuracy = 3
            groundedness = 3 if hits else 2
            reasoning = f"Mentions some required facts but misses others: {', '.join(hits[:5])}."
        elif hits:
            accuracy = 2
            groundedness = 2
            reasoning = f"Touches the right topic but misses too many facts: {', '.join(hits[:5])}."
        else:
            accuracy = groundedness = 1
            reasoning = "Does not reflect the source context."

        format_score = 4 if len(candidate_answer.split()) <= 60 else 3

    overall = round((accuracy + groundedness + format_score) / 3.0, 2)
    passed = overall >= 3.0 and accuracy >= 3 and groundedness >= 3
    if evaluation_type == "hallucination / abstention" and answerability == "unanswerable":
        passed = passed and abstains

    return JudgeScore(
        accuracy=accuracy,
        groundedness=groundedness,
        format=format_score,
        reasoning=reasoning,
        overall=overall,
        passed=passed,
    )


async def judge_answer(
    *,
    question: str,
    expected_behavior: str,
    source_context: str,
    candidate_answer: str,
    answerability: Literal["answerable", "unanswerable"],
    evaluation_type: str,
) -> JudgeScore:
    """Judge one answer.

    Defaults to a deterministic local judge. Set ``JUDGE_USE_FAKE=0`` and
    provide ``OPENAI_API_KEY`` to use the real tool-calling judge.
    """
    use_fake = os.getenv("JUDGE_USE_FAKE", "1").lower() not in {"0", "false", "no"}
    if use_fake:
        return _fake_judge(
            question,
            expected_behavior,
            source_context,
            candidate_answer,
            answerability,
            evaluation_type,
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    resp = await client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0,
        messages=_build_messages(question, expected_behavior, source_context, candidate_answer),
        tools=[JUDGE_TOOL],
        tool_choice={"type": "function", "function": {"name": "submit_scores"}},
    )
    arguments = resp.choices[0].message.tool_calls[0].function.arguments
    payload: dict[str, Any] = json.loads(arguments)
    accuracy = int(payload["accuracy"])
    groundedness = int(payload["groundedness"])
    format_score = int(payload["format"])
    reasoning = str(payload["reasoning"])
    overall = round((accuracy + groundedness + format_score) / 3.0, 2)
    passed = overall >= 3.0 and accuracy >= 3 and groundedness >= 3
    return JudgeScore(
        accuracy=accuracy,
        groundedness=groundedness,
        format=format_score,
        reasoning=reasoning,
        overall=overall,
        passed=passed,
    )

