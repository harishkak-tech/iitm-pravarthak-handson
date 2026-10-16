"""Compact the generated framework while retaining every unique source passage."""

from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/corpus_txt"

ADDITIONS = {
    "02": ("Health Referral Status and Reporting", "Health and nutrition referral reporting must keep referrals issued, referrals accepted, clinical assessments, treatment where relevant and completed follow-up separate. State the reporting period and denominator. NTR-7 tracks referral coordination; health records establish assessment and treatment. Reconcile only the minimum necessary information, retain the original discrepancy and correction trail, and do not merge unresolved screening and clinical records into a single beneficiary total."),
    "03": ("Education and Skills Implementation Challenges", "Education and skill-development implementation must address unequal access to devices, connectivity and language-appropriate content, teacher capacity and learning quality. Vocational training must align with actual labour-market needs. Enrolment, certification, placement and sustained employment remain separate measures; a placement immediately after training does not establish sustained employment."),
    "05": ("Renewable-Energy Users and Delivery Conditions", "Renewable-energy and power policy serves electricity users through improved access, reliability, affordability and sustainability. Rooftop solar adoption specifically concerns households and other consumers. Consumer awareness, financing, installation capacity, distribution-company processes and grid integration affect delivery. An application or sanctioned subsidy is not a commissioned, operating system."),
    "06": ("Grievance Verification Across Public Services", "For a disputed payment, ration transaction, water source or housing service, JGR-11 must link the underlying service record, evidence and correction owner. Preserve the original mismatch and correction trail. Record the decision, corrective action and verified remedy as separate stages. A portal update or administrative closure does not establish successful credit, completed collection, functional restoration or a verified remedy."),
    "08": ("MSME Delivery and Labour-Mobility Record Boundaries", "MSME and industrial-development delivery must coordinate finance, infrastructure, skills and market access rather than treating an administrative approval as an enterprise outcome. For migrant services, MSR-3 records the origin, destination, requested entitlement, correction and referral owner. A portability request must retain the service, reporting period and destination authority. Reconciliation preserves the original mismatch and correction trail; a referral alone proves neither ration collection nor payment."),
    "09": ("Financial-Inclusion Delivery Channels and Payment Checks", "Financial-inclusion delivery uses banks and formal financial channels, including digital transfer of eligible government benefits. Accessible banking channels, accurate records and grievance mechanisms guard against exclusion and payment errors. Check enrolment, eligibility verification, account linkage or seeding, payment-order generation, release and successful credit separately. A released payment is not a settled transaction. Preserve the original mismatch and correction trail when correcting the benefit record."),
    "10": ("Rural Works, Social Audit and Relief Verification", "For rural employment works, Gram Sabha review and social audit make the proposed asset, expenditure, work completed and maintenance responsibility visible to the community. Keep an asset completed separate from a later service or hydrological outcome. For disaster-related disputes, RRF-9 links the incident identifier, household or site reference, claimed need, source record, action owner, next review date and verification method. Closing an RRF-9 requires documented verification, not merely a caseworker note."),
}

TEMPLATE = re.compile(
    r"^(?:The .+ arrangements for .+ should be administered through a written procedure|"
    r"Implementation of .+ requires coordination between policy authorities|"
    r"Authorities should interpret .+ in a manner that is evidence-based|"
    r"Review of .+ should distinguish administrative activity from actual outcomes|"
    r"This expanded framework provides a longer, paragraph-based administrative treatment)"
)


def main():
    changes = []
    for path in sorted(SOURCE.glob("*.txt")):
        original = path.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", original) if p.strip()]
        kept, removed = [], []
        for paragraph in paragraphs:
            if TEMPLATE.match(paragraph) or paragraph.startswith("Expanded Policy Implementation Framework\n") or re.match(r"^Section \d+:", paragraph):
                removed.append(paragraph)
            elif paragraph not in kept:
                kept.append(paragraph)
        # Preserve every substantive passage, including sections inserted within
        # the generated framework, instead of deleting that entire text range.
        assert all(p in kept for p in paragraphs if p not in removed)
        if removed:
            heading = "Common Administration and Evidence Standards"
            kept.append(heading + "\n" + "-" * len(heading) + "\n"
                        "Use a written procedure with a named responsible authority, intended users, required records, completion criteria and routes for exceptions or clarification. Coordinate policy authorities, field offices, local institutions and delivery partners, retaining visible pending dependencies. Address distance, documentation, language, disability, connectivity and cost through outreach and assisted access. Distinguish administrative activity from actual outcomes, and record the unit, date, source, status and unresolved cases.")
        if path.name[:2] in ADDITIONS:
            heading, body = ADDITIONS[path.name[:2]]
            # These reading notes summarise existing passages, not external rules.
            if not any(p.startswith(heading + "\n") for p in kept):
                kept.append(heading + "\n" + "-" * len(heading) + "\n" + body)
        text = "\n\n".join(kept) + "\n"
        if path.name.startswith("11_"):
            text = text.replace("The approved pilot envelope was Rs 48 crore.", "The Integrated District Delivery Pilot in Sundar and Narmada (financial year 2024-25) had an approved envelope of Rs 48 crore.")
        if path.name.startswith("12_"):
            text = text.replace("The state approved an allocation of Rs 42 crore for the pilot.", "The Connected Services Pilot in Aster and Bhagirathi (financial year 2024-25) had a state-approved allocation of Rs 42 crore.")
        path.write_text(text, encoding="utf-8")
        counts = Counter(p.strip() for p in re.split(r"\n\s*\n", text) if p.strip())
        assert all(count == 1 for count in counts.values())
        changes.append({"source": path.name, "before_chars": len(original), "after_chars": len(text), "template_paragraphs_removed": len(removed), "duplicate_paragraphs_remaining": 0})
    out = ROOT / "docs/runs/corpus_revision_manifest.json"
    out.write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    print(f"Revised {len(changes)} sources: {sum(x['before_chars'] for x in changes)} -> {sum(x['after_chars'] for x in changes)} characters")


if __name__ == "__main__":
    main()
