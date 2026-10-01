"""Hindsight / leakage lexicon for the MIMIC-CDM Phase 0 audit (Q3, Q5).

Patterns flag text that may not have been available at the stage the field is
meant to represent. A flag is a screening signal for manual review, not a
leakage verdict. Categories are reported separately so that rates can be
interpreted per mechanism.
"""

import re

# Upstream redaction replaces target-disease strings with exactly four
# underscores; MIMIC de-identification uses three. A four-underscore token in
# PE or radiology therefore means the source text named the target disease.
REDACTION_MARKER = re.compile(r"(?<!_)_{4}(?!_)")

CATEGORIES = {
    # Text describing later course, procedures, or outcome.
    "course_hindsight": [
        r"\bs/p\b",
        r"\bstatus post\b",
        r"\bpost[- ]?op(?:erative(?:ly)?)?\b",
        r"\bPOD\s*#?\s*\d",
        r"\bwas taken to the (?:OR|operating room)\b",
        r"\bunderwent\b",
        r"\bwas found to have\b",
        r"\bsubsequently\b",
        r"\bhospital course\b",
        r"\bdischarged?\b",
        r"\btolerated (?:the )?procedure\b",
    ],
    # Results of investigations reported inside history text (S0 contains S2/S3).
    "ed_results_in_history": [
        r"\bin the (?:ED|emergency (?:department|room))\b",
        r"\b(?:CT|CTA|ultrasound|US|RUQUS|MRI|MRCP|HIDA|imaging)\b[^.]{0,60}\b(?:show(?:ed|s|ing)?|reveal(?:ed|s)?|demonstrat(?:ed|es)|notable|significant for|c/w|consistent with)\b",
        r"\blabs? (?:were |was )?(?:notable|significant|remarkable)\b",
        r"\b(?:WBC|white count|lipase|amylase|lactate|bilirubin|t\.? ?bili|ALT|AST|alk ?phos)\b\s*(?:of|was|=|:)?\s*\d",
    ],
    # Diagnosis- or treatment-suggestive shorthand not covered by upstream redaction.
    "diagnosis_shorthand": [
        r"\bappy\b",
        r"\bappendic(?:olith|eal)\b",
        r"\blap(?:aroscopic)? ?(?:chole|appy)\b",
        r"\bcholecystectomy\b",
        r"\bcholecystostomy\b",
        r"\bERCP\b",
        r"\bsphincterotomy\b",
        r"\b(?:IR|percutaneous) drain(?:age)?\b",
        r"\bpigtail\b",
        r"\bcolectomy\b",
        r"\bHartmann",
        r"\bpancreatic necrosis\b",
        r"\bphlegmon\b",
        r"\bgallstone pancreatitis\b",
        r"\bdiverticul",
        r"\bpericholecystic\b",
    ],
}

COMPILED = {
    name: [re.compile(p, re.IGNORECASE) for p in patterns]
    for name, patterns in CATEGORIES.items()
}


def flags(text):
    """Return the set of categories matched in text (including 'redaction_marker')."""
    found = set()
    if not text:
        return found
    for name, patterns in COMPILED.items():
        if any(p.search(text) for p in patterns):
            found.add(name)
    if REDACTION_MARKER.search(text):
        found.add("redaction_marker")
    return found


ALL_CATEGORIES = sorted(list(CATEGORIES) + ["redaction_marker"])
