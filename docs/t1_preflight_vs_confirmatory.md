# T1: why the preflight estimate (~13%) became 3.9% in the confirmatory analysis

**EXPLORATORY methodological audit (plan: [t1_exploratory_plan.md](t1_exploratory_plan.md), committed `d687e61` before these runs).** This is **not** a rescue: the confirmatory T1 result stands as **not supported** (preregistration `600f368`).

Setup: expanded MIMIC-IV, GREEN-only, 6 h, X1, one outer repeat, descriptive 1,000-resample intervals. Source: `results/exploratory/t1/`. The confirmatory specification rerun this way gives 3.9% (Δ 0.028 bits), identical to the 3-repeat confirmatory estimate, so the runs are comparable.

## Factorial results (relative Δ vs LL(`Model_D`); relative Δ vs empirical `H(Y|D)` in brackets)

| D×X interactions | Context | Penalty on D/context | Relative Δ | Δ bits (95% CI) | AUROC D → DX |
|---|---|---|---|---|---|
| No | None | Partial (unpenalized D) | 4.5% [4.5%] | 0.033 (0.024–0.042) | 0.776 → 0.821 |
| No | None | Shared | 3.9% [3.9%] | 0.029 (0.017–0.040) | 0.776 → 0.821 |
| No | Era main | Partial | 4.0% [4.0%] | 0.030 (0.021–0.039) | 0.794 → 0.823 |
| No | Era main | Shared | 3.4% [3.4%] | 0.025 (0.015–0.036) | 0.794 → 0.822 |
| **No** | **Full** | **Partial (= confirmatory)** | **3.9% [3.8%]** | 0.028 (0.020–0.036) | 0.805 → 0.829 |
| No | Full | Shared | 2.9% [2.9%] | 0.021 (0.011–0.032) | 0.804 → 0.826 |
| Yes | None | Partial | 15.2% [15.2%] | 0.113 (0.098–0.127) | 0.776 → 0.868 |
| **Yes** | **None** | **Shared (≈ preflight)** | **12.9% [12.9%]** | 0.096 (0.078–0.113) | 0.776 → 0.860 |
| Yes | Era main | Partial | 14.8% [14.7%] | 0.109 (0.094–0.123) | 0.794 → 0.868 |
| Yes | Era main | Shared | 12.5% [12.5%] | 0.092 (0.075–0.111) | 0.794 → 0.861 |
| Yes | Full | Partial | 14.4% [14.1%] | 0.105 (0.090–0.119) | 0.805 → 0.871 |
| Yes | Full | Shared | 11.7% [11.5%] | 0.085 (0.068–0.103) | 0.804 → 0.861 |

## Attribution (preflight-like 12.9% → confirmatory 3.9%; total −9.0 percentage points)

Exact Shapley values over the three binary factors:

| Design change | Contribution | Comment |
|---|---|---|
| **Removing diagnosis × patient-state interactions** | **−9.7 pts** | **Dominant.** With interactions, every context and penalty variant gives 11.7–15.2%; without them, 2.9–4.5% |
| Adding common context (none → era + diagnosis × era + operational) | −0.9 pts | Minor. Era main effects alone account for most of it |
| Unpenalized diagnosis/context (partial penalty) instead of shared | **+1.6 pts** | Works **against** the drop: the partial penalty increases the measured gain (the Q19 finding) |
| Timing cohort (RED excluded → GREEN only) | ≈ 0 | 12.7% vs 12.9% (preflight-like); 3.9% vs 3.9% (confirmatory) |
| Denominator (`H(Y|D)` → LL(`Model_D`)) | ≤ 0.3 pts | Negligible |
| Physiologic cleaning | 0 by construction | Identical in the preflight nested runs and the confirmatory run. Only the superseded fixed-C X0 run predates cleaning |

**One design choice dominates:** removing the diagnosis × X interactions. Under an additive model (one set of patient-state effects shared across diagnoses), most of the preflight gain disappears. With interactions, i.e. patient-state effects allowed to differ by diagnosis, the gain reappears at ≈ 12–15%.

Consistent with this, diverticulitis has a **negative** within-diagnosis Δ under the additive model (−0.033 bits) but a positive one with interactions (+0.063).

**Interpretation limits:**
- The interaction models were **not preregistered**. Their ≈ 14% is exploratory and was estimated on data already used.
- It must not be presented as T1 support.
- It generates one specific, testable hypothesis for new data: *patient-state information relevant to management is diagnosis-specific.*
