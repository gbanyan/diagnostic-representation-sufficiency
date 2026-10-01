# MC-MED primary confirmatory result (frozen)

**Result: SUPPORTED.** Both prespecified success conditions are met.

- **Preregistration:** `mcmed-confirmatory-prereg-v1` + [amendment 1](../docs/amendments/2026-10-01-newton-solver.md) (solver only, made before the test was opened).
- **Evaluation:** one-shot evaluation of the locked test set, 2026-10-01 04:56 CST.
- **Frozen before sensitivities:** this file is committed and tagged `mcmed-confirmatory-primary-result` before any sensitivity analysis runs.

| | Value | 95% CI (patient-cluster bootstrap, 2,000 replicates, seed 20261004) |
|---|---|---|
| Test visits / patients / ICU events | 6,570 / 4,535 / 212 (3.2%) | |
| L_D (Model D: context + soft D_hat) | 0.1260 nats (0.1817 bits) | |
| L_DX (Model D+X: + X_3h) | 0.1038 nats (0.1498 bits) | |
| **ΔL** | **0.0221 nats** | **0.0167 – 0.0276** |
| Δbits | 0.0319 bits | 0.0241 – 0.0399 |
| **RelativeGain** | **17.6%** | 13.7% – 21.2% |

**Criterion (preregistration section 22):**
1. 95% CI lower bound of ΔL > 0: **0.0167 > 0, met.**
2. RelativeGain ≥ 10%: **17.6%, met.**

## Secondary (locked test)

| Metric | Model D | Model D+X | Difference (95% CI) |
|---|---|---|---|
| AUROC | 0.787 | 0.870 | +0.083 (+0.059 to +0.106) |
| AUPRC | 0.117 | 0.336 | +0.218 (+0.156 to +0.277) |
| Brier | 0.0300 | 0.0256 | +0.0043 lower (0.0030 to 0.0058) |
| Calibration-in-the-large | -0.113 | -0.056 | |
| Calibration slope | 1.000 | 1.117 | |

Both models slightly over-predict on the test set (negative calibration-in-the-large; test prevalence is 3.2% vs 3.5% in development). Model D+X has a calibration slope slightly above 1.

**Decile calibration, Model D** (mean predicted vs observed):

| Decile | n | Predicted | Observed |
|---|---|---|---|
| 1 | 657 | 0.005 | <10 events |
| 2 | 657 | 0.010 | <10 events |
| 3 | 657 | 0.013 | <10 events |
| 4 | 657 | 0.016 | <10 events |
| 5 | 657 | 0.020 | <10 events |
| 6 | 657 | 0.024 | 0.020 |
| 7 | 657 | 0.029 | 0.020 |
| 8 | 657 | 0.037 | 0.050 |
| 9 | 657 | 0.057 | 0.070 |
| 10 | 657 | 0.146 | 0.123 |

**Decile calibration, Model D+X:**

| Decile | n | Predicted | Observed |
|---|---|---|---|
| 1 | 657 | 0.002 | <10 events |
| 2 | 657 | 0.004 | <10 events |
| 3 | 657 | 0.006 | <10 events |
| 4 | 657 | 0.008 | <10 events |
| 5 | 657 | 0.011 | <10 events |
| 6 | 657 | 0.015 | <10 events |
| 7 | 657 | 0.021 | 0.023 |
| 8 | 657 | 0.031 | 0.024 |
| 9 | 657 | 0.054 | 0.044 |
| 10 | 657 | 0.187 | 0.199 |

*Deciles with 1–9 events are shown as "<10 events" (small-cell rule). Suppression was applied after the freeze, as a disclosure fix only; no value changed.*

## Integrity

- **Coefficient SHA-256:** D `787930c735fbebdebb888565c3f89f41e18874f1272532e2362de1f85334aa58`; D+X `90d2a87d98406abaa89e8ef5f3e95cf8ffd3ca769d492a5af7c3024eebe562d9` (identical to the readiness report).
- **Immutable private predictions** (y_true, p_D, p_DX; read-only file): SHA-256 `6b02c6c7e38808e41fd93242ff207e9e3a69206cd616aa9f7412db65dea50770`.
- **Nothing was tuned after the predictions were produced.**

## Permitted statement

> At a 3-hour ED landmark, a cross-fitted disease-label representation did not retain all information in the contemporaneous patient state that was predictive of subsequent observed ED-to-ICU disposition.

**Scope of the statement:**
- It concerns an **experimentally generated disease-label representation** (a cross-fitted CCSR body-system posterior), not the clinician's diagnosis.
- It concerns observed ED-to-ICU disposition, not optimal care.
- It holds within the prespecified additive logistic model family.
- It is an independent confirmation in a conceptually matched escalation-of-care target. It is not a replication of MIMIC T3.
