# MC-MED robustness follow-up: dimension-matched granularity, Model D flexibility, comparator matched to MIMIC (plan)

**Date:** 2026-10-03. Committed before any run. Approved by the author on 2026-10-03.

**Status.** Exploratory and post-confirmatory. The already-opened MC-MED locked test set is reused descriptively. No margin is applied, no frozen result changes, and no verdict is issued.

**Why.** Reviewers repeatedly raised three unresolved interpretive questions:
1. the granularity effect (17.6% → 8.1% at 127 classes) cannot be separated from posterior dimensionality and encoder regularization;
2. the hard top-1 analysis changed the representation and did not test Model D misspecification with D̂ held fixed;
3. the MC-MED comparator (445 variables) is much richer than MIMIC X1 (32), which may partly explain the cross-cohort contrast.

## Common elements (identical to the granularity analysis, `exploratory/diagnostic_capacity/run.py`)

- **Models.** Model D is intercept + D block + season, unpenalized apart from the fixed ε ridge. Model D+X adds X with an L2 penalty C tuned by 4-fold patient-grouped inner CV on development data (same seed and grid).
- **Evaluation.** One fit on all development patients; evaluated on the test set.
- **Shared bootstrap.** 1,000 patient-cluster resamples, seed 20261006. Each variant gets a point estimate and percentile CI, plus a paired difference from the reference.
- **Reference (REF).** The frozen primary 20-class soft D̂ with the full X. **Reproduction gate:** REF must reproduce `capacity.json` R2 `soft_dhat` (L_D, L_DX and the Δbits CI bounds) within 1e-4 bits, or the run stops and no differences are reported.

## Variants

**1. Dimension-matched granularity.** Uses the 127-class posterior (R5, saved during the granularity analysis).
- **1a, aggregated:** sum the 127 class probabilities into the 20 primary body-system classes, giving 19 columns after dropping the primary reference class. Each R5 class maps to the body system of its development members. The global pooled "OTHER" class maps to the body system with the most of its development members, and the share that disagrees is reported.
- **1b, PCA:** the first 19 principal components of the 127 probabilities, fitted on development rows.
- **1c, regularization:** the 20-class body-system encoder refitted with the same cross-fitting but the encoder inverse penalty fixed at C = 0.01, the value every finer encoder selected (the primary used 0.003).

**2. Model D flexibility with D̂ fixed.** The primary 20-class posterior is held fixed throughout.
- **2a, additive log-ratio:** D enters as additive log-ratio columns, log(p_k / p_ref), ε ridge only.
- **2b, spline:** a cubic B-spline basis (4 knots, fitted on training rows) of each additive log-ratio column, 114 columns.
  - Model D tunes one L2 penalty C_D on the spline block by inner CV on Model D loss.
  - Model D+X keeps the spline block at the same effective penalty, by column scaling with s = sqrt(C_D / C_X), and tunes C_X for X.

**5. Comparator matched to MIMIC X1.** Primary D̂. X is restricted to the MC-MED analogues of MIMIC X1:
- age; sex; arrival mode;
- six triage vital signs; ESI (in place of acuity);
- 19 of MIMIC's 20 laboratory tests, with missing indicators. CRP is not available; lactate is the point-of-care measure; bicarbonate is CO2.
- MIMIC X1's pain score and prior-admission count have no released MC-MED analogue and are omitted.

## Interpretation rules (fixed now)

- **1a / 1b:** if the fraction stays near the 127-class value (8.1%), the finer encoder's label information persists at fixed dimension. If it returns near the 20-class value (17.6%), the decrease reflects added columns or encoder flexibility rather than label resolution. Intermediate values are reported as intermediate.
- **1c:** a large drop at 20 classes would implicate encoder regularization.
- **2a / 2b:** a material drop relative to REF indicates that part of the primary residual reflects the restricted form of Model D.
- **5:** describes how much of the MC-MED residual remains with a MIMIC-like comparator. Because representation, target, landmark and prevalence still differ, it does not convert the cross-cohort contrast into a controlled comparison.
- **For all variants:** paired differences against REF use the shared bootstrap. There are no p-values, no trend tests, and no thresholds.

## Disclosure control

Outputs are aggregates only. Exploratory encoders are saved to the private exploratory directory.
