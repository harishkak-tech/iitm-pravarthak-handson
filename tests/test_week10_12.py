import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.pipeline import pipeline
from src.pipeline.evidence import filter_evidence, normalize_citations, select_context, validate_citations
from src.pipeline.lifecycle import corpus_fingerprint, live_filter, publish_snapshot, snapshot_version
from src.pipeline.settings import RagSettings, RetrievalSettings
from src.eval.rag_metrics import check_thresholds, compute_kpis, score_rows


def test_citations_reject_invented_malformed_and_combined_ids():
    evidence = [{"chunk_id": "policy#1", "text": "Approved."}]
    assert validate_citations("Approved [policy#1].", evidence)["valid"]
    for text in ("Approved.", "Approved [other].", "Approved [policy#1] [", "Approved [policy#1, other]."):
        assert not validate_citations(text, evidence)["valid"]


def test_visible_labels_and_grouped_ids_normalize_without_inventing_evidence():
    evidence = [{"chunk_id": "a#0", "text": "Policy [GOV-TEST] first half."},
                {"chunk_id": "a#1", "text": "Policy [GOV-TEST] continuation."}]
    for raw in ("Answer [GOV-TEST].", "Answer [a#0; a#1].", "Answer [a#0, a#1]."):
        normalized = normalize_citations(raw, evidence)
        assert normalized == "Answer [a#0][a#1]."
        assert validate_citations(normalized, evidence)["valid"]
    raw = "Answer [a#0; invented]."
    assert normalize_citations(raw, evidence) == raw
    assert not validate_citations(raw, evidence)["valid"]
    assert normalize_citations("Answer [GOV-UNSEEN].", evidence) == "Answer [GOV-UNSEEN]."


def test_score_gate_and_context_budget_never_expose_discarded_chunks():
    hits = [{"chunk_id": "bad", "text": "wrong", "rerank_score": float("nan")},
            {"chunk_id": "low", "text": "unrelated", "rerank_score": -.2},
            {"chunk_id": "good", "text": "Approved.", "rerank_score": 2.0}]
    assert filter_evidence(hits, 0) == hits[2:]
    assert select_context(hits, 19) == [hits[0]]
    with pytest.raises(ValueError):
        RetrievalSettings(rerank_enabled=False, rerank_score_threshold=0)
    assert not validate_citations("Approved [good].", hits[:1])["valid"]


def test_corpus_changes_invalidate_existing_index_key(tmp_path):
    path = tmp_path / "one.pdf"
    path.write_bytes(b"old")
    before = corpus_fingerprint(tmp_path)
    path.write_bytes(b"new")
    assert corpus_fingerprint(tmp_path) != before


def test_snapshot_publication_preserves_history_and_hides_deleted_sources():
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    client = QdrantClient(":memory:")
    a = pipeline.Chunk("a#0", "a", "Old policy", [1., 0.])
    b = pipeline.Chunk("b#0", "b", "Removed document", [0., 1.])
    publish_snapshot(client, "kb", [a, b], [a.vector, b.vector], {})
    new = pipeline.Chunk("a#0", "a", "Updated policy", [1., 0.])
    publish_snapshot(client, "kb", [new], [new.vector], {})
    hits = client.query_points("kb", query=[1., 0.], query_filter=live_filter(), limit=20).points
    assert [h.payload["text"] for h in hits] == ["Updated policy"]
    assert client.count("kb", exact=True).count == 3
    old_version = snapshot_version([a, b])
    assert client.count("kb", count_filter=Filter(must=[FieldCondition(
        key="kb_version", match=MatchValue(value=old_version))]), exact=True).count == 2
    client.close()


def test_failed_upload_leaves_previous_snapshot_live():
    from qdrant_client import QdrantClient
    client = QdrantClient(":memory:")
    old = pipeline.Chunk("a", "a", "old", [1., 0.])
    publish_snapshot(client, "kb", [old], [old.vector], {})
    original = client.upsert
    def fail(**kwargs):
        original(**kwargs)
        raise RuntimeError("interrupted")
    client.upsert = fail
    new = pipeline.Chunk("a", "a", "new", [1., 0.])
    with pytest.raises(RuntimeError, match="interrupted"):
        publish_snapshot(client, "kb", [new], [new.vector], {})
    assert [h.payload["text"] for h in client.query_points(
        "kb", query=[1., 0.], query_filter=live_filter()).points] == ["old"]
    client.close()


