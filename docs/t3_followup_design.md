> **SUPERSEDED (2026-09-30): diagnosis timing semantics unresolved.** This design used the MC-MED visit diagnosis (`Dx_ICD10`) as the diagnosis D at a 3 h landmark. The dataset documentation places `Dx_ICD9`/`Dx_ICD10`/`Dx_name` among fields "summarizing the visit itself" (Kansal et al., *Sci Data* 2025, Methods → Visits), with no timestamp. It is **not** documented as the diagnosis available at 3 h, so it must not be used as `D_3h`. See [mcmed_diagnosis_semantics.md](mcmed_diagnosis_semantics.md) and the replacement design in [mcmed_dhat_design.md](mcmed_dhat_design.md). This file is kept unchanged below as the record.

# T3 follow-up: design for an independent confirmation of escalation-of-care sufficiency

**Status: DESIGN ONLY. Not run, not authorized, and no data inspected for outcomes.** It becomes a preregistration only after the author approves it and a binding commit is recorded, **before** any outcome in the new cohort is examined.

## Why a new study

In the confirmatory analysis (preregistration `600f368`), T3 was a prespecified **secondary** endpoint. **Its confirmatory status was lost under the hierarchical testing rule after T1 failed.**

The observed exploratory result was:
- relative gain ≈ 16.3% (Δ = 0.045 bits, 95% CI 0.035–0.056);
- AUROC ≈ 0.66 → 0.83.

The MIMIC-IV cohorts have now been used, so confirmation requires **new, untouched observations**.

## Primary question

Does contemporaneous patient state add **substantial** predictive information, beyond diagnosis and common operational context, about a **prespecified escalation-of-care endpoint** in observations never used in this project?

## Endpoint semantics (fixed)

- **Observed escalation of care**: an ICU admission or ICU transfer that actually happened.
- It is **never** "optimal ICU disposition". It reflects deterioration, clinician judgment, escalation practice, and bed/operational constraints.
- No causal or normative claim is permitted.

## Candidate untouched cohorts

| Candidate | Independence | Endpoint available | Diagnosis | Timing quality | Status / risks |
|---|---|---|---|---|---|
| **A. MC-MED** (Stanford ED, 118,385 adult visits to monitored ED beds, 2020-09 → 2022-09; PhysioNet v1.0.1) | **External**: a different health system and period; never touched | `ED_dispo` ∈ {Discharge, Inpatient, Observation, **ICU**}; `Admit_service`; `Dispo_time` | ED diagnosis `Dx_ICD10` / `Dx_name` (assigned at the ED visit: an ED-scale `D_final`-type object) | Labs have **`Order_time` and `Result_time`**, so availability at T is exact. Triage vitals, `Arrival_time`, `Dispo_time` | Credentialed DUA needed (the author must sign). Dates are randomly shifted with **season kept**, so calendar era may not be recoverable. Monitored-bed visits only (a selected ED population). The four abdominal diagnoses may be **too few**: counts must be checked (counts only, no outcomes) before registration |
| **B. MIMIC-IV, untouched diagnoses** (ED-admitted patients whose primary diagnosis is **not** one of the four studied) | Internal: new observations, same institution and period | The identical T3 definition (`transfers` ICU after T) | `D_icd`, primary billing (the same object as before) | The same landmark pipeline (labs `charttime`) | Available now; no new DUA. Not external: same practice environment. The diagnosis set must be fixed by a **rule** (e.g. the top-K most frequent primary diagnosis groups among ED admissions, excluding the four), chosen from **counts only** |
| C. Future MIMIC-IV-ED releases covering 2020+ | Temporal, same institution | Same | Same | Same | Not available now |
| D. eICU-CRD | — | Not definable (patients are already in the ICU) | — | — | **Unsuitable** |
| E. ER-REASON | — | Disposition categories only; no intra-visit timestamps | — | Poor | **Unsuitable** (no timing; access pending) |

**Update 2026-09-30.** The author signed the MC-MED DUA; access is verified (HTTP 200). The data dictionary confirms:
- `MRN` (patient ID) and `CSN` (visit ID);
- `ED_dispo` and `Dispo_time` (the time of the disposition decision);
- the primary visit diagnosis `Dx_ICD10`;
- labs with `Order_time` and `Result_time`;
- triage vitals (temperature in **°C**).

Chronological split files are provided. Only `visits.csv` and the split files are being downloaded, for **counts only**. Counts that combine every admitted category are allowed; **ICU-specific counts are not examined before registration.**

**Recommendation:** **A (MC-MED)** as the independent confirmation, **B** as an internal replication that can run sooner. B must not be presented as external confirmation.

## Design (to be fixed at registration)

