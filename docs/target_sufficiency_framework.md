# Target sufficiency framework

**Status:** pre-specified on 2026-09-29, **before** any outcome-level statistic was computed. Changes after results are seen must be logged in [decision_log.md](decision_log.md) as deviations.

## Central principle

A disease label can be **lossy with respect to the patient state** and still be **sufficient for a particular clinical target**. For patient state X, diagnosis D, and target Y, D is sufficient for Y if

```
P(Y | X, D) ≈ P(Y | D)        equivalently   I(Y ; X | D) ≈ 0
```

A diagnostic-bottleneck cost is expected only where `I(Y ; X | D) > 0` **and** the extra information is clinically meaningful. This phase only asks whether such targets exist.

**Research rule 11 (added to the README):** "Diagnosis is lossy" is not a justification for this experiment. The empirical condition is that *diagnosis discards recoverable information relevant to the chosen target.*

## Three diagnosis objects, never interchangeable

| Symbol | Meaning | Allowed use |
|---|---|---|
| `D_final` | Final / discharge diagnosis | Terminal reference; stratification; the **post-diagnostic** question "once diagnosis is established, is it sufficient for Y?" |
| `D_t` | Diagnosis or differential documented at time *t* | Early-decision analyses, only if a dataset records it with valid timing (none verified so far) |
| `D_hat_t` | Model-generated diagnosis from `S_t` | Early-decision analyses, always labelled "experimentally imposed bottleneck" |

For early examination planning, `D_final` is used only as a terminal reference or stratifier. It is never used as the impression available before the test was ordered.

## Three-stage test per target

**Stage A — residual variability.**
- Categorical Y: `H(Y | D)` in bits, overall and per diagnosis, plus the majority-class share per diagnosis.
- Continuous Y: `Var(Y | D)` and the within-diagnosis IQR.

**Stage B — recoverability.** Compare, on the **same** cohort, patient-grouped folds, landmark time, and outcome definition:

- `Model_D`: D → Y. For categorical Y this is logistic regression on D one-hot (≈ per-diagnosis base rates). For continuous Y it is linear regression on D one-hot.
- `Model_DX`: (D, X, X×D) → Y, using L2-regularized logistic or ridge regression with fixed hyperparameters (C = 1.0, α = 1.0; **no tuning**). Features are median-imputed with missing indicators and standardized, all fitted within each training fold.

Evaluation uses 5-fold `StratifiedGroupKFold` grouped by `subject_id` with seed 20260929, using out-of-fold predictions. For binary targets it reports log loss (bits), Brier score, and AUROC; for continuous targets, MSE and R². Each is reported overall and within each diagnosis.

`Δ = perf(Model_DX) − perf(Model_D)`, with a 95% interval from 1,000 subject-level bootstrap resamples of the out-of-fold predictions (paired). The log-loss improvement in bits per case is reported as an **estimate of the recoverable part of `I(Y ; X | D)` under these models**. It is not a direct estimate of mutual information.

Nested feature sets are evaluated in order to trace a sufficiency gradient over stages:

| Set | Content (MIMIC-CDM) | Stage analogue |
|---|---|---|
| X0 | Age, sex, triage vitals, acuity, pain, prior admissions | S0/S1 (structured) |
| X1 | X0 + first labs before the landmark | S2 |
| X2 | X1 + keyword flags from radiology findings charted before the landmark | S3 |

**Stage C — clinical relevance.** This is judged per target against a named decision: whether the recovered information would change a treatment, test, timing, intensity, or safety decision. Where it is unclear, the target is marked *Needs clinician review*.

## Pre-specified classification thresholds

| Condition | Rule |
|---|---|
| A. Near-deterministic given D | `H(Y | D) < 0.10` bits **or** majority class ≥ 97% in every diagnosis |
| C. Negligible recoverability | The 95% interval of Δlog-loss includes 0, **or** Δlog-loss < 2% of `H(Y | D)` |
| Meaningful recoverability | Δlog-loss ≥ 10% of `H(Y | D)` **and** within-D ΔAUROC ≥ 0.05 in at least one diagnosis with ≥ 50 cases per class |
| D. Leakage-dependent | The gain disappears (drops by more than half) when features are cut to an earlier landmark or to a sensitivity cohort that excludes same-day ambiguous procedures |
| H. Too small | Fewer than 50 events or fewer than 50 non-events in the analysed cohort |

Stopping criteria B (noise or provider preference), E (unclear relevance), F (timing cannot be aligned), and G (the reference is only observed behavior and cannot support the claim) are judged qualitatively and recorded with reasons.

## Classes

- **GREEN:** suitable for the main experiment. It has residual variability and meaningful, leakage-robust recoverability, and it is clinically relevant.
- **YELLOW:** potentially suitable, but needs clinician annotation, stronger temporal validation, a better reference, or more data.
- **BLUE:** a negative control, where diagnosis is approximately sufficient (condition A holds, or recoverability is negligible, for a clinically sensible reason).
- **RED:** do not use.

A convincing main result would be a **dissociation**: Δ ≈ 0 on a BLUE target together with a clinically meaningful Δ on a GREEN target.

## Interpretation rule

Never write "diagnosis is insufficient because the richer model performs better." This preflight establishes at most:

1. the target has residual within-diagnosis variability;
2. legitimate contemporaneous state predicts part of it;
3. the recovered information is plausibly clinically relevant.

It does **not** establish (4), that a bottleneck architecture pays a representation cost beyond model capacity. That is the future main experiment.

## Temporal sufficiency plan

For a target Y at stage *t*:

```
G_t     = Perf(D_t, X_t -> Y) − Perf(D_t -> Y)            (if D_t observed with valid timing)
G_hat_t = Perf(D_hat_t, X_t -> Y) − Perf(D_hat_t -> Y)    (D_hat_t = model-generated, labelled as such)
```

- **In this phase (MIMIC-CDM):** `D_final` with nested X0 → X2 at a fixed landmark, plus a second landmark as a leakage-sensitivity check. This measures the post-diagnostic `G` for treatment and trajectory targets.
- **Not in this phase:** `G_hat_t` for examination targets. It needs a `D_hat_t` model and valid early states. It is planned for after author approval.

**Provisional hypothesis, not a result:**
- `G_t` may be larger early for examination planning.
- It may shrink for categorical decisions as the diagnosis stabilizes.
- It may remain above 0 for individualized control decisions.
