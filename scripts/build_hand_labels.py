"""Generate fixtures/hand_labels.json with EXACT citation spans sliced
straight out of the real corpus text files (fixtures/corpus/*.txt).

Every span is produced by locating an anchor substring in the actual
document text and slicing forward to (approximately) the next sentence
boundary -- so every citation_span is guaranteed to be an exact,
verifiable substring of the source document, never hand-retyped.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "fixtures" / "corpus"
OUT_PATH = REPO_ROOT / "fixtures" / "hand_labels.json"

# (document_id, field_name, anchor, min_len_before_period_search, max_len,
#  classification, value, reason)
ENTRIES = [
    # --- adial_msa ---
    ("adial_msa", "effective_date", "is entered into effective March 15, 2023", 30, 90,
     "include", "March 15, 2023", None),
    ("adial_msa", "governing_law", "shall be construed and enforced in accordance with the laws of the Commonwealth of Virginia", 60, 200,
     "include", "Commonwealth of Virginia", None),
    ("adial_msa", "termination_for_convenience", "Termination for Convenience: Either party may terminate this Agreement at any time for any or no reason", 60, 300,
     "include", "Either party, any/no reason, notice per Sec 8.2", None),
    ("adial_msa", "limitation_of_liability", None, None, None,
     "uncertain", None, 'The word "liability" appears only twice, both in unrelated boilerplate (a no-agency disclaimer and a general indemnification list) -- there is no dedicated liability-cap or damages-exclusion clause. Flagged uncertain rather than a confident exclude because those two mentions are genuine (if weak) evidence, not silence.'),
    ("adial_msa", "assignment_restriction", "Contractor may not assign any of Contractor", 40, 220,
     "include", "Contractor may not assign rights/obligations without Company's consent", None),
    ("adial_msa", "confidentiality", "Contractor acknowledges that during the course of providing its Services hereunder, Contractor may have access to, develop or learn", 80, 260,
     "include", "Confidential Information defined and protected (Sec 4)", None),

    # --- cadrenal_msa ---
    ("cadrenal_msa", "effective_date", "is entered into as of August 21, 2024", 30, 90,
     "include", "August 21, 2024", None),
    ("cadrenal_msa", "governing_law", "This Agreement shall be governed by and construed in accordance with the laws of the State of California", 60, 220,
     "include", "State of California", None),
    ("cadrenal_msa", "termination_for_convenience", "Termination for Convenience . Either party may terminate this Agreement as of the thirtieth", 60, 260,
     "include", "30 days after written notice of termination (Sec 9.3)", None),
    ("cadrenal_msa", "limitation_of_liability", "Limitation of Liability . (a) The limit of L", 40, 260,
     "include", "Liability cap defined in Sec 6.3(a)", None),
    ("cadrenal_msa", "assignment_restriction", "Assignment . L&A may delegate its functions to subcontractors", 50, 260,
     "include", "L&A may delegate; Agreement binds successors/assigns (Sec 11.1)", None),
    ("cadrenal_msa", "confidentiality", "CONFIDENTIALITY 8.1.", 15, 260,
     "include", "Confidential Information defined (Sec 8)", None),

    # --- cassava_agreement ---
    ("cassava_agreement", "effective_date", "made and entered into effective on February", 20, 90,
     "uncertain", None, 'Date rendered with irregular internal spacing ("February 2 2 , 202 1"), a PDF-extraction artifact in the filed exhibit; the digit grouping cannot be read with full confidence as a single unambiguous date.'),
    ("cassava_agreement", "governing_law", "This Agreement is to be interpreted and enforced in accordance with the laws of the State of Delaware", 60, 220,
     "include", "State of Delaware", None),
    ("cassava_agreement", "termination_for_convenience", "Termination for Convenience of Statement of Work", 30, 240,
     "include", "Customer may terminate individual Statements of Work for convenience (Sec 6.3)", None),
    ("cassava_agreement", "limitation_of_liability", "Limitation of Liability. 8.3.1 Notwithstanding", 40, 260,
     "include", "Liability limitation defined in Sec 8.3", None),
    ("cassava_agreement", "assignment_restriction", "Assignment; Successors and Assigns . Neither Party may assign all or any part of this Agreement", 60, 260,
     "include", "Neither party may assign without the other's consent (Sec 12.3)", None),
    ("cassava_agreement", "confidentiality", "10. Confidentiality . [ *** ]", 10, 40,
     "uncertain", None, "Section 10 (Confidentiality) is redacted in the public SEC filing (marked \"[ *** ]\"); no extractable clause text or citation span is available even though the section is cross-referenced elsewhere in the agreement."),

    # --- clevelandbiolabs_agreement ---
    ("clevelandbiolabs_agreement", "effective_date", "is made on October 14, 2013", 20, 80,
     "include", "October 14, 2013", None),
    ("clevelandbiolabs_agreement", "governing_law", "shall be governed by the laws of the State of New York, irrespective", 50, 220,
     "include", "State of New York", None),
    ("clevelandbiolabs_agreement", "termination_for_convenience", "Termination for Convenience . Sponsor may terminate this Agreement in its entirety", 60, 320,
     "include", "Sponsor may terminate on 30-90 days written notice (Sec 13.1)", None),
    ("clevelandbiolabs_agreement", "limitation_of_liability", "IN NO EVENT SHALL EITHER PARTY, NOR THEIR RESPECTIVE AFFILIATES OR SUBCONTRACTORS BE LIABLE", 60, 320,
     "include", "Mutual liability limitation clause", None),
    ("clevelandbiolabs_agreement", "assignment_restriction", "ASSIGNMENT - SUBCONTRACTORS Neither party shall, without the prior written consent", 60, 260,
     "include", "Neither party may assign without consent (Sec 14)", None),
    ("clevelandbiolabs_agreement", "confidentiality", "means all information, materials, methods, procedures, techniques, strategies, policies, cell lines, molecules", 60, 260,
     "include", "Confidential Information defined (Sec 1.2)", None),

    # --- ezfill_agreement ---
    ("ezfill_agreement", "effective_date", "dated as of January 1, 2023", 20, 80,
     "include", "January 1, 2023", None),
    ("ezfill_agreement", "governing_law", "shall be governed by, construed, and enforced in accordance with the laws of the State of Florida", 60, 220,
     "include", "State of Florida", None),
    ("ezfill_agreement", "termination_for_convenience", "Termination for Convenience . Unless otherwise expressly set forth in this Agreement, after July 31, 2023", 60, 300,
     "include", "SFM may terminate for convenience after July 31, 2023 (Sec 5.2)", None),
    ("ezfill_agreement", "limitation_of_liability", None, None, None,
     "uncertain", None, 'The word "liability" recurs throughout the indemnification and insurance sections, but no dedicated liability-cap or consequential-damages-waiver clause is present. Flagged uncertain rather than a confident exclude because of that recurring (if diffuse) evidence.'),
    ("ezfill_agreement", "assignment_restriction", "No party may assign this Agreement without the prior written consent of the other party", 60, 300,
     "include", "Consent required to assign, with carve-outs for SFM (Sec 13c)", None),
    ("ezfill_agreement", "confidentiality", "Confidentiality . Contractor acknowledges and agrees that it will have access to, or become acquainted with, SFM", 60, 260,
     "include", "Confidential Information defined (Sec 7.0)", None),

    # --- fairpoint_agreement ---
    ("fairpoint_agreement", "effective_date", "entered into as of January __, 2007 between Capgemini", 30, 90,
     "uncertain", None, 'The date field in the filed exhibit is left blank ("January __, 2007") -- no day was ever filled in, so no unambiguous effective date can be extracted.'),
    ("fairpoint_agreement", "governing_law", "This Agreement shall be governed by and construed in accordance with the laws of the State of New York, without reference", 60, 240,
     "include", "State of New York", None),
    ("fairpoint_agreement", "termination_for_convenience", "for convenience, at any time upon 30 days prior written notice", 30, 200,
     "include", "Capgemini may terminate for convenience on 30 days notice (Sec 11(b)(iii))", None),
    ("fairpoint_agreement", "limitation_of_liability", "the total aggregate liability of either party under this Agreement or with respect to the Services", 60, 320,
     "include", "Aggregate liability cap (Sec 10(e))", None),
    ("fairpoint_agreement", "assignment_restriction", "Assignment . Neither this Agreement nor any of the rights or duties hereunder may be assigned", 60, 280,
     "include", "Neither party may assign without consent, with carve-out for Capgemini (Sec 14(i))", None),
    ("fairpoint_agreement", "confidentiality", "Neither party shall disclose to a third party Confidential Information", 40, 220,
     "include", "Mutual confidentiality obligation (Sec 5)", None),

    # --- galectin_agreement ---
    ("galectin_agreement", "effective_date", "This Master Services Agreement is effective as of March 12, 2020", 30, 90,
     "include", "March 12, 2020", None),
    ("galectin_agreement", "governing_law", "shall be governed by the laws of Delaware, without regard or giving effect to its principles of conflicts of law", 60, 240,
     "include", "Delaware", None),
    ("galectin_agreement", "termination_for_convenience", "A Party may terminate a Work Order prior to completion of the applicable Services at any time for any reason upon ninety (90) days written notice", 90, 340,
     "include", "Either party may terminate a Work Order for any reason on 90 days notice (Sec 21.2)", None),
    ("galectin_agreement", "limitation_of_liability", "REMEDIES AND LIMIT OF LIABILITY 18.1 Except as otherwise provided", 40, 260,
     "include", "Liability limitation (Sec 18)", None),
    ("galectin_agreement", "assignment_restriction", "Assignment . Each Party may transfer or subcontract any or all of its rights and obligations under this Agreement or a Work Order to its Affiliates", 90, 340,
     "include", "Assignable to Affiliates only (Sec 33.2)", None),
    ("galectin_agreement", "confidentiality", "means any and all commercial or technical information or materials and all derivatives thereof", 60, 260,
     "include", "Confidential Information defined (definitions section)", None),

    # --- graphicpkg_msa ---
    ("graphicpkg_msa", "effective_date", "is made and entered into as of November 29, 2007", 30, 90,
     "include", "November 29, 2007", None),
    ("graphicpkg_msa", "governing_law", "This Agreement will be governed by and construed in accordance with the substantive laws of Georgia", 60, 220,
     "include", "Georgia", None),
    ("graphicpkg_msa", "termination_for_convenience", "GPI may terminate (a) this Agreement or (b) one or more Service Towers, for convenience by providing Perot Systems with at least 120 days", 90, 340,
     "include", "GPI may terminate for convenience on 120 days notice + Termination Fee", None),
    ("graphicpkg_msa", "limitation_of_liability", "Limitation on Consequential Damages. OTHER THAN WITH RESPECT TO DAMAGES RESULTING FROM BREACHES", 70, 340,
     "include", "Consequential and direct damages caps (Article XVIII)", None),
    ("graphicpkg_msa", "assignment_restriction", "Binding Nature; Assignment. This Agreement will be binding on the Parties and their successors and permitted assigns. Neither Party may assign", 90, 340,
     "include", "Neither party may assign without consent (Sec 21.5)", None),
    ("graphicpkg_msa", "confidentiality", "obligation to keep confidential GPI", 20, 240,
     "include", "Subcontractor confidentiality flow-down obligation", None),

    # --- livewire_msa ---
    ("livewire_msa", "effective_date", "effective as of January 1, 2025", 20, 80,
     "uncertain", None, 'The document also references a related, separate Separation Agreement using identical phrasing ("effective as of September 26, 2022") earlier in the recitals; a naive date extractor risks conflating the two, so this is flagged for reviewer confirmation rather than confidently assumed to be January 1, 2025.'),
    ("livewire_msa", "governing_law", "shall be governed by and construed and interpreted in accordance with the Laws of the State of Delaware", 60, 240,
     "include", "State of Delaware", None),
    ("livewire_msa", "termination_for_convenience", "Termination for Convenience . Either Party may terminate this Agreement or any applicable Letter Agreement for convenience upon ninety (90) days", 90, 340,
     "include", "Either party may terminate for convenience on 90 days notice (Sec 8.4)", None),
    ("livewire_msa", "limitation_of_liability", "Limitation of Liability . WITHOUT LIMITING THE PARTIES", 40, 300,
     "include", "Liability limitation (Sec 7.6)", None),
    ("livewire_msa", "assignment_restriction", "Assignment . This Agreement and the rights and obligations hereunder may not be assigned or transferred by either Party", 80, 300,
     "include", "Neither party may assign without consent (Sec 9.1)", None),
    ("livewire_msa", "confidentiality", "means (a) non-public information and material of a Party or its Affiliates", 60, 260,
     "include", "Confidential Information defined", None),

    # --- nuscale_agreement ---
    ("nuscale_agreement", "effective_date", "of this Agreement is the date on which the Agreement is fully executed by both parties", 40, 130,
     "uncertain", None, "This filing bundles two agreements; the Fluor Supplier Agreement portion defines its Effective Date only circularly (\"the date on which the Agreement is fully executed\") rather than stating a calendar date in the text, so no fixed date can be extracted with confidence."),
    ("nuscale_agreement", "governing_law", "This Agreement shall be governed by the laws of the State of Oregon, without regard to its conflict of laws provisions", 60, 220,
     "include", "State of Oregon", None),
    ("nuscale_agreement", "termination_for_convenience", "13. Termination. Termination for Convenience", 15, 90,
     "include", "Task Orders may be terminated for convenience (Sec 13)", None),
    ("nuscale_agreement", "limitation_of_liability", "neither party shall be responsible or held liable to the other for indirect, special or consequential damages", 60, 280,
     "include", "Mutual consequential-damages waiver", None),
    ("nuscale_agreement", "assignment_restriction", None, None, None,
     "uncertain", None, 'No clause restricting or governing assignment of the Agreement itself was found; "assign" only appears in unrelated contexts (IP work-product assignment, boilerplate "successors and assigns," personnel reassignment). Flagged uncertain rather than a confident exclude because those decoy mentions are real, if misleading, evidence.'),
    ("nuscale_agreement", "confidentiality", "means any information concerning the business, operations, assets or trade secrets of a party", 60, 260,
     "include", "Confidential Information defined (Sec 7)", None),

    # --- vivos_agreement ---
    ("vivos_agreement", "effective_date", "is entered into as of July 31, 2026", 30, 90,
     "include", "July 31, 2026", None),
    ("vivos_agreement", "governing_law", "16.1 Governing Law. This Agreement shall be governed by and construed in accordance with the laws of the State of Colorado", 80, 260,
     "uncertain", None, "Two separate governing-law clauses appear in the same document naming different states: Section 16.1 specifies Colorado for the Agreement generally, while Section 8.3 separately specifies Delaware for officer-indemnification/D&O matters. No single jurisdiction can be extracted as \"the\" governing law without knowing which sub-topic is meant."),
    ("vivos_agreement", "termination_for_convenience", "No Termination for Convenience. Neither Party may terminate this Agreement for convenience", 60, 240,
     "exclude", "Explicitly disclaimed: convenience termination is not permitted (Sec 3.3)", None),
    ("vivos_agreement", "limitation_of_liability", "Limitation of Liability 10.1 Cap. EXCEPT FOR", 40, 260,
     "include", "Liability cap tied to fees paid in prior 12 months (Sec 10.1)", None),
    ("vivos_agreement", "assignment_restriction", "Assignment. Neither Party may assign this Agreement without the other Party", 40, 260,
     "include", "Neither party may assign without consent (Sec 16.6)", None),
    ("vivos_agreement", "confidentiality", "means all non-public information disclosed by one Party to the other Party in connection with this Agreement", 70, 260,
     "include", "Confidential Information defined (Sec 1.1)", None),

    # --- zixcorp_msa ---
    ("zixcorp_msa", "effective_date", "dated January 30, 2004", 15, 70,
     "include", "January 30, 2004", None),
    ("zixcorp_msa", "governing_law", "Governing Law. This Agreement shall be governed by the laws of the State of New Jersey", 60, 220,
     "include", "State of New Jersey", None),
    ("zixcorp_msa", "termination_for_convenience", "Termination for Convenience. Aventis shall have the right to terminate this Agreement for any reason, at any time, by giving written notice at least thirty (30) days", 100, 340,
     "include", "Aventis (later both parties) may terminate for any reason on 30 days notice (Sec 4.4)", None),
    ("zixcorp_msa", "limitation_of_liability", "liable to the other for any special, - 19 - <PAGE> incidental, punitive or consequential damages", 40, 200,
     "uncertain", None, 'This is a legacy SEC plaintext (.txt) filing that embeds SGML pagination artifacts ("- 19 - <PAGE>") directly inside the clause text, corrupting the exact wording; not confident the extracted span reflects the clause faithfully enough to ground a clean citation.'),
    ("zixcorp_msa", "assignment_restriction", "Assignment. Neither party shall have the right to assign this Agreement or any of the rights or obligations hereunder", 70, 280,
     "include", "Neither party may assign without consent (Sec 14.2)", None),
    ("zixcorp_msa", "confidentiality", "party disclosing Confidential Information shall be referred to as the", 40, 220,
     "include", "Confidential Information defined; discloser/recipient roles (Sec 3.1)", None),
]


def slice_span(text: str, anchor: str, min_len: int, max_len: int) -> str:
    idx = text.find(anchor)
    if idx == -1:
        raise ValueError(f"anchor not found: {anchor!r}")
    window = text[idx: idx + max_len]
    # look for a sentence-ending period after min_len chars of content
    cut = window.find(". ", min_len)
    if cut != -1:
        return window[: cut + 1]
    return window


def main():
    records = []
    missing_docs = set()
    doc_cache = {}
    for doc_id, field, anchor, min_len, max_len, classification, value, reason in ENTRIES:
        if doc_id not in doc_cache:
            path = CORPUS_DIR / f"{doc_id}.txt"
            doc_cache[doc_id] = path.read_text(encoding="utf-8")
        text = doc_cache[doc_id]

        if anchor is None:
            span = ""
        else:
            try:
                span = slice_span(text, anchor, min_len, max_len)
            except ValueError as e:
                print(f"MISSING ANCHOR [{doc_id}/{field}]: {e}")
                continue
            # sanity: must be an exact substring (guaranteed by construction,
            # but re-verify defensively)
            assert span in text, f"span not grounded for {doc_id}/{field}"

        records.append({
            "document_id": doc_id,
            "field_name": field,
            "correct_classification": classification,
            "correct_value": value,
            "citation_span": span,
            "reason": reason,
        })

    OUT_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(records)} hand labels to {OUT_PATH}")

    from collections import Counter
    print(Counter(r["correct_classification"] for r in records))


if __name__ == "__main__":
    main()
