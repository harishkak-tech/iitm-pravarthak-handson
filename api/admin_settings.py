"""Authenticated settings editor and background evaluation controls."""
import json
from pathlib import Path
import sqlite3
from typing import Literal, get_args, get_origin

from pydantic import BaseModel, ValidationError
import streamlit as st

from src.eval.jobs import latest_jobs, start_job
from src.pipeline.settings import Settings
from src.settings_store import SettingsConflict, save_settings, settings_database, settings_record


LABELS = {
    "top_k": "Retrieved chunks (k)", "rerank_enabled": "Enable reranking",
    "rerank_candidate_k": "Reranking candidates", "rrf_k": "RRF constant",
    "use_qdrant": "Use Qdrant", "provider": "Qdrant provider",
    "query_rewrite_enabled": "Enable query rewriting", "query_rewrite_n": "Query rewrite count",
    "hypothetical_retrieval_enabled": "Enable hypothetical retrieval (HyDE)",
    "question_limit": "Question limit", "concurrency": "Concurrent questions",
    "judge_use_fake": "Judge mode", "use_fake": "Use offline answer generation",
}


def _edit_model(model, prefix):
    result = {}
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        label = LABELS.get(name, name.replace("_", " ").capitalize())
        key = f"{prefix}.{name}"
        annotation = field.annotation
        args = get_args(annotation)
        nullable = type(None) in args
        base = next((arg for arg in args if arg is not type(None)), annotation) if nullable else annotation
        if isinstance(value, BaseModel):
            st.markdown(f"**{label}**")
            result[name] = _edit_model(value, key)
        elif nullable and base is bool:
            labels = ["Use environment default", "Live", "Offline"]
            options = [None, False, True]
            selected = st.selectbox(label, labels, index=options.index(value), key=key)
            result[name] = options[labels.index(selected)]
        elif get_origin(annotation) is Literal:
            options = list(args)
            result[name] = st.selectbox(label, options, index=options.index(value), key=key)
        elif base is bool:
            result[name] = st.checkbox(label, value=value, key=key)
        elif base in (int, float):
            result[name] = st.number_input(
                label, value=value, step=1 if base is int else 0.05, key=key,
                help="Leave empty to use the default or disable this limit." if nullable else None,
            )
        elif isinstance(value, dict):
            text = st.text_area(label, value=json.dumps(value, indent=2), key=key, height=100)
            try:
                result[name] = json.loads(text)
            except json.JSONDecodeError:
                result[name] = text  # Model validation reports the invalid field on save.
        elif name == "system_prompt":
            result[name] = st.text_area(label, value=str(value), height=240, key=key)
        else:
            result[name] = st.text_input(label, value=str(value), key=key)
    return result


def _editor_record(record):
    return {**record, "settings": record["settings"].model_dump(mode="json")}


@st.fragment(run_every="5s")
def job_status_view(db_path):
    if not st.session_state.get("admin_authenticated", False):
        return
    jobs = latest_jobs(db_path)
    if not jobs:
        st.info("No evaluations have been launched from the admin page yet.")
        return
    job = jobs[0]
    state = job["status"]
    st.subheader("Latest evaluation")
    st.caption(f"Settings revision {job['settings_revision']} · Job {job['id'][:8]}")
    if state in {"queued", "running"}:
        st.info("Evaluation queued." if state == "queued" else "Evaluation running. You can leave this page and return later.")
        completed, total = job["completed_questions"], job["total_questions"]
        if total:
            st.progress(min(completed / total, 1.0), text=f"{completed} of {total} questions evaluated")
        else:
            st.caption("Loading the corpus and preparing the first batch…")
    elif state == "completed":
        st.success(f"Evaluation completed. Results are saved as run {job['run_id']}.")
    else:
        st.error(f"Evaluation failed: {job.get('error') or 'Worker stopped unexpectedly.'}")
    previous_key = f"job_status:{job['id']}"
    previous = st.session_state.get(previous_key)
    st.session_state[previous_key] = state
    if previous in {"queued", "running"} and state in {"completed", "failed"}:
        # Refresh the other tabs and release the disabled launch button.
        st.cache_data.clear()
        st.rerun()
    if st.button("Refresh evaluation status", key="refresh_job_status"):
        st.cache_data.clear()
        st.rerun()
    with st.expander("Evaluation job history"):
        st.dataframe([{"Job": row["id"][:8], "Status": row["status"],
                       "Settings revision": row["settings_revision"], "Run": row["run_id"],
                       "Questions completed": row["completed_questions"], "Started (UTC)": row["started_at"]}
                      for row in jobs], hide_index=True, width="stretch")
        st.json(json.loads(job["settings_json"]))
        log_path = Path(job["artifacts_dir"]) / "worker.log"
        if log_path.is_file():
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - 16000))
                st.code(handle.read().decode("utf-8", errors="replace"), language="text")


