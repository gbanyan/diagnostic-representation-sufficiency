# MC-MED external confirmatory study: preregistration

**Status:** frozen at tag `mcmed-confirmatory-prereg-v1` (commit recorded in [decision_log.md](decision_log.md)). After the tag, this text is not edited in place. Changes go to `docs/amendments/`.

**Machine-readable choices:** [config/mcmed_confirmatory_v1.yaml](../config/mcmed_confirmatory_v1.yaml). **Code:** `src/mcmed/`.

**Authorization:** the author authorized the complete workflow on 2026-09-30, subject to the stop gates in section 27. It **supersedes** [t3_followup_design.md](t3_followup_design.md), which used the visit diagnosis directly as D at 3 h.

**Prior status (frozen, unchanged):**
- **MIMIC T1:** confirmatory, NOT SUPPORTED (relative gain 3.9% < 10%).
- **MIMIC T3:** exploratory only (16.3%). It generated the escalation-of-care hypothesis tested here.

## 1. Research question

At a 3-hour ED landmark, does a disease-label representation derived from the patient's current state retain the information in that state that predicts subsequent **observed ED-to-ICU disposition**? Or does the contemporaneous patient state contain substantial additional predictive information?

**This study does not test:**
- whether diagnosis is useless;
- whether clinicians reason with D_hat;
- whether ICU disposition is optimal care;
- whether richer state causes better outcomes;
- whether foundation models are superior;
- the conceptual framework as a whole.

## 2. Theoretical estimand

**Chains compared:** `X_3h → D_hat_3h → Y` versus `X_3h → (D_hat_3h, X_3h) → Y`.

With CE the held-out binary cross-entropy (natural log) on the locked test set:

```
ΔL           = CE(Y | context, D_hat_3h) − CE(Y | context, D_hat_3h, X_3h)
Δbits        = ΔL / ln 2
RelativeGain = ΔL / CE(Y | context, D_hat_3h)
```

The comparison measures information about observed escalation of care that is lost when the same state is compressed into the disease-label representation, within the prespecified model family (section 17–19).

**Wording.** D_hat_3h is **an experimentally generated disease-label representation**, i.e. a cross-fitted diagnostic-label representation estimated from information available by the 3-hour landmark. It is **never** called the clinician's working diagnosis, the actual 3-hour diagnosis, physician belief, or clinical ground truth at 3 hours.

## 3. Cohort

MC-MED v1.0.1 (Stanford ED, PhysioNet; all files SHA-256 verified). Inclusion, in order (counts in `results/mcmed/stageA_cohort.json`):

| Step | Visits | Patients | ICU |
|---|---|---|---|
| All visits | 118,385 | 70,545 | 2,766 |
| Admitted (`ED_dispo` ∈ Inpatient, Observation, ICU) | [redacted] | 30,815 | 2,766 (5.7%) |
| Valid `Arrival_time` and `Dispo_time` (1 excluded) | 48,138 | 30,815 | |
| Age ≥ 18 (0 excluded; the dataset is adult-only) | 48,138 | | |
| `Dispo_time` > T (13,011 excluded; ICU 10.0% among them) | 35,127 | 23,964 | 1,467 (4.2%) |
| Decision time > T (section 5; 858 excluded; ICU 6.9%) | 34,269 | 23,480 | 1,408 (4.1%) |
| No ICU / critical-care consult at or before T (section 6; 230 excluded; ICU 61.3%) | 34,039 | 23,350 | 1,267 (3.7%) |
| **Primary CCSR mapping available (section 8; 1,635 excluded; ICU 9.7%)** | **32,404** | **22,558** | **1,109 (3.4%)** |

- **Agreement with the audit.** These match the audit exactly (34,269 / 34,039 / 1,267).
- **Unmapped exclusion.** The visits removed because their diagnosis has no CCSR mapping (180 without `Dx_ICD10`; 1,455 with a code absent from CCSR v2024.1) have higher ICU prevalence. The attrition is reported, and it does not change the estimand's population definition beyond "CCSR-mappable visit diagnosis".

## 4. Landmark

