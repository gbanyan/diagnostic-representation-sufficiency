# Expanded MIMIC-IV cohort and temporal validation

**Pre-registered 2026-09-29, before the cohort was built.**

## Why

MIMIC-CDM (2,400 admissions) was filtered on discharge-summary text and required abdominal imaging. The landmark features are all structured, so the same pipeline can run on **all** MIMIC-IV admissions with these four primary diagnoses. This adds power (T3; diverticulitis) and allows a temporal validation.

## Cohort definition

- **Source:** MIMIC-IV 3.1 `hosp/diagnoses_icd` with **`seq_num = 1`** (the primary billing diagnosis), joined to `d_icd_diagnoses.long_title`.
- **Pathology rule:** a case-insensitive substring match, the same as the upstream CDM `extract_hadm_ids`:
  - "acute appendicitis" → appendicitis;
  - "acute cholecystitis" → cholecystitis;
  - "diverticulitis" → diverticulitis;
  - "acute pancreatitis" → pancreatitis.

  Titles matching more than one pathology are excluded.
- **Other requirements:** a linked ED stay (anchor = ED arrival) and age ≥ 18.
- **Diagnosis object:** `D_icd`, the primary billing diagnosis. This is a **different definition** from CDM's primary discharge-summary diagnosis. Both are `D_final`-type (discharge) objects, never `D_t`. Overlap with CDM is reported.

## Features, targets, analysis

- **Features:** X0 and X1 as in the CDM table. **X2 is not built:** imaging flags would need section-parsed report text, which is deferred.
- **Targets:** T1 (ICD procedures only; there is no discharge-procedure text), T3, T4, T5, and M1–M6, with the same definitions.
- **T1 timing classes:** the same rules (POE, transfers, ED departure), and RED is excluded in the primary analysis.
- **Stage A and Stage B:** nested CV, the same specification.
- **Independent replication:** the same analyses **excluding admissions in the CDM cohort**.
- **Temporal validation** (a secondary analysis for T1, T3, M5, M6):
  - train on `anchor_year_group` ≤ 2014–2016;
  - test on 2017–2019 and 2020–2022;
  - C selected by inner CV on the training period only.

  `anchor_year_group` is a per-patient shifted period, so this approximates, rather than equals, calendar time.
- **Classification:** the same framework thresholds. A class that differs from the CDM result is reported as a discrepancy, not resolved in favour of either cohort.

---

## Deviation (2026-09-29, before any expanded-cohort Stage B result was inspected): T1 definition

**Finding (semantics check):** in the 1,494 admissions shared with MIMIC-CDM, every discordant T1 label is the same pattern. CDM found the procedure only in the discharge-summary procedure section, and MIMIC-IV `procedures_icd` has **no** code for it:
- appendicitis: 171 such cases vs 387 concordant positives (≈ 31% of operations missed);
- cholecystitis: 125 vs 196 (≈ 39% missed).

So an **ICD-only T1 mislabels roughly a third of operated patients as non-operated**. This violates G11, and it explains the lower expanded-cohort procedure rates (appendicitis 49% vs 84% in CDM). It is not a population difference.

**Change:** T1 in the expanded cohort uses the **same definition as MIMIC-CDM**: an ICD procedure code **or** a procedure named in the discharge "Major Surgical or Invasive Procedure" section. The section is extracted with the pinned upstream function `dataset.procedures.extract_procedure_from_discharge_summary` (FW `e1b4a522`).
- The section text defines the **target** only. It is never a feature.
- Text-only positives carry the `T1_text_only` flag and follow the same timing classes.
- **Data:** this needs MIMIC-IV-Note 2.2 `discharge` (1.14 GB; downloaded for this purpose).
- **The ICD-only expanded run is kept and labelled INVALID for T1.** T3, T4, T5, and M1–M6 do not depend on this definition.

---

## Results (2026-09-29): ICD-only expanded table, targets other than T1

Source: `results/phase0/sufficiency/mimic_iv_expanded/`.

**Cohort:** 5,548 admissions (appendicitis 1,552, cholecystitis 1,039, diverticulitis 1,108, pancreatitis 1,849).
- Leakage checks pass (6 h cohort 5,492).
- Overlap with CDM: 1,494 admissions (1,482 with the same label). 906 CDM admissions are not in the expanded cohort (no primary-code match, or no ED stay).
- `anchor_year_group` has no 2020–2022 admissions here, so the temporal test period is **2017–2019** (train ≤ 2014–2016).

Registered specification (shared penalty); X1; 6 h. Δ = Δ log loss in bits (share of `H(Y|D)`).

