# MC-MED external confirmatory study: final report

**Study:** does compressing the 3-hour ED patient state into a disease-label representation discard information that predicts subsequent observed escalation of care?

**Protocol:**
- preregistration tag `mcmed-confirmatory-prereg-v1` (commit `c043529`);
- [amendment 1](../docs/amendments/2026-10-01-newton-solver.md) (solver, made before the test was opened);
- primary result tag `mcmed-confirmatory-primary-result` (commit `6c9834e`).

**Primary result: SUPPORTED.**

Terminology throughout: **D_hat_3h is an experimentally generated disease-label representation** (a cross-fitted CCSR body-system posterior estimated from information available by 3 h). It is **not** the clinician's working diagnosis.

## A. Cohort construction

MC-MED v1.0.1 (Stanford ED 2020–2022, PhysioNet; every file SHA-256 verified).

**Cohort:** adult ED visits admitted to hospital whose disposition was not yet decided at T = arrival + 3 h.
- **Decision time** = min(`Dispo_time`, first Admission/Transfer order).
- **Excluded:** visits with an ICU or critical-care consult at or before T (landmark validity), and visits without a CCSR-mappable visit diagnosis.

## B. Attrition

| Step | Visits | Patients | ICU | Excluded at this step |
|---|---|---|---|---|
| all_visits | 118,385 | 70,545 | 2766 (2.3%) | — |
| admitted (Inpatient/Observation/ICU) | [redacted] | 30,815 | 2766 (5.7%) | — |
| valid Arrival_time and Dispo_time | 48,138 | 30,815 | 2766 (5.7%) | 1 (ICU 0.0%) |
| age >= 18 | 48,138 | 30,815 | 2766 (5.7%) | — |
| Dispo_time > T | 35,127 | 23,964 | 1467 (4.2%) | 13,011 (ICU 10.0%) |
| decision_time = min(Dispo_time, first ADT order) > T | 34,269 | 23,480 | 1408 (4.1%) | 858 (ICU 6.9%) |
| no ICU / critical-care consult at or before T | 34,039 | 23,350 | 1267 (3.7%) | 230 (ICU 61.3%) |
| primary CCSR mapping available (unmapped excluded) | 32,404 | 22,558 | 1109 (3.4%) | 1,635 (ICU 9.7%) |

**Selection effects to keep in mind:**
- **The landmark removes rapidly escalated patients.** Visits decided within 3 h have ICU 10.0%.
- **Early-consult visits are a near-settled subgroup** (ICU 61.3%).
- **Unmapped diagnoses.** 180 visits have no diagnosis, and 1,455 have a code absent from CCSR v2024.1. This group has ICU 9.7%.

**The estimand is conditional on all of these.**

## C. Outcome prevalence

- **Final cohort:** 1,109 / 32,404 (3.4%).
- **Development:** 897 / 25,834 (3.5%), 18,023 patients.
- **Locked test:** 212 / 6,570 (3.2%), 4,535 patients. Deterministic MRN-hash split; no patient overlap.

## D. CCSR mapping

- **Mapping:** visit `Dx_ICD10` → AHRQ DXCCSR v2024.1, "Default CCSR CATEGORY OP" → first 3 letters (body system). File SHA-256 `04b25ceb6d557b999a92edc647ca9c61d54720a769dd951430135168ecacf863`.
- **Coverage:** 32,404 / 34,039 (95.2%) of otherwise eligible visits.
- **Rare-class rule:** body systems with < 50 visits → OTHER (MAL, PNL).
- **Final 20 classes:** SYM 8,042, CIR 4,627, DIG 4,342, INJ 2,488, GEN 1,941, RSP 1,316, MUS 1,295, NEO 1,239, END 1,195, INF 1,082, MBD 990, NVS 978, SKN 762, XXX 606, BLD 586, FAC 474, EYE 274, PRG 69, EAR 63, OTHER 35.
- **XXX** is CCSR's own "Unacceptable DX1" category (kept as audited).
- **No ICU information by class** was computed at any point.

## E. Diagnosis encoder quality (development, out-of-fold)

| Encoder | Classes | OOF log loss vs prior (nats) | Relative reduction | Top-1 accuracy (majority share) | Macro-F1 | C | Adequate |
|---|---|---|---|---|---|---|---|
| CCSR body system (primary) | 20 | 1.731 vs 2.463 | 29.7% | 0.448 (0.247) | 0.301 | 0.003 | yes |
| ICD-10 chapter (S2) | 23 | 1.758 vs 2.458 | 28.5% | 0.448 (0.312) | 0.245 | 0.003 | yes |
| CCSR, chronological (S4) | 20 | 1.729 vs 2.465 | 29.8% | 0.449 (0.245) | 0.295 | 0.003 | yes |

All fits converged. Details are in [mcmed_diagnosis_encoder_report.md](mcmed_diagnosis_encoder_report.md).

The encoder carries substantial diagnostic information but is an imperfect label estimator at 3 h. Rare or heterogeneous classes are rarely top-1.

## F. D_hat construction