def test_reingestion_is_idempotent_and_legacy_payloads_are_retired():
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    client = QdrantClient(":memory:")
    client.create_collection("kb", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    client.upsert("kb", points=[PointStruct(id=1, vector=[1., 0.], payload={"text": "legacy"})])
    chunk = pipeline.Chunk("a", "a", "new", [1., 0.])
    publish_snapshot(client, "kb", [chunk], [chunk.vector], {})
    assert client.retrieve("kb", ids=[1])[0].payload["deleted_at"]
    client.upsert = lambda **kw: pytest.fail("An identical snapshot must not upload again")
    publish_snapshot(client, "kb", [chunk], [chunk.vector], {})
    assert client.count("kb").count == 2
    client.close()


@pytest.mark.parametrize("raw,reason,sources", [
    ("Approved [a#0].", "answered", ["a#0"]),
    ("Approved [invented].", "citation_rejected", []),
    ("I don't know.", "evidence_insufficient", []),
])
def test_pipeline_validates_only_prompt_evidence(monkeypatch, raw, reason, sources):
    rag = RagSettings()
    rag.retrieval.query_rewrite_enabled = False
    rag.retrieval.rerank_enabled = False
    rag.retrieval.use_qdrant = False
    index = [pipeline.Chunk("a#0", "a", "Approved.", [1., 0.])]
    monkeypatch.setattr(pipeline, "get_index", lambda *a, **kw: index)
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **kw: [
        {"chunk_id": "a#0", "source": "a", "text": "Approved.", "score": 1.}])
    monkeypatch.setattr(pipeline, "_use_fake_rag", lambda: False)
    monkeypatch.setattr(pipeline, "token_accounting", lambda *a: {})
    call = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))], usage=None))
    monkeypatch.setattr(pipeline, "_client", SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=call))), raising=False)
    result = asyncio.run(pipeline.ask_rag("Approved?", rag_settings=rag))
    assert result.reason == reason
    assert result.sources == sources
    assert result.evidence[0]["text"] == "Approved."
    assert result.kb_version


def test_metrics_use_actual_rows_label_proxies_and_exclude_abstentions():
    row = {"id": "q1", "question": "leave policy", "answer_text": "leave approved",
           "expected_behavior": "leave approved", "contexts": ["leave approved"],
           "answerability": "answerable", "abstained": False, "pass_fail": True,
           "elapsed_seconds": 1., "cost_usd": .01, "judge_groundedness": 4}
    result = score_rows([row, {**row, "id": "q2", "abstained": True}], "offline-proxy")
    assert result["mode"] == "offline-proxy" and result["n"] == 1
    assert result["aggregates"]["context_recall"] == 1
    assert compute_kpis([row])["correct_abstention"]["rate"] is None
    assert check_thresholds({"faithfulness": .6}, {"faithfulness": {"min": .8}}) == ["faithfulness"]
    with pytest.raises(ValueError):
        score_rows([row], "automatic")


def test_empty_evidence_skips_generation(monkeypatch):
    rag = RagSettings()
    rag.retrieval.rerank_enabled = False
    rag.retrieval.query_rewrite_enabled = False
    rag.retrieval.use_qdrant = False
    monkeypatch.setattr(pipeline, "get_index", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "token_accounting", lambda *a: {})
    call = AsyncMock(side_effect=AssertionError("No evidence must skip generation"))
    monkeypatch.setattr(pipeline, "_client", SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=call))), raising=False)
    result = asyncio.run(pipeline.ask_rag("Unknown?", rag_settings=rag))
    assert result.abstained and result.reason == "retrieval_gate" and not result.sources
    call.assert_not_awaited()


