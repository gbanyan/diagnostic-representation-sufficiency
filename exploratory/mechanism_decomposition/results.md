# MC-MED mechanism decomposition: results (EXPLORATORY)

**Plan:** [plan.md](plan.md), committed before running (`0b7c8bd`).

**Status:**
- **Exploratory, post-confirmatory.** It was run after the primary result was seen.
- **It reuses the already-opened test set for description only.** There are no success thresholds, and it adds nothing to the confirmatory claim.

**Setup:**
- Every model is compared with the same Model D (soft D_hat + season).
- The frozen cohort, split, preprocessing, C grid, and development-CV tuning are used, with the Newton solver.
- 1,000-replicate patient-cluster bootstrap on the test set (6,570 visits, 212 ICU).
- All fits converged.

**Source:** `results/mechanism_decomposition.json`.

## Single families (Model D + one family)

| Model D + … | Model columns | C | Δbits (95% CI) | Relative gain (95% CI) | AUROC D → D+F |
|---|---|---|---|---|---|
| A. Physiology / vital state (triage vitals + numerics values) | 72 | 0.01 | 0.0123 (0.0078 to 0.0170) | **6.8%** (4.3% to 9.4%) | 0.787 → 0.828 |
|   A1. Triage vitals only | 6 | 0.1 | 0.0021 (-0.0009 to 0.0050) | **1.1%** (-0.5% to 2.8%) | 0.787 → 0.786 |
|   A2. Numerics value summaries only | 66 | 0.01 | 0.0116 (0.0073 to 0.0162) | **6.4%** (4.0% to 8.9%) | 0.787 → 0.825 |
| B. Laboratory values | 87 | 0.01 | 0.0146 (0.0092 to 0.0202) | **8.0%** (5.0% to 11.0%) | 0.787 → 0.829 |
| C. Medical history (PMH) | 176 | 0.001 | 0.0020 (0.0000 to 0.0039) | **1.1%** (0.0% to 2.2%) | 0.787 → 0.793 |
| D. Presenting context (age, sex, arrival, ESI, chief complaint) | 99 | 0.03 | 0.0145 (0.0099 to 0.0194) | **8.0%** (5.6% to 10.6%) | 0.787 → 0.827 |
| E. Measurement-process intensity (not-measured indicators + counts) | 171 | 0.1 | 0.0277 (0.0203 to 0.0349) | **15.2%** (11.6% to 18.9%) | 0.787 → 0.855 |
| F. Clinical state without measurement process (A+B+C+D values) | 434 | 0.003 | 0.0253 (0.0186 to 0.0324) | **13.9%** (10.5% to 17.6%) | 0.787 → 0.853 |

## Leave-one-family-out (Model D + all families except one)

| Model D + … | Model columns | C | Δbits (95% CI) | Relative gain (95% CI) | AUROC D → D+F |
|---|---|---|---|---|---|
| ALL (reconstruction of confirmatory X) | 605 | 0.003 | 0.0319 (0.0247 to 0.0399) | **17.6%** (13.8% to 21.4%) | 0.787 → 0.870 |
| ALL − A | 533 | 0.003 | 0.0321 (0.0250 to 0.0395) | **17.7%** (14.1% to 21.3%) | 0.787 → 0.870 |
| ALL − B | 518 | 0.003 | 0.0283 (0.0217 to 0.0350) | **15.6%** (12.2% to 19.0%) | 0.787 → 0.862 |
| ALL − C | 429 | 0.01 | 0.0326 (0.0249 to 0.0410) | **17.9%** (14.1% to 22.1%) | 0.787 → 0.872 |
| ALL − D | 506 | 0.003 | 0.0294 (0.0221 to 0.0366) | **16.2%** (12.4% to 19.9%) | 0.787 → 0.863 |
| F. Clinical state without measurement process (A+B+C+D values) | 434 | 0.003 | 0.0253 (0.0186 to 0.0324) | **13.9%** (10.5% to 17.6%) | 0.787 → 0.853 |

**Reconstruction check passed.** ALL reproduces the confirmatory estimate (17.6%; the same information re-presented with explicit indicators).

**ALL − E equals F:** removing the measurement-process block leaves the clinical-state values only.

## Descriptive reading (no thresholds; families overlap, so gains are not additive)

1. **Measurement-process intensity alone (E) carries most of the incremental signal:** 15.2% (11.6–18.9%), AUROC 0.855. E is only whether each lab was resulted and each monitor parameter observed by 3 h, plus monitoring counts.
2. **Clinical-state values without any measurement-process information (F) also carry most of it:** 13.9% (10.5–17.6%), AUROC 0.853.
3. **E and F therefore overlap heavily.** Removing E from ALL lowers the gain from 17.6% to 13.9%, the largest leave-one-out drop. Removing any single value family (A, B, C, or D) changes it by at most 2 points.
4. **The physiology-only question.**
   - Physiology alone (A) retains **6.8% (4.3–9.4%)**; the CI excludes 0.
   - This comes almost entirely from the **monitored numerics** trajectory summaries (6.4%). **Triage vitals add ≈ 1% (CI includes 0)** beyond the disease-label representation.
   - Removing physiology from ALL changes nothing (17.7%). Its information is **redundant** with labs, presenting context, and measurement-process signals.
5. **Labs (8.0%) and presenting context (8.0%)** are each comparable to physiology. History adds ≈ 1%.

## Interpretation (descriptive)

- **Pure physiologic state does retain predictive information beyond the disease-label representation**, but only a minority of the confirmed gain (about 7% vs 17.6%). It is fully redundant with the other information classes.
- **A large share of the signal is available from measurement-process information alone:** which tests had resulted and whether and how intensively the patient was monitored by 3 h.
- **Taken together:** the disease-label representation does not preserve **severity or uncertainty information that is expressed both in the patient's measured state and in clinician work-up and monitoring behavior.** The two sources are largely interchangeable for prediction.
- **Neither reading is preferred.** The data cannot separate "patient severity that clinicians also perceived" from "clinician concern per se". The measurement-process variables are legitimate 3 h information, and they are **not** relabelled leakage (see [measurement_process_audit.md](measurement_process_audit.md)).

**Caveats:**
- The analysis is post hoc and reuses the test set.
- Families are correlated.
- It is a single model family (additive, L2).
- Missing indicators also proxy the missing values themselves.
- No subgroup analyses were run, and none should be added on this test set.
