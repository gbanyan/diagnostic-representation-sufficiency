# Main experiment preregistration — confirmatory target-sufficiency analysis

**Status: APPROVED by the author on 2026-09-30.** This commit is the binding version; its hash is recorded in [decision_log.md](decision_log.md). Nothing had been run under this specification before approval. Any later change is a logged deviation.

**Scope.** This is the confirmatory **target-sufficiency** analysis: does contemporaneous patient state carry information about an observed clinical action beyond diagnosis? It is **not** the diagnostic-bottleneck experiment, which needs representation-constrained versus direct planners with matched capacity and remains unauthorized.

**Data-reuse disclosure (read first).** Every candidate cohort below was already analyzed in the preflight. Preflight point estimates for T1 and T3, including a 2008–2016 → 2017–2019 temporal split for T1, are in [model_selection_preflight.md](model_selection_preflight.md) and [expanded_cohort_preflight.md](expanded_cohort_preflight.md). No untouched MIMIC-IV data exist for these endpoints.
- This preregistration therefore fixes the **analysis specification** before the confirmatory run. It does **not** provide a blind holdout.
- Reported results must say so.
- External confirmation (another dataset with an equivalent T1) is not currently available: eICU has no T1 analogue, and ER-REASON is not accessible.

---

## A. Research question

Among adult ED patients with one of four acute abdominal diagnoses, does contemporaneous patient state available 6 h after ED arrival (demographics, triage vitals, first labs) add held-out predictive information about the **observed** next major management action, beyond the diagnosis and common calendar/operational context?

Formally, it tests whether `I(Y ; X | D, C) > 0`, and whether the gain is non-trivial, estimated by the held-out log-loss difference between `Model_D` (D + C) and `Model_DX` (D + C + X).

## B. Primary endpoint: T1

**T1 = the pathology's definitive procedure performed after the landmark T** (operative vs non-operative management).

| Diagnosis | Procedure family (pinned upstream code lists, FW `e1b4a522`) |
|---|---|
| Appendicitis | Appendectomy |
| Cholecystitis | Cholecystectomy |
| Diverticulitis | Colectomy or drainage |
| Pancreatitis | ERCP |

**Evidence:** an ICD procedure code (`procedures_icd`) **or** a procedure named in the discharge "Major Surgical or Invasive Procedure" section (pinned upstream extractor). The section text defines the target only and is never a feature.

**Timing:** GREEN / YELLOW / RED as in section G. The procedure must be ordered after T.

**Semantics:** observed clinician behavior, **not** optimal care.

## C. Secondary confirmatory endpoint: T3

**T3 = first ICU transfer after T.**
- **Definition:** a `transfers.careunit` matching an intensive-care unit, with `intime ≥ T`. The cohort excludes patients already in an ICU before T.
- **Semantics:** **observed escalation of care / observed ICU transfer**. It reflects a mixture of deterioration, clinician judgment, escalation practice, and bed/workflow constraints.
- It is **never** to be described as optimal disposition, best management, or causal benefit.

## D. Negative controls (interpretive, not part of the success criterion)

| ID | Definition (landmark T = 6 h) | Expected | Note |
|---|---|---|---|
| M5 | Among admissions with a systemic antibiotic order placed in (T, T+24 h]: whether an anaerobic-coverage order (metronidazole, piperacillin-tazobactam, carbapenem, ampicillin-sulbactam) is placed in that window | Δ ≈ 0 | Non-trivial; non-event counts 37–93 per diagnosis |
| T5 | Organ operated (appendix / gallbladder / colon), among operated admissions with exactly one organ family | Δ ≈ 0 | Near-deterministic given D; multinomial |
| M3 | Enoxaparin vs subcutaneous heparin, among VTE-prophylaxis orders in (T, T+48 h] | Δ ≈ 0 | Simple check; **58 events total, < 10 in two diagnoses: low power** |

No further negative controls will be added.

## E. Cohort

**Primary cohort (approved):** the **expanded MIMIC-IV cohort with the CDM-aligned T1 definition** (`mimic_iv_expanded_dxproc_landmark_table`; [expanded_cohort_preflight.md](expanded_cohort_preflight.md)).

- **Inclusion:**
  - MIMIC-IV 3.1 admissions whose **primary billing diagnosis** (`diagnoses_icd.seq_num = 1`) title matches exactly one of "acute appendicitis", "acute cholecystitis", "diverticulitis", "acute pancreatitis";
  - a linked MIMIC-IV-ED stay;
  - age ≥ 18.
- **Diagnosis object:** `D_icd` (a `D_final`-type discharge object; **never** `D_t`).
- **Landmark cohort (6 h):**
  - alive and in hospital at T;
  - no PACU transfer before T.
- **T1 cohort, additionally:**
  - no target-procedure ICD date before T's calendar date;
  - timing class per section G.