def test_golden_judge_and_saved_rows_use_only_generation_evidence(tmp_path, monkeypatch):
    from src.eval.golden import GoldenEntry, evaluate_golden_set
    from src.eval.judge import JudgeScore
    visible = {"chunk_id": "a#0", "source": "a", "text": "Visible evidence"}
    omitted = {"chunk_id": "b#0", "source": "b", "text": "Omitted evidence"}
    answer = pipeline.RagAnswer(question="Question?", content="Visible evidence [a#0].",
        retrieved=[visible, omitted], evidence=[visible], raw_answer="Visible evidence [a#0].",
        kb_version="version", citation_validation={"valid": True, "cited_ids": ["a#0"]})
    judge = AsyncMock(return_value=JudgeScore(accuracy=4, groundedness=4, format=4,
        overall=4, passed=True, reasoning="Supported"))
    monkeypatch.setattr("src.eval.golden.judge_answer", judge)
    entry = GoldenEntry(id="q", question="Question?", expected_behavior="Visible evidence",
        answerability="answerable", evaluation_type="fact", document="a")
    rows, _ = asyncio.run(evaluate_golden_set([entry], {}, AsyncMock(return_value=answer),
        judge_log_path=tmp_path / "judge.jsonl"))
    assert "Omitted evidence" not in judge.call_args.kwargs["source_context"]
    assert rows[0].contexts == ["Visible evidence"]
    assert rows[0].retrieved == [visible, omitted] and rows[0].kb_version == "version"


def test_live_metric_contract_and_errors_never_fall_back(monkeypatch):
    import sys
    def construct(**kwargs):
        return kwargs
    sample = {"id": "q", "question": "Q?", "answer_text": "A", "expected_behavior": "A",
              "contexts": ["A"], "answerability": "answerable", "abstained": False}
    def evaluate(dataset, **kwargs):
        assert dataset["samples"][0]["retrieved_contexts"] == ["A"]
        assert kwargs["raise_exceptions"] is True
        return SimpleNamespace(to_pandas=lambda: SimpleNamespace(to_dict=lambda orient: [{
            "faithfulness": 1., "answer_relevancy": .8,
            "llm_context_precision_with_reference": .7, "context_recall": .6}]))
    monkeypatch.setitem(sys.modules, "ragas", SimpleNamespace(EvaluationDataset=construct,
        SingleTurnSample=construct, evaluate=evaluate))
    monkeypatch.setitem(sys.modules, "ragas.metrics", SimpleNamespace(**{
        name: construct for name in ("Faithfulness", "ResponseRelevancy",
        "LLMContextPrecisionWithReference", "LLMContextRecall")}))
    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=construct, OpenAIEmbeddings=construct))
    monkeypatch.setitem(sys.modules, "ragas.llms", SimpleNamespace(LangchainLLMWrapper=lambda value: value))
    monkeypatch.setitem(sys.modules, "ragas.embeddings", SimpleNamespace(LangchainEmbeddingsWrapper=lambda value: value))
    result = score_rows([sample], "live")
    assert result["aggregates"]["context_precision"] == .7 and result["mode"] == "live"
    def fail(*args, **kwargs):
        raise RuntimeError("judge unavailable")
    sys.modules["ragas"].evaluate = fail
    with pytest.raises(RuntimeError, match="judge unavailable"):
        score_rows([sample], "live")


def test_unversioned_mode_is_isolated_and_replaces_only_its_own_collection():
    from qdrant_client import QdrantClient
    from src.pipeline.lifecycle import publish_unversioned
    rag = RagSettings()
    versioned_name = rag.collection_name()
    rag.qdrant.versioned_ingestion_enabled = False
    assert rag.collection_name() == versioned_name + "_unversioned"
    client = QdrantClient(":memory:")
    a = pipeline.Chunk("a", "a", "old", [1., 0.])
    b = pipeline.Chunk("b", "b", "new", [1., 0.])
    publish_snapshot(client, versioned_name, [a], [a.vector], {})
    publish_unversioned(client, rag.collection_name(), [a], [a.vector], {})
    publish_unversioned(client, rag.collection_name(), [b], [b.vector], {})
    assert client.count(versioned_name).count == 1
    hits = client.query_points(rag.collection_name(), query=[1., 0.]).points
    assert [h.payload["text"] for h in hits] == ["new"]
    with pytest.raises(ValueError, match="_unversioned"):
        publish_unversioned(client, versioned_name, [b], [b.vector], {})
    client.close()


