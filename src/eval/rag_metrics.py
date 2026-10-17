"""Week 11 metrics with explicit live/proxy modes and real pipeline evidence."""
from __future__ import annotations

import math
import re

NAMES = ("faithfulness", "answer_relevance", "context_precision", "context_recall")


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def score_rows(rows: list[dict], mode: str) -> dict:
    """Never silently substitute proxy metrics for a requested live run.

    Unanswerable references and abstentions are excluded from these four metrics;
    abstention performance is reported separately in the KPI report.
    """
    if mode not in {"live", "offline-proxy"}:
        raise ValueError("Metric mode must be live or offline-proxy")
    eligible = [r for r in rows if r.get("answerability") == "answerable" and not r.get("abstained")]
    if not eligible:
        return {"mode": mode, "n": 0, "aggregates": {n: None for n in NAMES}, "per_row": {}}
    if mode == "live":
        # Optional pinned integration, imported only when explicitly requested.
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithReference, LLMContextRecall
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        dataset = EvaluationDataset(samples=[SingleTurnSample(
            user_input=r["question"], response=r["answer_text"],
            retrieved_contexts=r["contexts"], reference=r["expected_behavior"])
            for r in eligible])
        result = evaluate(dataset, metrics=[Faithfulness(), ResponseRelevancy(),
                          LLMContextPrecisionWithReference(), LLMContextRecall()],
                          llm=LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0)),
                          embeddings=LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small")),
                          raise_exceptions=True)
        records = result.to_pandas().to_dict("records")
        columns = ("faithfulness", "answer_relevancy", "llm_context_precision_with_reference", "context_recall")
        per_row = {r["id"]: {name: float(record[column]) for name, column in zip(NAMES, columns)}
                   for r, record in zip(eligible, records)}
    else:
        per_row = {}
        for row in eligible:
            answer, question, reference = (_tokens(row[k]) for k in ("answer_text", "question", "expected_behavior"))
            contexts = [_tokens(c) for c in row["contexts"]]
            union = set().union(*contexts)
            per_row[row["id"]] = {
                "faithfulness": len(answer & union) / max(len(answer), 1),
                "answer_relevance": len(answer & question) / max(len(question), 1),
                "context_precision": sum(bool(c & reference) for c in contexts) / max(len(contexts), 1),
                "context_recall": len(reference & union) / max(len(reference), 1),
            }
    if any(not math.isfinite(v) for scores in per_row.values() for v in scores.values()):
        raise ValueError("Nonfinite evaluation score; no successful report was produced")
    return {"mode": mode, "n": len(eligible), "per_row": per_row,
            "configuration": {"ragas_version": "0.2.15", "judge_model": "gpt-4o-mini",
                              "embedding_model": "text-embedding-3-small"} if mode == "live" else {},
            "aggregates": {name: sum(s[name] for s in per_row.values()) / len(per_row) for name in NAMES}}


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def compute_kpis(rows: list[dict]) -> dict:
    def rate(flags):
        return {"numerator": sum(flags), "denominator": len(flags),
                "rate": sum(flags) / len(flags) if flags else None}
    answered = [r for r in rows if not r["abstained"]]
    unanswerable = [r for r in rows if r["answerability"] == "unanswerable"]
    answerable = [r for r in rows if r["answerability"] == "answerable"]
    use_rag_seconds = bool(rows) and all(r.get("rag_seconds", 0) > 0 for r in rows)
    latencies = [r["rag_seconds"] if use_rag_seconds else r["elapsed_seconds"] for r in rows]
    return {
        "task_success": rate([r["pass_fail"] for r in rows]),
        "citation_validity": rate([r.get("citation_validation", {}).get("valid", False) for r in answered]),
        "correct_abstention": rate([r["abstained"] for r in unanswerable]),
        "false_abstention": rate([r["abstained"] for r in answerable]),
        "grounded_response": rate([(r.get("judge_groundedness") or 0) >= 3 for r in answered]),
        "hallucination": rate([(r.get("judge_groundedness") or 0) < 3 or r["answerability"] == "unanswerable" for r in answered]),
        "latency_p50_seconds": percentile(latencies, .5),
        "latency_p95_seconds": percentile(latencies, .95),
        "latency_measure": "rag_wall_seconds" if use_rag_seconds else "allocated_eval_row_elapsed_seconds",
        "mean_generation_cost_usd": sum(r["cost_usd"] for r in rows) / len(rows) if rows else None,
    }


def check_thresholds(report: dict, thresholds: dict) -> list[str]:
    """Threshold values have explicit min/max directions; unknown metrics fail loudly."""
    failures = []
    for name, bounds in thresholds.items():
        if name not in report:
            raise ValueError(f"Threshold metric is unknown or disabled: {name}")
        value = report[name]
        if isinstance(value, dict):
            value = value["rate"]
        if not bounds or set(bounds) - {"min", "max"}:
            raise ValueError(f"Invalid threshold bounds for {name}")
        if value is None or any((value < bound if direction == "min" else value > bound)
                                for direction, bound in bounds.items()):
            failures.append(name)
    return failures
