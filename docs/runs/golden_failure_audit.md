# Golden-run failure audit

Judge log: `docs\runs\judge_logs\golden_eval_20261011_171210_406427.jsonl`. Generation model: `gpt-5-mini`.
Passed: 77/104 (74.0%). Failed: 27.
Failed rows missing at least one expected source: 8.

## Findings and proposed changes

1. Remove repeated administrative paragraphs before indexing. This preserves facts while reducing duplicate candidates. The duplication counts below refer to TXT sources; regenerate and inspect the styled PDFs after an approved corpus edit.
2. Keep topic-specific passages self-contained: name the subject, record identifier, required fields and verification conditions together. Copy only existing source facts; do not add golden answers as new policy facts.
3. Keep each pilot's name, districts and reporting period beside its accounting figures. Q062 and Q069 retrieve two separate pilots with different budgets; ambiguous questions should accept clarification or identify the intended pilot explicitly.
4. Review judge failures before using pass rate as the sole metric. Q024's expected behavior permits a concise subset, but its judge demands omitted examples. Q127's judge rejects claimed need and source record although the RRF-9 source requires both. Q075 correctly abstains according to the judge but is penalized for supplementary figures.
5. Capture retrieved chunks and the exact generation context in future runs. A document-level retrieval hit cannot establish that the required passage reached the model. Current saved rows do not include that context, so attribution to retrieval versus generation is provisional.
6. Establish a gpt-4o-mini baseline, then compare changes on the same questions and judge. This run used gpt-5-mini; improved gpt-4o-mini performance is not yet measured.

## Source duplication

| Source | Characters | Repeated paragraph occurrences beyond first |
| --- | ---: | ---: |
| 01_Agriculture_and_Farmers_Welfare.txt | 131215 | 139 |
| 02_Health_and_Public_Health.txt | 129386 | 139 |
| 03_Education_and_Skills.txt | 126436 | 140 |
| 04_Housing_and_Urban_Development.txt | 125443 | 140 |
| 05_Renewable_Energy_and_Power.txt | 127417 | 140 |
| 06_Digital_India_and_Public_Services.txt | 129205 | 139 |
| 07_Transport_and_Infrastructure.txt | 127847 | 140 |
| 08_MSME_and_Industrial_Development.txt | 127819 | 140 |
| 09_Financial_Inclusion_and_Social_Security.txt | 127706 | 139 |
| 10_Rural_Development_and_Livelihoods.txt | 129359 | 139 |
| 11_Integrated_District_Delivery_Casebook.txt | 3633 | 0 |
| 12_State_Implementation_Brief.txt | 3136 | 0 |

## Every failing question

### Q013: What role do Gram Sabha review and social audit play for rural employment works?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: State that Gram Sabha review and social audit should make the proposed asset, expenditure, work completed, and maintenance responsibility visible to the community.

Judge reasoning: The candidate answer provides a detailed explanation of the roles of Gram Sabha review and social audit, but it includes additional information not directly related to the expected behavior. The expected behavior focuses on making the proposed asset, expenditure, work completed, and maintenance responsibility visible to the community. While the candidate answer mentions this, it also includes other roles such as separating asset vs. outcome, verifying entitlement and transactions, and operating within formal verification procedures, which are not directly supported by the source context provided for this specific question. Therefore, the accuracy and groundedness scores are limited to 2. The format is clear and well-structured, earning a score of 3.

Candidate answer:

Gram Sabha review and social audit perform complementary verification and transparency functions for rural employment works:

