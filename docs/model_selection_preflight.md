# Model selection for the preflight (Q13): nested cross-validation

**Pre-registered 2026-09-29, before any nested-CV result was computed.** This follows author decision Q13. The earlier fixed-C runs (C = 1.0) remain in `results/phase0/sufficiency/mimic_cdm/{x0,full}/` as provenance. For classification they are superseded by the nested runs (`nested/`).

## Why nested CV

With fixed C, the D+X model overfit as legitimate features were added: AUROC rose while log loss worsened ([target_decision_table.md](target_decision_table.md)). Shrinking the feature set could remove exactly the residual information the preflight is meant to detect, so **the feature set is not reduced**. Nested CV instead chooses the regularization strength inside each training fold, so the held-out estimate is never used for tuning.

## Design

| Element | Specification |
|---|---|
| Unit of splitting | Patient (`subject_id`). All admissions of a patient fall in the same fold, at both levels. |
| Outer loop | `StratifiedGroupKFold(n_splits=5, shuffle=True)`, stratified on Y (binary/categorical) or on D (continuous). **Repeated 3 times** with seeds 20260929, 20260930, 20260931. |
| Inner loop | On each outer-training set: `StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=outer_seed + outer_fold_index)`, same stratification and grouping. |
| C grid (logistic) | {1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1, 3, 10, 100} (11 values; L2) |
| α grid (ridge, continuous targets) | α = 1 / C over the same 11 values |
| Selection rule | The C with the lowest mean inner-fold held-out loss: log loss for binary/categorical targets, MSE for continuous. **Ties go to the smaller C** (stronger regularization). The model is then refit on the full outer-training set with that C and evaluated once on the outer test fold. |
| Identical budget for both models | `Model_D` (D one-hot) and `Model_DX` (D one-hot + X + X×D) use the **same** grid, inner splits, selection rule, and outer folds. |
| Preprocessing | Median imputation + missing indicators, `log1p` for the listed skewed features, standardization, and clipping to ±5 SD. All are fit on the training part only, at each level ([data_cleaning_rules.md](data_cleaning_rules.md)). |
| Feature sets | Unchanged from the framework: X0 ⊂ X1 ⊂ X2, all timestamped ≤ landmark T. |
| Leakage controls | Features are cut at T (labs by `charttime`, radiology by `storetime`); targets fall after T; `leakage_checks` must pass before modeling. For T1, the procedure-timing classes from [procedure_timing_audit.md](procedure_timing_audit.md) apply: the primary analysis excludes RED; a sensitivity analysis excludes RED and YELLOW. |

## Metrics (all out-of-fold on the outer test folds)

- **Log loss** in bits (proper loss; closest to the conditional-information interpretation). Δ = `loss(Model_D)` − `loss(Model_DX)`.
- **AUROC**: overall and within each diagnosis (discrimination).
- **Brier score.**
- **Calibration** of `Model_DX`:
  - calibration intercept and slope, from logistic recalibration of the out-of-fold logit on Y;
  - expected calibration error over 10 equal-width bins.
- **Uncertainty:**
  - a 1,000-resample subject-level paired bootstrap on repeat 1;
  - mean ± SD across the 3 outer repeats.
- **Selected C:** its distribution across outer folds, reported for both models.

Both AUROC and log loss are reported, and neither is given priority. **If they disagree after tuning, the disagreement is reported, not resolved by choosing a metric.**

## Classification thresholds

These are unchanged from [target_sufficiency_framework.md](target_sufficiency_framework.md): "meaningful" requires Δ log loss ≥ 10% of `H(Y|D)` **and** within-D ΔAUROC ≥ 0.05. Because the within-D out-of-fold AUROC of `Model_D` departs from 0.5 through fold effects, the within-D ΔAUROC criterion is evaluated as `AUROC(Model_DX) − 0.5`.

## Prohibited

- Tuning on outer test folds.
- Feature pruning based on held-out results.
- Adding model families after seeing results. A later change requires a new registered specification.

---

## Results, part 1: unfiltered cohorts (computed after this document was committed in `e15301a`)

Source: `results/phase0/sufficiency/mimic_cdm/nested/`.
- Values are the mean over 3 outer repeats. The CI is the subject-bootstrap interval on repeat 1.
- Δ = Δ log loss in bits.
- Within-D AUROC is that of `Model_DX`, averaged over repeats.
- T1 is shown **before** the procedure-timing filter; the filtered results are in part 2.

