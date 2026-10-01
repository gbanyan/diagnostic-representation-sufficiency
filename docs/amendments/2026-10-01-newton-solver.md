# Amendment 1: exact Newton solver for the downstream logistic models

**Timestamp:** 2026-10-01, about 04:40 CST. Made after the tag `mcmed-confirmatory-prereg-v1` and **before the locked test was opened**. `test_opened_primary.flag` does not exist, and no test prediction has been computed.

## What had been seen

- **Stage E:** the diagnosis encoder report (diagnosis metrics only).
- **Stage F (first run, development data only):** the development inner-CV results at the selected C. The downstream relative log-loss gain was 13.1% (L_D 0.1344 vs L_DX 0.1168 nats; 897 events).
- **Locked test:** no locked-test outcome or prediction of any kind.

**This disclosure is made because a development result was visible when this amendment was written.**

## Reason

The first Stage F run triggered **stop gate 9** (convergence):
- `final_DX_converged = false`, and some inner fits reported `converged = false`;
- the numerical penalty-zero check failed.

A development-only diagnostic compared the preregistered L-BFGS solution (`PartialLogistic`, from `600f368`) with an exact Newton solve of the **identical** objective:

| Fit (all development data) | L-BFGS objective / max \|gradient\| | Newton objective / max \|gradient\| | Max prediction difference |
|---|---|---|---|
| Model D+X, C = 0.003 | 2870.869 / 0.099 | 2870.622 / 1.0e-12 (8 iterations) | 0.021 |
| Model D+X, C = 1e-8 (penalty check) | 3456.171 / 16.9 | 3451.901 / 1.4e-9 | 0.058 |
| Model D | converged (max \|gradient\| 1.8e-3) | 1.6e-13 | 4.7e-5 |

**Diagnosis.** L-BFGS stopped short of the optimum. The design combines 19 near-collinear soft-probability columns, which are unpenalized apart from ε = 1e-4 (condition number of the unpenalized block ≈ 1,800), with about 600 penalized X columns. The objective is strictly convex, so the Newton solution is its unique optimum.

## Change

Model D and Model D+X are fit with `src/mcmed/newton_logistic.py`:
- exact Hessian;
- Armijo backtracking;
- convergence at max |gradient| < 1e-6.

**Unchanged:** the objective, the penalties (including ε), the intercept treatment, the C grid, the CV folds, the tie rule, the data, and every other preregistered choice.

**Validation (tests/test_mcmed.py):**
- the Newton solver matches `PartialLogistic` on well-conditioned synthetic data (≤ 1e-5);
- the fully penalized fit matches scikit-learn;
- C → 0 recovers Model D.

The real-data penalty-zero check is restored to strict tolerances: X coefficients < 1e-4, predictions within 1e-4, and log loss within 1e-6 of Model D. This replaces the loosened tolerances added before the tag.

The development CV is also parallelized (8 processes). The result does not depend on this.

## Scientific consequence

**None intended.** The same estimator is now computed correctly. C is re-selected under the corrected fits by the unchanged rule. Whatever C and numbers result are what is reported. No other change is made in light of the development result.

**Side note.** The MIMIC confirmatory runs (`600f368`) used the same L-BFGS implementation, but on much smaller designs (about 30 X columns, one-hot diagnosis). Whether they were affected is not examined here, since that is outside this study's scope. It is listed as an open check for the author.
