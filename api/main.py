"""api/main.py â€” REFERENCE for Week 3 Lab Step 1.

The completed version. Wraps the local RAG pipeline behind a stable HTTP
contract (Question/Answer with field names question/content) while delegating
to the RAG pipeline internally.

Run with:
    uvicorn api.main:app --reload --port 8000
    # React development server: cd frontend && npm install && npm run dev

Hit with curl:
    curl -X POST http://localhost:8000/ask_batched \
         -H "Content-Type: application/json" \
         -d '{"questions": ["What is RAG?", "Who is eligible for PM-KISAN?"]}'
"""
import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

# RAG pipeline â€” the underlying engine
from src.pipeline.pipeline import RagAnswer as _RagAnswer
from src.pipeline.pipeline import ask_rag as _ask_rag
from src.pipeline.pipeline import close_qdrant_clients


logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Public W3 API models â€” locked in ADR 0002
# These are intentionally separate from the W2 internal models (which use
# `text` field names). The endpoint handlers translate between the two.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Question(BaseModel):
    """Public request shape â€” locked in ADR 0002."""
    question: str = Field(min_length=1, max_length=10000)

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be blank")
        return question.strip()


class Answer(BaseModel):
    """Public response shape â€” locked in ADR 0002."""
    content: str
    sources: list[str] = Field(default_factory=list)
    cost_usd: float
    retries: int


class BatchQuestions(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=100)
    concurrency: int = Field(default=5, ge=1, le=20)

    @field_validator("questions")
    @classmethod
    def reject_blank_questions(cls, questions: list[str]) -> list[str]:
        if any(not question.strip() for question in questions):
            raise ValueError("Questions must not be blank")
        return questions


class BatchAnswer(Answer):
    question: str


class SingleAnswer(Answer):
    question: str
    retrieved: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    citation_validation: dict[str, Any] = Field(default_factory=dict)
    abstained: bool = False
    reason: str = "answered"
    kb_version: str = ""
    discarded_ids: list[str] = Field(default_factory=list)
    prompt_tokens_by_section: dict[str, Any] = Field(default_factory=dict)


class BatchResponse(BaseModel):
    answers: list[BatchAnswer]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        close_qdrant_clients()


app = FastAPI(
    lifespan=lifespan,
    title="Capstone API",
    description="Wraps the W2 async pipeline. Contract locked in ADR 0002 (W3); internals upgraded W4+.",
    version="1.0.0",
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# /ask_batched â€” non-streaming reference endpoint
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.post("/ask_batched", response_model=BatchResponse)
async def ask_batched(q: BatchQuestions) -> BatchResponse:
    """Answer questions concurrently and return results in request order."""
    log.info("ask_batched  count=%s concurrency=%s", len(q.questions), q.concurrency)
    pipeline_answers = await _ask_rag(q.questions, concurrency=q.concurrency)
    answers = [
        BatchAnswer(
            question=question,
            content=pipeline_ans.content,
            sources=pipeline_ans.sources,
            cost_usd=pipeline_ans.cost_usd,
            retries=pipeline_ans.retries,
        )
        for question, pipeline_ans in zip(q.questions, pipeline_answers)
    ]
    return BatchResponse(answers=answers)


@app.post("/ask_rag", response_model=SingleAnswer)
async def ask_single_rag(q: Question) -> SingleAnswer:
    """Answer one question and include retrieved evidence for inspection."""
    pipeline_ans = await _ask_rag(q.question)
    return SingleAnswer(
        question=q.question,
        content=pipeline_ans.content,
        sources=pipeline_ans.sources,
        cost_usd=pipeline_ans.cost_usd,
        retries=pipeline_ans.retries,
        retrieved=pipeline_ans.retrieved,
        evidence=getattr(pipeline_ans, "evidence", []),
        citation_validation=getattr(pipeline_ans, "citation_validation", {}),
        abstained=getattr(pipeline_ans, "abstained", False),
        reason=getattr(pipeline_ans, "reason", "answered"),
        kb_version=getattr(pipeline_ans, "kb_version", ""),
        discarded_ids=getattr(pipeline_ans, "discarded_ids", []),
        prompt_tokens_by_section=getattr(pipeline_ans, "prompt_tokens_by_section", {}),
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# /health â€” liveness probe
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/health")
async def health():
    return {"status": "ok"}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# /ask â€” streaming endpoint (the contracted one)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def stream_answer(question_text: str):
    """Async generator yielding the answer word-by-word.

    The RAG pipeline itself is non-streaming; this wrapper streams the
    grounded answer token-by-token to the client.
    """
    pipeline_ans: _RagAnswer = await _ask_rag(question_text)
    streamed_text = pipeline_ans.content
    if pipeline_ans.sources and "[Sources:" not in streamed_text:
        streamed_text = f"{streamed_text}\n\nSources: {', '.join(pipeline_ans.sources)}"
    for word in streamed_text.split(" "):
        yield word + " "
        await asyncio.sleep(0.05)


@app.post("/ask")
async def ask(q: Question):
    """Streaming /ask â€” the contracted endpoint."""
    log.info("ask  question=%r", q.question[:80])
    return StreamingResponse(
        stream_answer(q.question),
        media_type="text/plain",
    )


def _is_streamlit_runtime() -> bool:
    """Return True only when Streamlit is executing this file."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        return False

    return get_script_run_ctx() is not None


def run_streamlit_app() -> None:
    """Use the same public/admin UI from either supported Streamlit entrypoint."""
    from api.results_viewer import main

    main()


if _is_streamlit_runtime():
    run_streamlit_app()


# Keep the original API contract, with a same-origin namespace for React.
from api.web_admin import router as admin_router
from fastapi.staticfiles import StaticFiles

app.include_router(admin_router)
app.include_router(admin_router, prefix="/api")
for route, endpoint, methods in [
    ("/health", health, ["GET"]),
    ("/ask_rag", ask_single_rag, ["POST"]),
    ("/ask_batched", ask_batched, ["POST"]),
    ("/ask", ask, ["POST"]),
]:
    app.add_api_route("/api" + route, endpoint, methods=methods)

# Build with `npm run build` before starting Uvicorn to serve React directly.
frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