| Target (landmark) | Set | Δ (95% CI) | Share of `H(Y|D)` | AUROC D → DX | Calibration of DX (slope / ECE) | Selected C for DX | Within-D AUROC (appendicitis / cholecystitis / diverticulitis / pancreatitis) |
|---|---|---|---|---|---|---|---|
| T1 (6 h) | X0 | 0.069 (0.049–0.090) | 8.9% | 0.755 → 0.827 | 1.03 / 0.021 | 0.1 | 0.69 / 0.78 / 0.58 / 0.67 |
| T1 (6 h) | X1 | 0.102 (0.076–0.134) | 13.1% | 0.755 → 0.844 | 1.02 / 0.018 | 0.03 | 0.72 / 0.78 / 0.67 / 0.80 |
| T1 (6 h) | X2 | 0.107 (0.080–0.139) | 13.7% | 0.755 → 0.846 | 1.00 / 0.017 | 0.03 | 0.75 / 0.78 / 0.69 / 0.79 |
| T1 (3 h) | X2 | 0.098 (0.071–0.126) | 12.7% | 0.755 → 0.843 | 1.04 / 0.022 | 0.03 | 0.74 / 0.78 / 0.68 / 0.78 |
| T3 (6 h) | X1 | 0.057 (0.037–0.071) | 19.0% | 0.634 → 0.843 | 1.05 / 0.009 | — | 0.82 / 0.80 / 0.89 / 0.76 |
| T4 (6 h) | X1 | R² 0.212 → 0.413 | — | — | — | — | within-D ΔMSE > 0 in all four |
| T5 (6 h) | X0–X2 | −0.045 to −0.099 (CIs below 0) | < 0 | — | — | 1–3 | — |

**Metric disagreement after tuning.** The earlier fixed-C pattern (AUROC up, log loss down or negative as features were added) **does not persist**. With C chosen in inner folds (usually 0.03–0.1 for `Model_DX`):
- AUROC and log-loss improvements move together;
- both grow from X0 to X1;
- calibration slopes are 1.00–1.09.

The earlier disagreement was a regularization artifact of fixed C = 1.

**T5 negative control: a model artifact to note.** `Model_DX` is worse than `Model_D` (Δ < 0, CI below 0). The shared L2 penalty also shrinks the *diagnosis main effects* in `Model_DX`, so it cannot express "diagnosis settles Y" as sharply as the separately tuned `Model_D` (C = 10–100). The penalty is largest in the 33 all-colon diverticulitis cases.

The substantive reading, that **X adds no information about T5**, is unaffected. But the **size** of a negative Δ is partly this artifact, and every target's Δ carries a small **conservative** bias from it. The main experiment's pre-registration should leave diagnosis offsets unpenalized (or fit per diagnosis). This is recorded, not changed here: the specification was pre-registered.

**Classification consequences, pending timing filtering and Q15:**
- **T1:** unfiltered, it now meets both pre-specified parts of "meaningful recoverability":
  - Δ ≥ 10% of `H(Y|D)` with a CI above 0;
  - within-D AUROC − 0.5 ≥ 0.05 in diagnoses with ≥ 50 per class.
- **T3:** Δ = 19% of `H(Y|D)`, but no diagnosis has ≥ 50 events (16 / 46 / 24 / 45). The within-D criterion cannot be assessed, so T3 is underpowered within diagnosis.

## Results, part 2: T1 after procedure-timing filtering (Q14)

Source: `nested/stage_b_T1_L{3,6}_{exclude_red,green_only}_nested.json`. Timing classes are defined in [procedure_timing_audit.md](procedure_timing_audit.md).

| Landmark / cohort | n | `H(Y|D)` | Set | Δ (95% CI, repeat 1) | Share of `H(Y|D)` | AUROC D → DX | Calibration slope / ECE |
|---|---|---|---|---|---|---|---|
| 6 h, unfiltered (reference) | 2,329 | 0.777 | X1 | 0.102 (0.076–0.134) | 13.1% | 0.755 → 0.844 | 1.02 / 0.018 |
| **6 h, exclude RED (primary)** | **2,270** | 0.773 | X0 | 0.065 (0.041–0.083) | 8.4% | 0.758 → 0.828 | 1.04 / 0.022 |
| | | | **X1** | **0.104 (0.072–0.129)** | **13.5%** | **0.758 → 0.849** | 1.07 / 0.025 |
| | | | X2 | 0.111 (0.076–0.135) | 14.4% | 0.758 → 0.852 | 1.00 / 0.019 |
| 6 h, GREEN only (sensitivity) | 1,908 | 0.810 | X1 | 0.091 (0.060–0.120) | 11.2% | 0.750 → 0.834 | 1.01 / 0.028 |
| | | | X2 | 0.090 (0.060–0.119) | 11.1% | 0.750 → 0.834 | 0.98 / 0.025 |
| 3 h, exclude RED | 2,356 | 0.769 | X1 | 0.093 (0.077–0.129) | 12.1% | 0.758 → 0.843 | 1.08 / 0.024 |
| 3 h, GREEN only | 2,152 | 0.782 | X1 | 0.084 (0.053–0.111) | 10.7% | 0.763 → 0.839 | 0.99 / 0.029 |

