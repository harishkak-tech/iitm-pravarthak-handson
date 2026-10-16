"""Validate golden-set structure and source anchors without API calls.

Use --fix-known-issues to normalise duplicate sources and evaluation labels.
Lexical anchor checks support review; they do not prove semantic entailment.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval.golden import GoldenEntry


def validate(rows, corpus, pdf_dir):
    errors, warnings = [], []
    seen_ids, seen_questions = set(), set()
    for raw in rows:
        label = raw.get("id", "unknown")
        try:
            entry = GoldenEntry.model_validate(raw)
        except Exception as exc:
            errors.append(f"{label}: invalid schema: {exc}")
            continue
        if entry.id in seen_ids:
            errors.append(f"{label}: duplicate ID")
        seen_ids.add(entry.id)
        question = " ".join(entry.question.lower().split())
        if question in seen_questions:
            errors.append(f"{label}: duplicate question")
        seen_questions.add(question)
        sources = entry.source_documents or ([entry.document] if entry.document else [])
        if len(sources) != len(set(sources)):
            errors.append(f"{label}: duplicate source documents")
        if entry.document and entry.source_documents and entry.document not in sources:
            errors.append(f"{label}: primary document absent from sources")
        for name in set(sources + ([entry.document] if entry.document else [])):
            if name not in corpus:
                errors.append(f"{label}: missing source {name}")
            if not (pdf_dir / (Path(name).stem + ".pdf")).is_file():
                errors.append(f"{label}: missing styled PDF for {name}")
        if entry.answerability == "answerable" and not sources:
            errors.append(f"{label}: answerable entry has no sources")
        if entry.evaluation_type.startswith("three-source") and len(set(sources)) != 3:
            errors.append(f"{label}: three-source label has {len(set(sources))} distinct sources")
        if "cross-document" in entry.evaluation_type and len(set(sources)) < 2:
            errors.append(f"{label}: cross-document label has fewer than two sources")
        context = "\n".join(corpus.get(name, "") for name in sources)
        for name, fragments in entry.evidence.items():
            if name not in sources:
                errors.append(f"{label}: evidence document {name} absent from sources")
            normalized = " ".join(corpus.get(name, "").split())
            if not fragments:
                errors.append(f"{label}: empty evidence list for {name}")
            for fragment in fragments:
                if not fragment.strip() or " ".join(fragment.split()) not in normalized:
                    errors.append(f"{label}: evidence fragment absent from {name}: {fragment!r}")
        if entry.answerability == "answerable" and entry.evidence and set(entry.evidence) != set(sources):
            errors.append(f"{label}: evidence does not cover every declared source")
        for code in set(re.findall(r"\b[A-Z]{2,4}-\d+\b", entry.expected_behavior)):
            if code not in context:
                errors.append(f"{label}: expected record identifier {code} absent from declared sources")
        if entry.expected_behavior.startswith(("Answer using the relevant", "Retrieve the relevant passage", "Answer only from the document's treatment")):
            warnings.append(f"{label}: broad expected behavior; consider a source-backed fact checklist")
    return errors, warnings


def fix_known_issues(rows):
    changes = []
    for row in rows:
        before = json.loads(json.dumps(row))
        sources = list(dict.fromkeys(row.get("source_documents", [])))
        if "source_documents" in row:
            row["source_documents"] = sources
        if sources:
            if row["evaluation_type"].startswith("three-source") and len(sources) == 2:
                row["evaluation_type"] = row["evaluation_type"].replace("three-source", "two-source", 1)
            if len(sources) == 1 and "cross-document" in row["evaluation_type"]:
                row["evaluation_type"] = row["evaluation_type"].replace("cross-document", "multi-section")
        if before != row:
            changes.append({"id": row["id"], "before": before, "after": row})
    return changes


def validate_snapshot(golden_path, root=ROOT):
    """Detect a changed dataset or corpus against its optional recorded snapshot."""
    manifest_path = golden_path.with_name("golden_set_manifest.json")
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if Path(manifest["golden_path"]).name != golden_path.name:
        return []
    errors = []
    paths = [(golden_path, manifest["golden_sha256"])]
    for source in manifest["corpus"]:
        name = source["document"]
        paths.extend([
            (root / manifest["text_directory"] / name, source["text_sha256"]),
            (root / manifest["pdf_directory"] / (Path(name).stem + ".pdf"), source["pdf_sha256"]),
        ])
    for path, expected in paths:
        if not path.is_file():
            errors.append(f"Snapshot file missing: {path.name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"Snapshot changed: {path.name}; review the golden set and refresh its manifest")
    expected_names = {source["document"] for source in manifest["corpus"]}
    actual_names = {path.name for path in (root / manifest["text_directory"]).glob("*.txt")}
    if expected_names != actual_names:
        errors.append("Snapshot document list differs from the current text corpus")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-path", type=Path, default=ROOT / "docs/goldenset/golden_set.jsonl")
    parser.add_argument("--fix-known-issues", action="store_true")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.golden_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    changes = fix_known_issues(rows) if args.fix_known_issues else []
    if changes:
        args.golden_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        (ROOT / "docs/runs/golden_set_revision_manifest.json").write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    corpus = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "docs/corpus_txt").glob("*.txt")}
    errors, warnings = validate(rows, corpus, ROOT / "docs/corpus_pdf_styled")
    errors.extend(validate_snapshot(args.golden_path))
    report = {
        "golden_path": str(args.golden_path), "total": len(rows),
        "answerability": dict(Counter(row["answerability"] for row in rows)),
        "errors": errors, "review_warnings": warnings,
        "limitations": [
            "Structural and record-anchor validation is deterministic; semantic completeness needs source review.",
            "Evidence fragments establish textual anchors, not full semantic entailment of every expected answer.",
            "This set is tied to the documented corpus snapshot; review it when corpus content changes.",
            "This validation does not call generation or judge models, measure pass rate, or change judge thresholds.",
        ],
    }
    report_path = ROOT / "docs/runs/golden_set_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Validated {len(rows)} entries: {len(errors)} errors, {len(warnings)} review warnings; {len(changes)} entries corrected")
    for error in errors:
        print(error)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