**Development D_hat:**
- 5-fold patient-grouped cross-fitting (inner 4-fold CV for C, on diagnosis log loss only);
- every visit's D_hat comes from an encoder that never saw that patient.

**Test D_hat:** produced once by the encoder fit on all development patients.

**Downstream parameterization:**
- soft posterior with K − 1 = 19 probability columns;
- reference class SYM, the largest development class.

## G. Model D

Intercept + 19 soft-D_hat columns + season (3), all unpenalized (ε = 1e-4), fit by exact Newton (amendment 1).

## H. Model D+X

Model D + X_3h, with 445 raw columns (605 after missing indicators):
- demographics and arrival mode;
- triage vitals and ESI;
- chief-complaint tokens (89);
- prior PMH (175 CCS indicators + count);
- labs resulted by T (84 components);
- pre-T monitor/chart numerics (11 measures × 7 summaries).

**Penalty:** L2 on X only. **C = 0.003**, chosen by 4-fold development CV.

**Structure:** no interactions; no class weighting.

**Convergence:** every fit converged. The penalty-zero property was verified: as C → 0, Model D+X converges to Model D linearly in C.

## I–L. Primary result (locked test, one evaluation)

| | Value | 95% CI (patient-cluster bootstrap, 2,000 replicates) |
|---|---|---|
| L_D | 0.1260 nats | |
| L_DX | 0.1038 nats | |
| **ΔL** | **0.0221 nats** | 0.0167 – 0.0276 |
| **Δbits** | **0.0319 bits** | 0.0241 – 0.0399 |
| **RelativeGain** | **17.6%** | 13.7% – 21.2% |

**Criterion:**
- CI lower bound of ΔL > 0 (0.0167): met.
- RelativeGain ≥ 10% (17.6%): met.

**→ SUPPORTED.** Frozen in [mcmed_primary_frozen.md](mcmed_primary_frozen.md).

## M. Secondary: discrimination and calibration (locked test)

| | Model D | Model D+X | Difference (95% CI) |
|---|---|---|---|
| AUROC | 0.787 | 0.870 | +0.083 (+0.059 to +0.106) |
| AUPRC | 0.117 | 0.336 | +0.218 (+0.156 to +0.277) |
| Brier | 0.0300 | 0.0256 | 0.0043 lower (0.0030–0.0058) |
| Calibration-in-the-large / slope | -0.113 / 1.00 | -0.056 / 1.12 | |

Both models over-predict slightly in the test set (prevalence 3.2% vs 3.5% in development).

## N. Sensitivities (run after the primary freeze; no confirmatory role)

| Analysis | Test n / ICU | D columns | C | L_D | L_DX | ΔL nats (95% CI) | Δbits | RelativeGain (95% CI) | AUROC D → D+X |
|---|---|---|---|---|---|---|---|---|---|
| **Primary** (soft CCSR) | 6,570 / 212 | 19 | 0.003 | 0.1260 | 0.1038 | 0.0221 (0.0167–0.0276) | 0.0319 | **17.6%** (13.7%–21.2%) | 0.787 → 0.870 |
| S1 hard top-1 CCSR | 6,570 / 212 | 17 | 0.003 | 0.1325 | 0.1035 | 0.0290 (0.0226–0.0358) | 0.0418 | **21.9%** (17.8%–25.8%) | 0.703 → 0.873 |
| S2 soft ICD-10 chapter | 6,570 / 212 | 22 | 0.003 | 0.1233 | 0.1038 | 0.0194 (0.0145–0.0245) | 0.0280 | **15.8%** (12.1%–19.3%) | 0.807 → 0.870 |
| S3 primary + race/ethnicity | 6,570 / 212 | 19 | 0.003 | 0.1260 | 0.1041 | 0.0218 (0.0164–0.0273) | 0.0315 | **17.3%** (13.5%–21.1%) | 0.787 → 0.868 |
| S4 chronological split | 3,459 / 109 | 19 | 0.003 | 0.1256 | 0.1058 | 0.0198 (0.0127–0.0270) | 0.0285 | **15.7%** (10.5%–20.6%) | 0.780 → 0.857 |

**Notes:**
- **S1:** 2 of the 19 non-reference classes were never top-1 in development, so it has 17 columns. As expected, a hard label keeps less than the soft posterior, so X adds more.
- **S2:** a chapter-level soft representation gives a similar result.
- **S3:** race and ethnicity change essentially nothing.
- **S4:** trained on the earlier periods (train + val, 24,879 visits) and tested on the later period (3,459 visits, 109 ICU). The gain holds, with a wider interval.
- **Consistency:** every sensitivity has a CI for ΔL above 0 and a point RelativeGain above 10%. They support the primary conclusion's robustness but **do not add confirmatory weight**.

## O. Leakage audit

**Feature timing (asserted in code):**
- lab values only if `Result_time` ≤ T;
- numerics only if `Time` ≤ T;
- PMH only if noted before the arrival date.

