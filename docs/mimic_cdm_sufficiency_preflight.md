# MIMIC-CDM — target sufficiency preflight

- **Date:** 2026-09-29
- **Rules:** [target_sufficiency_framework.md](target_sufficiency_framework.md), pre-specified in commit `88e34b3`.
- **Evidence:** MIMIC-IV-Ext-CDM 1.1 joined to MIMIC-IV 3.1 (`admissions`, `patients`, `transfers`, `procedures_icd`, `d_labitems`, `labevents`), MIMIC-IV-ED 2.2 (`edstays`, `triage`), and MIMIC-IV-Note 2.2 (`radiology`), via `src/preflight/`.
- **Results location:** aggregates only, in `results/phase0/sufficiency/mimic_cdm/`. The patient-level landmark table stays on gbminipc (private directory).

**Diagnosis object used throughout:** `D_final`, the CDM pathology, which is the primary discharge diagnosis. Every Stage B analysis here is **post-diagnostic**: *once the diagnosis is established, does the richer contemporaneous state add information about Y?* None of it is an early-diagnosis analysis. `D_t` does not exist in this dataset, and `D_hat_t` analyses are planned but not run.

## Answers to the preflight questions

1. **What exactly is the diagnosis label?** One of four pathologies. The admission's ICD `long_title` contains the pathology, *and* the pathology appears in the parsed primary discharge diagnosis ([gates/mimic_cdm.md](gates/mimic_cdm.md) Q1).
2. **Is it a final/discharge diagnosis?** Yes. It is `D_final` and must never be treated as `D_t`.
3. **Which treatment decisions are largely determined by the diagnosis alone?**
   - The organ operated on, among operated patients (T5): `H(Y|D)` = 0.068 bits, and ≥ 96% within every diagnosis. This is near-deterministic, and X adds nothing (Δ log loss < 0).
   - The rubric's always-required items (antibiotics; supportive care) are disease-level by construction, but they cannot be observed without prescriptions or eMAR (T10, not evaluated).
4. **Which treatment decisions vary substantially within diagnosis?** Whether the definitive procedure is performed (T1, operative vs non-operative management):

   | Diagnosis | Procedure performed |
   |---|---|
   | Appendicitis | 84% |
   | Cholecystitis | 72% |
   | Diverticulitis (colectomy or drainage) | 21% |
   | Pancreatitis (ERCP) | 34% |

   `H(Y|D)` = 0.78 bits, against `H(Y)` = 0.95 bits.
5. **What variables explain that within-diagnosis variation?** Partly the contemporaneous state. X0 (age, sex, triage vitals, acuity, prior admissions) lifts overall AUROC from 0.755 to 0.827 and recovers 8.7% of `H(Y|D)`. Adding first labs (X1) raises within-D AUROC to 0.70–0.79. Imaging flags (X2) add no further calibrated gain. Individual coefficients were not inspected; this is screening, not attribution.
6. **Does the original treatment rubric distinguish broad categorical treatment from individualized control decisions?** No. Only procedure yes/no items vary by patient, and the rubric has no dose, timing, or intensity content ([gates/mimic_cdm.md](gates/mimic_cdm.md) Q6–Q8).
7. **Are treatment criteria patient-specific, or mostly disease-guideline mappings?** Mostly disease mappings. The patient-specific part is observed procedures, plus one diagnosis sub-type (biliary pancreatitis).
8. **Are severity, comorbidity, lab, and imaging variables available before the treatment target?**
   - **Triage vitals and acuity:** yes, for 1,632 of 2,400 cases. 762 admissions have no linked ED stay (2,400 − 1,638); for them the anchor is ED registration or admission time, and triage features are missing.
   - **Labs:** yes, time-stamped via `labevents`. The CDM release itself has no lab times.
   - **Imaging:** yes, time-stamped by report `storetime` via MIMIC-IV-Note.
   - **Comorbidity:** only prior-admission counts. Discharge ICD codes are excluded as leakage.
9. **Can early examination decisions be evaluated independently of the final diagnosis?** Not with `D_final`. T6 (first imaging modality) and T7 (imaging count) are reported stratified by `D_final` only. Stage B refuses them (G9). An evaluation needs `D_hat_t` and a complaint-level reference.
10. **Can S0–S4 snapshots be built without hindsight leakage?**
    - **Structured S0/S1:** yes, from triage (the landmark design).
    - **Free-text S0 (HPI):** no. Discharge-derived, with 29–85% lexicon flags (gate record).
    - **S2 (labs):** yes, cut by `charttime`.
    - **S3 (imaging):** yes, cut by report `storetime`. The released set is not a first-imaging snapshot: 21–48% of reports come more than 24 h after arrival.
    - **Leakage assertions** (no feature after T; targets after T) pass at both landmarks (`leakage_checks.json`).