@pytest.mark.parametrize("enforce,gate,budget,trace", [
    (False, True, True, True), (True, False, True, True),
    (True, True, False, True), (True, True, True, False),
])
def test_runtime_feature_switches(monkeypatch, enforce, gate, budget, trace):
    rag = RagSettings(validate_answer_citations=enforce,
        empty_evidence_abstention_enabled=gate, trace_enabled=trace)
    rag.retrieval.rerank_enabled = False
    rag.retrieval.query_rewrite_enabled = False
    rag.retrieval.use_qdrant = False
    rag.retrieval.context_budget_enabled = budget
    rag.retrieval.max_context_chars = 20
    hit = {"chunk_id": "a", "source": "a", "text": "A" * 100, "score": 1.}
    if not enforce or not trace:
        hit["text"] = "A"
    monkeypatch.setattr(pipeline, "get_index", lambda *a, **kw: [])
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **kw: [hit])
    monkeypatch.setattr(pipeline, "_use_fake_rag", lambda: False)
    counter = lambda *a: {"mode": "test"}
    if not trace:
        def counter(*args):
            pytest.fail("Tracing disabled must skip token accounting")
    monkeypatch.setattr(pipeline, "token_accounting", counter)
    raw = "Uncited answer." if not enforce else "Answer [a]."
    call = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))], usage=None))
    monkeypatch.setattr(pipeline, "_client", SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=call))), raising=False)
    result = asyncio.run(pipeline.ask_rag("Question", rag_settings=rag))
    call.assert_awaited_once()
    if not enforce:
        assert result.content == raw and not result.citation_validation["valid"]
    if not gate:
        assert result.evidence == [] and result.reason == "citation_rejected"
    if not budget:
        assert result.evidence == [hit]
    if not trace:
        assert result.raw_answer == "" and result.prompt_tokens_by_section == {}


def test_corpus_detection_switch_controls_fingerprinting(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "corpus_fingerprint", lambda *a: pytest.fail("Detection disabled"))
    keys = []
    monkeypatch.setattr(pipeline, "_cached_index", lambda *args: keys.append(args) or ())
    assert pipeline.get_index(tmp_path, detect_corpus_changes=False) == []
    assert keys[0][-1] == ""


def test_citation_grounding_judge_can_be_disabled():
    from src.eval.judge import judge_rubric
    assert "specific chunk(s) cited" in judge_rubric(True)
    assert "specific chunk(s) cited" not in judge_rubric(False)


def test_runner_honors_evaluation_switches_and_persists_mode(tmp_path, monkeypatch):
    import json
    import sys
    from scripts import run_golden_set
    from src.eval.golden import GoldenEntry
    from src.eval.judge import JudgeScore
    from src.pipeline.settings import Settings
    settings = Settings()
    settings.evaluation.kpis_enabled = False
    settings.evaluation.metrics_mode = "offline-proxy"
    settings.evaluation.thresholds_enabled = False
    settings.evaluation.citation_grounding_enabled = False
    entry = GoldenEntry(id="q", question="Policy?", expected_behavior="Approved",
                        document="a", answerability="answerable", evaluation_type="fact")
    hit = {"chunk_id": "a", "source": "a", "text": "Approved"}
    answer = pipeline.RagAnswer(question=entry.question, content="Approved [a].",
                               retrieved=[hit], evidence=[hit])
    monkeypatch.setattr(run_golden_set, "Settings", lambda: settings)
    monkeypatch.setattr(run_golden_set, "load_golden_set", lambda p: [entry])
    monkeypatch.setattr(run_golden_set, "load_corpus_documents", lambda p: {})
    monkeypatch.setitem(sys.modules, "src.pipeline.pipeline", SimpleNamespace(ask_rag=AsyncMock(return_value=[answer])))
    judge = AsyncMock(return_value=JudgeScore(accuracy=4, groundedness=4, format=4,
                         overall=4, passed=True, reasoning="Supported"))
    monkeypatch.setattr("src.eval.golden.judge_answer", judge)
    asyncio.run(run_golden_set._run(golden_path=tmp_path / "set.jsonl", corpus_dir=tmp_path,
        limit=1, rows_out=tmp_path / "rows.jsonl", summary_out=tmp_path / "summary.json",
        db_path=tmp_path / "results.db", thresholds_path=tmp_path / "must-not-be-read.json"))
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["kpis"] == {} and summary["rag_metrics"]["mode"] == "offline-proxy"
    assert judge.call_args.kwargs["citation_grounding_enabled"] is False
