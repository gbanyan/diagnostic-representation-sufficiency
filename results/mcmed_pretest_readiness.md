# MC-MED pre-test readiness report (Stage F)

**Preregistration:** `mcmed-confirmatory-prereg-v1` + [amendment 1](../docs/amendments/2026-10-01-newton-solver.md) (exact Newton solver).

**Source:** `results/mcmed/stageF_develop_primary.json`.

**Scope.** Development data only. **The locked test has not been opened.**

## Design

| Item | Value |
|---|---|
| Development visits / patients / ICU events | 25,834 / 18,023 / 897 |
| D block | soft D_hat, **19 columns** (K = 20, K−1 parameterization; reference class **SYM**, the largest development class) |
| Common context | season (season=JJA, season=MAM, season=SON; reference DJF), unpenalized |
| X_3h | 445 raw columns, **605 model columns** after missing indicators |
| Model D | intercept + D block + season (23 coefficients), unpenalized (ε = 1e-4) |
| Model D+X | Model D + X (L2 on X only), **C = 0.003** |
| Solver | exact Newton (amendment 1). Final max \|gradient\|: D 0.0e+00, D+X 0.0e+00; 9 iterations |
| Convergence | all 44 inner fits: **True**; final D: **True**; final D+X: **True** |
| Coefficient SHA-256 | D `787930c735fbebdebb888565c3f89f41e18874f1272532e2362de1f85334aa58`<br>D+X `90d2a87d98406abaa89e8ef5f3e95cf8ffd3ca769d492a5af7c3024eebe562d9` |

### C selection (4-fold patient-grouped development CV; mean held-out log loss, nats)

| C | Log loss (D+X) |
|---|---|
| 0.0001 | 0.1260 |
| 0.001 | 0.1176 |
| 0.003 | 0.1168 |
| 0.01 | 0.1183 |
| 0.03 | 0.1207 |
| 0.1 | 0.1235 |
| 0.3 | 0.1257 |
| 1.0 | 0.1276 |
| 3.0 | 0.1291 |
| 10.0 | 0.1306 |
| 100.0 | 0.1328 |

C = 0.003 has the lowest loss. The curve is smooth, with an interior minimum.

## Checks

1. **Leakage.** The feature code asserts that lab `Result_time`, numerics `Time` ≤ T, and PMH before the arrival date hold (Stage A). The encoder saw diagnosis labels only. Development D_hat is out-of-fold. Test D_hat came from the development-only encoder. No outcome was used in any feature or vocabulary rule.
2. **Convergence.** Passed (above).
3. **Penalty-zero verification.**
   - At C = 1e-8, the X coefficients are ≤ 4.9e-6 and the predictions are within 7.1e-5 of Model D. The log loss is within 2.1e-6, just above the 1e-6 tolerance set in amendment 1, because C = 1e-8 is finite.
   - The residual scales **exactly linearly with C**. At C = 1e-9 and 1e-10, the maximum X coefficient is 4.9e-7 and 4.9e-8, the prediction difference is 7.1e-6 and 7.1e-7, and the log-loss difference is 2.1e-7 and 2.1e-8.
   - So Model D+X converges to Model D as C → 0: the D and context block is unpenalized. **Verified.** The flag in the JSON is the finite-C tolerance miss, not a penalty leak.
4. **Calibration behavior (development CV at the selected C).**
   - Model D: calibration-in-the-large +0.000, slope 0.973.
   - Model D+X: calibration-in-the-large +0.009, slope 0.988.
   - Both are well calibrated. There is no class reweighting.
5. **Frozen objects.**
   - The private `models_primary.pkl` holds the coefficients, whose hashes are above.
   - X preprocessing is deterministic from development data (median imputation, indicators, scaling, ±5 SD clipping).
   - The test step asserts identical column names.

**Readiness: all gates pass.** Proceed to the one-shot locked test.

## Development-CV estimates (not confirmatory)

L_D 0.1344 vs L_DX 0.1168 nats (relative 13.1%); AUROC 0.774 → 0.849.

These are shown for transparency (see the amendment 1 disclosure). **The confirmatory result is the locked test only.**