11. **Does treatment response appear in any input used before treatment planning?** Not in the landmark features: labs and imaging are cut at T, and post-T values are excluded. In the released CDM fields, yes. "First lab per admission" can be post-treatment, and the radiology set includes post-procedure studies (gate record Q3).
12. **Are procedures and treatments extracted retrospectively from discharge summaries?**
    - Partly. `discharge_procedures.csv` is discharge text with no timestamp.
    - ICD procedure codes carry a `chartdate` (day resolution).
    - For T1, 325 of 2,365 cohort admissions at 6 h have text-only evidence, and 622 are same-day ambiguous (dated the same day as the landmark, with no PACU time to settle whether before or after). The sensitivity cohort excludes both.

## Landmark cohort and attrition

| | 3 h | 6 h |
|---|---|---|
| CDM admissions | 2,400 | 2,400 |
| Alive in hospital at T, no PACU before T | 2,392 | 2,365 |
| T1: procedure dated before T's date (excluded) | 11 | 36 |
| T1: same-day ambiguous (retained; excluded in sensitivity) | 536 | 622 |
| T1: discharge-text-only evidence (retained; excluded in sensitivity) | 328 | 325 |
| ICU before T (excluded from T3) | 24 | 56 |

Anchors: ED arrival for 1,638; ED registration for 667; admission time for 95.

**Semantic finding: PACU transfers do not mark operations.** Only 120 of 767 coded appendectomies in the 6 h cohort have a PACU transfer. T2 (any PACU after T) and T9 (time to PACU) therefore measure documentation, not surgery. They are RED.

## Results

See the per-target summary in [target_decision_table.md](target_decision_table.md). The numbers are in `results/phase0/sufficiency/mimic_cdm/`:
- `stage_a_L{3,6}.json`: Stage A.
- `x0/stage_b_*.json`: Stage B with X0.
- `full/stage_b_*.json`: Stage B with X0/X1/X2.
- `x0_superseded_precleaning/`: the pre-cleaning run, superseded (see decision log).

### Stage B summary (6 h landmark; 3 h in brackets)

| Target | `H(Y|D)` | X0 Δ log loss (share of `H(Y|D)`) | X1 | X2 | Within-D AUROC of `Model_DX` (X1): appendicitis / cholecystitis / diverticulitis / pancreatitis |
|---|---|---|---|---|---|
| T1 procedure | 0.777 | 0.068 [0.068], 8.7% | 0.066, 8.5% [8.2%] | 0.038, 4.9% (CI crosses 0) [5.4%] | 0.70 / 0.77 / 0.75 / 0.79 |
| T1 sensitivity cohort | 0.872 | 0.050, 5.7% [6.0%] | −0.019 (CI crosses 0) | −0.091 (CI below 0) | 0.63 / 0.76 / 0.68 / 0.77 |
| T3 ICU | 0.297 | 0.007, 2.3% (CI crosses 0) | −0.060 | −0.096 | (events per D 16–46) |
| T4 LOS (R²) | — | 0.21 → 0.33 | 0.21 → 0.35 | 0.21 → 0.34 | within-D R² (X2): 0.22 / 0.21 / 0.04 / 0.07 |
| T5 organ | 0.068 | −0.038 (CI below 0) | −0.112 | −0.095 | — |

**Interpretation, within the limits of rule 12:**
1. **T1 has residual within-diagnosis variability.** `H(Y|D)` is 0.78 bits.
2. **Legitimate contemporaneous state ranks that variability within every diagnosis** (AUROC 0.70–0.79 with labs). This is stable between the 3 h and 6 h landmarks, which argues against dependence on post-landmark information.
3. **The calibrated information gain under the pre-specified fixed model is modest** (≤ 8.8% of `H(Y|D)`, below the pre-set 10%). It shrinks as features are added (overfitting from untuned L2 + X×D interactions) and in the smaller sensitivity cohort.
4. **Clinical relevance is not yet established** (Stage C).

This preflight does **not** show that diagnosis is insufficient for T1. Whether the recovered information is decision-relevant, and whether a bottleneck architecture pays a cost beyond model capacity, remain open.

### Lab timing of the released CDM "first labs" (Q3, from `results/phase0/mimic_cdm/timing.json`)

- **Coverage:** 132,103 of 138,788 release lab items (95.2%) were matched to a `labevents` time. Of these, 80.2% have matching values, so the reconstruction is approximate.
- **Timing:** median 0.9–1.5 h after arrival, but 6.5–24% of items come more than 6 h after arrival and 2.5–12% more than 24 h. Between 18% (appendicitis) and 68% (pancreatitis) of cases have at least one released "first" lab more than 24 h after arrival.
- **Conclusion:** the released S2 is not an initial-labs snapshot. The landmark table does not use the release values; it cuts `labevents` at T directly.