- **T3 cohort, additionally:** no ICU transfer before T.

**Counts (6 h)**, from `results/phase0/prereg/counts_mimic_iv_expanded_dxproc_landmark_table_L6.json`. Cells show events / non-events.

| Analysis | n | Events | Appendicitis | Cholecystitis | Diverticulitis | Pancreatitis |
|---|---|---|---|---|---|---|
| T1 primary (GREEN only) | 4,990 | 1,833 | 812 / 395 | 595 / 336 | 199 / 866 | 227 / 1,560 |
| T1 sensitivity (GREEN + YELLOW) | 5,332 | 2,175 | 1,021 / 395 | 683 / 336 | 224 / 866 | 247 / 1,560 |
| T3 | 5,412 | 276 | 15 / 1,495 | 60 / 955 | 57 / 1,028 | 144 / 1,658 |
| M5 | 2,638 | 2,425 | 732 / 42 | 635 / 41 | 868 / 37 | 190 / 93 |
| M3 | 3,881 | 58 | < 10 / 1,240 | < 10 / 754 | 15 / 786 | 29 / 1,043 |
| T5 | 1,323 | — | appendix 732, colon 12 | gallbladder 385 | colon 133 | gallbladder 55 |

**Era distribution (T1 primary):** 2008–10 1,153; 2011–13 1,375; 2014–16 1,365; 2017–19 1,097. No 2020–22 admissions are present.

**Alternative:** the MIMIC-CDM cohort (T1 GREEN-only n = 1,908, 1,037 events), which adds the X2 imaging flags. Its landmark table predates the era column and would need a rebuild. It is proposed here only as a **sensitivity analysis** (feature-richness), not as the primary cohort.

## F. Exact temporal rules

| Element | Rule |
|---|---|
| Anchor `t0` | Earliest `edstays.intime` linked to the admission |
| Landmark | `T = t0 + 6 h` (primary); `t0 + 3 h` (sensitivity) |
| Demographics | Age at `t0` (`anchor_age` + year offset), sex: static |
| Prior admissions | Count of the patient's admissions with `admittime < t0` |
| Triage | The anchor ED stay's triage record (recorded at triage, ≈ `t0`) |
| Labs | First value per pre-specified lab with `charttime ∈ [t0 − 1 h, T]`. Rows with another admission's `hadm_id` are excluded; rows without `hadm_id` are attributed by patient and window |
| Outcome timing | T1 per section G. T3: ICU `intime ≥ T` |
| Leakage assertion | No feature timestamp after T; no positive target before T. `leakage_checks` must pass before modeling |

## G. Procedure-timing policy (T1)

Classes are per [procedure_timing_audit.md](procedure_timing_audit.md). Within-day order is never inferred from a date.

- **GREEN:** the procedure date is after T's date, **or** a PACU stay began after T (none before), **or** the patient was still in the ED at T, with no post-operative evidence before T. Non-operated admissions are GREEN by definition.
- **YELLOW:** no GREEN criterion and no post-op evidence before T, but a consistent partial signal after T (post-op orders only after T, a surgical service, or non-specific preparation).
- **RED:** post-op evidence before T, or no evidence beyond a same-day date or discharge text.

| Analysis | Cases | n | Positives |
|---|---|---|---|
| **Primary** | GREEN only | 4,990 | 1,833 |
| **Sensitivity 1** | GREEN + all YELLOW (RED excluded) | 5,332 | 2,175 |

- **RED** (121 positives) is always excluded.
- **No narrower YELLOW subset is proposed.** No criterion inside YELLOW has verified timestamp semantics that would make it defensible (for example, post-op order latency after the operation is unverified).
- **Attrition from timing:** 5,453 → 5,332 (exclude RED) → 4,990 (GREEN only). Removal is selective for positives, so GREEN-only lowers the event rate. Both cohorts are reported.

## H. `Model_D` (diagnosis + common context)

For binary Y:

```
logit P(Y = 1) = α + Σ_d β_d·1[D = d] + Σ_k γ_k·C_k
```

- **D:** one-hot over 4 diagnoses, with the reference absorbed into α.
- **C:** the common context (section N).
- **Penalty:** none; every coefficient is unpenalized (a fixed numerical-stability ridge ε = 1e-4 is applied identically to unpenalized coefficients in both models).
- **Tuning:** none, because `Model_D` has no penalized coefficient.

For T5 (3 classes), the same form is multinomial.

## I. `Model_DX` (diagnosis + common context + patient state)

```
logit P(Y = 1) = α + Σ_d β_d·1[D = d] + Σ_k γ_k·C_k + Σ_j θ_j·X_j
```

