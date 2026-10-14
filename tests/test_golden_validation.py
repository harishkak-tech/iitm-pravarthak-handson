"""Guard against invalid source coverage and non-repeatable editorial repairs."""

from scripts.validate_golden_set import fix_known_issues, validate


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
        id="Q062", document="one.txt", question="What is the pilot budget?",
        expected_behavior="Distinguish funding stages.", answerability="answerable",
        evaluation_type="numerical reasoning",
    ), dict(
        id="Q114", document="one.txt", source_documents=["one.txt", "two.txt", "two.txt"],
        question="What should reporting distinguish?", expected_behavior="Evidence stages.",
        answerability="answerable", evaluation_type="three-source reasoning",
    )]
    assert len(fix_known_issues(rows)) == 2
    assert fix_known_issues(rows) == []
    assert rows[1]["source_documents"] == ["one.txt", "two.txt"]
    assert rows[1]["evaluation_type"] == "two-source reasoning"
