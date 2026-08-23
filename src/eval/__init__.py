"""Golden-set evaluation helpers for the capstone."""

from .golden import (
    GoldenEntry,
    GoldenEvalRow,
    GoldenEvalSummary,
    build_grounded_prompt,
    evaluate_golden_set,
    is_abstention,
    load_corpus_documents,
    load_golden_set,
    write_eval_artifacts,
)
from .judge import JudgeScore, judge_answer
