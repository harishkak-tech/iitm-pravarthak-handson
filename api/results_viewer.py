"""Public question page and authenticated admin evaluation dashboard."""

from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.results_reader import read_history, read_results
from api.ask_ui import ask_view, answer_details_view
from src.admin_auth import authenticate_admin
from api.admin_settings import settings_view


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
    st.subheader(f"Eight evaluation KPIs · Run {selected}")
    kpis = summary.get("kpis", {})
    def metric_number(value, suffix="", digits=2):
        return f"{value:.{digits}f}{suffix}" if isinstance(value, (int, float)) else "Not recorded"
    cards = []
    for label, key in [("Task success", "task_success"), ("Citation validity", "citation_validity"),
                       ("Correct abstention", "correct_abstention"), ("False abstention", "false_abstention"),
                       ("Grounded responses", "grounded_response"), ("Hallucination", "hallucination")]:
        rate = kpis.get(key, {})
        value = rate.get("rate")
        cards.append((label, metric_number(value * 100 if value is not None else None, "%", 1),
                      f"{rate.get('numerator')} / {rate.get('denominator')}" if rate else "Not recorded"))
    cards.append(("Response latency (p50)", metric_number(kpis.get("latency_p50_seconds"), " s"),
                  "p95: " + metric_number(kpis.get("latency_p95_seconds"), " s")))
    cost = kpis.get("mean_generation_cost_usd")
    cards.append(("Mean generation cost", "$" + metric_number(cost, "", 6) if cost is not None else "Not recorded", "USD per question"))
    for offset in (0, 4):
        for column, (label, value, help_text) in zip(st.columns(4), cards[offset:offset + 4]):
            column.metric(label, value, help=help_text, border=True)
    st.caption(f"Latency measure: {kpis.get('latency_measure', 'Not recorded')}. Missing metrics were not recorded for this run.")
    st.subheader(f"Settings used · Run {selected}")
    st.caption("Saved snapshot from this evaluation.")
    def settings_rows(value, prefix=""):
        result = []
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict) and item:
                result.extend(settings_rows(item, name))
            else:
                result.append({"Setting": name, "Value": json.dumps(item)})
        return result
    st.caption(f"Golden set: {run['golden_path']} · Corpus: {run['corpus_dir']} · Question limit: {run.get('entry_limit') or 'All'}")
    st.dataframe(settings_rows({"settings": run["settings"], "judge": run["judge_settings"]}), hide_index=True, width="stretch")
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


def navigate(view):
    st.query_params["view"] = view


def logout():
    st.session_state.pop("admin_authenticated", None)
    navigate("home")


def login_view(auth_path):
    st.subheader("Admin login")
    with st.form("admin_login", clear_on_submit=True):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    if submitted:
        if authenticate_admin(auth_path, username, password):
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password.")


def admin_view():
    # Keep the authorization check here as well as in the page router.
    if not st.session_state.get("admin_authenticated", False):
        return
    st.subheader("Administration")
    st.sidebar.caption("Signed in as admin")
    st.sidebar.button("Log out", on_click=logout)
    supplied = st.sidebar.text_input("Database path", value=os.getenv("APP_RESULTS_DB", str(ROOT / "results.db")))
    if st.sidebar.button("Refresh results", icon=":material/refresh:"):
        history_snapshot.clear()
        result_snapshot.clear()
    path = Path(supplied).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    st.sidebar.caption("Times shown in IST")
    settings_tab, golden_tab, diagnostics_tab = st.tabs(["Settings and runs", "Golden evaluations", "Answer diagnostics"])
    with settings_tab:
        settings_view()
    with golden_tab:
        st.caption("Browse saved runs, their settings and the answers behind each score.")
        try:
            history = history_snapshot(str(path.resolve()))
            golden_view(str(path.resolve()), history["golden_runs"])
            with st.expander("Older batch runs"):
                batch_view(str(path.resolve()), history["runs"])
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            st.error(f"Could not read results: {exc}")
    with diagnostics_tab:
        if st.session_state.get("rag_last_answer"):
            answer_details_view()
        else:
            st.info("Ask a question to inspect its answer details here.")


def main():
    st.set_page_config(page_title="Government Policy Knowledge Assistant", page_icon=":material/chat:",
                       layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""<style>
        .block-container { max-width: 1120px; padding-top: 2.5rem; padding-bottom: 3rem; }
        h1 { font-size: 2.15rem !important; letter-spacing: -0.045em; line-height: 1.2 !important; }
        div[data-testid="stForm"] { border-radius: 16px; padding: 1.5rem; }
        div[data-testid="stTextArea"] textarea { border-radius: 10px; }
        div[data-testid="stBaseButton-primaryFormSubmit"] button,
        button[kind="primaryFormSubmit"] { background-color: #0f766e; border-color: #0f766e; }
        </style>""", unsafe_allow_html=True)
    admin_route = st.query_params.get("view") == "admin"
    heading, navigation = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.title("Government Policy Knowledge Assistant")
    with navigation:
        if admin_route:
            st.button("Back to questions", type="tertiary", on_click=navigate, args=("home",))
        else:
            st.button("Admin login" if not st.session_state.get("admin_authenticated") else "Admin",
                      type="tertiary", on_click=navigate, args=("admin",))
    st.divider()
    if not admin_route:
        ask_view()
    elif not st.session_state.get("admin_authenticated", False):
        auth_path = Path(os.getenv("APP_AUTH_DB", str(ROOT / "results.db")))
        login_view(auth_path)
    else:
        admin_view()


if __name__ == "__main__":
    main()
