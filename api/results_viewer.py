"""Read-only evaluation dashboard. Run: streamlit run api/results_viewer.py."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.results_reader import read_history, read_results
from api.ask_ui import ask_view


def local_time(value):
    try:
        return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %H:%M IST")
    except (TypeError, ValueError):
        return str(value)


def run_record(run):
    summary = run["summary"]
    rag = run["settings"].get("rag", {})
    retrieval = rag.get("retrieval", {})
    return {
        "Run": run["id"], "Started": local_time(run["started_at"]), "Model": run["model"],
        "Questions": summary.get("total", 0), "Passed": summary.get("passed", 0),
        "Pass rate (%)": round(summary.get("pass_rate", 0) * 100, 2),
        "Retrieval time (s)": summary.get("total_retrieval_seconds"),
        "LLM answer time (s)": summary.get("total_generation_seconds"),
        "Judge time (s)": summary.get("total_judge_seconds"),
        "Retrieval hit rate (%)": (
            round(summary["retrieval_hit_rate"] * 100, 2)
            if summary.get("retrieval_hit_rate") is not None else None
        ),
        "Retrieval hits": summary.get("retrieval_hits"),
        "Answerable questions": summary.get("answerable"),
        "Cost ($)": summary.get("total_cost_usd", 0), "k": retrieval.get("top_k"),
        "Reranking": retrieval.get("rerank_enabled"),
        "Reranking candidate limit": retrieval.get("rerank_candidate_k"),
        "Reranking model": retrieval.get("rerank_model"),
        "RRF k": retrieval.get("rrf_k"),
        "Retrieval": retrieval.get("strategy"),
        "Query rewriting": retrieval.get("query_rewrite_enabled"),
        "Query rewrite count": retrieval.get("query_rewrite_n"),
        "Query rewrite model": retrieval.get("query_rewrite_model"),
        "Hypothetical retrieval (HyDE)": retrieval.get("hypothetical_retrieval_enabled"),
        "Hypothetical retrieval model": retrieval.get("hypothetical_retrieval_model"),
        "Chunking": rag.get("chunking", {}).get("strategy"),
        "Corpus version": rag.get("metadata", {}).get("version"),
    }


@st.cache_data(ttl=10, max_entries=8)
def history_snapshot(path):
    return read_history(path)


@st.cache_data(ttl=10, max_entries=32)
def result_snapshot(path, run_id, golden):
    return read_results(path, run_id, golden=golden)


def golden_view(path, runs):
    if not runs:
        st.info("No golden runs saved yet. Completed golden evaluations appear here automatically.")
        return
    st.subheader("Run history")
    records = [run_record(run) for run in runs]
    st.dataframe(records, hide_index=True, width="stretch")
    if len(runs) > 1:
        st.bar_chart([{"Run": str(r["Run"]), "Pass rate (%)": r["Pass rate (%)"]} for r in reversed(records)], x="Run", y="Pass rate (%)")
    selected = st.selectbox("Inspect run", [r["id"] for r in runs], format_func=lambda i: next(
        f"Run {r['id']} · {r['model']} · {local_time(r['started_at'])}" for r in runs if r["id"] == i
    ))
    run = next(r for r in runs if r["id"] == selected)
    summary = run["summary"]
    if summary.get("rag_metrics") or summary.get("kpis"):
        with st.expander("RAG metrics and evaluation KPIs", expanded=True):
            metrics = summary.get("rag_metrics", {})
            st.caption(f"Metric mode: {metrics.get('mode', 'off')}. Latency measure: {summary.get('kpis', {}).get('latency_measure', 'unavailable')}.")
            st.json({"metrics": {k: v for k, v in metrics.items() if k != "per_row"},
                     "kpis": summary.get("kpis", {})})
    with st.container(horizontal=True):
        st.metric("Pass rate", f"{summary.get('pass_rate', 0):.1%}", border=True)
        st.metric("Passed / total", f"{summary.get('passed', 0)} / {summary.get('total', 0)}", border=True)
        st.metric("Retrieval hit rate", f"{summary.get('retrieval_hit_rate', 0):.1%}", border=True)
        st.metric("Generation cost", f"${summary.get('total_cost_usd', 0):.4f}", border=True)
    st.caption(
        "Retrieval hit rate: answerable questions where all expected source documents "
        f"were retrieved ({summary.get('retrieval_hits', 0)} / {summary.get('answerable', 0)})."
    )
    with st.expander("Settings, judge configuration and summary"):
        st.write("Saved generation model:", run["model"])
        st.caption(f"Golden set: {run['golden_path']} · Corpus: {run['corpus_dir']}")
        st.json({"settings": run["settings"], "judge": run["judge_settings"], "summary": summary})
    rows = result_snapshot(path, selected, True)
    if not rows:
        st.info("This run has no question results.")
        return
    st.subheader("Question results")
    status = st.radio("Show", ["Failed", "All", "Passed"], horizontal=True)
    search = st.text_input("Search questions, answers or judge reasoning", placeholder="Question ID, topic or record identifier")
    types = sorted({r.get("evaluation_type", "unknown") for r in rows})
    chosen_types = st.multiselect("Evaluation types", types)
    filtered = [r for r in rows if
                (status == "All" or bool(r["pass_fail"]) == (status == "Passed"))
                and (not chosen_types or r.get("evaluation_type", "unknown") in chosen_types)
                and (not search or search.casefold() in " ".join(str(r.get(k, "")) for k in
                     ("id", "question", "answer_text", "judge_reasoning")).casefold())]
    st.caption(f"Showing {len(filtered)} of {len(rows)} questions")
    if not filtered:
        st.info("No questions match these filters.")
        return
    table = [{"ID": r["id"], "Question": r["question"], "Passed": r["pass_fail"],
              "Retrieved expected sources": r.get("retrieval_hit"), "Accuracy": r.get("judge_accuracy"),
              "Groundedness": r.get("judge_groundedness"), "Overall": r.get("judge_overall"),
              "Type": r.get("evaluation_type")} for r in filtered]
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("Download filtered results", json.dumps(filtered, indent=2, ensure_ascii=False),
                       file_name=f"golden_run_{selected}_{status.lower()}.json", mime="application/json")
    question_id = st.selectbox("Inspect question", [r["id"] for r in filtered],
                               key=f"question_{selected}")
    row = next(r for r in filtered if r["id"] == question_id)
    with st.container(border=True):
        st.subheader(f"{row['id']} · {'Passed' if row['pass_fail'] else 'Failed'}")
        st.write(row["question"])
        st.markdown("**Expected behavior**")
        st.write(row["expected_behavior"])
        st.markdown("**Model answer**")
        st.write(row["answer_text"])
        st.markdown("**Judge reasoning**")
        st.write(row.get("judge_reasoning") or "No judge reasoning saved.")
        st.caption("Expected sources: " + ", ".join(row.get("source_documents") or [row.get("document") or "None"]))
        with st.expander("Complete result"):
            st.json(row)


def batch_view(path, runs):
    if not runs:
        st.info("No batch runs saved in this database.")
        return
    st.dataframe(runs, hide_index=True, width="stretch")
    run_id = st.selectbox("Inspect batch run", [r["id"] for r in runs])
    rows = result_snapshot(path, run_id, False)
    st.caption("Older batch runs do not record model or settings snapshots.")
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        index = st.selectbox("Inspect batch answer", range(len(rows)),
                             format_func=lambda i: str(rows[i]["question"]))
        st.write(rows[index]["answer"])
    else:
        st.info("No answers stored for this batch run.")


def main():
    st.set_page_config(page_title="Government Policy Knowledge Assistant", page_icon=":material/assessment:", layout="wide")
    st.title("Government Policy Knowledge Assistant")
    ask_tab, golden_tab = st.tabs(["Ask questions", "Golden evaluations"])
    with ask_tab:
        ask_view()
    supplied = st.sidebar.text_input("Database path", value=str(ROOT / "results.db"))
    if st.sidebar.button("Refresh results", icon=":material/refresh:"):
        history_snapshot.clear()
        result_snapshot.clear()
    path = Path(supplied).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    st.sidebar.caption("Read-only viewer · Times shown in IST")
    with golden_tab:
        st.caption("Browse saved runs, their settings and the answers behind each score.")
        try:
            history = history_snapshot(str(path.resolve()))
            golden_view(str(path.resolve()), history["golden_runs"])
            with st.expander("Older batch runs"):
                batch_view(str(path.resolve()), history["runs"])
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            st.error(f"Could not read results: {exc}")


if __name__ == "__main__":
    main()
