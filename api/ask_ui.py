"""Question form backed by the RAG HTTP API; no pipeline imports required."""

import os

import requests
import streamlit as st


def ask_view():
    st.header("Ask the knowledge assistant")
    st.caption("Ask about the document corpus. Each question is answered independently.")
    api_base = st.sidebar.text_input(
        "RAG API URL", value=os.getenv("RAG_API_BASE_URL", "http://localhost:8000")
    ).rstrip("/")
    with st.form("rag_question"):
        question = st.text_area(
            "Your question", placeholder="Who is eligible for PM-KISAN?", height=120
        )
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.spinner("Searching the corpus and preparing your answer..."):
                    response = requests.post(
                        f"{api_base}/ask_rag",
                        json={"question": question.strip()},
                        timeout=(10, 300),
                    )
                    response.raise_for_status()
                    answer = response.json()
                    if not isinstance(answer.get("content"), str):
                        raise ValueError("Missing answer content")
                    st.session_state["rag_last_answer"] = answer
            except requests.ConnectionError:
                st.error("Cannot reach the RAG API. Start it on port 8000 or update the API URL.")
            except requests.Timeout:
                st.error("The API timed out. Try again once the service is ready.")
            except requests.HTTPError as exc:
                st.error(f"The API returned HTTP {exc.response.status_code}. Check the API logs.")
            except (ValueError, KeyError, IndexError, TypeError):
                st.error("The API returned an unexpected answer format.")
            except requests.RequestException:
                st.error("Could not send the question. Check the API URL and connection.")

    answer = st.session_state.get("rag_last_answer")
    if answer:
        st.subheader("Latest answer")
        st.caption(answer.get("question", ""))
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