**Within-D AUROC of `Model_DX` (X1)**, reported as AUROC [n / events]:

| Cohort | Appendicitis | Cholecystitis | Diverticulitis | Pancreatitis |
|---|---|---|---|---|
| 6 h primary | 0.73 [891 / 742] | 0.79 [635 / 452] | 0.66 [249 / 51] | 0.79 [495 / 154] |
| 6 h GREEN only | 0.71 [670 / 521] | 0.77 [540 / 357] | 0.63 [238 / 40] | 0.77 [460 / 119] |

**Reading (rule 12 applies):**
- In the primary cohort and in every sensitivity cohort, at both landmarks, T1 meets both pre-specified Stage B criteria:
  - Δ ≥ 10% of `H(Y|D)` with a CI above 0;
  - within-D AUROC − 0.5 ≥ 0.05 in diagnoses with ≥ 50 per class.
- The GREEN-only margin is small (10.4–11.2%), and diverticulitis has < 50 events there.
- The recoverable information does **not** depend on the timing-ambiguous cases.

This establishes residual variability (1) and recoverability (2) for T1. **It does not establish clinical relevance (3): Stage C is deferred (Q15).**

---

## Addendum (pre-registered 2026-09-29, before the run): Q19 sensitivity — unpenalized diagnosis main effects

**Motivation:** in `Model_DX`, the shared L2 penalty also shrinks the D main effects (the T5 artifact in Results part 1), which biases Δ conservatively.

**Specification:** identical to the nested-CV design above, except that in `Model_DX` the D one-hot **main-effect** columns are multiplied by s = 100 before fitting. This lowers the effective L2 penalty on the D main effects by a factor of s² = 10⁴, which is effectively unpenalized. Interaction columns (X×D) and X columns are unchanged. `Model_D` is unchanged (it already tunes C up to 100).

- **Targets:** T1 (6 h, primary cohort with RED excluded), T3, T5, M2, M5, M6 (6 h). Feature sets X0 / X1 / X2.
- **Expectations, stated before running:**
  - negative controls (T5, M5) should move toward Δ ≈ 0 from below;
  - positive candidates should be unchanged or slightly higher.
- **Classification:** this is a sensitivity analysis, and it does not change classes by itself. If it changes a class, that is reported as a discrepancy for the author.
- **Output:** `results/phase0/sufficiency/mimic_cdm/q19_unpenalized_d/`.

### Q19 results (6 h landmark; T1 = primary cohort with RED excluded)

Source: `results/phase0/sufficiency/mimic_cdm/q19_unpenalized_d/`. Δ log loss in bits, mean of 3 repeats (share of `H(Y|D)`). The CI is for the unpenalized-D model, repeat 1.

| Target | Set | Shared penalty (registered) | Unpenalized D main effects (Q19) | 95% CI (Q19) |
|---|---|---|---|---|
| T1 | X1 | 0.104 (13.5%) | **0.128 (16.6%)** | 0.105–0.149 |
| T1 | X2 | 0.111 (14.4%) | **0.135 (17.4%)** | 0.111–0.155 |
| T3 | X1 | 0.057 (19.0%) | 0.055 (18.5%) | 0.039–0.070 |
| T5 (negative control) | X1 | −0.099 | **+0.002 (2.6%)** | −0.002–0.005 |
| T5 | X2 | −0.090 | +0.004 (5.1% of a tiny `H(Y|D)` = 0.068) | 0.000–0.008 |
| M2 | X1 / X2 | 9.8% / 10.0% | 9.9% / 10.2% | 0.031–0.057 (X1) |
| M5 (negative control) | X1 | −0.008 | +0.006 (1.3%) | −0.002–0.014 |
| M5 | X2 | −0.003 | +0.008 (1.8%) | 0.000–0.016 |
| M6 | X1 | 25.3% | 25.2% | 0.091–0.146 |

**Reading, against the expectations registered above:**
- Both negative controls move from negative to ≈ 0, as expected. The earlier negative Δ was the shared-penalty artifact.
- T1 rises, as expected (the conservative bias is removed).
- T3, M2, and M6 are essentially unchanged.
- **No class changes.** The negative-control / positive-candidate dissociation is cleaner under this specification.
- **Recommendation for the main-experiment pre-registration: unpenalized diagnosis main effects.**