| Target | Full expanded cohort | Excluding CDM admissions (independent) | Temporal: train ≤ 2016, test 2017–2019 |
|---|---|---|---|
| T3 ICU | 0.047 (17.1%), CI 0.036–0.059; AUROC 0.635 → 0.829. Within-D AUROC 0.81 / 0.73 / 0.78 / 0.83; events 15 / 60 / 57 / 144 | 0.050 (17.1%), n 3,948 | 0.054 (19.6%), CI 0.029–0.080; AUROC 0.722 → 0.855; slope 1.11 |
| M6 insulin | 0.137 (26.8%), CI 0.117–0.157; AUROC 0.638 → 0.863 | 0.132 (24.7%) | 0.110 (21.5%), CI 0.079–0.141; slope 1.20 |
| M2 broad-spectrum | 0.042 (8.9%), CI 0.028–0.052 | — | — |
| M5 anaerobic (negative control) | −0.009 (−2.5%; the shared-penalty artifact, cf. Q19) | −0.010 (CI includes 0) | +0.001 (0.2%, CI includes 0) |
| T5 organ (negative control) | −0.084 (shared-penalty artifact) | — | — |
| T4 remaining LOS | R² 0.154 → 0.316 | — | — |

**Reading:**
- **T3 now meets both "meaningful" criteria.** Cholecystitis, diverticulitis, and pancreatitis each have ≥ 50 events, with within-D AUROC 0.73–0.83. It replicates in the CDM-independent subset and in the later period. Stage C is not assessed.
- **M6 and M5 replicate across all three analyses.** The positive / negative dissociation holds in a different population and a later period.
- **M2 stays below the 10% threshold.**
- **T1:** see the corrected-definition run (`mimic_iv_expanded_dxproc`).

## Results (2026-09-29): T1 with the corrected (CDM-aligned) definition

Source: `results/phase0/sufficiency/mimic_iv_expanded_dxproc/`.
- 5,247 of 5,548 admissions have a discharge summary.
- Leakage checks pass.

**The correction works.** T1 procedure rates recover:

| Diagnosis | Corrected | ICD-only | CDM |
|---|---|---|---|
| Appendicitis | 73.5% | 49% | 84% |
| Cholecystitis | 67.3% | 38% | 72% |
| Diverticulitis | 21.3% | 21% | 21% |
| Pancreatitis (ERCP) | 15.1% | 14% | 34% |

The pancreatitis difference from CDM remains. It plausibly reflects the different selection, and it is not interpreted clinically.

**Timing classes, 6 h:** 2,296 positives; GREEN 1,833, YELLOW 342, RED 121.

| T1 analysis (X1, 6 h, registered shared-penalty spec) | n | Δ (95% CI) | Share of `H(Y|D)` | AUROC D → DX | Calibration slope (DX) |
|---|---|---|---|---|---|
| Primary (RED excluded) | 5,332 | 0.099 (0.085–0.117) | **13.2%** | 0.786 → 0.866 | 1.03 |
| GREEN only | 4,990 | 0.094 (0.073–0.109) | 12.7% | 0.775 → 0.859 | 1.00 |
| Excluding CDM admissions (independent) | 3,895 | 0.088 (0.072–0.110) | **12.0%** | 0.758 → 0.845 | — |
| **Temporal:** train ≤ 2016 (4,192), test 2017–2019 (1,140) | 1,140 | **0.043 (−0.009 to 0.095)** | 5.8% | 0.715 → 0.791 | **0.65** (`Model_D` also 0.64) |

Within-D AUROC (primary, X1) is 0.71 / 0.75 / 0.72 / 0.81 for appendicitis / cholecystitis / diverticulitis / pancreatitis, with ≥ 50 per class in every diagnosis.

**Reading:**
- **T1 replicates within the same period.** It holds in a 2.2× larger cohort and in a CDM-independent subset (12.0–13.2%, versus 13.5% in CDM). It meets both Stage B criteria.
- **Temporal transport is mixed.** Discrimination transfers (AUROC +0.08), but the calibrated gain does not reach significance: the CI includes 0.
  - In the later period, **both** `Model_D` and `Model_DX` are miscalibrated (slope ≈ 0.65, negative intercept: later procedure rates are overestimated).
  - This is consistent with a base-rate shift between periods. It is reported, not interpreted.
  - By contrast, T3 and M6 transport well (slope 1.1–1.2).
- **T1 therefore carries a temporal-transport caveat:** a main experiment would need period-specific recalibration or a within-period design.
