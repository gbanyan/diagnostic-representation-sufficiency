# Open questions

| # | Question | Gate(s) | Status | Resolution / evidence |
|---|---|---|---|---|
| Q1 | Can MIMIC-CDM support clinically meaningful control-layer treatment evaluation? | G4, G5, G11 | answered (as released: no) | Rubric saturated by a label-only oracle; only a new patient-specific reference could work — [gates/mimic_cdm.md](gates/mimic_cdm.md) Q8 |
| Q2 | Can staged S0–S4 states be reconstructed without leakage? | G1, G7 | open (blocked on access) | Not as released; time-cut repair possible with MIMIC-IV — gate record Q3 |
| Q3 | How patient-specific is the original treatment rubric? | G5, G9, G11 | answered (code level) | Only observed procedures + the 'biliary' subtype; prevalence needs rows — gate record Q7 |
| Q4 | Is ER-REASON sufficiently complete for early-differential validation? | G2, G6, G12 | open | |
| Q5 | Are eICU diagnosis/treatment offsets dense and trustworthy enough? | G1, G12 | open | |
| Q6 | Is clinician annotation necessary for a gold early-impression subset? | G2, G12 | open | |
| Q7 | What minimum sample size remains after all restrictions? | G6, G8 | open | |
| Q8 | Does the author currently hold credentialed access to MIMIC-IV, MIMIC-IV-Ext-CDM, ER-REASON, and eICU? | — | answered: credentialed, but project DUAs unsigned | HTTP 403 on mimic-iv-ext-cdm, mimiciv, mimic-iv-note, mimic-iv-ed, eicu-crd (2026-09-29); MIMIC-CXR-JPG works. ER-REASON not checked |
| Q9 | Are MIMIC-CDM HPI/PE fields extracted from discharge summaries, and do they contain hindsight language? | G1, G7 | half answered | Yes, discharge-derived; hindsight rate needs row audit |
| Q10 | Does MIMIC-CDM's examination-request scoring depend on the final diagnosis? | G9 | answered: yes | Evaluator selected by true pathology — gate record Q9 |
| Q11 | What equivalence margin and minimum effect size define "no measurable cost"? | G8 | open | Needs author decision before Phase 1 |
| Q12 | Which base model(s) and compute budget will be matched across arms, and may patient text be sent to an external API under the applicable data use agreement? | — | open | Needs author decision before Phase 1 |

Update the status to `answered`, `blocked`, or `stop` with an evidence locator when resolved.

## Added by the target sufficiency preflight (2026-09-29)

| # | Question | Status | Evidence / next step |
|---|---|---|---|
| Q13 | Should Stage B use a pre-registered regularization choice (e.g. nested CV over C) or a reduced feature set, given that fixed C = 1 with X×D interactions overfits (AUROC rises while log loss falls)? | **answered**: nested CV, full feature set (author decision) | Pre-registered in [model_selection_preflight.md](model_selection_preflight.md). The disagreement is resolved after tuning |
| Q14 | Can T1 procedure timing be resolved below day resolution (MIMIC-IV `poe` order times, `services` transfers)? | **answered (partially resolvable)** | Of the 622 same-day ambiguous cases: 258 GREEN, 315 YELLOW, 49 RED ([procedure_timing_audit.md](procedure_timing_audit.md)). No pre-op order exists in POE |
| Q15 | What drives non-operative management within each diagnosis, and is it decision-relevant rather than preference (Stage C for T1)? | **DEFERRED — AUTHOR DECISION PENDING** | A stratified private case list is prepared (120 cases); it has not been reviewed or interpreted |
| Q16 | Is there a *non-trivial* negative control in which diagnosis settles a real decision? T5 is near-trivial | **answered: M5** (anaerobic coverage) | Δ ≈ 0 at both landmarks; power is limited by non-event counts 22–49 per D |
| Q17 | Should eICU `lab` / `vitalPeriodic` (≈ 2.3 GB) be downloaded to evaluate E1 Stage B? | **answered: deferred**; MIMIC-IV prescriptions downloaded instead | [prescription_target_audit.md](prescription_target_audit.md) |
| Q18 | Does eICU problem-list entry lag the actions at full scale and per hospital? | open | Demo: ~75% of entries come after the action |

## Added after Q13 / Q14 / Q17 (2026-09-29)

| # | Question | Status |
|---|---|---|
| Q19 | Should the main experiment leave diagnosis offsets unpenalized (or fit per diagnosis)? A shared L2 penalty shrinks the D main effects in `Model_DX` (the T5 artifact), biasing every Δ conservatively | open: pre-registration decision |
| Q20 | Is M6 (insulin) within scope? The recovered information is not diagnosis-specific (`I(Y;D)` ≈ 0) | open: author decision |
| Q21 | Should YELLOW timing cases (362 T1 positives at 6 h) stay in the primary analysis? Stage B conclusions hold either way | open |
