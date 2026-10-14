"""Write a local failure report without calling an LLM or altering the corpus."""

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    summary = json.loads((ROOT / "docs/runs/golden_eval_summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (ROOT / "docs/runs/golden_eval_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    failed = [row for row in rows if not row["pass_fail"]]
    model = "not recorded"
    db_path = ROOT / "results.db"
    if db_path.exists():
        con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        try:
            if con.execute("SELECT name FROM sqlite_master WHERE name='golden_runs'").fetchone():
                for saved_model, saved_summary in con.execute("SELECT model, summary_json FROM golden_runs ORDER BY id DESC"):
                    if json.loads(saved_summary).get("judge_log_path") == summary.get("judge_log_path"):
                        model = saved_model
                        break
        finally:
            con.close()
    lines = [
        "# Golden-run failure audit", "",
        f"Judge log: `{summary['judge_log_path']}`. Generation model: `{model}`.",
        f"Passed: {summary['passed']}/{summary['total']} ({summary['pass_rate']:.1%}). Failed: {len(failed)}.",
        f"Failed rows missing at least one expected source: {sum(not row['retrieval_hit'] for row in failed)}.", "",
        "## Findings and proposed changes", "",
        "1. Remove repeated administrative paragraphs before indexing. This preserves facts while reducing duplicate candidates. The duplication counts below refer to TXT sources; regenerate and inspect the styled PDFs after an approved corpus edit.",
        "2. Keep topic-specific passages self-contained: name the subject, record identifier, required fields and verification conditions together. Copy only existing source facts; do not add golden answers as new policy facts.",
        "3. Keep each pilot's name, districts and reporting period beside its accounting figures. Q062 and Q069 retrieve two separate pilots with different budgets; ambiguous questions should accept clarification or identify the intended pilot explicitly.",
        "4. Review judge failures before using pass rate as the sole metric. Q024's expected behavior permits a concise subset, but its judge demands omitted examples. Q127's judge rejects claimed need and source record although the RRF-9 source requires both. Q075 correctly abstains according to the judge but is penalized for supplementary figures.",
        "5. Capture retrieved chunks and the exact generation context in future runs. A document-level retrieval hit cannot establish that the required passage reached the model. Current saved rows do not include that context, so attribution to retrieval versus generation is provisional.",
        "6. Establish a gpt-4o-mini baseline, then compare changes on the same questions and judge. This run used gpt-5-mini; improved gpt-4o-mini performance is not yet measured.", "",
        "## Source duplication", "",
        "| Source | Characters | Repeated paragraph occurrences beyond first |",
        "| --- | ---: | ---: |",
    ]
    for path in sorted((ROOT / "docs/corpus").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        counts = Counter(p.strip() for p in re.split(r"\n\s*\n", text) if p.strip())
        lines.append(f"| {path.name} | {len(text)} | {sum(n - 1 for n in counts.values())} |")
    lines.extend(["", "## Every failing question", ""])
    for row in failed:
        lines.extend([
            f"### {row['id']}: {row['question']}", "",
            f"Expected source documents retrieved: {row['retrieval_hit']}. Accuracy: {row['judge_accuracy']}; groundedness: {row['judge_groundedness']}.", "",
            f"Expected behavior: {row['expected_behavior']}", "",
            f"Judge reasoning: {row['judge_reasoning']}", "",
            "Candidate answer:", "", row["answer_text"], "",
        ])
    out = ROOT / "docs/runs/golden_failure_audit.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(failed)} failures to {out}")


if __name__ == "__main__":
    main()
