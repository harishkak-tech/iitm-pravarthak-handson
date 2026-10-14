"""Validate golden-set structure and source anchors without API calls.

Use --fix-known-issues to apply the documented corpus-v2 editorial corrections.
Lexical anchor checks support review; they do not prove semantic entailment.
"""

from __future__ import annotations

import argparse
from collections import Counter
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
        label = row["id"]
        if label == "Q077":
            sources = ["11_Integrated_District_Delivery_Casebook.txt", "12_State_Implementation_Brief.txt"]
            row["source_documents"] = sources
        if sources:
            if row["evaluation_type"].startswith("three-source") and len(sources) == 2:
                row["evaluation_type"] = row["evaluation_type"].replace("three-source", "two-source", 1)
            if len(sources) == 1 and "cross-document" in row["evaluation_type"]:
                row["evaluation_type"] = row["evaluation_type"].replace("cross-document", "multi-section")
        number = int(label[1:])
        if 61 <= number <= 80 and label not in {"Q068", "Q071", "Q077", "Q080"} and not row["question"].startswith("For the "):
            pilot = "Integrated District Delivery Pilot (Sundar and Narmada)" if number <= 70 else "Connected Services Pilot (Aster and Bhagirathi)"
            row["question"] = f"For the {pilot}, {row['question'][0].lower() + row['question'][1:]}"
        if label == "Q012":
            row["expected_behavior"] = "State that MGNREGA provides a legal framework for guaranteed wage employment subject to the provisions of the Act. The corpus does not specify an exact number of guaranteed days; do not require or invent that number."
        if label == "Q075":
            row["expected_behavior"] = "Abstain from giving a completed-house count: the Connected Services brief reports 1,200 housing referrals, not completed houses. Mentioning that referral count or distinguishing unrelated installation figures is acceptable if clearly labeled and not presented as completed houses."
        if label == "Q127":
            row["expected_behavior"] = "State that RRF-9 requires the incident identifier, household or site reference, claimed need, source record, action owner, next review date and verification method. Closure requires documented verification, not merely a caseworker note. Accept equivalent wording for these fields."
        if before != row:
            changes.append({"id": label, "before": before, "after": row})
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-path", type=Path, default=ROOT / "docs/goldenset/golden_set_104.jsonl")
    parser.add_argument("--fix-known-issues", action="store_true")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.golden_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    changes = fix_known_issues(rows) if args.fix_known_issues else []
    if changes:
        args.golden_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        (ROOT / "docs/runs/golden_set_revision_manifest.json").write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    corpus = {p.name: p.read_text(encoding="utf-8") for p in (ROOT / "docs/corpus").glob("*.txt")}
    errors, warnings = validate(rows, corpus, ROOT / "docs/corpus_pdf_styled")
    report = {
        "golden_path": str(args.golden_path), "total": len(rows),
        "answerability": dict(Counter(row["answerability"] for row in rows)),
        "errors": errors, "review_warnings": warnings,
        "limitations": [
            "Structural and record-anchor validation is deterministic; semantic completeness needs source review.",
            "Several questions exercise the same facts (Q061/Q064, Q093/Q125, Q094/Q126); keep their weighting in mind.",
            "Corpus-v2 reading notes were informed by failures on this set. Treat it as a development set; use new held-out questions to measure generalisation.",
            "This validation does not call generation or judge models, measure pass rate, or change judge thresholds.",
        ],
    }
    (ROOT / "docs/runs/golden_set_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(rows)} entries: {len(errors)} errors, {len(warnings)} review warnings; {len(changes)} entries corrected")
    for error in errors:
        print(error)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
