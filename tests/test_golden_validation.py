"""Guard against invalid source coverage and non-repeatable editorial repairs."""

from scripts.validate_golden_set import fix_known_issues, validate, validate_snapshot


def test_validator_detects_duplicate_sources_and_missing_evidence(tmp_path):
    row = dict(
        id="Q999", document="one.txt", source_documents=["one.txt", "one.txt"],
        question="What does the record say?", expected_behavior="Require JGR-11 verification.",
        answerability="answerable", evaluation_type="three-source reasoning",
    )
    (tmp_path / "one.pdf").touch()
    errors, _ = validate([row, row], {"one.txt": "Unrelated source."}, tmp_path)
    assert any("duplicate source documents" in error for error in errors)
    assert any("three-source label" in error for error in errors)
    assert any("identifier JGR-11 absent" in error for error in errors)
    assert any("duplicate ID" in error for error in errors)


def test_editorial_fixes_are_idempotent():
    rows = [dict(
        id="GS3-01-01", document="one.txt", source_documents=["one.txt", "one.txt"], question="What is the policy?",
        expected_behavior="Distinguish funding stages.", answerability="answerable",
        evaluation_type="cross-document reasoning",
    ), dict(
        id="Q114", document="one.txt", source_documents=["one.txt", "two.txt", "two.txt"],
        question="What should reporting distinguish?", expected_behavior="Evidence stages.",
        answerability="answerable", evaluation_type="three-source reasoning",
    )]
    assert len(fix_known_issues(rows)) == 2
    assert fix_known_issues(rows) == []
    assert rows[1]["source_documents"] == ["one.txt", "two.txt"]
    assert rows[1]["evaluation_type"] == "two-source reasoning"


def test_normalizer_does_not_apply_retired_question_specific_edits():
    rows = [dict(
        id=label, document="one.txt", question="What does the current corpus say?",
        expected_behavior="Use the current facts.", answerability="answerable",
        evaluation_type="retrieval",
    ) for label in ("Q012", "Q062", "Q075", "Q077", "Q127", "GS3-X01")]
    assert fix_known_issues(rows) == []


def test_validator_checks_evidence_against_declared_sources(tmp_path):
    row = dict(
        id="GS3-X01", document="one.txt", source_documents=["one.txt", "two.txt"],
        question="What do the two services do?", expected_behavior="Describe both services.",
        answerability="answerable", evaluation_type="cross-document reasoning",
        evidence={"one.txt": ["missing quotation"]},
    )
    for name in ("one", "two"):
        (tmp_path / (name + ".pdf")).touch()
    corpus = {"one.txt": "First service.", "two.txt": "Second service."}
    errors, _ = validate([row], corpus, tmp_path)
    assert any("evidence fragment absent" in error for error in errors)
    assert any("every declared source" in error for error in errors)
    row["evidence"] = {"one.txt": ["First service."], "two.txt": ["Second service."]}
    assert validate([row], corpus, tmp_path) == ([], [])


def test_snapshot_detects_changed_content_and_added_documents(tmp_path):
    import hashlib
    import json

    golden = tmp_path / "golden_set.jsonl"
    golden.write_text("{}\n", encoding="utf-8")
    text_dir, pdf_dir = tmp_path / "text", tmp_path / "pdf"
    text_dir.mkdir()
    pdf_dir.mkdir()
    text = text_dir / "one.txt"
    pdf = pdf_dir / "one.pdf"
    text.write_text("Original policy.", encoding="utf-8")
    pdf.write_bytes(b"Snapshot fixture")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "golden_path": golden.name, "golden_sha256": digest(golden),
        "text_directory": "text", "pdf_directory": "pdf",
        "corpus": [{"document": text.name, "text_sha256": digest(text), "pdf_sha256": digest(pdf)}],
    }
    golden.with_name("golden_set_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_snapshot(golden, tmp_path) == []
    text.write_text("Changed policy.", encoding="utf-8")
    (text_dir / "two.txt").write_text("New policy.", encoding="utf-8")
    errors = validate_snapshot(golden, tmp_path)
    assert any("Snapshot changed: one.txt" in error for error in errors)
    assert any("document list differs" in error for error in errors)


def test_current_golden_set_matches_pdf_sources():
    import json
    from collections import Counter
    from pathlib import Path
    from src.eval.golden import load_corpus_documents, load_golden_set

    root = Path(__file__).resolve().parents[1]
    path = root / "docs/goldenset/golden_set.jsonl"
    manifest = json.loads(path.with_name("golden_set_manifest.json").read_text(encoding="utf-8"))
    entries = load_golden_set(path)
    assert len(entries) == manifest["total"]
    assert dict(Counter(entry.answerability for entry in entries)) == manifest["answerability"]
    multi_source = [entry for entry in entries if len(set(entry.source_documents)) >= 2]
    assert len(multi_source) * 2 == len(entries)
    assert len(multi_source) == manifest["cross_document_questions"]
    assert all(entry.answerability == "answerable" for entry in multi_source)
    assert all(set(entry.evidence) == set(entry.source_documents) for entry in multi_source)
    pdf_dir = root / "docs/corpus_pdf_styled"
    corpus = load_corpus_documents(pdf_dir)
    assert {entry.document for entry in entries} == set(corpus)
    assert all(entry.evidence for entry in entries if entry.answerability == "answerable")
    errors, warnings = validate([entry.model_dump() for entry in entries], corpus, pdf_dir)
    assert not errors, errors
    assert not warnings, warnings
    assert validate_snapshot(path) == []
