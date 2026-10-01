# Manual leakage audit protocol — MIMIC-CDM (Q3, Q5)

Applies to the stratified sample of 200 cases (50 per pathology, seed 20260929) drawn by `audit.cdm_audit sample`. The per-case records stay in the private directory. Only aggregate counts are committed.

## Reviewer instructions

For each case, read each stage field **as if it were written at that stage's time**. Ask: *could a clinician have written this sentence at that point?*

| Stage | Field(s) | Intended time |
|---|---|---|
| S0 | Patient History | Presentation, before examination and results |
| S1 | Physical Examination | Initial examination |
| S2 | Laboratory Tests (with offsets from the timing audit) | Initial labs |
| S3 | Radiology findings (with offsets) | First diagnostic imaging |

## Per-case record (private)

```text
hadm_id:
pathology:
reviewer:
S0_leak: none | results_of_tests | diagnosis_implied | treatment_or_course | diagnosis_named
S0_evidence_type:          # category only, no verbatim text
S1_leak: (same scale)
S1_is_admission_exam: yes | no | unclear
S2_items_after_24h: count  # from timing output
S3_first_abdominal_imaging_before_procedure: yes | no | unclear
S3_leak: (same scale)
lexicon_flags_confirmed: [categories confirmed as true leakage]
lexicon_flags_false_positive: [categories]
missed_by_lexicon: [categories]
usable_at_stage: S0 | S1 | S2 | S3 | none   # latest stage reconstructable without leakage
notes:                     # paraphrase only; no patient text
```

## Leak scale definitions

- **results_of_tests:** the text reports lab or imaging results that belong to a later stage (for example, CT findings in the HPI).
- **diagnosis_implied:** the text makes the diagnosis near-certain without naming it (for example "dilated appendix with appendicolith", or a `____` redaction marker).
- **treatment_or_course:** it mentions treatment, procedures, response, or hospital course.
- **diagnosis_named:** it names the diagnosis via a synonym not covered by redaction.

## Aggregates to report

For each stage and pathology:

- share of cases at each leak level;
- the share with any leak above none (compared against the ≤ 5% threshold);
- lexicon precision and recall against the manual labels;
- the distribution of `usable_at_stage`.

Inter-rater agreement: if a second reviewer is available, double-review 40 cases (10 per pathology) and report Cohen's κ for `S0_leak` and `S1_leak`.