| Element | Specification |
|---|---|
| Population (A) | Adult ED visits with hospital admission (Inpatient, Observation, or ICU). Primary diagnosis group from `Dx_ICD10` mapped by a fixed rule (e.g. AHRQ CCSR body-system categories), fixed before outcome inspection. A four-abdominal-diagnosis subset only if the counts allow |
| Landmark | `T = Arrival_time + 3 h` (primary; ED decisions are earlier than in inpatient care). Cohort: `Dispo_time > T` (disposition not yet decided at T) |
| Endpoint | A: `ED_dispo = ICU` (vs Inpatient/Observation), decided after T. B: first ICU transfer after T (as in MIMIC T3) |
| X (patient state) | Demographics, triage vitals and acuity, labs with **`Result_time ≤ T`**, and missing indicators. The same cleaning rules. No free text |
| Common context (both arms, unpenalized) | Diagnosis group; arrival time-of-day block; weekend; season (A; calendar era if recoverable); diagnosis × period if a period exists |
| Model | The **same** partial-penalty specification as `600f368`: diagnosis + context unpenalized, L2 on X only, no D×X interactions (unless the author registers them as a separately stated hypothesis) |
| Regularization | Nested CV, C grid {1e-4 … 100} (11 values), minimum inner log loss, ties to the smaller C |
| Splits | Patient-grouped by `MRN` (verified in the data dictionary), stratified by Y × period. Temporal validation uses the dataset's own chronological split files (`split_chrono_{train,val,test}.csv`): calendar dates are shifted per patient (season kept), so the provided chronological split is the only valid time ordering |
| Primary metric | Held-out log loss: Δ and relative Δ vs LL(`Model_D`) |
| Secondary | AUROC, Brier score, calibration |
| **Substantive margin** | Success = 95% CI lower bound of Δ > 0 **and** relative Δ ≥ 10% (the same threshold as T1, for comparability). *A stricter alternative, e.g. requiring the lower bound of relative Δ ≥ 5%, is an author decision to be fixed at registration* |
| Uncertainty | 2,000-resample patient-level bootstrap; 3 outer repeats |
| Negative control | One prespecified, non-trivial control available in the new data (for example, an ED medication-class choice determined by diagnosis), fixed at registration and **not** selected after results |
| Temporal validity | No feature after T (`Result_time`, not `Order_time`). Leakage assertions must pass before modeling |
| No outcome switching | One primary endpoint. No substitution after inspection |

## Pre-registration checklist before any access to outcomes

1. The author signs the MC-MED DUA (A), or approves B.
2. Cohort counts (**counts only**) by diagnosis group, and landmark eligibility.
3. Fix the diagnosis mapping, landmark, context, and negative control.
4. Commit the binding preregistration.
5. Build the table and run the leakage checks.
6. Run once. Report every result.

## Permitted claim if successful

> "In an independent cohort, contemporaneous patient state contains substantial predictive information about observed escalation of care beyond diagnosis."

It would **not** show:
- optimal care;
- a causal effect;
- general diagnostic insufficiency;
- a representation-constraint (bottleneck) cost.

## Sources

- MC-MED: Kansal A, Chen E, Jin T, Rajpurkar P, Kim D. PhysioNet v1.0.1, https://physionet.org/content/mc-med/1.0.1/ (accessed 2026-09-30).
- Paper: *Scientific Data* 2025, https://www.nature.com/articles/s41597-025-05419-5.

## Counts-only step (2026-09-30; `results/t3_followup/mcmed_counts/counts.json`)

**No outcome was examined.** "Admitted" combines Inpatient, Observation, and ICU; ICU was never split out. `visits.csv` and the three chronological split files passed SHA-256 verification against the published `SHA256SUMS.txt`.

| Quantity | Count |
|---|---|
| ED visits / patients (all adults) | 118,385 / 70,545 |
| Admitted visits (combined) / patients | 48,139 / 30,815 |
| Hours from arrival to disposition decision (admitted) | median 4.2 (IQR 2.9–5.8; p95 9.0) |
| Admitted with the decision **after 3 h** (landmark-eligible) | **35,127** |
| Admitted with the decision after 6 h | 11,090 |
| Eligible (3 h) by chronological split: train / val / test / not in a split file | 23,719 / 3,386 / 3,625 / 4,397 |
| Eligible (3 h), four abdominal diagnoses: appendicitis / cholecystitis / diverticulitis / pancreatitis | 343 / 299 / 179 / 217 |
| Largest ICD-10 chapters among eligible visits | R (symptoms) 10,596; K 4,470; I 3,383; S 2,118; N 1,997 |

**Consequences for the design (proposed; the author decides at registration):**
1. **Population:** all admitted adult ED visits with a disposition decision after the 3 h landmark (n ≈ 35,000). The four-abdominal-diagnosis subset (n ≈ 1,000) is too small for an escalation endpoint. At most it is a descriptive stratum.
2. **Diagnosis representation:** the ED primary `Dx_ICD10`, grouped by a **count-based rule fixed now, without outcomes**. Each ICD-10 3-character category with ≥ 200 eligible visits is its own level; the rest are pooled within their ICD-10 chapter. Symptom codes (chapter R) are kept as diagnosis levels, because they *are* the ED label assigned.
3. **Landmark 3 h**, with the cohort restricted to `Dispo_time > T`. A 6 h landmark (n ≈ 11,000) is an optional sensitivity analysis.
4. **Temporal validation:** use the dataset's chronological splits (train+val → test). Visits not in a split file are excluded from the temporal analysis only.
5. **Endpoint:** `ED_dispo = ICU` vs the other admitted categories. It is ED-level escalation, which differs from the MIMIC T3 (ICU transfer after the landmark during the stay). The difference must be stated; it is a T3-*like* confirmation, not a replication of the identical endpoint.
