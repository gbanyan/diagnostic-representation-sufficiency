# Confirmatory target-sufficiency analysis — results

**Preregistration:** [main_experiment_preregistration.md](main_experiment_preregistration.md), binding commit `600f368` (approved 2026-09-30). Run on 2026-09-30. The code is `src/confirmatory/`. Its partial-penalty validation tests passed before the run, and the leakage checks passed for both cohorts.

**Data-reuse disclosure.** These cohorts were analyzed in the preflight. This is a preregistered specification applied to previously screened data. **No blind holdout exists.**

Results: `results/main/target_sufficiency/*.json` (aggregates; counts below 10 suppressed).

---

## Primary endpoint T1: operative vs non-operative management

**Setup:** expanded MIMIC-IV cohort, GREEN-only, landmark 6 h, X1. Context = era + diagnosis × era + time of day + weekend (unpenalized).

| Quantity | Value |
|---|---|
| n / events | 4,990 / 1,833 |
| Log loss, `Model_D` (≈ `H(Y|D,C)`) | 0.727 bits |
| **Δ = LL_D − LL_DX** | **0.028 bits** (95% CI 0.020–0.036; SD across repeats 0.0003) |
| **Relative Δ** | **3.9%** (95% CI 2.8–5.0%) |
| AUROC D → DX | 0.806 → 0.830 (ΔAUROC CI 0.019–0.030) |
| Brier D → DX | 0.1653 → 0.1573 |
| Calibration slope D / DX | 0.98 / 0.99 (ECE 0.007 / 0.02) |
| Selected C (`Model_DX`), 15 outer folds | 0.003: 7, 0.01: 8 |

**Registered success criteria:**
- (i) CI lower bound > 0: **met**.
- (ii) Relative Δ ≥ 10%: **not met** (the whole CI lies below 10%).

**Conclusion (preregistered rule): the primary positive-target hypothesis is NOT supported.** Contemporaneous patient state adds a statistically detectable but small amount of held-out information about observed operative management beyond diagnosis and common context. It is below the prespecified non-trivial threshold. No re-specification follows.

**Within-diagnosis Δ** (descriptive):

| Diagnosis | n / events | Δ (bits) | AUROC (DX) |
|---|---|---|---|
| Appendicitis | 1,207 / 812 | +0.039 | 0.68 |
| Cholecystitis | 931 / 595 | +0.052 | 0.67 |
| Diverticulitis | 1,065 / 199 | **−0.033** | 0.54 |
| Pancreatitis | 1,787 / 227 | +0.046 | 0.73 |

### Sensitivity analyses (descriptive; all as preregistered)

| # | Analysis | n | Relative Δ | Δ (95% CI) |
|---|---|---|---|---|
| 1 | GREEN + YELLOW | 5,332 | 3.8% | 0.028 (0.021–0.036) |
| 2 | Landmark 3 h | 5,457 | 3.7% | 0.027 (0.018–0.035) |
| 3 | Era main effects only (no diagnosis × era) | 4,990 | 4.1% | 0.030 (0.020–0.039) |
| 4 | Temporal holdout: train ≤ 2016 (3,893), test 2017–2019 (1,097) | 1,097 | −0.7% raw; −0.7% after intercept recalibration | −0.007 (−0.031 to 0.020); recalibrated −0.006 (−0.035 to 0.025) |
| 5 | MIMIC-CDM cohort with X2 (imaging flags) | 1,908 | 4.8% | 0.039 (0.021–0.055) |

- The timing-sensitivity flag (|Δ| change > 50% between GREEN and GREEN+YELLOW) is **not** triggered.
- **Temporal holdout:** AUROC is 0.72 → 0.74 (raw), and both models are miscalibrated in the later period (slope ≈ 0.65). **No temporal transport of the incremental information is shown.**

## Secondary endpoint T3: observed ICU transfer (escalation of care)

Because T1 failed, **T3 is reported as exploratory only and cannot rescue T1** (preregistration section R).

| Quantity | Value |
|---|---|
| n / events | 5,412 / 276 |
| Log loss `Model_D` | 0.278 bits |
| Δ | 0.045 bits (95% CI 0.035–0.056) |
| Relative Δ | 16.3% (CI 12.9–19.5%) |
| AUROC D → DX | 0.663 → 0.825 (ΔAUROC CI 0.129–0.190) |
| Calibration slope D / DX | 0.80 / 0.99. `Model_D` is at the edge of the [0.8, 1.25] flag range (0.802, not flagged) |

Within-D Δ (events): appendicitis +0.006 (15), cholecystitis +0.021 (60), diverticulitis +0.053 (57), pancreatitis +0.088 (144).

**Semantics:** observed ICU transfer reflects deterioration, clinician judgment, escalation practice, and operational constraints. It is **not** optimal disposition, and no causal or normative claim is made.

## Negative controls (interpretive; not part of the success criterion)

| Control | n (events) | Δ (95% CI) | Relative Δ (CI) | Behaved as a negative control? |
|---|---|---|---|---|
| M5 anaerobic coverage | 2,638 (2,425) | 0.0014 (−0.003 to 0.004) | 0.4% (−0.7 to 1.1%) | **Yes** (≈ 0) |
| T5 organ operated | 1,323 (multinomial) | −0.0006 (−0.005 to 0.002) | −0.5% (−3.9 to 1.6%) | **Yes** (≈ 0). **Flag:** one of three repeats reported non-convergence (near-complete separation, e.g. diverticulitis → colon). Estimates are consistent across repeats |
| M3 enoxaparin vs SC heparin | 3,881 (58) | 0.006 (0.001–0.011) | 5.1% (1.1–9.4%) | **No**: small but CI above 0. With 58 events the estimate is imprecise |

