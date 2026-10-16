# Corpus PDF content audit

Reviewed: 14 October 2026. Scope: all 14 PDFs in `docs/corpus_pdf_styled`, their matching text sources, source-reference manifest, and the PDF extraction path. No corpus content was edited during this audit.

## Result

The PDFs are readable, but the collection still mixes official-source summaries with local training material and repeated reporting guidance. For a government-policy reference corpus, the training-only definitions and repeated boilerplate are cleanup candidates. Related policy topics should be organised rather than indiscriminately deleted.

## Checks completed

- All 14 PDFs opened and extracted successfully: 47 pages in total.
- Extracted body text matched the corresponding text sources exactly, after excluding page footers and normalising whitespace.
- No exact repeated paragraphs were found within an individual document. A separate comparison across documents found one repeated block in ten files.
- No text lines outside the page body bounds were detected. All 47 rendered pages were visually reviewed using contact sheets.
- All `[GOV-...]` references resolve to manifest entries associated with the current document filenames. This checks reference consistency, not the current accuracy of every external source.
- Document numbering and matching text/PDF names run continuously from 01 through 14.

## Content findings

### 1. Local training-record definitions mixed with policy material

The corpus explicitly identifies these kinds of codes as local training conventions, not authenticated government-prescribed forms. Nevertheless, their individual definitions use wording such as "is used", "must include" and "requires", which can look authoritative when a retrieved chunk omits the disclaimer elsewhere in the document.

| Code | Local record name | Primary source location | Styled PDF page |
| --- | --- | --- | --- |
| SRR-12 | Source Reliability Register | `01_Agriculture_and_Farmers_Welfare.txt:71` | 3 |
| NTR-7 | Nutrition Referral Tracker | `02_Health_and_Public_Health.txt:70` | 3 |
| GSC-8 | Gender Support Case File | `03_Education_and_Skills.txt:77` | 3 |
| ECR-5 | Environmental Compliance Record | `05_Renewable_Energy_and_Power.txt:52` | 2 |
| JGR-11 | Justice and Grievance Register | `06_Digital_India_and_Public_Services.txt:80` | 4 |
| FPS-21 | Fair Price Shop Exception Log | `07_Transport_and_Infrastructure.txt:59` | 2 |
| MSR-3 | Migrant Support Record | `08_MSME_and_Industrial_Development.txt:91` | 4 |
| RRF-9 | Relief Reconciliation Form | `10_Rural_Development_and_Livelihoods.txt:62` | 3 |

Recommendation: move the definitions and their dependent exercises to a separate training-fixture collection, or remove them from the policy-reference corpus. Update dependent evaluation questions at the same time. Do not relabel them as official forms. SRR-12 and NTR-7 also appear in cross-document references that would need cleanup.

### 2. Exact boilerplate duplication across documents

The complete "Common Administration and Evidence Standards" block appears in documents 01 through 10. Its body starts "Use a written procedure with a named responsible authority". There are ten copies of this block, or nine copies beyond the first. The earlier per-document duplicate check does not detect this cross-document repetition.

Recommendation: keep this guidance once in a methodology document outside the policy retrieval collection, or remove it from the ingestible PDFs. This reduces repeated generic text competing with specific programme facts.

### 3. Internal corpus instructions and repeated editorial guidance

All 14 documents contain corpus-related or editorial wording. Examples include instructions beginning "In corpus reporting exercises", explanations that a distinction is "editorial guidance", local file paths such as `docs/corpus_sources.json`, and references to training cases or pilots. Documents 04 and 12 and the rural-housing supplement in document 10 still mention casebook or pilot material even after the two casebook files were removed.

Some cautions are useful policy context: an application is different from an approval, or a loan from a grant. The cleanup should preserve these substantive distinctions while removing unnecessary instructions about how the training corpus itself should be used. Standalone editorial reporting paragraphs can be moved to methodology material.

### 4. Mixed topics and document naming

Eight files contain a second top-level policy title: 01, 02, 03, 05, 06, 07, 08 and 10. Related topics are not automatically unwanted, but the filenames do not consistently describe the full contents.

Examples:

- Document 07, titled Transport and Infrastructure, also contains Food Security, Public Distribution and Local Nutrition, including the local FPS-21 definition.
- Document 03 also contains Gender Equality, Safety and Care Economy.
- Document 08 also contains Labour Mobility, Social Protection and Urban Informal Work.
- Document 06 also contains Legal Aid, Citizen Grievances and Administrative Justice.

Recommendation: split these into accurately named topic documents or broaden the names and metadata. Preserve relevant official-source policy information when reorganising.

### 5. Provenance identifiers need retrieval support

The `[GOV-...]` identifiers are useful provenance, not junk to delete. Their URLs live in the separate JSON manifest. The current ingestion code reads PDFs and attaches document/page/section metadata, but does not resolve that manifest into source URLs. A reference identifier or local manifest path in retrieved text therefore does not by itself give the model the underlying official URL.

Recommendation: attach resolved official URLs to chunk metadata or include usable references in each document. Keep review dates and version-specific qualifications where they help interpret policy facts.

## PDF layout and ingestion findings

### Headings stranded at page ends

| Document | Page | Heading |
| --- | --- | --- |
| 01 Agriculture and Farmers' Welfare | 3 | Climate Resilience and Emergency Service |
| 04 Housing and Urban Development | 2 | Implementation |
| 09 Financial Inclusion and Social Security | 2 | Financial-Inclusion Delivery Channels and Payment Checks |
| 10 Rural Development and Livelihoods | 2 | Relief Lifecycle |

These are pagination defects, not corruption. Several PDFs also have lightly filled final pages; reflowing content can improve presentation without deleting valid information.

### Page-number footers enter ingestion text

All 47 pages have page-number footers. In `src/pipeline/pipeline.py`, `_load_pdf_documents` uses the full result of `page.get_text("text")` and collects all text lines. The fixed, semantic and structure-aware chunking branches consume these values without a footer filter. Footer text such as "Page 1 of 3" is therefore eligible for chunking. The evaluation loader also extracts complete page text.

Recommendation: preserve page numbers visually in PDFs, but exclude the footer area from body extraction. The text/PDF consistency validator already excludes the bottom 40 points; the ingestion path should use an equivalent, tested body-text rule.

## Suggested cleanup order

1. Separate local training-record definitions and revise their evaluation dependencies.
2. Remove cross-document boilerplate and trim internal corpus instructions while retaining useful policy qualifications.
3. Organise mixed-topic sections under appropriate names and resolve source URLs for retrieval.
4. Correct pagination and exclude page footers from ingestion.
5. Revalidate matching text/PDF content and evaluation coverage, then rebuild the retrieval index.

This was a local content and layout audit. It did not re-verify every policy amount, deadline or eligibility rule against live official sources, run model-quality evaluations, or modify the Qdrant index.