T = `Arrival_time` + 3 h. Timestamps are shifted per patient, and within-patient order and intervals are preserved (README, "Timestamps and De-identification").

## 5. Decision-time exclusion

**Rule (unchanged from the audit):**
- decision_time = min(`visits.Dispo_time`, earliest `orders.Order_time` with `orders.Order_type` ∈ {Admission, Transfer});
- a visit is eligible only if decision_time > T.

**Why.** Admission/transfer orders precede `Dispo_time` in 15.4% of admitted visits. Visits whose disposition was already decided by T are excluded, because their outcome is known before the prediction landmark.

## 6. Early ICU / critical-care exclusion (landmark validity)

**Rule.** Visits are excluded when an order with `orders.Order_type` = Consult and `Procedure_name` containing "ICU" or "CRITICAL CARE" has `Order_time` ≤ T.

**Why.** Escalation is visibly under way in these visits (61.3% end in ICU disposition). They are excluded as a landmark-validity rule. Consults are never predictors.

## 7. Outcome

**Y = 1 if `ED_dispo` = ICU** (observed ED-to-ICU disposition after T). No class reweighting, resampling, or SMOTE.

**Relation to MIMIC T3.** This is **not** identical to MIMIC T3 (later inpatient ICU transfer). It is an **independent confirmation in a conceptually matched escalation-of-care target**. It is never optimal ICU disposition, best clinical management, or causal benefit.

## 8. CCSR taxonomy (frozen before any outcome modeling)

**Mapping:**
- visit `Dx_ICD10`, dots removed, upper-case;
- → AHRQ DXCCSR v2024.1, column "Default CCSR CATEGORY OP";
- → **body system = first three letters of the category**.

File `DXCCSR_v2024-1.csv`, SHA-256 `04b25ceb6d557b999a92edc647ca9c61d54720a769dd951430135168ecacf863`.

**Unmapped handling.** Unmapped visits are excluded (section 3). No outcome-informed "other" mapping is created.

**Rare-class rule (as audited).** Body systems with fewer than 50 visits in the final cohort become `OTHER`: MAL (congenital malformations) and PNL (perinatal conditions).

**Final classes: 20.**

| Class | Visits (%) |
|---|---|
| SYM | 8,042 (24.8) |
| CIR | 4,627 (14.3) |
| DIG | 4,342 (13.4) |
| INJ | 2,488 (7.7) |
| GEN | 1,941 (6.0) |
| RSP | 1,316 (4.1) |
| MUS | 1,295 (4.0) |
| NEO | 1,239 (3.8) |
| END | 1,195 (3.7) |
| INF | 1,082 (3.3) |
| MBD | 990 (3.1) |
| NVS | 978 (3.0) |
| SKN | 762 (2.4) |
| XXX | 606 (1.9) |
| BLD | 586 (1.8) |
| FAC | 474 (1.5) |
| EYE | 274 (0.8) |
| PRG | 69 (0.2) |
| EAR | 63 (0.2) |
| OTHER | 35 (0.1) |

- **XXX.** This is CCSR's own category "XXX111, Unacceptable DX1" (for example external-cause codes). It was part of the audited ontology and is kept as assigned, without regrouping.
- **Symptom diagnoses (SYM).** Kept as a class.
- **No outcome information was used.** No ICU information by class was computed or used.

**Sensitivity taxonomy (S2).** ICD-10 chapter (first character), with the same < 50 rule (P, Q, Y → OTHER), giving 23 classes on the same cohort.

## 9. D_hat definition

`p_hat(D = k | X_3h)`, k = 1…20, is the soft posterior of the diagnosis encoder (section 10), cross-fitted (section 11).

**In the downstream models:**
- **Parameterization.** K − 1 = 19 probability columns. The reference class is dropped: the **largest development class by diagnosis count** (expected SYM), chosen without the outcome.
- **Why K − 1.** The probabilities sum to 1, so with an intercept the reference-class parameterization avoids exact collinearity.
- **Sensitivity S1:** hard top-1 (one-hot of argmax, same reference). A class never predicted in development has no column.

