# MIMIC T1 solver audit: POST-HOC NUMERICAL ROBUSTNESS AUDIT

**Authorized** by the author on 2026-10-01.

**Not a new confirmation.** The frozen T1 result (`600f368`; `results/main/target_sufficiency/primary_T1.json`; `docs/main_experiment_results.md`) is not modified.

**Code:** `audits/mimic_t1_solver_audit.py` (commit before running). **Output:** `audits/results/mimic_t1_solver_audit.json` (aggregates only).

## Why this audit

In the MC-MED workflow the same `PartialLogistic` L-BFGS implementation failed to reach the optimum on an ill-conditioned design ([amendment 1](../docs/amendments/amendment_1_final.md)). The question here is whether the frozen T1 estimate carries the same problem.

## Step 0: what the existing artifacts showed

1. **Recorded convergence.** The frozen JSON records `converged = True` for all three repeats. This flag covers only the 10 **outer** fits per repeat (Model D and Model D+X × 5 folds), using scipy's success flag.
2. **Inner fits.** The 220 **inner tuning** fits per repeat had no recorded convergence status.
3. **Warnings.** None from the optimizer were suppressed. The `warnings` filter in `select_C` and `nested` covers only scikit-learn split warnings.
4. **Weakness of the flag.** scipy's success flag can be met by the relative objective-change criterion (`ftol`), so it does not guarantee a small gradient.

Convergence was therefore **uncertain** (unrecorded for inner fits, and success-flag only for outer fits). The authorized robustness re-evaluation was run.

## Step 1: the original solver, instrumented (repeat 1, seed 20260929)

The analysis was re-run exactly as frozen. Each L-BFGS fit was additionally compared with the exact Newton optimum of the **same** objective.

| Quantity | Value |
|---|---|
| Fits audited (10 outer + 220 inner) | 230 |
| scipy success = false | **0** |
| Max \|gradient\| of the objective (median / p90 / p99 / max) | 0.0005 / 0.0016 / 0.0032 / 0.0057 |
| Objective gap to the exact optimum (max) | < 5e-5 (rounds to 0.0000) |
| Max prediction difference vs the optimum (median / p90 / p99 / max) | 0.0000 / 0.0000 / 0.0001 / 0.0001 |
| Fits with a prediction difference > 1e-3 | 0 |

The rerun reproduces the frozen repeat-1 numbers exactly:
- selected C [0.003, 0.003, 0.003, 0.01, 0.01];
- log loss D 0.7280, D+X 0.6996 bits;
- Δ 0.0284 bits (CI 0.0202–0.0362);
- relative gain 3.90% (2.77–4.96%).

**Answers:**
1. **Did L-BFGS converge under the documented criterion?** Yes, in every fit.
2. **Were any folds non-converged?** No.
3. **Were convergence warnings ignored?** No optimizer warnings exist to ignore. The status of the inner fits was simply not recorded.
4. **Could incomplete optimization bias Model D or Model D+X?** Not materially. Every fit is within 1e-4 in predicted probability of the exact optimum.

**Why T1 differs from MC-MED.** The T1 design is small and well conditioned: 19 unpenalized one-hot columns and 60 penalized columns. MC-MED combined 19 near-collinear soft-probability columns with about 600 penalized columns.

## Step 2: robustness re-evaluation with the exact Newton solver (3 repeats)

**Held identical:** cohort (n = 4,990; 1,833 events), folds and seeds, features (X1), preprocessing, context, penalty structure, C grid, tie rule, bootstrap, and success rule. Only the solver changed (`src/mcmed/newton_logistic.py`, validated in the MC-MED tests).

| | Frozen (L-BFGS) | Audit (Newton) |
|---|---|---|
| Selected C (repeats 1 / 2 / 3) | [.003,.003,.003,.01,.01] / [.01,.003,.003,.01,.01] / [.01,.01,.003,.01,.003] | identical |
| Log loss D (mean, bits) | 0.7272 | 0.7272 |
| Log loss D+X (mean, bits) | 0.6989 | 0.6989 |
| Δ (mean) | 0.0284 bits | 0.0284 bits |
| Δ 95% CI (repeat 1) | 0.0202–0.0362 | 0.0202–0.0362 |
| **Relative gain** (mean; repeat-1 CI) | **3.90%** (2.77–4.96%) | **3.90%** (2.77–4.96%) |
| AUROC D → D+X (mean) | 0.8056 → 0.8298 | 0.8056 → 0.8298 |
| Success rule | CI > 0: yes; ≥ 10%: **no** → not supported | identical |

## Conclusion

- **The frozen T1 result is numerically robust to the solver.** The original fits converged, and the Newton re-evaluation reproduces every reported number to the reported precision.
- **The T1 interpretation does not change.** Diagnosis plus common context is approximately sufficient under the prespecified 10% criterion.
- **The evidence chain is unchanged.**

**Not audited here** (outside the authorization): the other MIMIC endpoints (T3, M3, M5, T5) and sensitivities. They use the same designs and similar sizes. T5 (multinomial) had one recorded non-convergence flag in the frozen results; that is already disclosed in `docs/main_experiment_results.md`.
