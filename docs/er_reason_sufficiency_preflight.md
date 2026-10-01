# ER-REASON — target sufficiency preflight

- **Date:** 2026-09-29
- **Data status:** **no row access.** The data use agreement is signed, but the study request the dataset authors must review is pending, so `physionet.org/files/er-reason/1.0.0/` returns HTTP 403.
- **Evidence:** everything here comes from public documentation and code, via [gates/er_reason.md](gates/er_reason.md). No statistic in this file comes from ER-REASON rows.

## Diagnosis objects in ER-REASON

| Object | Field | Classification |
|---|---|---|
| `D_final` (ED scale) | `primaryeddiagnosisname` | ED diagnosis at ED departure, after the full workup. Never a `D_t` for triage or initial assessment. |
| `D_t` | None | No contemporaneous, time-stamped clinician differential exists. |
| Expert hypothetical differential | `Rule_Out` (72 cases) | Written retrospectively by a study-recruited EM physician from chief complaint + demographics + one-liner. **Not** the treating physician's impression. It can serve as a *reference* for `D_hat_0`, not as `D_t`. |
| `D_hat_t` | — | Would be model-generated from S0/S1 text, labelled as an experimental bottleneck. |

## Answers to the preflight questions

1. **Are `Rule_Out` / `Decision_Factors` contemporaneous with the state being evaluated?** No. They were written in a study application, after care, at a *controlled* information state (the pre-encounter one-liner view). Their "time" is a design choice, not a clinical timestamp.
2. **Retrospectively authored at end of encounter?** Retrospective, yes, but not by the treating team and not at the encounter's end. They were authored during the study by annotators. Whether annotators were blinded to the ED diagnosis or disposition is **NOT YET VERIFIED**.
3. **Is `Treatment_Plan` prospective or reconstructed?** Neither. It is a hypothetical "what would you do given the history and physical", written by one annotator. It is not the observed treatment.
4. **Cases with complete state + `Rule_Out` + `Decision_Factors` + `Treatment_Plan` + final diagnosis:** at most **72** (documentation). The exact count is UNKNOWN until rows are available.
5. **Expert-authored rationale cases:** 72, apparently one annotator each (NOT YET VERIFIED). The 194-case adjudicated script-concordance set is probably not in the public release (NOT YET VERIFIED; see the gate record, P0).
6. **Validation rather than training?** Yes. 72 cases can support only a **validation / face-validity** role: comparing `D_hat_0` with `Rule_Out`, and a small exam-plan reference built from `Decision_Factors`. It cannot support model training or a primary endpoint.
7. **Patient-state variables that explain treatment variation within diagnosis?** **Cannot evaluate.** There are no structured, timed treatments, and the ED course is un-timed free text. The only observed, near-complete decision is `eddisposition`.

## Candidate targets

| ID | Target | Stage A (H(Y\|D)) | Stage B (X\|D) | Clinical relevance | Leakage | Status |
|---|---|---|---|---|---|---|
| R1 | Disposition (admit / discharge / other) given the ED diagnosis, from S1 text (MDM and later removed) | Cannot evaluate (no rows) | Cannot evaluate | Plausible: a management decision that depends on severity and social factors beyond the label | High: end-of-encounter note; "historical" notes may include current-visit content | **Cannot evaluate with current data → YELLOW candidate** once access, the leakage audit, and the label-only oracle test are complete |
| R2 | `Treatment_Plan` concepts | Cannot evaluate | Cannot evaluate | Low as a primary endpoint: hypothetical, single annotator, n = 72 | Annotator exposure unknown | **RED as a primary target**; possible supplementary validation |
| R3 | `Decision_Factors` as an S0 exam-plan reference (examination target) | Not a sufficiency target (a reference standard for plans) | — | Plausible | Built through the annotator's own differential, which biases it toward the bottleneck arm | **YELLOW (validation only)**: needs a blinding check and a precision-aware metric |

## Negative-control candidates

None can be evaluated without rows. Once access is granted, one candidate is disposition within diagnoses that are nearly always discharged or nearly always admitted (Stage A condition A). That would give a within-dataset BLUE target to pair with R1.

## Questions for the dataset authors (from the gate record)

1. Which files v1.0.0 contains: `icd_10_codes.csv`, and the script-concordance set?
2. Are the "historical" notes strictly from prior encounters?
3. What did annotators see, and were they blinded to the ED diagnosis and disposition?
4. How was `One_Sentence_Extracted` produced?
5. Which LLM endpoints are permitted? Default: local open-weight models only.