- Make planning and delivery visible: they ensure the proposed asset, the expenditure, the work completed, and who is responsible for maintenance are visible to the community (planning/financial/completion/maintenance records) [10_Rural_Development_and_Livelihoods.txt#page-19-chunk-9].  
- Separate asset vs. outcome: Gram Sabha review enables scrutiny of both the completed physical asset and the later service or hydrological outcome, so the community can distinguish between construction and subsequent performance/benefits (asset vs. outcome) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-9].  
- Verify entitlement and transactions: social audit and grievance review test whether a reported transaction actually corresponds to an accessible entitlement for the household (transaction-to-entitlement verification) [07_Transport_and_Infrastructure.txt#page-35-chunk-16].  
- Operate within formal verification procedures: audit and verification for Rural Development and Livelihoods should be run through a written procedure with a named responsible authority and be interpreted in an evidence‑based, inclusive, and proportionate manner (administration and standards for verification) [10_Rural_Development_and_Livelihoods.txt#page-29-chunk-11] [10_Rural_Development_and_Livelihoods.txt#page-29-chunk-19] [10_Rural_Development_and_Livelihoods.txt#page-29-chunk-3].

If you want, I can summarize these roles into a short checklist for conducting a Gram Sabha review and social audit.

### Q015: What delivery channels and safeguards are described for financial-inclusion and social-security programmes?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 3.

Expected behavior: Use the corpus to identify formal financial channels/digital benefit transfer, accessible banking channels, accurate records, and grievance mechanisms as relevant delivery or safeguard mechanisms. Do not invent a mechanism not stated in the document.

Judge reasoning: The candidate answer accurately reflects the source context by stating that delivery standards and risk safeguards must be administered through a written procedure with a named responsible authority. However, it fails to mention specific delivery channels or safeguard mechanisms like formal financial channels, digital benefit transfer, accessible banking channels, accurate records, and grievance mechanisms, which are expected. The answer is well-structured and clear, but due to the omission of key expected details, the accuracy score is limited to 2. The groundedness is good as it does not contradict the source, but it lacks completeness.

Candidate answer:

Supported by the provided context:

- Delivery standards for Financial Inclusion and Social Security programmes must be administered through a written procedure with a named responsible authority [09_Financial_Inclusion_and_Social_Security.txt#page-9-chunk-7; 09_Financial_Inclusion_and_Social_Security.txt#page-8-chunk-20].  
- Authorities should interpret those delivery standards in an evidence‑based, inclusive, and proportionate way to the programmes’ needs [09_Financial_Inclusion_and_Social_Security.txt#page-8-chunk-28; 09_Financial_Inclusion_and_Social_Security.txt#page-10-chunk-1].  
- Risk and safeguards arrangements must likewise be administered through a written procedure with a named responsible authority [09_Financial_Inclusion_and_Social_Security.txt#page-18-chunk-24; 09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-18].

What is not in the provided context:
- No specific delivery channels are described (e.g., cash, bank accounts, mobile money, vouchers, in‑person kiosks).  
- No detailed list of safeguard measures or their operational content (e.g., data protection steps, grievance mechanisms, verification processes) is provided.

### Q018: What implementation challenges affect education and skill-development programmes?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Retrieve the relevant passage and answer only with information supported by the document.

Judge reasoning: The candidate answer identifies several implementation challenges affecting education and skill-development programmes, such as aligning training with labor-market needs and addressing broad policy objectives. However, it includes some points that are not directly supported by the source context, such as the mention of inclusiveness and proportionality to needs, which is not clearly linked to implementation challenges in the provided context. Additionally, the point about coordination across government levels for rural programmes is not explicitly tied to education and skills in the source context. The format is clear and well-structured, but due to the inaccuracies and lack of grounding, the scores for accuracy and groundedness are limited.

Candidate answer:

Supported by the provided context, these implementation challenges affect education and skill-development programmes:

- Aligning training with labour‑market needs — effective skills policy requires that training content be aligned with actual labour‑market demand [03_Education_and_Skills.txt#page-1-chunk-6].

- Addressing a broad set of policy objectives simultaneously — programmes must cover access, quality, equity, learning outcomes, teacher development, higher education, vocational learning and the link between education and employability, which creates a wide scope for implementation [03_Education_and_Skills.txt#page-1-chunk-0].

- Ensuring inclusiveness and proportionality to needs — programmes should be inclusive and proportionate to the needs of the Education and Skills sector, which implies meeting diverse needs across populations [03_Education_and_Skills.txt#page-10-chunk-0; 03_Education_and_Skills.txt#page-14-chunk-0].

- Administrative complexity / expanded implementation framework — there is an expanded policy implementation framework (a longer, paragraph‑based administrative treatment), indicating administrative complexity in implementing Education and Skills policies [03_Education_and_Skills.txt#page-1-chunk-13].

- Administering continuity and resilience arrangements — continuity and resilience arrangements for Education and Skills need to be administered, indicating an implementation task/challenge around maintaining continuity and resilience [03_Education_and_Skills.txt#page-31-chunk-28].

- Coordination across government levels for rural programmes — rural programmes (which include education/skills interventions in rural areas) require coordination across national, State and local institutions, posing an implementation challenge for multi‑level coordination and inclusion [10_Rural_Development_and_Livelihoods.txt#page-1-chunk-7].

What the provided context does NOT supply
- The context does not provide details or examples of other common implementation barriers (for example, specific funding constraints, teacher shortages, infrastructure gaps, monitoring & evaluation mechanisms, or concrete case studies). It also does not quantify the scale or frequency of these challenges.

### Q021: Which groups are intended to benefit from renewable-energy and power programmes?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Retrieve the relevant passage and answer only with information supported by the document.

Judge reasoning: The candidate answer accurately reflects the general objectives of renewable-energy and power programmes, such as improving electricity access and supporting energy security, which are supported by the source context. However, it incorrectly claims that the document does not list specific population groups as beneficiaries, which is not explicitly stated in the source context. The answer is well-structured and clear, but the lack of specific beneficiary groups mentioned in the source context limits its accuracy and groundedness scores.

Candidate answer:

Supported by the provided context:
- Renewable-energy and power programmes are intended to improve electricity access, reliability, affordability and sustainability, and to support long-term energy security and lower‑carbon development — i.e., beneficiaries are those who need better access to and more affordable, reliable, sustainable electricity and the wider public interest in energy security and decarbonisation [05_Renewable_Energy_and_Power.txt#page-1-chunk-0].
- Authorities are instructed to interpret mandates and objectives in an evidence‑based, inclusive and proportionate way to meet the needs of renewable energy and power — indicating a broadly inclusive beneficiary scope rather than a narrow, exclusive one [05_Renewable_Energy_and_Power.txt#page-3-chunk-12; 05_Renewable_Energy_and_Power.txt#page-2-chunk-8].

Not supported by the provided context:
- The document excerpts do not list specific population groups (for example: rural households, low‑income consumers, businesses, industry, or particular regions) as intended beneficiaries. No such detailed beneficiary list appears in the supplied text.

### Q023: What implementation challenges affect MSME and industrial-development programmes?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 3.

Expected behavior: Retrieve the relevant passage and answer only with information supported by the document.

Judge reasoning: The candidate answer accurately identifies that the source context does not list specific implementation challenges but infers potential issues from the administrative requirements and objectives. However, it does not provide a complete or direct answer to the question about implementation challenges, as the source does not explicitly mention them. The answer is well-grounded in the source context, as it correctly references the need for written procedures and evidence-based interpretation. The format is clear and well-structured, but the lack of direct information on challenges limits its accuracy score.

Candidate answer:

Short answer: The provided excerpts do not directly list specific implementation challenges. They do, however, state the administrative design and interpretive requirements whose absence or weak application would impair MSME and industrial-development programmes.

Supported facts and implications from the context
- Programmes should be administered through a written procedure with a named responsible authority; lacking such documented responsibility would hinder clear implementation and accountability [08_MSME_and_Industrial_Development.txt#page-3-chunk-4] [08_MSME_and_Industrial_Development.txt#page-2-chunk-16].  
- Authorities are required to interpret mandate and objectives in an evidence‑based, inclusive and proportionate way; failure to apply those principles (e.g., not using evidence, not being inclusive or proportionate) would undermine effective implementation [08_MSME_and_Industrial_Development.txt#page-2-chunk-8] [08_MSME_and_Industrial_Development.txt#page-3-chunk-12] [08_MSME_and_Industrial_Development.txt#page-8-chunk-0] [08_MSME_and_Industrial_Development.txt#page-12-chunk-0].  
- MSME policy objectives that programmes must deliver include promotion of entrepreneurship, employment, competitiveness, technology adoption and access to markets and finance; shortcomings in delivering on any of these objectives point to implementation gaps (the text lists these objectives but does not enumerate obstacles) [08_MSME_and_Industrial_Development.txt#page-1-chunk-0].  
- An expanded policy implementation framework exists (longer, paragraph‑based administrative treatment), which implies additional administrative detail and complexity that implementers must follow; complexity or poor uptake of that framework could be a practical challenge, though the text does not provide examples [08_MSME_and_Industrial_Development.txt#page-1-chunk-16].

What the context does NOT contain
- The excerpts do not provide a concrete list of real-world implementation problems (for example: funding shortfalls, capacity gaps, coordination failures, monitoring & evaluation weaknesses, regulatory barriers, corruption, or timeline delays). Those specific challenges are not stated in the provided text.

If you want a list of commonly reported implementation challenges (beyond what these excerpts support), tell me and I will provide them, but that would go beyond the supplied context.

### Q024: What outcomes are rural-development and livelihoods programmes intended to support?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Answer from the policy overview: employment, improved rural housing, road connectivity and access to markets/schools/healthcare/services, and livelihoods supported through SHGs, savings, credit, skills, enterprise development, and local participation. A concise subset is acceptable if it faithfully represents the document; do not require every listed example.

Judge reasoning: The candidate answer includes several relevant outcomes such as employment, improved housing, and infrastructure, which align with the expected behavior. However, it omits key aspects like road connectivity and access to markets, schools, and healthcare, which are crucial for a complete answer. Additionally, while the answer is mostly grounded in the source context, it introduces some elements like 'inclusive, proportionate implementation' that are not directly tied to the expected outcomes. The format is clear and well-structured, but due to the omissions and slight deviations, the accuracy and groundedness scores are limited.

Candidate answer:

According to the provided context, rural-development and livelihoods programmes are intended to support these outcomes:

- Employment (including non-farm employment) and broader livelihoods opportunities [10_Rural_Development_and_Livelihoods.txt#page-1-chunk-0].  
- Improved housing conditions for eligible rural households (subject to land, construction capacity, water/electricity access and local implementation) [10_Rural_Development_and_Livelihoods.txt#page-1-chunk-5].  
- Roads, access to essential services and social assistance that support rural living standards [10_Rural_Development_and_Livelihoods.txt#page-1-chunk-0].  
- Strengthened local institutions and collective/community organizations that support savings, credit access, skills development, enterprise development and local participation [10_Rural_Development_and_Livelihoods.txt#page-1-chunk-7].  
- Infrastructure and natural‑resource assets that enhance resilience (for example, water‑conservation, groundwater recharge and watershed assets linked to village water‑security planning) [10_Rural_Development_and_Livelihoods.txt#page-19-chunk-8].  
- Inclusive, proportionate implementation tailored to local needs and coordinated across national, State and local institutions [10_Rural_Development_and_Livelihoods.txt#page-8-chunk-0; 10_Rural_Development_and_Livelihoods.txt#page-1-chunk-7].  

If you want, I can group these into program design objectives or suggest indicators to measure each outcome.

### Q062: What is the difference between the pilot's approved envelope, released funds, and reported expenditure?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Distinguish approved, released, and spent amounts and report the three values with their accounting meaning.

Judge reasoning: The candidate answer correctly identifies the three financial measures: approved, released, and reported expenditure, and provides their definitions. However, it introduces an inconsistency by mentioning two different approved amounts (Rs 48 crore and Rs 42 crore) without explaining the discrepancy, which is not addressed in the source context. This affects both accuracy and groundedness, as the answer should not introduce confusion or unsupported claims. The format is clear and well-structured, but the lack of clarity on the differing approved figures impacts the overall score.

Candidate answer:

Short answer: they are three distinct financial measures — approved = the planned/allotted amount, released = funds transferred out to implementing agencies, and reported expenditure = the amount recorded as spent (payments for operations, training, etc.). These should not be used interchangeably [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-4; 12_State_Implementation_Brief.txt#page-1-chunk-5].

What the context reports (numbers)
- Approved pilot envelope: Rs 48 crore (documented as the approved pilot envelope) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3]. Another place records a state-approved allocation of Rs 42 crore for the pilot [12_State_Implementation_Brief.txt#page-1-chunk-3]. The context does not explain the difference between these two approved figures.
- Released by 31 March 2025: Rs 31 crore (funds transferred) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3; 12_State_Implementation_Brief.txt#page-1-chunk-5].
- Reported expenditure: Rs 27.4 crore (amount recorded as spent) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3; 12_State_Implementation_Brief.txt#page-1-chunk-5].

Other relevant distinctions in the context
- A released transfer is not the same as a successful credit to a beneficiary; reporting should separate released amounts from amounts actually credited/received by beneficiaries [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-11; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].
- For budgeting questions, the materials recommend clarifying whether “budget” refers to approved, released or spent amounts [11_Integrated_District_Delivery_Casebook.txt#page-2-chunk-5].

What the context does not provide
- A reconciliation or explanation for the differing approved figures (Rs 48 crore vs Rs 42 crore) is not provided in the excerpts.

### Q069: How much of the approved pilot budget was spent?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 3.

Expected behavior: Clarify that the approved amount was Rs 48 crore and reported expenditure was Rs 27.4 crore; do not confuse expenditure with release.

Judge reasoning: The candidate answer provides the correct figures for the approved budget (Rs 48 crore) and the reported expenditure (Rs 27.4 crore) from the Integrated District Delivery Casebook, which aligns with the expected behavior. However, it introduces additional information from the State Implementation Brief, which is not required by the expected behavior and could cause confusion. This affects the accuracy score, as the answer should focus solely on the figures relevant to the question. The groundedness is good, as the figures are supported by the source context, but the inclusion of unnecessary information slightly detracts from it. The format is clear and well-structured, but the inclusion of extraneous details affects its conciseness.

Candidate answer:

The context asks to clarify whether “budget” means approved, released or spent; below I give separate, source‑specific figures for approved, released and spent amounts.

1) Integrated District Delivery Casebook (pilot envelope)
- Approved (pilot envelope): Rs 48 crore [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3].  
- Released by 31 March 2025: Rs 31 crore [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3].  
- Reported spent by 31 March 2025: Rs 27.4 crore [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3].  
- Implied share spent of the approved envelope: 27.4 / 48 ≈ 57.1% (calculated from the above figures) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-3].

2) State Implementation Brief (state allocation)
- Approved (state allocation): Rs 42 crore [12_State_Implementation_Brief.txt#page-1-chunk-3].  
- Released by end of 2024–25: Rs 25 crore [12_State_Implementation_Brief.txt#page-1-chunk-4].  
- Reported spent by end of 2024–25: Rs 23.9 crore [12_State_Implementation_Brief.txt#page-1-chunk-4].  
- Implied share spent of the approved allocation: 23.9 / 42 ≈ 56.9% (calculated from the above figures) [12_State_Implementation_Brief.txt#page-1-chunk-3][12_State_Implementation_Brief.txt#page-1-chunk-4].

Which figure is the answer depends on which “approved pilot budget” you mean: the Rs 48 crore pilot envelope (spent Rs 27.4 crore) or the Rs 42 crore state allocation (spent Rs 23.9 crore). The provided context contains both sets of figures.

### Q075: How many housing units were completed in the pilot?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 3.

Expected behavior: Abstain because the brief reports 1,200 housing referrals but does not report completed houses.

Judge reasoning: The candidate answer correctly identifies that the source context does not provide a definitive count of housing units completed, aligning with the expected behavior to abstain. However, it goes beyond the expected behavior by listing related figures, which is not necessary and could be misleading. The answer is mostly grounded in the source context, but the additional details about installations and systems could imply completion, which is not explicitly stated in the source. The format is clear and well-structured, but the inclusion of unnecessary details affects conciseness.

Candidate answer:

The documents do not state a single, definitive count of “housing units completed.” Below I list the related, separate lifecycle figures available in the context and then the conclusion.

Planning / targets
- Planning target: 25,000 registered households for 2025–26. [11_Integrated_District_Delivery_Casebook.txt#page-2-chunk-0]

Registration / identity / eligibility
- Identity and eligibility checks were completed for 17,500 households. [12_State_Implementation_Brief.txt#page-1-chunk-8]
- Of those, 2,400 passed the initial eligibility review. [12_State_Implementation_Brief.txt#page-1-chunk-12]

Referrals / transactions
- The pilot received 3,600 clean-energy referrals. [12_State_Implementation_Brief.txt#page-1-chunk-11]
- The brief separately reports 1,200 referrals but “does not report how many houses were finally completed.” [12_State_Implementation_Brief.txt#page-1-chunk-16]
- A payment or service transaction was successfully completed for 14,200 households at least once. [12_State_Implementation_Brief.txt#page-1-chunk-8]

Installation verification and commissioning
- 1,760 installations were verified by inspection. [12_State_Implementation_Brief.txt#page-1-chunk-12]
- Distribution companies had commissioned systems for 3,100 households by the reporting date. [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-11]

Other (finance / works)
- State approved allocation: Rs 42 crore for the pilot. [12_State_Implementation_Brief.txt#page-1-chunk-3]
- Rural access works scheduled: 86 km. [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-14]

Conclusion
- The context does not provide a single, explicit number for “housing units completed.” The closest proxy counts are: 1,760 installations verified by inspection [12_State_Implementation_Brief.txt#page-1-chunk-12] and 3,100 systems commissioned by distribution companies [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-11], but neither is labeled definitively as total “houses completed.” The brief explicitly notes it does not report final completions. [12_State_Implementation_Brief.txt#page-1-chunk-16]

### Q085: A person completed assisted online enrolment for a benefit but says the money has not arrived. What should the caseworker check without assuming the enrolment was successful delivery?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Explain that the caseworker should check eligibility verification, account seeding, payment-order generation, release, and successful credit, retaining a correction trail; enrolment is not proof of payment.

Judge reasoning: The candidate answer provides a detailed list of checks a caseworker should perform, which aligns with the expected behavior. However, it does not explicitly mention 'retaining a correction trail,' which is a key part of the expected behavior. The answer is mostly grounded in the source context, but it introduces some elements not directly supported by the source, such as the specific mention of 'MSR-3' which is not clearly linked to the context provided. The format is clear and well-structured, but due to the accuracy and grounding issues, it cannot score higher than 2 in those dimensions.

Candidate answer:

Do not assume assisted enrolment = payment or receipt. Assisted submission/enrolment is a distinct event and is not proof that the person has received the benefit or is eligible for payment [06_Digital_India_and_Public_Services.txt#page-19-chunk-8] [02_Health_and_Public_Health.txt#page-36-chunk-1].

Check these separate stages/statuses and possible exceptions (keep each stage distinct):

- Service record / stage reached
  - Verify the service record shows which stage was reached, who verified it, and any pending corrections; the record must not treat enrolment as proof of eligibility or payment [06_Digital_India_and_Public_Services.txt#page-19-chunk-8].

- Identity verification
  - Confirm identity matching is complete and there are no identity exceptions blocking payment [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9]. Identity exceptions commonly delay payments [08_MSME_and_Industrial_Development.txt#page-35-chunk-8].

- Eligibility verification
  - Check whether eligibility verification was completed (eligibility is a distinct stage separate from enrolment) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8].

- Bank account details / account seeding
  - Confirm the beneficiary’s bank account was seeded/recorded correctly and there are no bank-account exceptions [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8] and note that benefit payments are routed through bank accounts/assisted points [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-17].

- Payment-order generation
  - Check whether a payment order was actually generated (this is a separate stage) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8].

- Payment release vs successful credit (transaction confirmation)
  - If a transfer was “released,” confirm whether the transaction was successfully credited to the account—released ≠ successful credit until the transaction is confirmed [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21] [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8].

- Transaction exceptions
  - Look for transaction failures, holds or other transaction exceptions that would prevent crediting [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9] [08_MSME_and_Industrial_Development.txt#page-35-chunk-8].

- Other program-specific exceptions
  - For some programmes (e.g., wage/attendance-linked payments), check attendance or programme-specific conditions that may delay payment [08_MSME_and_Industrial_Development.txt#page-35-chunk-8].

- Records of assisted action
  - If there is an MSR-3 or similar referral, note that it confirms assistance was initiated but does not prove the person actually received money or services [08_MSME_and_Industrial_Development.txt#page-35-chunk-6].

What the context does NOT provide
- The context does not give step-by-step system commands, exact UI locations, phone numbers, or timelines to resolve each exception. It also does not provide the specific operational escalation/resolution workflow for each type of exception.

If you want, I can turn the above into a checklist the caseworker can use when looking at the beneficiary’s case record.

### Q088: A district dashboard says referrals increased. What additional status information is needed before treating this as better completed care?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Request separate counts for referrals issued, accepted, clinically assessed, treated where relevant, and completed follow-up, with the reporting period and denominator.

Judge reasoning: The candidate answer provides a detailed breakdown of the stages and statuses needed to evaluate whether increased referrals indicate better completed care. However, it does not fully align with the expected behavior, which specifically requests separate counts for referrals issued, accepted, clinically assessed, treated, and completed follow-up, along with the reporting period and denominator. The candidate answer does not explicitly mention the need for the reporting period and denominator, which are crucial for accuracy. Additionally, while the answer is mostly grounded in the source context, it introduces some elements not directly supported by the provided excerpts, such as the emphasis on resolved exceptions and authentication, which are not directly linked to the expected behavior. The format is clear and well-structured, but the accuracy and groundedness issues prevent a higher score.

Candidate answer:

You need to know, separately, what stage or status the dashboard’s “referrals increased” number actually represents — and you must not treat a rise in referrals as better completed care without evidence of later stages, verifications and resolved exceptions. The context supports these distinct items (each shown below is required or cautioned by the cited guidance):

Lifecycle / case-status stages (show which one the dashboard counts)
- Screening / assessment (people screened or assessed) — separate from referrals or completed treatment [02_Health_and_Public_Health.txt#page-36-chunk-3] [02_Health_and_Public_Health.txt#page-35-chunk-21].
- Referrals generated / accepted (referrals issued or referrals accepted) — distinct from treatment completion [02_Health_and_Public_Health.txt#page-36-chunk-3] [07_Transport_and_Infrastructure.txt#page-35-chunk-10].
- Referrals pending (outstanding, awaiting action) — joint reviews should reconcile minimum information to identify pending referrals [02_Health_and_Public_Health.txt#page-35-chunk-21].
- Referrals completed / treatment completed (cases where the referral led to completed care or treatment) — must be reported separately, not collapsed into screening/assessment counts [02_Health_and_Public_Health.txt#page-1-chunk-11] [02_Health_and_Public_Health.txt#page-35-chunk-21].
- Follow-ups / completed follow-ups (post-treatment completion) — counts of completed follow-ups are distinct and should be reported if relevant [02_Health_and_Public_Health.txt#page-36-chunk-3].

Record, verification and transaction statuses you should see
- Whether the dashboard number is “registered” vs “verified” vs “approved” records — dashboards should state if totals represent registrations or verified records [06_Digital_India_and_Public_Services.txt#page-19-chunk-11].
- Whether cases were “approved” or the referral action was actually completed as a transaction (e.g., completed transaction, released payment, or sustained service) — dashboards must clarify if totals are approved cases, released payments, completed transactions or sustained service [06_Digital_India_and_Public_Services.txt#page-19-chunk-11].
- Evidence of outcomes rather than only certificates or input documents — do not treat certificates or completion-of-paperwork as proof of service/outcome without relevant service evidence [10_Rural_Development_and_Livelihoods.txt#page-19-chunk-11].

Exceptions, authentication and resolution information
- Whether increases reflect attempted or partial actions (e.g., attempted authentication) rather than fully completed actions — dashboards must state if they report allocation, attempted authentication, completed collection, or resolved exceptions [07_Transport_and_Infrastructure.txt#page-35-chunk-13].
- Whether exceptions were raised and resolved (resolved exceptions) or remain open [07_Transport_and_Infrastructure.txt#page-35-chunk-13].

Warnings about collapsing or merging counts
- Do not collapse distinct items (screening, assessment, referral, completed treatment) into a single beneficiary count — that hides whether referrals actually led to completed care [02_Health_and_Public_Health.txt#page-35-chunk-21].
- Do not merge unrelated collection/receipt metrics with care metrics (for example, household ration collection vs children screened vs treatment completed) [07_Transport_and_Infrastructure.txt#page-35-chunk-10].

Practical check/example the context gives
- A report of N referrals (e.g., “1,200 referrals”) is incomplete if it does not report how many cases were finally completed — the brief reported referrals but not final completions [12_State_Implementation_Brief.txt#page-1-chunk-16].

What the context does not provide
- The context does not give a single mandated checklist or exact labels that a district must use for every referral metric, nor does it give numeric thresholds or a required data schema — it gives examples and principles (separate stages, verify records, report completed outcomes, show resolved exceptions) but not an exhaustive standardized field list.

Bottom line recommendation from the cited guidance
- Before treating “referrals increased” as better completed care, the dashboard must explicitly say which status it is counting (screenings, referrals generated, referrals accepted, pending referrals, referrals completed, follow-ups completed, verified/approved records, completed transactions or sustained services) and must show whether exceptions/authentication were resolved. If the dashboard does not provide those separate statuses and evidence of completed treatment/outcome, you cannot assume increased referrals mean improved completed care [02_Health_and_Public_Health.txt#page-36-chunk-3] [02_Health_and_Public_Health.txt#page-35-chunk-21] [06_Digital_India_and_Public_Services.txt#page-19-chunk-11] [07_Transport_and_Infrastructure.txt#page-35-chunk-13] [12_State_Implementation_Brief.txt#page-1-chunk-16].

### Q090: When nutrition and health records disagree for a family, how should the discrepancy be handled?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 3.

Expected behavior: Use purpose-limited, auditable reconciliation with the minimum necessary information and preserve a correction trail; do not overwrite or collapse the unresolved mismatch into a single beneficiary total.

Judge reasoning: The candidate answer accurately reflects the need for purpose-limited, auditable reconciliation and preserving the original discrepancy, which aligns with the expected behavior and source context. However, it does not explicitly mention not overwriting or collapsing the unresolved mismatch into a single beneficiary total, which is a key part of the expected behavior. The answer is well-grounded in the source context, but it lacks completeness in addressing all aspects of the expected behavior. The format is clear, concise, and well-structured, providing a logical flow of information.

Candidate answer:

Use approved service reconciliation, under controlled governance — not ad hoc changes.

- Reconcile only through approved service processes when a family is referred between a nutrition centre and a health facility; the minimum information needed for continuity of care may be reconciled that way [02_Health_and_Public_Health.txt#page-19-chunk-9].  
- Any reconciliation must be purpose‑limited, auditable, and supported by a correction process that preserves (records) the original discrepancy rather than erasing it [02_Health_and_Public_Health.txt#page-36-chunk-2].  
- Data and records arrangements must be run under a written procedure with a named responsible authority (i.e., there should be an identified accountable party and documented procedure for handling such discrepancies) [02_Health_and_Public_Health.txt#page-12-chunk-7] [02_Health_and_Public_Health.txt#page-13-chunk-8].  
- Families must have a clear local route to ask for a missed entitlement or to correct a record (so the family can initiate review/correction) [02_Health_and_Public_Health.txt#page-35-chunk-18].  
- Keep lifecycle states distinct when resolving differences (e.g., eligible household, allocated entitlement, authenticated transaction, collected ration, nutrition/health outcome); a household may appear in a ration registry before identity or household composition is corrected, so fixes should respect those separate states and histories [07_Transport_and_Infrastructure.txt#page-35-chunk-4].

What the provided context does not specify: the exact operational steps, timelines, technical mechanisms for preserving the original discrepancy, or which specific roles/teams perform each verification step beyond the requirement for a “named responsible authority.” These operational details are not in the supplied text.

### Q095: After flooding, a district issued emergency water and released cash to affected households. Which records and status checks are needed before it claims water service and relief were verified?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Link the SRR-12 and incident/RRF-9 records, distinguish emergency supply from source restoration, and distinguish released cash from successful credit and verified receipt.

Judge reasoning: The candidate answer provides a detailed breakdown of the records and status checks needed before claiming verification of emergency water service and cash relief. However, it does not explicitly mention the SRR-12 and incident/RRF-9 records, which are part of the expected behavior. The answer does distinguish between emergency supply and source restoration, and between released cash and successful credit, aligning with the expected behavior. The answer is mostly grounded in the source context, but it includes some interpretations and assumptions not directly supported by the excerpts, such as the specific processes for verification and the exact nature of the records. The format is clear and well-structured, but the omission of key expected elements affects the overall accuracy and groundedness.

Candidate answer:

Based only on the supplied excerpts, the district should have the following distinct records and status checks before it can claim that emergency water service and cash relief were verified.

1) Incident planning and exposure records (prepare/trace lifecycle start)
- A district incident plan that records hazard triggers, which settlements were exposed, which agencies are responsible, what communication channels were used, and the criteria to close each operational stage [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-13].  
- Pre- and post-disruption risk assessments for flood/contamination/heat hazards (to show what was expected and what was reviewed after the event) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-4].

2) Household registration and beneficiary lists (who should receive aid)
- A household register and verification trail: households listed/registered, duplicate removal, document checks, and a verified-households count (example process and outcome are referenced in the casebook) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-6; 10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1].

3) Delivery orders and delivery verification (evidence of dispatch and receipt)
- Records of relief orders issued (cash transfer orders) and delivery verification records showing orders were delivered/received; dashboards should separately report relief orders issued and deliveries verified [10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1].  
- For cash, a released transfer must be confirmed by the transaction confirmation before it can be counted as a successful credit (a “released” transfer alone is not proof of payment) [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].

4) Emergency water service vs restored source (distinguish service types)
- Explicit records distinguishing emergency water supply from restoration of the original source — the district must show whether the water provided was temporary/emergency supply or that the original source was restored [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-18].  
- Dashboards should report water sources restored separately from emergency fallback supplies and also indicate communities using an emergency fallback supply [10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1; 01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10].

5) Water service functionality and safety checks (technical verification)
- Records that households are connected and that connections are functional [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10].  
- Water source testing results, with unsafe results flagged and documented as resolved (sources tested; unsafe results resolved) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10].  
- Where emergency supply was used, a record that communities are using the emergency fallback supply (and not counting this as normal monthly collection) — emergency provision should not be reported as normal monthly collection data [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10; 07_Transport_and_Infrastructure.txt#page-35-chunk-15].

6) Grievances and closure criteria (outcome and accountability)
- Records that grievances have been logged and closed where relevant, and dashboard entries showing grievances closed [10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1].  
- Use the incident-plan criteria for closing operational stages to justify when the district considers the response complete [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-13].

What the provided context does not specify
- The exact evidence formats or acceptable proof types for delivery verification (e.g., beneficiary signatures, electronic transaction receipts), timing requirements for confirmations, numeric thresholds or KPIs for “functional” connections, or the precise dashboard fields and schemas. Those operational details are not included in the excerpts supplied.

Summary (minimum required to claim “verified”)
- For cash: beneficiary registration + relief order issued + confirmed transaction (not just “released”) + delivery verification (and grievance closure if applicable) [11_Integrated_District_Delivery_Casebook.txt#page-1-chunk-6; 10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].  
- For water: incident records + household lists, plus separate evidence that either (a) emergency supply was delivered and communities are using the fallback supply (not recorded as normal monthly collection) with deliveries verified, or (b) the original source was restored and shown to be tested, safe, and connections functional; also record that unsafe results were resolved and grievances closed [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-18; 10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1; 01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10; 07_Transport_and_Infrastructure.txt#page-35-chunk-15].

If you want, I can format this as a checklist you can use on the district dashboard (e.g., required fields and verification ticks) — but the specific formats and evidence types would need rules not present in the provided context.

### Q097: A village says its failed source was restored, but residents have filed complaints. How should the authorities verify and close the case?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Use the SRR-12 for source status, the incident or RRF-9 record for action and verification, and a JGR-11 verification record for the grievance; neither administrative closure alone proves restoration.

Judge reasoning: The candidate answer provides a detailed procedure for verifying and closing the case of a failed water source, but it lacks completeness and grounding in some areas. It correctly mentions the use of the SRR-12 and the need for verification before closing the record, which aligns with the expected behavior. However, it omits the use of the JGR-11 verification record for grievances, which is a key part of the expected behavior. Additionally, while it discusses linking corrective evidence (ECR-5) for urban drainage issues, this is not directly relevant to the expected behavior for verifying a restored water source. The format is clear and well-structured, but the answer could be more concise by focusing strictly on the expected behavior.

Candidate answer:

What the authorities must (and must not) do — based only on the provided context

1) Use the SRR-12 record and incident plan
- Any failed source should be recorded in the Source Reliability Register (SRR‑12) and linked to the incident plan for that failure. The SRR‑12 entry must show the source identifier, failure category, affected users, fallback supply, responsible authority and expected restoration date [01_Agriculture_and_Farmers_Welfare.txt#page-35-chunk-21; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-19].

2) Ensure the initial failure was properly documented
- On failure, the responsible local authority should already have documented the fallback supply, the affected users, and the expected restoration action and date in the record [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-5; 01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-0].

3) Do not accept emergency supply as restoration
- If an emergency/fallback supply was provided, record it as the fallback measure but do not record that as restoration of the original source [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-6].

4) Verify physical/service restoration before closing the SRR‑12
- A closed SRR‑12 entry is not proof that service is restored until the source is verified functional. Authorities must therefore verify the source is actually functional before considering the SRR‑12 closed [01_Agriculture_and_Farmers_Welfare.txt#page-35-chunk-21].

5) Link and record supporting evidence where relevant
- If the failure was caused or affected by urban drainage/waste issues, link the corrective evidence (ECR‑5) to the source record and report the responsible correction path [05_Renewable_Energy_and_Power.txt#page-35-chunk-8].

6) Track grievances separately and report closure
- Complaints from residents (grievances) must be tracked and closed separately from the water‑source restoration record; district reporting should show water sources restored and grievances closed as separate items [10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1].

What the context does not specify
- The provided context does not give the exact verification procedure (who performs verification, what checks or measurements constitute “verified functional,” acceptable evidence types beyond ECR‑5 for drainage/waste, or timelines for verification and grievance adjudication). It also does not specify how to resolve conflicting claims (authority says restored but residents complain) or the appeals/next steps if verification shows the source is not functional.

Practical minimum procedure (derived from the supported rules)
- Do not close the SRR‑12 or mark the source restored until a verification step confirms the source is functional [01_Agriculture_and_Farmers_Welfare.txt#page-35-chunk-21].
- Ensure the SRR‑12 is up to date and linked to the incident plan, and that the fallback supply and affected users are recorded [01_Agriculture_and_Farmers_Welfare.txt#page-35-chunk-21; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-19].
- If an emergency supply remains in use, keep it recorded as fallback and do not treat that as restoration [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-6].
- If relevant, attach corrective evidence (ECR‑5) and correction path to the source record [05_Renewable_Energy_and_Power.txt#page-35-chunk-8].
- Only after verification should the district dashboard be updated to show the water source as restored; close the grievance record separately and report that closure too [10_Rural_Development_and_Livelihoods.txt#page-36-chunk-1].

If you want, I can draft a short checklist for the verification visit and the records/fields to update — but note I would be inferring verification steps not specified in the supplied context.

### Q102: An assisted ration transaction failed during a connectivity outage and the household complains that its record was overwritten. What is the correct handling?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Retain the offline or original transaction and correction trail in FPS-21, reconcile after service resumes without overwriting the mismatch, and record the grievance lifecycle and verified remedy separately in JGR-11.

Judge reasoning: The candidate answer provides a detailed step-by-step process for handling the failed transaction, which aligns with some aspects of the expected behavior, such as retaining offline records and using RRF-9 for reconciliation. However, it does not explicitly mention recording the grievance lifecycle and verified remedy separately in JGR-11, which is a key part of the expected behavior. Additionally, while the answer is mostly grounded in the source context, it introduces some procedural details not explicitly covered in the provided context, such as the specific use of RRF-9 and the detailed steps for verification and monitoring. The format is clear and well-structured, but due to the inaccuracies and partial grounding, the scores for accuracy and groundedness are limited to 2.

Candidate answer:

What to do — step‑by‑step (each stage kept distinct)

1) During the outage (continuity and evidence)
- Use the offline registers / assisted‑authentication process so assisted transactions remain available and are recorded despite connectivity failures [07_Transport_and_Infrastructure.txt#page-35-chunk-11].  
- Preserve the offline record (paper/offline log, timestamps, operator identity) as the primary evidence of the attempted assisted transaction.

2) Distinguish states before changing records
- Treat entitlement, authenticated transaction and collection as separate states: confirm whether the household’s entitlement was allocated, whether an authentication/transaction was recorded, and whether the ration was actually collected — do not collapse these into one status [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Remember authentication can fail because of incorrect source records (not necessarily ineligibility), and approvals or payments may be delayed by banks or local providers — so investigate record vs system/network causes [06_Digital_India_and_Public_Services.txt#page-1-chunk-13].

3) When the household complains its record was overwritten (grievance/correction owner)
- Treat this as a cross‑service correction / disputed household record: identify the underlying source record and the owner responsible for correcting it (the correction owner) rather than just taking ad‑hoc action [06_Digital_India_and_Public_Services.txt#page-35-chunk-17].

4) Open a formal incident/reconciliation record (use RRF-9)
- If the dispute concerns a household record, supply issue, service disruption or payment status during an incident, open an RRF‑9 (Relief Reconciliation Form). The RRF‑9 must include: incident identifier, household or site reference, claimed need, source record, action owner, next review date and verification method [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-17].  
- Keep the offline register and any failed‑transaction logs attached to the RRF‑9 as supporting evidence.

5) Verification and closing
- Carry out the documented verification method specified in the RRF‑9 (e.g., recheck source registry, biometric/ID checks, witness/field verification) and record results. An RRF‑9 can only be closed after documented verification — a caseworker note alone is not sufficient [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-17].

6) Monitoring and metrics
- Record this event for digital access metrics (assisted‑service use, failed transactions, outage duration and language/accessibility impacts), not just as a registered user event, so outages and assisted failures are tracked and remediated [06_Digital_India_and_Public_Services.txt#page-1-chunk-15].  
- Ensure grievance redressal and continuity rules are followed in line with large‑system requirements for access, data handling and outages [06_Digital_India_and_Public_Services.txt#page-1-chunk-11].

What the provided context does NOT specify
- The context does not give the precise operational format of the offline register, the technical steps to resynchronize records, nor the exact verification checks to perform for every local implementation. It also does not state timeframes for RRF‑9 review or the identity of the specific “correction owner” role in your local system.

### Q103: A migrant is listed for a portable ration and a cash benefit but has not received either. Which delivery stages should be checked?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Check portability and FPS-21 transaction status for the ration, and eligibility, account seeding, payment order, release and successful credit for cash; listing or registration proves neither delivery.

Judge reasoning: The candidate answer provides a detailed breakdown of the stages to check for both cash benefits and portable rations, which aligns with the expected behavior. However, it introduces additional stages and details not explicitly mentioned in the source context, such as 'identity/bank details and any identity or bank corrections' and 'distribution/release at the service point,' which are not directly supported by the provided context. This affects both accuracy and groundedness, as the answer includes unsupported details. The format is clear and well-structured, but due to the inaccuracies and lack of grounding, it cannot score higher than 2 in accuracy and groundedness.

Candidate answer:

Supported by the context, you should treat cash and in‑kind (portable ration) as separate lifecycles and verify each distinct stage. Below are the stages to check and the specific records/statuses or exceptions to look for.

A. Cash benefit — stages to check
- Registration / assisted enrolment (is the person enrolled?) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 02_Health_and_Public_Health.txt#page-36-chunk-1].  
- Eligibility verification (has eligibility been confirmed?) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12].  
- Identity / bank details and any identity or bank corrections (are there unresolved identity or bank exceptions?) [08_MSME_and_Industrial_Development.txt#page-35-chunk-5; 09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9].  
- Account seeding (was the beneficiary account seeded/linked?) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8].  
- Payment‑order generation (was a payment order created?) [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8].  
- Payment release (was the transfer released?) — but note that a released transfer is not the same as funds reaching the person [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].  
- Transaction confirmation / successful credit (was the credit to the recipient’s account actually confirmed?) — this is the final confirmation of receipt for cash [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].  
- Check for transaction/eligibility/bank/identity exceptions that can leave someone registered but unpaid [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9].

B. Portable ration (in‑kind) — stages to check
- Registration / enrolment (is the person registered for the ration?) [01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12].  
- Eligibility verification (has entitlement been verified?) [01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12].  
- Referral / service‑point assignment and whether assistance was initiated (e.g., MSR‑3 referral record for mobility/portable services) — MSR‑3 records requested entitlement, destination service point and any identity/bank correction fields and shows that assistance was initiated, but such a referral does not prove the ration was collected [08_MSME_and_Industrial_Development.txt#page-35-chunk-5; 08_MSME_and_Industrial_Development.txt#page-35-chunk-6].  
- Distribution/release at the service point (was the ration released to the distribution point?) [01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12].  
- Actual collection / receipt confirmation (was the ration physically collected by the beneficiary?) — enrolment or a referral alone is not proof of collection [03_Education_and_Skills.txt#page-35-chunk-7; 02_Health_and_Public_Health.txt#page-36-chunk-1; 08_MSME_and_Industrial_Development.txt#page-35-chunk-6].

C. Records/statuses to inspect (cross‑cutting)
- MSR‑3 referral fields (origin reference, destination service point, requested entitlement, any identity/bank correction, referral owner, review date) to see whether assistance was initiated and if corrections were flagged [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- System flags for identity, bank, eligibility or transaction exceptions that can block payment or collection [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9].  
- Confirm that any “assisted entry,” form submission, booking or release has a downstream confirmation of actual receipt (forms/releases/bookings are not proof of having received the benefit) [02_Health_and_Public_Health.txt#page-36-chunk-1; 03_Education_and_Skills.txt#page-35-chunk-7; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].

What the context does not provide
- The exact system screens, API calls, office contacts, or step‑by‑step queries to run to verify each stage is not included in the provided context. The context also does not give specific timeframes for each stage or the local operational workflow to remediate exceptions.

Summary action checklist (based on the above)
1. Check MSR‑3/referral record for the migrant’s requested entitlement and any correction flags [08_MSME_and_Industrial_Development.txt#page-35-chunk-5; 08_MSME_and_Industrial_Development.txt#page-35-chunk-6].  
2. Verify registration/enrolment and eligibility status for both cash and ration [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12].  
3. For cash: check identity/bank details, account seeding, payment‑order, release status and final transaction credit [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-8; 10_Rural_Development_and_Livelihoods.txt#page-35-chunk-21].  
4. For ration: check distribution/release at service point and physical collection/receipt confirmation [01_Agriculture_and_Farmers_Welfare.txt#page-1-chunk-12; 08_MSME_and_Industrial_Development.txt#page-35-chunk-6].  
5. Look for identity/bank/eligibility/transaction exceptions that could explain non‑receipt [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-9].

If you want, I can format these into a short checklist you can use when querying the local systems or help draft the exact queries/messages to the responsible office — but the context does not include system‑specific query steps or contact points.

### Q107: A destination-city worker uses assisted access for a portable ration. What should the system preserve when source and destination records differ?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Preserve the original mismatch, service period, destination authority and correction trail; an assisted request or shared identifier does not prove entitlement collection.

Judge reasoning: The candidate answer provides a detailed response but does not fully align with the expected behavior. It includes additional elements like provenance and lifecycle states that are not mentioned in the expected behavior. The expected behavior specifically mentions preserving the original mismatch, service period, destination authority, and correction trail, which are not explicitly covered in the candidate answer. The answer also introduces concepts like 'provenance' and 'lifecycle states' that are not directly supported by the source context. The format is clear and well-structured, but due to the inaccuracies and lack of grounding, it cannot score higher than 2 in accuracy and groundedness.

Candidate answer:

Short answer: preserve provenance (the source/origin reference and correction owner) plus all distinct entitlement and transaction states (allocated entitlement, authenticated transaction, proof of collection, and outcome), and record any destination-side corrections/referrals separately — do not treat an MSR/referral as proof of collection. The context supports these points but does not give field-level or retention/implementation details. 

Details (each statement cites the source used)

- Preserve the origin/source reference so the destination record always links back to the source-district record (and do not assume the source record is current) [08_MSME_and_Industrial_Development.txt#page-35-chunk-10] [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- Preserve who is responsible for corrections (the “correction owner”) and link grievances to the underlying source record so cross-service corrections can be traced [06_Digital_India_and_Public_Services.txt#page-35-chunk-17].  
- Preserve the distinct lifecycle states separately: eligible household (registry membership), allocated entitlement, an authenticated transaction, a collected ration, and the downstream nutrition/health outcome — the system must distinguish and retain these states rather than merging them [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Preserve destination-side referral and correction metadata recorded in the MSR-3: destination service point, requested entitlement, any identity or bank correction, referral owner and review date [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- Do not conflate an MSR-3 referral with proof of receipt: an MSR-3 shows assistance was initiated but does not prove the worker actually obtained a ration (so preserve separate evidence of collection/transaction) [08_MSME_and_Industrial_Development.txt#page-35-chunk-6] [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Preserve any pending identity/household-composition corrections as a distinct status (a household can be present in the ration registry before identity/composition is corrected) [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Maintain confidential, assisted and non-digital access channels for such cases as needed (so assisted access records and privacy controls should be preserved) [03_Education_and_Skills.txt#page-35-chunk-1] [02_Health_and_Public_Health.txt#page-35-chunk-17] [08_MSME_and_Industrial_Development.txt#page-35-chunk-10].

What the context does not specify
- The exact data fields, formats, retention periods, verification workflows, or implementation mechanics for preserving these links and states are not provided in the cited context.

### Q108: A migrant care worker is referred to health and safety services. Which facts must be kept confidential and which service stages must be distinguished?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 3.

Expected behavior: Share only minimum purpose-limited information; distinguish MSR-3 referral, health assessment or treatment, GSC-8 risk and safety actions, service access and verified resolution.

Judge reasoning: The candidate answer accurately identifies the service stages that must be distinguished, such as referral acceptance, clinical assessment, treatment, and follow-up, as well as the need to separate initiation from proof of outcome. However, it lacks explicit mention of confidentiality rules, which are not detailed in the source context. The answer is grounded in the source context, but it does not fully address the expected behavior regarding confidentiality. The format is clear and well-structured, but the omission of key confidentiality details limits the accuracy score.

Candidate answer:

What the context supports

1) Confidentiality — what the documents record (but note: the context does NOT state explicit confidentiality rules)
- The Mobility Case Record (MSR‑3) records: origin reference, destination service point, requested entitlement, identity or bank correction, referral owner and review date [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- The provided context does not specify which of those fields must be kept confidential or the legal/privacy rules to apply. (No explicit confidentiality policy text is present in the provided excerpts.)

2) Service stages that must be kept distinct (different records/evidence for each)
- For health referrals, health facilities should record the following as separate service stages: referral acceptance, clinical assessment, treatment, and follow‑up [02_Health_and_Public_Health.txt#page-19-chunk-7].  
- The mobility/worker lifecycle should treat these as separate stages with their own evidence: registered, placed, employed, paid and retained (each requiring its own evidence) [08_MSME_and_Industrial_Development.txt#page-35-chunk-4].  
- The MSR‑3 referral itself confirms assistance was initiated but is not proof of outcomes (it does not prove the worker obtained a job, received a wage, collected a ration or accessed health care) — so initiation (referral created) must be treated separately from verification of outcome [08_MSME_and_Industrial_Development.txt#page-35-chunk-6].  
- For legal/ protection referrals, a referral is a coordination step only and is not proof that legal representation, safety planning or remedy was received [06_Digital_India_and_Public_Services.txt#page-35-chunk-19].  
- Where care is transferred between providers (example: nutrition centre ↔ health facility), the minimum information needed for continuity of care should be reconciled through approved service processes (i.e., data exchange should be limited to the minimum needed and reconciled via agreed processes) [02_Health_and_Public_Health.txt#page-19-chunk-9].

Practical implication from the excerpts
- The record fields that contain personal/financial identifiers (identity, bank correction) are explicitly recorded in the MSR‑3 [08_MSME_and_Industrial_Development.txt#page-35-chunk-5], but the excerpts do not state the confidentiality protections or handling rules for those facts.  
- The excerpts require separating administrative/referral initiation records from subsequent acceptance, clinical assessment, treatment and follow‑up records, and separating initiation/referral from proof of outcome (employment, payment, service received) [02_Health_and_Public_Health.txt#page-19-chunk-7; 08_MSME_and_Industrial_Development.txt#page-35-chunk-6; 08_MSME_and_Industrial_Development.txt#page-35-chunk-4].

If you need explicit confidentiality obligations (who may view which fields, retention and sharing rules, consent requirements), the provided context does not include those details.

### Q110: A city creates temporary work maintaining drainage after a heat and flood season. What should monitoring avoid combining?

Expected source documents retrieved: False. Accuracy: 1; groundedness: 2.

Expected behavior: Avoid combining workers contacted, work allocated, payments credited, drainage assets maintained, environmental compliance and reduced climate risk into one performance total; each has a separate unit and evidence path.

Judge reasoning: The candidate answer does not accurately address the expected behavior, which is to avoid combining specific metrics into one performance total. Instead, it focuses on not treating emergency actions as routine service delivery, which is not the same as the expected behavior. The answer is partially grounded in the source context, as it references relevant points about emergency actions, but it does not directly address the expected behavior of separating different performance metrics. The format is clear and well-structured, but due to the inaccuracies, it cannot score higher in accuracy or groundedness.

Candidate answer:

Monitoring should NOT treat the temporary/emergency drainage work as the same as routine service delivery or as proof of service continuity. Specifically:

- Do not report an emergency action (e.g., temporary drainage maintenance after a heat/flood event) as a normal monthly collection/service delivery [07_Transport_and_Infrastructure.txt#page-35-chunk-15].  
- Do not treat emergency works as proof that households received safe drinking water or that a water source remained functional through the dry season [01_Agriculture_and_Farmers_Welfare.txt#page-19-chunk-15].  
- Distinguish emergency water supply/response from restoration of the original source (i.e., separate emergency fixes from longer-term source restoration) [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-18].  
- Where drainage or waste failures affect a water source, monitoring should link the emergency evidence to the source record and report the responsible correction path rather than collapsing records into routine indicators [05_Renewable_Energy_and_Power.txt#page-35-chunk-8].

These points are supported by the provided context. No additional guidance beyond these items is available in the supplied excerpts.

### Q114: Residents challenge an environmental dashboard total that mixes samples, complaints and inspections. What is the correct response?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: State the unit, period, evidence method and threshold for each measure; preserve the complaint and correction trail in JGR-11 rather than presenting mixed counts as one ranking.

Judge reasoning: The candidate answer correctly identifies that public dashboards should not mix different measures into a single performance indicator, which is supported by the source context. However, it fails to address the expected behavior of stating the unit, period, evidence method, and threshold for each measure, and preserving the complaint and correction trail in JGR-11. The answer is partially grounded in the source context but does not fully align with the expected behavior. The format is clear and well-structured, but due to the omission of key expected details, the accuracy and groundedness scores are limited.

Candidate answer:

Short answer
- The dashboard is misleading — public dashboards must not rank or aggregate locations using mixed measures (inspections, complaints, samples, verified compliance) as a single performance indicator [05_Renewable_Energy_and_Power.txt#page-35-chunk-13].

What to tell residents (supported by the guidance)
- Explain that the dashboard should display each measure separately (e.g., complaints, inspections, samples, verified compliance) rather than a single mixed total [05_Renewable_Energy_and_Power.txt#page-35-chunk-13].  
- Say you will show the lifecycle stages distinctly on the dashboard:
  - Complaints/grievances: filed, acknowledged within the service standard (and other case statuses) [06_Digital_India_and_Public_Services.txt#page-36-chunk-0].  
  - Inspections: sites inspected and inspection findings recorded as evidence (use an Environmental Compliance Record form that records site, condition, evidence source, corrective owner, due date and verification result) [05_Renewable_Energy_and_Power.txt#page-35-chunk-5].  
  - Samples: samples collected and their results; unsafe results and resolutions should be listed separately (analogous to “sources tested, unsafe results resolved”) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10].  
  - Corrective actions and outcomes: report corrective actions reported complete separately from remedies that have been verified as meeting outcome standards — an “action-complete” status does not prove the environmental outcome until verification is recorded [05_Renewable_Energy_and_Power.txt#page-35-chunk-5; 06_Digital_India_and_Public_Services.txt#page-36-chunk-0].
- Commit to labeling every dashboard total to state exactly what it represents (e.g., registrations, verified records, approved cases, completed transactions, sustained service) so users know what the numbers mean [06_Digital_India_and_Public_Services.txt#page-19-chunk-11].  
- Note timestamps: totals may be based on different update times, so show or clarify update times for each measure [06_Digital_India_and_Public_Services.txt#page-1-chunk-14].

What the guidance does not supply (so you must not claim it)
- The context does not give a required phrasing for the resident reply, a deadline for fixing the dashboard, or the current dashboard’s internal data to prove whether the dashboard in question in fact mixes these measures. Those implementation details are not in the provided context.

Summary suggested message to residents (concise, based only on guidance above)
- “You are right to flag this. Guidance requires that inspections, complaints and sample results not be mixed into a single performance ranking. We will (a) separate those measures on the dashboard, (b) label each total to state exactly what it represents and when it was last updated, and (c) record verification before counting actions as verified compliance (an action‑complete report alone is not proof of outcome).” [05_Renewable_Energy_and_Power.txt#page-35-chunk-13; 06_Digital_India_and_Public_Services.txt#page-36-chunk-0; 05_Renewable_Energy_and_Power.txt#page-35-chunk-5; 06_Digital_India_and_Public_Services.txt#page-19-chunk-11; 06_Digital_India_and_Public_Services.txt#page-1-chunk-14]

### Q115: A waste disruption affects food distribution near a nutrition centre. What can local teams coordinate without claiming a nutrition outcome?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Coordinate stock, access, sanitation and outreach records, but keep commodity distribution, screening, referral, clinical care and nutritional outcome measures distinct.

Judge reasoning: The candidate answer provides a detailed list of actions that local teams can coordinate, such as commodity distribution, linking waste evidence, and prioritizing public health outreach. However, it includes actions like using approved referral pathways and applying food-security policy elements, which are not explicitly mentioned in the expected behavior. The expected behavior focuses on coordinating stock, access, sanitation, and outreach records without claiming nutrition outcomes, which is not fully aligned with the candidate's broader scope. The answer is partially grounded in the source context but includes some extrapolations not directly supported by the provided excerpts. The format is clear and well-structured, but due to the inaccuracies and partial grounding, the scores for accuracy and groundedness are limited to 2.

Candidate answer:

You can coordinate multiple operational, surveillance and referral actions — but you must not represent those actions as having produced a nutrition or clinical outcome. Relevant, allowable coordination (with record/verification notes) and what you must not claim:

What local teams can coordinate (and how to record/verify)
- Commodity distribution to support food access (operational delivery only). Do not treat this as proof of dietary adequacy, growth improvement, or completed clinical care [07_Transport_and_Infrastructure.txt#page-35-chunk-8].  
- Link waste/drainage evidence (ECR-5) with the affected water‑source record and report the responsible corrective action path (document the ECR-5 evidence and the correction path) [05_Renewable_Energy_and_Power.txt#page-35-chunk-8].  
- Use sanitation observations, water‑quality results and local disease surveillance to target and prioritise corrective action or outreach (use these data to guide actions, not to assert causation) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-3; 02_Health_and_Public_Health.txt#page-19-chunk-8].  
- Prioritise public‑health outreach based on water‑quality alerts, sanitation conditions and disease surveillance (document alerts and outreach decisions) [02_Health_and_Public_Health.txt#page-19-chunk-8].  
- If clinical assessment is needed, use approved referral pathways between the nutrition centre and health facility and reconcile the minimum information required for continuity of care through approved processes (record referrals and the minimum reconciled information) [02_Health_and_Public_Health.txt#page-35-chunk-19; 02_Health_and_Public_Health.txt#page-19-chunk-9].  
- Maintain reporting that keeps household ration collection separate from counts of children screened, referrals accepted or treatments completed (keep those statuses distinct in reports) [07_Transport_and_Infrastructure.txt#page-35-chunk-10].  
- Apply food‑security policy elements where relevant (entitlement delivery, local storage, nutrition support, price resilience, grievance channels) as operational supports — record these program elements but do not infer outcomes from them alone [07_Transport_and_Infrastructure.txt#page-35-chunk-3].

What you must not claim or conflate
- Do not claim that commodity distribution establishes dietary adequacy, child growth improvement, or completed clinical care [07_Transport_and_Infrastructure.txt#page-35-chunk-8].  
- Do not infer safe water use, disease prevention, or a completed health outcome from a household connection, a sanitation certificate, or a nutrition registration alone [02_Health_and_Public_Health.txt#page-19-chunk-8].  
- Do not claim causation between sanitation/water observations and outcomes unless causation has been established (use observations to target action but not to assert cause/effect) [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-3].  
- Do not merge household ration collection figures with children screened, referrals accepted or treatments completed in reporting (keep those records and statuses separate) [07_Transport_and_Infrastructure.txt#page-35-chunk-10].

If you want, I can format a short checklist for on‑site teams to follow (actions to take, records to make, and exact wording to avoid) based on the points above.

### Q119: A confidential support case includes a failed assisted food-entitlement transaction. How should the records be reconciled?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Use purpose-limited, auditable reconciliation and preserve the FPS-21 correction trail; do not expose GSC-8 details or treat assisted authentication as completed collection.

Judge reasoning: The candidate answer provides a detailed stepwise guidance on reconciling records for a failed assisted food-entitlement transaction. However, it does not fully align with the expected behavior, which emphasizes the use of purpose-limited, auditable reconciliation and preserving the FPS-21 correction trail. The candidate answer does not mention FPS-21, which is a key aspect of the expected behavior. Additionally, while the answer is mostly grounded in the source context, it introduces some elements not explicitly covered, such as the detailed stepwise guidance, which may not be fully supported by the source. The format is clear and well-structured, but due to the inaccuracies and partial grounding, the scores for accuracy and groundedness are limited to 2.

Candidate answer:

Short answer
- Reconcile only the minimum information needed to continue support through an approved service process; do not overwrite the original mismatched record and do not treat any linked identifier or a successful assisted form submission as proof that the entitlement was received. [02_Health_and_Public_Health.txt#page-19-chunk-9] [06_Digital_India_and_Public_Services.txt#page-35-chunk-18] [02_Health_and_Public_Health.txt#page-36-chunk-1]

Detailed, stepwise guidance (separate lifecycle pieces, records, statuses, exceptions, verification and outcomes)

1) Records to update (what to record)
- Record the minimum reconciliation fields required for continuity of care (e.g., origin/destination, entitlement requested, referral owner, review/follow-up dates) rather than copying or replacing source records. [02_Health_and_Public_Health.txt#page-19-chunk-9] [08_MSME_and_Industrial_Development.txt#page-35-chunk-5]
- If the case is confidential, record confidentiality constraints, preferred contact method, referral owner, immediate safety actions and consent-based information‑sharing limits in the case file. [03_Education_and_Skills.txt#page-35-chunk-3]

2) Statuses and exceptions (how to mark the transaction)
- Mark the assisted food-entitlement transaction as failed (or “pending resolution”) in the local case lifecycle; keep the source record’s original mismatch visible rather than overwriting it. [06_Digital_India_and_Public_Services.txt#page-35-chunk-18]
- Treat assisted data entry or a successful form submission as delivery-support activity, not as proof that the family actually received food or cash. Do not change the outcome to “delivered” based solely on the assisted submission. [02_Health_and_Public_Health.txt#page-36-chunk-1]

3) Correction trail and resolution route (audit and remediation)
- Retain a case-level correction/audit trail showing the failed transaction, the corrections attempted (identity/bank corrections or authentication attempts), and who owns the referral. Provide an accessible route for resolving authentication failures, inactive accounts or rejected transactions. [09_Financial_Inclusion_and_Social_Security.txt#page-19-chunk-10]
- If relevant to a migrant or portability case, capture origin reference, destination service point, requested entitlement and any identity/bank corrections in the Migrant Support Record so the destination can act without assuming source-district records are current. [08_MSME_and_Industrial_Development.txt#page-35-chunk-5] [08_MSME_and_Industrial_Development.txt#page-35-chunk-10]

4) Confidentiality and reporting restrictions
- Do not expose confidential case details in public dashboards or mix safety/support case counts with general beneficiary totals. Apply the confidentiality restrictions and consent limits recorded in the case file when sharing reconciliation information. [03_Education_and_Skills.txt#page-35-chunk-9] [03_Education_and_Skills.txt#page-35-chunk-3]

5) Verification and final outcome
- Require independent, verifiable confirmation of entitlement receipt before finalizing the case as “delivered” (the context explicitly prohibits treating form submission or a linked identifier as proof). [02_Health_and_Public_Health.txt#page-36-chunk-1] [06_Digital_India_and_Public_Services.txt#page-35-chunk-18]

What the provided context does not specify
- The context does not give exact technical fields, message formats, or the step‑by‑step user interface or API calls to perform the reconciliation, nor specific timeframes or who exactly must verify receipt. It also does not specify what counts as acceptable independent proof of receipt. These operational details are not available in the supplied text.

### Q120: A person is referred from a housing service to safety support and the housing case closes. What still needs verification?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Verify the actual housing-service status, any GSC-8 safety review and the JGR-11 remedy where a grievance exists; an administrative housing closure is not a verified safety or housing outcome.

Judge reasoning: The candidate answer correctly identifies several verification steps needed after a housing case closes, such as verifying referral acceptance, service access, and a documented safe-resolution review. However, it misses verifying the actual housing-service status and the JGR-11 remedy where a grievance exists, which are explicitly mentioned in the expected behavior. The answer is mostly grounded in the source context, but it does not fully align with the expected behavior, particularly regarding the JGR-11 remedy. The format is clear and well-structured, providing a detailed breakdown of each verification step.

Candidate answer:

Supported by the supplied guidance, these distinct items still need verification after the housing case closes:

1. Referral acceptance by the safety service
   - The support lifecycle treats “referral issued” and “referral accepted” as separate stages, so acceptance by the receiving safety service must be verified, not assumed from the referral having been sent [03_Education_and_Skills.txt#page-35-chunk-2].

2. That the person actually accessed the safety service
   - “Service accessed” is a separate lifecycle stage and must be verified (i.e., evidence the service was used) [03_Education_and_Skills.txt#page-35-chunk-2].

3. A documented safe-resolution review (required to count as a verified safety outcome)
   - A GSC-8 closure (safe-resolution) requires a documented safe-resolution review and cannot be inferred from a referral alone; closure should not be treated as a verified safety outcome without that review [03_Education_and_Skills.txt#page-35-chunk-4][03_Education_and_Skills.txt#page-35-chunk-11].

4. Local verification of the housing referral (where applicable)
   - Housing referrals were sent to urban local bodies for local verification, so that local verification step must be completed/verified [12_State_Implementation_Brief.txt#page-1-chunk-15].

5. If there is a dispute, completion and documented verification of an RRF-9
   - If the household record, supply/service/payment status or similar is disputed, an RRF-9 must be used and must include the incident ID, household/site reference, claimed need, source record, action owner, next review date and verification method; closing an RRF-9 requires documented verification (not just a caseworker note) [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-17].

Notes on what the context does not specify
- The guidance does not give the exact forms/evidence that count as acceptable verification for each stage, who (which role/agency) must perform the safe-resolution review, or specific timeframes for verification steps—those details are not present in the provided excerpts.

### Q121: A benefit grievance is marked resolved after a portal update. What evidence is needed for a verified remedy?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: Retain the original mismatch and correction trail, identify the payment stage, and require JGR-11 verification that the intended correction or successful credit occurred; a portal update alone is not enough.

Judge reasoning: The candidate answer correctly identifies that a portal update alone is insufficient for verifying a remedy and that the grievance lifecycle includes a distinct 'remedy verified' stage. However, it fails to mention the need for JGR-11 verification, which is a key part of the expected behavior. The answer is partially grounded in the source context, as it references the grievance lifecycle and the need for evidence-based verification, but it does not fully align with the expected behavior due to the omission of JGR-11 verification. The format is clear and well-structured, but the omission of a key fact affects the overall accuracy and groundedness scores.

Candidate answer:

Supported by the provided context:

- A portal update alone does not constitute a verified remedy. The grievance lifecycle treats “remedy verified” as a distinct stage (filed → acknowledged → assigned → investigated → decision-issued → corrective action completed → remedy verified), so marking resolved on the portal is not the same as verification of restoration of service [06_Digital_India_and_Public_Services.txt#page-35-chunk-14].  
- A grievance closed only in an administrative register should not automatically be treated as a verified restoration of service — administrative closure is not sufficient evidence of remedy [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-12].  
- For benefit-transfer grievances you must identify the underlying source record and the correction owner (so the corrective action can be traced to the system and actor that actually effect payments) — that identification is required for cross‑service corrections such as benefit transfers [06_Digital_India_and_Public_Services.txt#page-35-chunk-17].  
- Authorities are expected to interpret grievances and appeals in an evidence‑based manner, so verification should be supported by objective evidence rather than only a portal flag or internal note [07_Transport_and_Infrastructure.txt#page-30-chunk-8] [09_Financial_Inclusion_and_Social_Security.txt#page-30-chunk-17].

What the context does NOT provide:
- It does not list the specific items that count as acceptable evidence (for example, transaction logs, bank payment confirmations, updated subsidy registers, screenshots, or independent field verification).  
- It does not prescribe the exact verification procedure, who must perform the verification, or thresholds for deeming a remedy “verified.”

Summary (concise): To verify a benefit remedy you need (1) identification of the underlying source record and the correction owner for the benefit transfer [06_...#page-35-chunk-17], (2) documented completion of corrective action and an explicit verification step in the grievance lifecycle rather than just a portal/admin closure [06_...#page-35-chunk-14; 01_...#page-36-chunk-12], and (3) objective evidence supporting the restoration because authorities must decide on an evidence‑based basis [07_...#page-30-chunk-8; 09_...#page-30-chunk-17]. The exact forms of acceptable evidence and the verification process are not specified in the provided context.

### Q123: A migrant's complaint says a ration entitlement was denied at destination. What information must the case record preserve?

Expected source documents retrieved: True. Accuracy: 1; groundedness: 1.

Expected behavior: Preserve the service period, destination authority, portability request, FPS-21 transaction or exception, original mismatch, correction owner and JGR-11 verification method.

Judge reasoning: The candidate answer fails to accurately capture the expected behavior, which requires preserving specific items such as service period, destination authority, portability request, FPS-21 transaction or exception, original mismatch, correction owner, and JGR-11 verification method. The candidate answer includes some relevant details but omits key elements like the JGR-11 verification method and original mismatch. Additionally, it introduces unsupported elements like 'nutrition or health outcome' and 'review date,' which are not part of the expected behavior. The format is clear and well-structured, but due to significant inaccuracies and lack of grounding in the source context, the scores for accuracy and groundedness are low.

Candidate answer:

Synthesize from the provided context only — the case record should preserve the following distinct items (grouped by lifecycle stage), with the precise facts below supported by the cited sources.

Intake / portability request
- The specific service being claimed (ration), the reporting period, and the destination authority/service point to which the migrant was sent (portability request must state service, period and destination authority; MSR tracks destination service point) [08_MSME_and_Industrial_Development.txt#page-35-chunk-12] [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].

Identity / correction information
- The origin reference (home record) that ties the migrant to an originating household or registry [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- Any identity or bank corrections requested or applied (identity/bank correction details) [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- If a household entry existed in the ration registry before identity/household-composition correction, that presence/status should be recorded (household presence vs corrected identity) [07_Transport_and_Infrastructure.txt#page-35-chunk-4].

Entitlement / transaction lifecycle states (each as separate recorded facts and timestamps)
- Whether the household was eligible and whether an entitlement was allocated to them (eligible household; allocated entitlement) [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Whether a transaction was authenticated (authenticated transaction) [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Whether the ration was actually collected at destination (collected ration) — and if not collected, the recorded reason for non-collection/denial [07_Transport_and_Infrastructure.txt#page-35-chunk-4].  
- Any downstream outcomes relevant to health/nutrition (nutrition or health outcome), if available [07_Transport_and_Infrastructure.txt#page-35-chunk-4].

Referral, ownership, review and closure metadata
- The referral owner (who is responsible for following up) and the review date for the case [08_MSME_and_Industrial_Development.txt#page-35-chunk-5].  
- If the case is closed at the destination (e.g., FPS-21 closure), the record must preserve either a confirmed replacement transaction or a documented reason that the entitlement was not due (FPS-21 closure requirement) [07_Transport_and_Infrastructure.txt#page-35-chunk-7].  
- Any documented attempts or initiation of assistance (an MSR-3 referral confirms assistance was initiated) — but note that such a referral does not prove the ration was actually obtained at destination [08_MSME_and_Industrial_Development.txt#page-35-chunk-6].

Grievance linkage and correction ownership
- Identification of the underlying source record that gave rise to the entitlement and the correction owner responsible for fixing it (cross‑service grievance should identify source record and correction owner) [06_Digital_India_and_Public_Services.txt#page-35-chunk-17].  
- Record of whether the migrant/family used a local route to ask for the missed entitlement or to correct the record (families should have a clear local route to ask for missed entitlement or correct a record) [02_Health_and_Public_Health.txt#page-35-chunk-18].

Verification and audit evidence
- Evidence needed for social audit or grievance review to test whether the reported transaction corresponds to an accessible entitlement for the household (audit should be able to test transaction → entitlement mapping) [07_Transport_and_Infrastructure.txt#page-35-chunk-16].

Important caution from the context
- An MSR-3 referral entry only confirms that assistance was initiated; it is explicitly not proof that the worker collected the ration at destination or accessed services [08_MSME_and_Industrial_Development.txt#page-35-chunk-6].

What the provided context does NOT specify
- The exact field names, file format, retention periods, or who is authorized to close or edit specific fields are not specified in the supplied text. The context also does not supply templates or the exact evidence items (e.g., copies of POS receipts, eyewitness statements) that count as proof of collection beyond the general guidance above.

If you want, I can convert these requirements into a checklist of specific fields the case record should contain.

### Q124: A community complaint concerns an unsafe waste site and confidential safety risks. What should public reporting show and withhold?

Expected source documents retrieved: False. Accuracy: 2; groundedness: 2.

Expected behavior: Report separate grievance and environmental evidence measures with their definitions, while withholding confidential GSC-8 information; resolution requires ECR-5 and JGR-11 verification, not a mixed dashboard total.

Judge reasoning: The candidate answer provides a detailed breakdown of what public reporting should show and withhold, aligning with the expected behavior to some extent. However, it fails to mention the need for JGR-11 verification, which is a key part of the resolution process according to the expected behavior. This omission affects the accuracy score, as it is a critical component of the expected behavior. The answer is mostly grounded in the source context, but it does not fully align with the expected behavior, particularly regarding the verification requirements. The format is clear and well-structured, providing distinct sections for what should be shown and withheld, but the omission of JGR-11 affects the overall completeness.

Candidate answer:

Short answer
- Public reporting should show operational and verification facts about the waste system and any water/sanitation impacts, but must withhold confidential case-level safety information and must not mix safety-support counts into general beneficiary totals. [05_Renewable_Energy_and_Power.txt#page-35-chunk-6] [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10] [03_Education_and_Skills.txt#page-35-chunk-9]

What public reporting should show (distinct items)
- Waste system lifecycle stages recorded separately: segregation, collection, transport, processing and safe disposal. [05_Renewable_Energy_and_Power.txt#page-35-chunk-6]  
- Sanitation operations and outcomes: safe containment, collection, treatment and reuse or disposal status. [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-2]  
- Infrastructure vs functionality as separate indicators: households connected and connections functional reported separately. [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10]  
- Water testing and remedial statuses separately: sources tested, any unsafe test results, and unsafe results resolved. [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10]  
- Emergency fallback use: communities using an emergency fallback supply (if relevant) reported separately. [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-10]  
- If the waste site failure affects a water source, link the relevant ECR-5 evidence to the source record and report the responsible correction path. [05_Renewable_Energy_and_Power.txt#page-35-chunk-8]  
- Preparedness and accountability items relevant to disruptions: stock condition, last‑mile access constraints, community notice arrangements and escalation contacts. [07_Transport_and_Infrastructure.txt#page-35-chunk-14]  
- Avoid relying on single declarations (e.g., “infrastructure coverage” or “open‑defecation‑free”) as proof of sustained safe management or safe water/health outcomes — provide the operational and test evidence instead. [01_Agriculture_and_Farmers_Welfare.txt#page-36-chunk-2]

What public reporting should withhold (distinct items)
- Do not publish confidential case information (individual safety incidents, identifying case details) on public dashboards. [03_Education_and_Skills.txt#page-35-chunk-9]  
- Do not merge or publish safety‑support counts in a way that exposes individuals by combining them with general beneficiary totals; keep safety-support figures separate and protected. [03_Education_and_Skills.txt#page-35-chunk-9]

What the provided context does NOT specify
- The context does not give exact redaction rules, formats, fields, or thresholds for what counts as “confidential” or how to anonymize data, nor does it provide a complaint‑handling workflow, timelines for public updates, or technical templates for linking ECR‑5 evidence. These operational details are not in the supplied excerpts.

### Q127: What must be documented before an RRF-9 relief-reconciliation case can close?

Expected source documents retrieved: True. Accuracy: 2; groundedness: 2.

Expected behavior: State that the incident identifier, relevant record, action owner, review date and verification method must be recorded, and closure needs documented verification rather than a caseworker note.

Judge reasoning: The candidate answer correctly identifies that the RRF-9 must record the incident identifier, household or site reference, action owner, next review date, and verification method, which aligns with the expected behavior and source context. However, it incorrectly includes 'claimed need' and 'source record' as necessary for closure, which are not mentioned in the expected behavior. Additionally, the mention of closure reasons like administrative closure, service completion, or unresolved withdrawal is not relevant to the RRF-9 closure requirements and is not supported by the source context for this specific form. The format is clear and well-structured, but the inaccuracies and unsupported details affect the accuracy and groundedness scores.

Candidate answer:

- The RRF‑9 itself must record: the incident identifier, household or site reference, claimed need, source record, action owner, next review date and verification method [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-17].

- Before an RRF‑9 relief‑reconciliation case can be closed there must be documented verification of the resolution (formal verification), not merely a caseworker note [10_Rural_Development_and_Livelihoods.txt#page-35-chunk-17].

- Also, the closure reason for a closed case must be retained (e.g., administrative closure, service completion, unresolved withdrawal) and not be discarded [08_MSME_and_Industrial_Development.txt#page-35-chunk-14].
