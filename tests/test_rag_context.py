from src.eval.golden import GoldenEntry, build_grounded_prompt
from src.pipeline.pipeline import build_prompt


def _context_from_prompt(prompt: str) -> str:
    before_question = prompt.split("\n\nQuestion:", 1)[0]
    before_question = before_question.split("\n\n---", 1)[0]
    return before_question.split("Context:\n", 1)[1]


def test_build_prompt_caps_retrieved_context() -> None:
    retrieved = [
        {"chunk_id": "handbook.txt#0", "text": "A" * 500},
        {"chunk_id": "handbook.txt#1", "text": "B" * 500},
    ]

    _, prompt = build_prompt("What is the policy?", retrieved, max_context_chars=80)
    context = _context_from_prompt(prompt)

    assert len(context) <= 80
    assert "B" not in context


def test_golden_prompt_accepts_retrieved_chunks_not_a_document() -> None:
    entry = GoldenEntry(
        id="golden-1",
        document="handbook.txt",
        question="What is the policy?",
        expected_behavior="Answer from the handbook.",
        answerability="answerable",
        evaluation_type="fact",
    )
    retrieved = [{"chunk_id": "handbook.txt#3", "text": "A" * 500}]

    prompt = build_grounded_prompt(entry, retrieved, max_context_chars=80)
    context = _context_from_prompt(prompt)

    assert len(context) <= 80
    assert "[handbook.txt#3]" in context