def settings_view():
    if not st.session_state.get("admin_authenticated", False):
        return
    path = settings_database()
    record = settings_record(path)
    editor_key = f"settings_editor:{path}"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = _editor_record(record)
    editor = st.session_state[editor_key]
    st.subheader("Saved application settings")
    st.caption(f"Saved in the database · Revision {record['revision']} · Updated by {record['updated_by']}")
    if flash := st.session_state.pop("settings_flash", None):
        st.success(flash)
    if editor["revision"] != record["revision"]:
        st.warning("Another session updated the settings. Reload the saved values before saving.")
    if st.button("Reload saved settings"):
        st.session_state[editor_key] = _editor_record(record)
        st.rerun()
    jobs = latest_jobs(path)
    active = any(job["status"] in {"queued", "running"} for job in jobs)
    settings = Settings.model_validate(editor["settings"])
    prefix = f"editor:{path}:{editor['revision']}"
    st.caption("Saved settings apply to new questions and evaluations. A running evaluation keeps its launch settings.")
    with st.form("saved_application_settings"):
        data = settings.model_dump(mode="json")
        groups = [("Retrieval and reranking", "rag", "retrieval"),
                  ("Answer generation", "rag", "generation"),
                  ("Qdrant connection", "rag", "qdrant"),
                  ("Golden-set run", None, "golden"),
                  ("Evaluation and judge", None, "evaluation"),
                  ("Corpus", "rag", "corpus"), ("Chunking", "rag", "chunking"),
                  ("Embeddings", "rag", "embedding"), ("Metadata", "rag", "metadata")]
        for title, parent, name in groups:
            with st.expander(title, expanded=title == "Retrieval and reranking"):
                model = getattr(getattr(settings, parent), name) if parent else getattr(settings, name)
                edited = _edit_model(model, f"{prefix}.{parent or ''}.{name}")
                if parent:
                    data[parent][name] = edited
                else:
                    data[name] = edited
        with st.expander("Answer safeguards and advanced settings"):
            # Reuse the typed editor for the remaining scalar fields.
            from pydantic import create_model
            for model, target, excluded, group in [
                (settings.rag, data["rag"], {name for _, parent, name in groups if parent == "rag"}, "safeguards"),
                (settings, data, {"rag", "golden", "evaluation"}, "advanced"),
            ]:
                fields = {name: (field.annotation, getattr(model, name)) for name, field in type(model).model_fields.items()
                          if name not in excluded}
                scalar_model = create_model("ScalarSettings", **fields)()
                target.update(_edit_model(scalar_model, f"{prefix}.{group}"))
        st.caption("Changing corpus, chunking, embedding or collection settings requires ingesting the matching index before evaluation.")
        save = st.form_submit_button("Save settings")
        launch = st.form_submit_button("Save and run golden set", type="primary", disabled=active)
    if save or launch:
        try:
            updated = save_settings(data, expected_revision=editor["revision"], db_path=path)
            st.session_state[editor_key] = _editor_record(updated)
            if launch:
                start_job(db_path=path, expected_revision=updated["revision"])
            st.session_state["settings_flash"] = "Settings saved. Evaluation launched." if launch else "Settings saved."
            st.rerun()
        except (ValidationError, SettingsConflict, ValueError, OSError, sqlite3.Error) as exc:
            st.error(str(exc))
    if active:
        st.caption("An evaluation is already active. You can save settings for the next run.")
    job_status_view(str(path))