- **X** is the patient-state feature set (**X1** = X0 + labs):
  - age, sex, prior admissions (log1p), ambulance arrival;
  - triage temperature, heart rate, respiratory rate, SpO₂, SBP, DBP, pain, acuity;
  - 20 first labs before T (WBC, neutrophils %, Hb, platelets, CRP, lactate, lipase, total bilirubin, ALT, AST, ALP, creatinine, BUN, glucose, Na, K, bicarbonate, albumin, INR, calcium), with log1p for the skewed labs;
  - a missing indicator for every X feature.
- **No D×X interactions** (none are preregistered).
- **The only difference from `Model_D` is the addition of X.**

## J. Penalized vs unpenalized coefficients

| Coefficient block | `Model_D` | `Model_DX` |
|---|---|---|
| Intercept α | Unpenalized | Unpenalized |
| Diagnosis β | Unpenalized | Unpenalized |
| Common context γ (section N) | Unpenalized | Unpenalized |
| Patient state θ (X and its missing indicators) | — | **L2, strength 1/C** |

**Implementation:** exact partial penalization by direct minimization of the penalized negative log-likelihood (L-BFGS; the penalty mask applies to θ only). It will be validated **before any real-data run** by unit tests on synthetic data:
1. fully penalized → matches scikit-learn;
2. C → ∞ → matches the unpenalized maximum likelihood;
3. θ → 0 as C → 0, recovering `Model_D`.

This replaces the ×100 column-scaling approximation used in the Q19 preflight.

## K. C grid

`C ∈ {1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1, 3, 10, 100}` (11 values). It applies to θ only and is identical for every endpoint and control.

## L. Nested cross-validation

- **Outer:** 5-fold, **repeated 3 times** (seeds 20260929, 20260930, 20260931). Out-of-fold predictions are made for every patient in each repeat.
- **Inner:** 4-fold on each outer-training set (seed = outer seed + fold index). C is selected by the **lowest mean inner held-out log loss**, with **ties going to the smaller C**. The model is then refit on the full outer-training set with the chosen C and evaluated once on the outer test fold.
- **Identical folds** for `Model_D` and `Model_DX` in every repeat. `Model_D` has no inner selection step.
- **Preprocessing** (median imputation, missing indicators, log1p, standardization, clipping at ±5 SD) is fit on training data at each level only.

## M. Patient-level split rules

- `StratifiedGroupKFold` grouped by `subject_id`, so all admissions of a patient share a fold, at both levels.
- **Stratification label = Y × era** (T1 and T3: 2 × 4 = 8 strata; T5: organ × era). This keeps calendar-era balance across folds.

## N. Common context, including calendar era

The common context C is supplied identically to both models, is unpenalized, and is **not** counted as incremental patient-state information.

| Variable | Definition | Proposed for |
|---|---|---|
| Era | `anchor_year_group` one-hot (2008–10, 2011–13, 2014–16, 2017–19; reference 2008–10) | All endpoints (author requirement) |
| **Diagnosis × era** | Saturated diagnosis × era cells: 3 × 3 = 9 interaction indicators on top of the diagnosis and era main effects (16 cells in total), unpenalized | **All endpoints (approved)** |
| Arrival time of day | `t0` hour block: 00–08, 08–16, 16–24 (one-hot; reference 08–16) | All endpoints (approved) |
| Weekend arrival | `t0` on Saturday/Sunday | All endpoints (approved) |

**Why diagnosis × era is recommended.** Drift is diagnosis-specific: GREEN-only T1 rates by era run 72% → 57% for appendicitis, 11% → 27% for diverticulitis, and 5% → 15–20% for pancreatitis. Era main effects alone would leave diagnosis-specific drift available for X to absorb, which could attribute practice change to patient state. The interaction is context × diagnosis, not D × X.

**Caveat:** `anchor_year_group` is a patient-level shifted 3-year window, so it approximates calendar time.

## O. Metrics

- **Primary:** held-out log loss (cross-entropy, bits) of `Model_D` and `Model_DX`.
  - **Δ = LL(`Model_D`) − LL(`Model_DX`)**, overall.
  - Relative Δ = Δ / LL(`Model_D`); LL(`Model_D`) estimates `H(Y | D, C)`.
- **Secondary:** AUROC (overall, and within each diagnosis).
- **Also reported:**
  - Brier score;
  - calibration intercept, slope, and ECE (10 bins) for both models;
  - the selected-C distribution.
- **AUROC / log-loss disagreement,** if present after tuning, is reported and interpreted, not resolved by choosing a metric.

## P. Missing data

- X missing values: median imputation within training folds, plus a missing indicator per feature. The indicators belong to X (penalized). Missingness at T is information available at T.
- C has no missing values: era and arrival time are always defined. An admission missing `anchor_year_group` is excluded and counted.
- No imputation uses Y or any post-T information.

## Q. Physiologic cleaning