---

## Post-hoc observations (NOT preregistered; hypotheses for a future separately registered analysis)

1. **The preflight-to-confirmatory drop in T1** (≈ 13% → 3.9%) coincides with the registered removal of diagnosis × X interactions and the addition of context.
   - The era-main-effects-only sensitivity (4.1%) makes diagnosis × era an unlikely cause.
   - The negative within-diagnosis Δ for diverticulitis suggests that patient-state effects may differ by diagnosis, and a shared (additive) X effect may fit poorly.
   - **This is not tested here.** Testing it requires a new preregistration (e.g. "D × X interactions" as a separate hypothesis). It would be exploratory given the data reuse.
2. **M3 changed from ≈ 0 (preflight, shared penalty) to a small positive Δ** under the registered specification. It is not interpreted clinically (Q15 remains deferred).

## What this analysis permits and does not permit

**Permitted (T1, as registered):**
> "Under the preregistered additive specification, contemporaneous patient state adds statistically detectable but small held-out predictive information (3.9% of the conditional log loss) about observed operative management beyond diagnosis and calendar/operational context. This is below the prespecified threshold for a non-trivial gain, and it did not transport to a later period."

**Not permitted:**
- that T1 variation is clinically meaningful (Q15 is DEFERRED);
- that richer models provide better care;
- that observed management was optimal;
- that diagnosis is generally sufficient or insufficient;
- that foundation models are superior;
- any causal claim;
- any claim about a diagnostic-bottleneck (representation) cost;
- any temporal transportability.

## Implications for the project (for the author's decision)

- **The registered positive-target hypothesis failed on T1.** Per the preregistration, T3's larger effect cannot substitute for it.
- Next steps require **author decisions**. Options include:
  - (a) stop the target-sufficiency line for T1 as registered;
  - (b) register a new, explicitly **exploratory** analysis of D × X heterogeneity for T1;
  - (c) register T3 as the primary endpoint of a **new** study. It cannot be confirmatory on these data, because the data have been used.

---

## FROZEN interpretation (author instruction, 2026-09-30)

**T1: completed confirmatory result.**
- Incremental patient-state information beyond diagnosis is statistically detectable: Δ = 0.028 bits, 95% CI 0.020–0.036; AUROC 0.806 → 0.830.
- The prespecified substantive criterion was **not met**: relative Δ = 3.9%, 95% CI 2.8–5.0%, below 10%.
- **T1 therefore does not support the primary positive hypothesis.** For this dataset and target, **diagnosis + common context is approximately sufficient under the prespecified criterion.**
- All prespecified sensitivity analyses (3.7–4.8%) and the temporal holdout (≈ 0) are preserved above.
- T1 is **not** described as positive, rescued, nearly significant, clinically meaningful, or evidence that diagnosis is insufficient.

**T3: secondary endpoint, hypothesis-generating.**
- T3 is a prespecified secondary endpoint **whose confirmatory status was lost under the hierarchical testing rule after T1 failed.**
- Observed exploratory result: relative gain ≈ 16.3%; AUROC ≈ 0.66 → 0.83.
- **Permitted interpretation:** contemporaneous patient state appears to contain substantial information about **observed escalation of care** beyond diagnosis.
- ICU transfer is not optimal care.
- A new confirmation study is designed in [t3_followup_design.md](t3_followup_design.md). It is not run.

## Target summary matrix

| Target | Role | Prespecified status | Incremental gain (relative Δ; Δ 95% CI) | Interpretation |
|---|---|---|---|---|
| T1 operative vs non-operative | Primary endpoint | Confirmatory: **not supported** (criterion (ii) failed) | 3.9% (Δ 0.020–0.036 bits) | Detectable but small. Diagnosis + context is approximately sufficient under the prespecified criterion. No temporal transport |
| T3 observed ICU transfer | Secondary endpoint | **Confirmatory status lost** (hierarchy); hypothesis-generating | 16.3% (Δ 0.035–0.056 bits) | Patient state appears to carry substantial information about observed escalation. Needs independent confirmation |
| M5 anaerobic coverage | Negative control | Descriptive | 0.4% (Δ −0.003 to 0.004) | ≈ null, as expected. A useful control |
| T5 organ operated | Negative control (trivial) | Descriptive | −0.5% (Δ −0.005 to 0.002) | ≈ null, as expected. One repeat had a convergence flag (near-separation) |
| M3 enoxaparin vs SC heparin | Negative control (check) | Descriptive | 5.1% (Δ 0.001–0.011) | **Not** a successful negative control. Small positive estimate with **only 58 events**; not over-interpreted |

**Pattern: target-dependent sufficiency, not universal superiority of richer state.**
- Under one fixed specification, the information added by patient state ranges from ≈ 0 (M5, T5) through small (T1, M3) to substantial (T3, exploratory).
- Only T1 was a confirmatory test, and it did not meet its substantive threshold.
