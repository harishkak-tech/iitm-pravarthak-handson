"""Question form backed by the RAG HTTP API; no pipeline imports required."""

import os
import re
import logging
from pathlib import Path
import time
from urllib.parse import urlsplit

import requests
import streamlit as st
from dotenv import load_dotenv

from src.pipeline.logging_config import get_logger


ROOT = Path(__file__).resolve().parents[1]
log = get_logger("ask_ui", ROOT / "logs/ui.log")
log.propagate = False
if not any(type(handler) is logging.StreamHandler for handler in log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)


def api_base_url():
    load_dotenv(ROOT / ".env")
    return os.getenv("RAG_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def post_question(question, api_base):
    """Send to the backend and log routing/status without question text or secrets."""
    url = f"{api_base}/ask_rag"
    parsed = urlsplit(url)
    host = parsed.hostname or "unknown"
    # Do not log userinfo, URL query parameters, response bodies or question text.
    destination = f"{parsed.scheme}://{host}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"
    started = time.perf_counter()
    log.info("Sending question to API %s", destination)
    try:
        with requests.Session() as session:
            # Streamlit and FastAPI share this VM. A proxy must not intercept
            # loopback requests; keep environment proxy support for remote APIs.
            if host in {"localhost", "127.0.0.1", "::1"}:
                session.trust_env = False
            response = session.post(url, json={"question": question}, timeout=(10, 300))
        log.log(logging.ERROR if response.status_code >= 400 else logging.INFO,
                "API %s returned HTTP %s after %.2fs", destination, response.status_code,
                time.perf_counter() - started)
        return response
    except requests.RequestException as exc:
        log.error("API %s request failed: %s after %.2fs", destination,
                  type(exc).__name__, time.perf_counter() - started)
        raise


def public_answer_text(answer):
    """Hide known citation markers for display without changing the saved answer."""
    known = set(answer.get("sources") or [])
    known.update(answer.get("citation_validation", {}).get("cited_ids") or [])
    for hit in [*(answer.get("evidence") or []), *(answer.get("retrieved") or [])]:
        if hit.get("chunk_id"):
            known.add(hit["chunk_id"])

    def remove_citation(match):
        marker = match.group(1).strip()
        if marker.lower().startswith("sources:"):
            marker = marker[len("sources:"):].strip()
        parts = [part.strip() for part in re.split(r"[,;]", marker)]
        if marker in known or (parts and all(part in known for part in parts)):
            return ""
        return match.group(0)

    # Preserve normal bracketed text and Markdown links, rather than deleting
    # every bracketed expression in the model's prose.
    return re.sub(r"[ \t]*\[([^\[\]\n]+)\](?!\()", remove_citation, answer["content"]).strip()


def ask_view():
    api_base = api_base_url()
    with st.form("rag_question"):
        question = st.text_area(
            "Ask a question", placeholder="What would you like to know?", height=150
        )
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            st.session_state.pop("rag_last_answer", None)
            try:
                with st.spinner("Searching the corpus and preparing your answer..."):
                    response = post_question(question.strip(), api_base)
                    response.raise_for_status()
                    answer = response.json()
                    if not isinstance(answer, dict) or not isinstance(answer.get("content"), str):
                        raise ValueError("Missing answer content")
                    st.session_state["rag_last_answer"] = answer
            except requests.ConnectionError:
                st.error("The assistant is unavailable right now. Please try again shortly.")
            except requests.Timeout:
                st.error("The API timed out. Try again once the service is ready.")
            except requests.HTTPError:
                st.error("The assistant could not answer right now. Please try again shortly.")
            except (ValueError, KeyError, IndexError, TypeError):
                st.error("The assistant returned an incomplete response. Please try again.")
            except requests.RequestException:
                st.error("Could not send your question. Please try again shortly.")

    answer = st.session_state.get("rag_last_answer")
    if answer:
        with st.container(border=True):
            st.subheader("Answer")
            st.markdown(public_answer_text(answer))


def answer_details_view():
    """Technical answer details, rendered only in the authenticated admin view."""
    answer = st.session_state.get("rag_last_answer")
    if answer:
        st.markdown("**Original answer with citations**")
        st.markdown(answer["content"])
        with st.expander("Sources", expanded=True):
            for source in answer.get("sources", []):
                st.text(source)
            if not answer.get("sources"):
                st.caption("No sources returned.")
        st.caption(f"Generation cost: ${answer.get('cost_usd', 0):.6f}")
        chunks = answer.get("retrieved", [])
        st.subheader(f"Retrieved chunks ({len(chunks)})")
        st.caption("Retrieved passages in ranking order. Only chunks listed under Answer evidence were sent to the model.")
        for rank, chunk in enumerate(chunks, start=1):
            with st.expander(f"{rank}. {chunk.get('chunk_id', 'Unknown chunk')}"):
                st.caption(f"Source: {chunk.get('source', 'Unknown source')}")
                if chunk.get("score") is not None:
                    st.caption(f"Retrieval score: {chunk['score']}")
                st.text(chunk.get("text", ""))
                if chunk.get("metadata"):
                    st.json(chunk["metadata"])
        if not chunks:
            st.caption("No chunk text returned. Submit a new question after restarting the API.")
        if "evidence" in answer:
            with st.expander("Answer evidence and citations"):
                st.caption(f"Knowledge-base version: {answer.get('kb_version', '')}")
                st.json({"reason": answer.get("reason"),
                         "citations": answer.get("citation_validation", {}),
                         "discarded_ids": answer.get("discarded_ids", []),
                         "prompt_tokens": answer.get("prompt_tokens_by_section", {})})
                for hit in answer["evidence"]:
                    st.text(f"[{hit['chunk_id']}]\n{hit['text']}")