## 10. Diagnosis encoder

**Model.** Multinomial logistic regression with L2 on all non-intercept coefficients (scikit-learn lbfgs; max_iter 10,000; tol 1e-4, the library default). A timing check before the tag showed that tol 1e-6 did not converge at large C.

**Convergence rule.** A C value with any non-converged fit in the relevant CV is not selectable. If no value is selectable, or the final encoder does not converge: STOP.

**Input:** X_3h only, with the same preprocessing as section 16 (fit on each training portion).

**Supervision:** the frozen visit-diagnosis class. The final/visit diagnosis is **never** an input.

**The encoder never receives:** the ICU outcome, the disposition, anything after T, `Admit_service`, or consults.

**Tuning.** C comes from the grid of section 20 and is chosen by **multiclass diagnosis log loss only** (ties → smaller C).

**Adequacy gate** (evaluated on development out-of-fold predictions before any ICU test comparison):
1. pooled OOF multiclass log loss is at least **10% lower** than the class-prior baseline (each fold's training prior);
2. every one of the 5 folds beats its prior baseline;
3. top-1 accuracy exceeds the majority-class share.

If the gate fails: **STOP**. No post-hoc encoder is substituted.

**Also reported:** macro-F1, class-wise recall, and top-label calibration error.

## 11. Cross-fitting

Development patients are split into 5 patient-grouped folds (`StratifiedGroupKFold`, stratified by diagnosis class, grouped by MRN, seed 20261001).

**Development D_hat.** For each fold f:
1. C_f is chosen by an inner 4-fold patient-grouped CV on the other four folds (seed 20261001 + 1 + f);
2. the encoder is fit on the other four folds;
3. fold f is predicted.

Concatenating the folds gives out-of-fold D_hat for every development visit. It comes from an encoder that never saw that patient's diagnosis.

**Locked-test D_hat.**
1. C\* = the grid value with the lowest mean held-out diagnosis loss across the same 5 development folds.
2. The encoder is fit on **all development patients** and predicts the test set **once**.
3. No test patient's diagnosis is ever used in training.

**Declared property.** The test D_hat comes from an encoder trained on 100% of development, while development D_hat came from encoders trained on 80% of it (standard stacking). Downstream tuning uses the development OOF D_hat.

## 12. Patient split

- **Test assignment:** a patient is in the **locked test** set if `int(sha256("mcmed-confirmatory-v1:diagnosis-bottleneck:2026-09-30:" + MRN)[:15 hex], 16) / 16^15 < 0.20`. All other patients are in **development**.
- **Generated once.** The split is generated once, never regenerated, and not chosen by prevalence or performance.
- **Where the manifest lives.** The manifest (MRN → set) is private, outside git. Its SHA-256 and aggregate counts are committed (`results/mcmed/stageC_split.json`).

## 13. Common context

Both models receive the identical, unpenalized **season** (meteorological DJF/MAM/JJA/SON of the shifted arrival date; reference DJF). The de-identification documents season as preserved.

**Deviation from the authorized context list.** The authorization listed time-of-day category, weekend, season, and calendar year/era. Three of these are **not recoverable** in MC-MED:

- **Time of day and weekday.** The arrival-hour and weekday distributions are uniform. Across 118,385 visits, the hourly counts range from 4,794 to 5,034 and the weekday counts from 16,697 to 17,027. Real ED arrivals are strongly diurnal and weekly, so the de-identifying shift randomized clock time and weekday. Only season is documented as preserved. Including these variables would add noise, not operational context.
- **Calendar year / era.** Dates are shifted per patient, so year is not recoverable. The dataset's chronological split labels visits by period, but 11% of visits (4,066 in this cohort) belong to no period. Membership also depends on the patient's future visits (patients spanning periods are dropped), so it would bring future information into context.

**Consequence.**
- The context is season only.
- Temporal drift cannot be adjusted within the primary analysis. It is examined by S4 (chronological split).
- This is a conservative implementation choice that does not change the estimand. It is recorded here before any outcome modeling.

## 14. X_3h feature set (GREEN only)

All selection rules below use **development visits only** and **never the outcome**. They are frozen before the locked test. Resulting lists are in `results/mcmed/stageA_features_build.json`.

| Group | Construction |
|---|---|
| Demographics | Age (perturbed 0–2 y by de-identification; ≥ 90 binned); sex (one-hot of development levels, missing explicit) |
| Arrival | Means of arrival (one-hot of development levels) |
| Triage | Temperature (°C → °F), HR, RR, SpO₂, SBP, DBP, ESI (1–5) |
| Chief complaint | Comma-separated triage complaint tokens (upper-case). Multi-hot of tokens in ≥ 50 development visits, plus "other token present" and "missing". No LLM, no outcome association. Token list kept private (SHA-256 committed) |
| Past medical history | PMH rows with `Noted_date` **before the arrival date** (date-level). Indicators for PMH CCS categories present in ≥ 1% of development visits, plus the count of distinct prior codes |
| Labs | First result per component with **`Result_time` ≤ T**. Components resulted by T in ≥ 5% of development visits. Censored values ("<0.01") take the limit value. Components with < 50% numeric first results also get an abnormal flag (`Component_abnormal`: Normal 0, abnormal/critical 1). Race-based calculations ("EGFR FOR AFRICAN AMERICAN") excluded |
| Numerics | Measures HR, RR, SpO₂, SBP, DBP, MAP, Temp, Pain, Perf, 1min_HRV, 5min_HRV (Monitor and Chart pooled), rows with **`Time` ≤ T**. Per measure: first, last, min, max, median, OLS slope per hour of elapsed time, and count. Included if observed by T in ≥ 25% of development visits |

**Numerics details:**
- **Slope:** undefined (missing) with fewer than two observations or no time spread.
- **Count:** 0 when not observed.
- **Observed / not-observed:** carried by the missing indicator of the value summaries.

## 15. Excluded from primary X

- race, ethnicity (sensitivity S3 only); marital status (not in MC-MED);
- `Payor_class`;
- `Admit_service`;
- ICU / critical-care consultation and **all orders** (clinician actions);
- oxygen flow (`LPM_O2`) and other treatment intensity; medications;
- `Roomed_time`;
- `Visit_no` / `Visits`;
- every post-disposition field (`ED_LOS`, `Hosp_LOS`, `DC_dispo`, `Departure_time`, next-visit fields);
- `Dx_*` (supervision target only);
- any lab, imaging, or numerics value after T;
- imaging impression text;
- same-day or later PMH;
- home medications.

## 16. Preprocessing and cleaning

The rules follow [data_cleaning_rules.md](data_cleaning_rules.md). They are fixed before the locked test.

**Bounds** (closed intervals; outside → missing):

| Measure | Bounds |
|---|---|
| HR | 20–250 |
| RR | 4–60 |
| SpO₂ | 50–100 |
| SBP | 40–300 |
| DBP | 20–200 |
| MAP | 25–250 |
| Temperature | 90–110 °F |
| Pain | 0–10 |
| Perfusion index | 0.01–20 |
| HRV | 0.01–2000 |
| ESI | 1–5 |

Monitor zeros (lead-off artifacts) fall outside the bounds.

**Order of operations:**
1. **log1p** is applied to non-negative continuous columns whose development skewness exceeds 2. It is determined once on development data, and the list is recorded.
2. Then, **within each training portion:**
   - median imputation with missing indicators;
   - standardization;
   - clipping to ±5 SD.
3. Categorical vocabularies come from development only.

Nothing uses Y.

## 17. Model D

`logit P(Y=1) = intercept + D block (19 columns) + season (3)`.

All coefficients are unpenalized, apart from a fixed numerical ridge ε = 1e-4 on non-intercept columns, identical in both models (the `600f368` implementation, `src/confirmatory/partial_logistic.py`).

## 18. Model D+X

`Model D + X_3h` (after section 16 preprocessing).

- There are no D × X interactions, polynomial terms, or nonlinear terms.
- **Same:** cohort, development/test sets, target, context, landmark, tuning budget.

## 19. Penalty rules

- **Unpenalized:** the intercept, the D block, and the context.
- **L2 with strength 1/C:** X only.

**Implementation.** Exact L-BFGS on the partial-penalty objective (`PartialLogistic`). The validation tests (tests/test_partial_logistic.py) cover:
- the fully penalized fit matches scikit-learn;
- C→∞ gives the MLE;
- C→0 gives Model D.

The development run also verifies on the real data that at C = 1e-8 the X coefficients are < 1e-4, the development log loss equals Model D's within 1e-5 nats, and predictions agree within 1e-3 (soft D_hat columns are near-collinear, so the optimizer may stop at slightly different points along flat directions).

## 20. C grid and tuning

**Grid:** {1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1, 3, 10, 100}, unchanged from `600f368`.

**Selection:**
- C for Model D+X is chosen by the lowest mean held-out log loss in a 4-fold patient-grouped CV on development (stratified by Y, seed 20261003); ties go to the smaller C.
- Model D has no tuning parameter.
- Both final models are refit on all development data.

**Convergence.** Non-convergence of any final model is a stop gate.

## 21. Primary metric

Held-out binary cross-entropy (log loss) on the locked test set: L_D, L_DX, ΔL (nats), Δbits, and RelativeGain.

**Secondary:**
- AUROC, AUPRC, Brier score;
- calibration intercept (calibration-in-the-large) and slope;
- decile calibration table.

The interpretation is based on log loss, not AUROC.

## 22. Success criterion (unchanged from `600f368`)

The primary hypothesis is **SUPPORTED** only if **both** hold:
1. the 95% CI lower bound of ΔL is > 0;
2. the point RelativeGain is ≥ 10%.

Otherwise it is **NOT SUPPORTED**.

Values of 8–9% are not success. AUROC does not substitute for the criterion.

## 23. Uncertainty

**Patient-cluster bootstrap** on the locked test set:
- 2,000 replicates, seed 20261004;
- MRNs resampled with replacement, with all their visits;
- percentile 95% CIs for ΔL, Δbits, RelativeGain, and the AUROC, AUPRC, and Brier differences.

## 24. Sensitivities

These run only after the primary result is committed and tagged (`mcmed-confirmatory-primary-result`). Each is a full development refit and a single locked-test evaluation.

| ID | Change |
|---|---|
| S1 | Hard top-1 CCSR D_hat instead of the soft posterior |
| S2 | ICD-10-chapter soft D_hat: a new encoder with identical cross-fitting |
| S3 | Primary X plus race and ethnicity (downstream X only; D_hat unchanged). MC-MED has no marital-status field |
| S4 | Temporal robustness, a full refit on the dataset's chronological split (see below) |

**S4 details:**
- **Training:** encoder cross-fitting and downstream tuning on visits in `split_chrono_train` ∪ `split_chrono_val`.
- **Evaluation:** once on `split_chrono_test` (the dataset guarantees later periods and no patient overlap).
- **Excluded:** visits in no period.
- **Feature vocabularies:** stay the frozen primary ones.

Sensitivities have no confirmatory role and cannot change the primary conclusion. No other sensitivities are added.

## 25. Permitted claims

**If SUPPORTED:**
> "At a 3-hour ED landmark, a cross-fitted disease-label representation did not retain all information in the contemporaneous patient state that was predictive of subsequent observed ED-to-ICU disposition."

**If NOT SUPPORTED:**
> "Under the prespecified MC-MED representation, cohort, and escalation-of-care target, the richer contemporaneous state did not provide a sufficiently large incremental gain beyond the diagnostic-label representation."

**Relation to MIMIC:**
- MIMIC T1 found a categorical/protocolized decision approximately diagnosis-sufficient under the threshold.
- MIMIC T3 generated the escalation hypothesis.
- MC-MED independently tests a conceptually matched escalation-of-care target with an explicit cross-fitted disease-label bottleneck.

## 26. Prohibited claims

- disease labels are useless, or diagnosis should be abandoned;
- ICU care improved, or the richer representation caused better decisions;
- ICU disposition is optimal care;
- D_hat is the clinician's diagnosis;
- the endpoint is identical to MIMIC T3, or this is a literal replication;
- the conceptual framework is proven;
- "trend", "nearly", "almost significant", "rescued", "promising confirmation".

**After the test is opened:** no model shopping of any kind (networks, foundation models, LLM embeddings, new features, interactions, thresholds, landmarks, endpoints).

## 27. Stopping conditions (before opening the locked test)

1. full numerics integrity fails;
2. cohort semantics differ materially from the audit;
3. disposition timing cannot be resolved;
4. the early-consult exclusion cannot be implemented reliably;
5. the CCSR mapping is not reproducible;
6. the encoder fails the adequacy gate (section 10);
7. cross-fitting cannot be made leakage-free;
8. protected-data rules would be violated;
9. Model D or Model D+X fails to converge;
10. an implementation choice would change the scientific meaning.

Ordinary implementation details are resolved conservatively and documented.

## Execution order

1. Stage A: numerics download and verification; cohort; features.
2. Stage C: split.
3. Tag.
4. Stage E: encoder (gate).
5. Stage F: downstream development (`results/mcmed_pretest_readiness.md`).
6. Stage G: one-shot test.
7. Stage H: `results/mcmed_primary_frozen.md`, tag `mcmed-confirmatory-primary-result`.
8. Stage I: S1–S4.
9. Stage J: `results/mcmed_final_report.md`.

**Environment:** gbminipc, Linux, Python 3.14.2, scikit-learn 1.9.1, numpy 2.5.3, scipy 1.18.1, OpenBLAS (scipy-openblas 0.3.34). One BLAS/OpenMP thread per process (`src.preflight`). The encoder runs 8 worker processes.

**Data protection:**
- Nothing patient-level (MRN, CSN, free text, split manifest, predictions) is committed.
- Committed outputs are aggregates, with counts < 10 suppressed.
- No credentialed data are sent to an LLM.

## Appendix: Stage A verification (completed before the tag)

**Numerics integrity.** `data/numerics.csv` is 2,758,767,634 bytes and 47,821,508 rows. Its SHA-256 `225509cec1822e7b89bb047837775c90cf40d1aa8136bd94eb85330782d66ab9` matches PhysioNet's `SHA256SUMS.txt`. All 101,893 CSNs in the file are contiguous.

**Numerics coverage:**
- 28,514 of 32,404 cohort visits (88.0%) have numerics rows at or before T.
- The rest have **no rows at all** for the visit in the released file, which the missing indicators carry.
- In development, HR/RR/SpO₂/BP are observed by T in 87.6% of visits, temperature 85.2%, pain 70.3%, perfusion index 71.4%, and HRV 59.4%. All 11 measures meet the ≥ 25% rule.

**Labs.** 31,127 visits (96.1%) have a lab result by T.

**X_3h.** 445 raw columns: demographics 7, triage 7, chief complaint 91, PMH 176, labs 87, numerics 77. Missing indicators are added in preprocessing.
- The log1p list, lab components, and PMH categories are in `results/mcmed/stageA_features_build.json`.
- The chief-complaint vocabulary (89 tokens) is private, SHA-256 `5b5a7946b058926531a47b1c7adb9cb25404e8f8f7aeabb287aa979a423d185c`.

**Leakage checks (asserted in code):**
- every lab value used has `Result_time` ≤ T;
- every numerics row used has `Time` ≤ T (elapsed ≤ 3 h);
- PMH `Noted_date` < arrival date;
- no feature is built from a forbidden field;
- orders, consults, medications, oxygen flow, imaging text, and post-decision fields are never read by the feature code.

**Split** (`results/mcmed/stageC_split.json`):

| Set | Visits | Patients | ICU |
|---|---|---|---|
| Development | 25,834 | 18,023 | 897 (3.5%) |
| Locked test | 6,570 | 4,535 | 212 (3.2%) |

There is no patient overlap. Manifest SHA-256 `90739be0ebaba21d5d568ce94b88d17af370e06b11375c0fdb7e1071fe47fd42`.
