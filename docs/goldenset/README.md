# Golden set for the current policy corpus

`golden_set.jsonl` replaces the old 60/84/104-question files and uses fresh `GS3-...` identifiers. The default evaluation and validation commands load this file.

The set was authored against the 14 documents in `docs/corpus_txt` and their matching styled PDFs on 14 October 2026. It contains 126 questions:

- 35 answerable single-document questions.
- 28 unanswerable questions: two for each document, testing unsupported amounts, live statistics, current deadlines or individual case information.
- 63 answerable cross-document questions, each requiring facts from two or three documents.

Exactly half of the 126 questions require multiple documents. The other half contains 35 answerable and 28 unanswerable single-document questions. Every corpus document has single-document coverage and participates in cross-document cases.

Every answerable entry has concrete expected behavior and an `evidence` mapping from each required document to excerpts present in that document. Excerpts are anchors for review, not complete reference answers. Whitespace is normalised when checking them. Unanswerable questions test whether the answer is available in this corpus, even if an external source might answer them.

Questions cover programme facts, numerical units and calculations, eligibility boundaries, jurisdictions, service stages, date-sensitive notices and distinctions between applications, approvals and delivered outcomes. Local training-record codes and the removed casebooks are excluded. The actual corpus still contains some training/editorial material identified in `docs/reviews/corpus_content_audit_20261014.md`; creating this set did not clean or rewrite the corpus.

`golden_set_manifest.json` records the dataset version, coverage, counts and SHA-256 hashes of the golden set and every text/PDF source. Review the set and refresh the snapshot whenever corpus content changes. Its scores are not directly comparable with the retired sets, and it is a development benchmark rather than an independently held-out generalisation measure.

From the repository root:

```powershell
python scripts/validate_corpus_pdfs.py
python scripts/validate_golden_set.py
python scripts/run_golden_set.py
```

The first two commands validate locally without generation/judge API calls. The last command runs evaluation using the configured retrieval index and judge; rebuild the index after corpus changes before using its scores. Validation does not measure answer quality or establish that all expected claims are semantically entailed just because their evidence fragments exist.