As in [data_cleaning_rules.md](data_cleaning_rules.md), unchanged:
- **Triage bounds** (out-of-bounds values set to missing): temperature 90–110 °F, HR 20–250, RR 4–60, SpO₂ 50–100, SBP 40–300, DBP 20–200, pain 0–10, acuity 1–5.
- **log1p** for `prior_admissions` and the listed skewed labs.
- **Clipping** of standardized X at ±5 SD.
- **Labs** are not bounded; no impossible values were found.

## R. Multiplicity and hierarchical interpretation

1. **T1 (primary)** is tested first. It alone determines whether the primary positive-target hypothesis is supported.
2. **T3 (secondary confirmatory)** is interpreted confirmatorily **only if T1 succeeds** (fixed-sequence gatekeeping, α = 0.05 each). If T1 fails, T3 is reported as exploratory and **cannot rescue** T1.
3. **Negative controls, sensitivity analyses, AUROC, and within-diagnosis results** are descriptive and interpretive. They do not enter the success criterion.

## S. Uncertainty

- **Primary interval:** a 2,000-resample **patient-level paired bootstrap** of the repeat-1 out-of-fold predictions, percentile 95% CI for Δ (and for the AUROC difference).
- **Also:** mean ± SD of Δ across the 3 outer repeats.

## T. Success, failure, and stopping criteria

**T1 success** requires both:
- (i) the 95% CI lower bound of Δ > 0;
- (ii) Δ ≥ **10% of LL(`Model_D`)**. This is the preflight framework's threshold, re-expressed against `H(Y | D, C)`.

**T3 success:** the same criteria, evaluated only if T1 succeeds.

**Stop, or report as not supported, if:**
- `leakage_checks` fails (**stop before modeling**);
- the partial-penalty implementation fails its validation tests (**stop**);
- any diagnosis has < 50 events or < 50 non-events in the T1 primary cohort (report; the overall test still runs). Currently all four have ≥ 199.
- T1 criterion (i) or (ii) fails: **the primary hypothesis is not supported.** No re-specification follows.

**Flag, without changing the conclusion:**
- Δ differs by > 50% between the GREEN-only and GREEN+YELLOW cohorts (timing sensitivity);
- the `Model_D` calibration slope falls outside [0.8, 1.25].

**Sensitivity analyses** (descriptive; pre-specified here):
1. GREEN + YELLOW (section G).
2. Landmark 3 h.
3. Common context **without** diagnosis × era (era main effects only).
4. **Temporal holdout:**
   - train 2008–2016, test 2017–2019 (1,097 GREEN-only T1 admissions in the test era);
   - era and diagnosis × era terms are omitted (the test era is not estimable); the diagnosis and operational context are kept;
   - Δ, AUROC, and calibration are reported raw, and also after **intercept-only recalibration applied identically to both models** (each model's logit gets an additive offset estimated on a patient-grouped random 25% of the test era; both are evaluated on the other 75%; seed 20260929).
   - **Disclosure:** the preflight already inspected this split for T1 (Δ = 5.8% of `H(Y|D)`, CI including 0; both models miscalibrated).
5. MIMIC-CDM cohort with X2 (imaging flags), after the table rebuild.

## U. Claims explicitly NOT permitted

The analysis can, at most, support:

> "Contemporaneous patient-state information contains predictive information about an observed clinical action beyond diagnosis (and common calendar/operational context)."

It does **not** support:
- that a richer model provides better care;
- that the observed treatment or escalation was optimal;
- that diagnosis is generally insufficient (the result is target-specific);
- that foundation models are superior;
- any causal effect of patient state, or of any treatment;
- that the recovered variation is clinically meaningful (**Q15 remains DEFERRED — AUTHOR DECISION PENDING**);
- a representation-constraint (bottleneck) cost. That needs the later bottleneck experiment, which separates representation constraint from predictive capacity;
- temporal transportability, unless the temporal-holdout sensitivity analysis supports it.

---

## Approved decisions (2026-09-30)

1. **Primary cohort:** expanded MIMIC-IV (`D_icd`, X1). MIMIC-CDM with X2 is sensitivity analysis 5.
2. **Diagnosis × era** is in the common context for all endpoints; "era main effects only" is sensitivity analysis 3.
3. **Operational context** (time of day, weekend) is included for all endpoints.
4. **YELLOW policy:** GREEN only for the primary analysis; GREEN + YELLOW as sensitivity analysis 1; no narrower YELLOW subset.
5. **No blind holdout exists.** The data-reuse disclosure at the top must accompany every reported result.

## Execution order

1. Implement the partial-penalty model and pass its three validation tests (section J) on synthetic data.
2. Rebuild derived tables, with no modeling:
   - medication companions for the primary table;
   - the MIMIC-CDM table with the era column (for sensitivity analysis 5).
3. Run `leakage_checks`. It must pass.
4. Primary analysis (T1), then T3, negative controls, and sensitivity analyses. All results are reported, including failures.
