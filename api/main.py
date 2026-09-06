"""api/main.py â€” REFERENCE for Week 3 Lab Step 1.

The completed version. Wraps the local RAG pipeline behind a stable HTTP
contract (Question/Answer with field names question/content) while delegating
to the RAG pipeline internally.

Run with:
    uvicorn api.main:app --reload --port 8000
    streamlit run api/main.py --server.port 8501

Hit with curl:
    curl -X POST http://localhost:8000/ask_batched \
         -H "Content-Type: application/json" \
         -d '{"question": "What is RAG?"}'
"""
import asyncio
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# RAG pipeline â€” the underlying engine
from src.pipeline.pipeline import RagAnswer as _RagAnswer
from src.pipeline.pipeline import ask_rag as _ask_rag


logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Public W3 API models â€” locked in ADR 0002
# These are intentionally separate from the W2 internal models (which use
# `text` field names). The endpoint handlers translate between the two.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Question(BaseModel):
    """Public request shape â€” locked in ADR 0002."""
    question: str


class Answer(BaseModel):
    """Public response shape â€” locked in ADR 0002."""
    content: str
    sources: list[str] = Field(default_factory=list)
    cost_usd: float
    retries: int


app = FastAPI(
    title="Capstone API",
    description="Wraps the W2 async pipeline. Contract locked in ADR 0002 (W3); internals upgraded W4+.",
    version="1.0.0",
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# /ask_batched â€” non-streaming reference endpoint
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.post("/ask_batched", response_model=Answer)
async def ask_batched(q: Question) -> Answer:
    """Non-streaming. Returns the full Answer in a single JSON body."""
    log.info("ask_batched  question=%r", q.question[:80])
    pipeline_ans = await _ask_rag(q.question)
    return Answer(
        content=pipeline_ans.content,
        sources=pipeline_ans.sources,
        cost_usd=pipeline_ans.cost_usd,
        retries=pipeline_ans.retries,
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
    """Render the Streamlit chat UI for the /ask endpoint."""
    import httpx
    import streamlit as st

    default_api_url = "http://localhost:8000/ask"
    api_url = os.getenv("CAPSTONE_API_URL", default_api_url)
    try:
        api_url = st.secrets.get("CAPSTONE_API_URL", api_url)
    except Exception:
        pass

    st.set_page_config(page_title="Capstone Q&A", page_icon="Q", layout="centered")
    st.title("Capstone Q&A")
    st.caption("Ask a question and stream the API response token by token.")

    with st.sidebar:
        st.subheader("Connection")
        api_url = st.text_input("API endpoint", value=api_url)
        st.caption("Start uvicorn separately, then point the UI at the /ask endpoint.")

    with st.form(key="ask_form", clear_on_submit=False):
        question = st.text_area(
            "Your question",
            placeholder="e.g. What is the leave policy?",
            height=120,
        )
        submitted = st.form_submit_button("Ask")

    if submitted and question.strip():
        placeholder = st.empty()
        answer = ""

        try:
            with httpx.Client(timeout=60.0) as client:
                with client.stream("POST", api_url, json={"question": question.strip()}) as response:
                    response.raise_for_status()
                    for chunk in response.iter_text():
                        if chunk:
                            answer += chunk
                            placeholder.markdown(answer)
        except httpx.ConnectError:
            st.error("Cannot reach the API. Is uvicorn running on port 8000?")
        except httpx.HTTPStatusError as exc:
            st.error(f"API error: {exc.response.status_code} {exc.response.reason_phrase}")
        except httpx.TimeoutException:
            st.error("Request timed out after 60 seconds.")
        except Exception as exc:
            st.error(f"Unexpected error: {type(exc).__name__}: {exc}")


if _is_streamlit_runtime():
    run_streamlit_app()