**Never read by the feature code:** orders, consults, medications, oxygen flow, imaging text, `Admit_service`, payor, `Roomed_time`, visit counts, and all post-disposition fields. A feature-name guard backs this up.

**Outcome timing:**
- disposition decided by T (via `Dispo_time` or an earlier ADT order) → excluded;
- ICU or critical-care consult by T → excluded.

**Encoder and D_hat:**
- the diagnosis encoder saw diagnosis labels only;
- development D_hat is out-of-fold;
- test D_hat comes from a development-only encoder;
- no vocabulary or selection rule used the outcome.

**Residual risks:**
- **Patient-state proxies for care processes.** Some X features partly reflect processes, for example which labs were resulted by T and the density of monitor measurements (counts). They are measurements of the patient, but their presence reflects clinician ordering and monitoring intensity. This is disclosed and **not removed**; the preregistration fixed it.
- **Numerics coverage.** 12% of cohort visits have no numerics rows.

## P. Limitations

1. **D_hat is an estimated representation, and the gain is relative to this encoder.** Its accuracy is moderate: 45% top-1 over 20 classes, 30% log-loss reduction. A more accurate diagnosis estimator could leave less for X to add.
   - The result shows that **this** cross-fitted disease-label posterior, estimated from the same state, loses escalation-relevant information.
   - It does not show that any possible diagnosis representation would.
   - **No hindsight comparator was part of the preregistration.** A comparator using the true visit diagnosis was not run and is not reported.
2. **Context is season only.** De-identification randomized time of day, weekday, and year. Temporal drift is addressed only through S4.
3. **The population is conditional:** admitted, undecided at 3 h, no early critical-care consult, CCSR-mappable. Rapid escalations are excluded by design.
4. **Additive logistic family.** There are no D × X interactions. Results say nothing about other model classes.
5. **Observed disposition, not optimal care.** It is a single center, Stanford 2020–2022.
6. **Amendment 1 (solver)** was made after a development-CV estimate had been seen. It changes only the numerical optimizer of the same objective.
7. **Chief-complaint representation.** Simple multi-hot tokens (89) are used. A richer text representation was not pre-specified.
8. **The hard-top-1 (S1) and chapter (S2) encoders** are the same model family as the primary. No other encoder was tried.

## Q. Permitted interpretation

> At a 3-hour ED landmark, a cross-fitted disease-label representation did not retain all information in the contemporaneous patient state that was predictive of subsequent observed ED-to-ICU disposition.

> Contemporaneous patient-state information provided substantial incremental predictive information about observed escalation of care beyond a disease-label representation derived from the same state.

**Size of the effect:**
- held-out cross-entropy reduced by 0.032 bits per visit, 17.6% of Model D's cross-entropy;
- AUROC 0.787 → 0.870.

## R. Prohibited interpretation

- disease labels are useless, or diagnosis should be abandoned;
- the richer representation improves ICU care or decisions (nothing causal or interventional was tested);
- ICU disposition is optimal care;
- D_hat equals clinicians' diagnoses or reasoning;
- this replicates MIMIC T3 (the endpoints differ);
- the broader conceptual framework is confirmed.

## S. Relation to prior MIMIC findings

| Study | Target | Status | Relative gain |
|---|---|---|---|
| MIMIC T1 | Operative vs non-operative management (4 abdominal diagnoses, observed D) | Confirmatory, **NOT SUPPORTED** | 3.9% |
| MIMIC T3 | Later inpatient ICU transfer | Exploratory (hierarchy) | 16.3% |
| **MC-MED** | **Observed ED-to-ICU disposition** (D_hat from a 20-class ontology) | **Confirmatory, SUPPORTED** | **17.6%** |

**The combined picture remains target-dependent:**
- a categorical, protocolized decision (T1) was approximately diagnosis-sufficient under the prespecified threshold;
- escalation-of-care targets retained substantial information beyond diagnosis, first as the exploratory hypothesis from MIMIC T3 and now as an independent confirmation in a conceptually matched escalation-of-care target.

**The two escalation studies differ** in endpoint (inpatient transfer vs ED disposition), diagnosis representation (observed four-class D vs estimated 20-class posterior), and setting. They are **not** a replication pair.

## Deviations and amendments (complete list)

1. **Context = season only** (recorded before any outcome modeling). Time of day, weekday, and year are not recoverable.
2. **Encoder convergence rule** (tol 1e-4; a non-converged C is ineligible), fixed before the tag.
3. **Amendment 1:** exact Newton solver for the downstream models, made before the test was opened.
4. **Penalty-zero check.** At C = 1e-8 the strict log-loss tolerance was missed by the finite-C residual (2.1e-6 vs 1e-6), and the prediction tolerance in some sensitivities by rounding. Linear convergence to Model D as C → 0 verified the property (readiness report).
5. **Suppression fix after the freeze.** Decile calibration cells with 1–9 events were suppressed in committed files after the freeze. Values were unchanged.
6. **Operational incident.** A monitoring error briefly started a duplicate sensitivity job. It was killed within a minute, before any output. Nothing was duplicated, and the one-shot guards were never exercised.
