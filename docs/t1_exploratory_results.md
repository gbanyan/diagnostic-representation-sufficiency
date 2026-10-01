# T1 residual signal: exploratory heterogeneity results

**EXPLORATORY** (plan committed `d687e61` before the runs). There is one outer repeat; intervals are descriptive, and no p-values are given. The confirmatory T1 conclusion (not supported) is unchanged. No clinical interpretation is made (**Q15 DEFERRED**).

Setup: confirmatory specification (additive, full context, partial penalty), expanded MIMIC-IV, GREEN-only, 6 h, X1. Overall Δ = 0.028 bits (3.9%). Source: `results/exploratory/t1/`.

## E1. Where the residual lives

| Stratum | n (events) | Δ (bits) | AUROC DX within stratum |
|---|---|---|---|
| Appendicitis | 1,207 (812) | +0.039 | 0.68 |
| Cholecystitis | 931 (595) | +0.052 | 0.67 |
| Diverticulitis | 1,065 (199) | **−0.033** | 0.54 |
| Pancreatitis | 1,787 (227) | +0.046 | 0.73 |
| Era 2008–10 | 1,153 (281) | +0.018 | — |
| Era 2011–13 | 1,375 (533) | +0.037 | — |
| Era 2014–16 | 1,365 (588) | +0.045 | — |
| Era 2017–19 | 1,097 (431) | +0.008 | — |

## E2. Diagnosis-specific patient-state effects (interaction model, exploratory)

Within-D Δ: appendicitis +0.095, cholecystitis +0.158, diverticulitis +0.063, pancreatitis +0.109 bits. Every diagnosis gains once X effects may differ by diagnosis (see [t1_preflight_vs_confirmatory.md](t1_preflight_vs_confirmatory.md)).

## E3. Feature groups (additive model)

| Group | Only this group: relative Δ (Δ, 95% CI) | All X minus this group: relative Δ |
|---|---|---|
| Demographics / history | 1.8% (0.013, 0.008–0.018) | 3.1% |
| Triage vitals | 0.4% (0.003, 0.001–0.005) | 3.7% |
| Inflammatory labs | 0.4% (0.003, 0.000–0.006) | 3.5% |
| **Hepatobiliary / pancreatic labs** | **1.7%** (0.013, 0.006–0.018) | **2.6%** (largest drop) |
| Renal / metabolic labs | −0.1% (−0.001, −0.002 to 0.000) | 4.0% |
| Hematologic / other labs | 0.9% (0.007, 0.002–0.011) | 3.5% |

## E4. Measured values vs test-ordering pattern

| X representation | Relative Δ | Δ (95% CI) |
|---|---|---|
| Values only (no missing indicators) | 4.0% | 0.029 (0.021–0.038) |
| Missing indicators only (which tests were drawn by T) | −0.1% | −0.001 (−0.002 to 0.001) |

## E5. Complication status (finer, discharge-coded diagnosis; explanatory stratifier only)

Subtype counts (complicated / uncomplicated): appendicitis 412 / 795; cholecystitis 341 / 590; diverticulitis 313 / 752; pancreatitis 99 / 1,688.

| Model_D includes diagnosis × complication subtype? | LL(`Model_D`) | Δ from X (bits) | Within-D Δ (appendicitis / cholecystitis / diverticulitis / pancreatitis) |
|---|---|---|---|
| No (confirmatory) | 0.728 | 0.028 | 0.039 / 0.052 / −0.033 / 0.046 |
| Yes | 0.690 | 0.024 (0.016–0.031) | **0.013** / 0.040 / −0.018 / 0.048 |

## E6. Imaging findings (MIMIC-CDM cohort)

X1: 4.5% (0.037, 0.020–0.053). X2 (adds imaging flags): 4.7% (0.038, 0.020–0.054). Imaging flags add ≈ 0.2 pts.

## Reading, against the categories fixed in the plan

| Category | Evidence | Assessment |
|---|---|---|
| (1) Within-diagnosis clinical heterogeneity captured by a finer diagnosis | E5: for appendicitis, adding complication status removes about two-thirds of X's contribution. Cholecystitis and pancreatitis are largely unchanged | **Partly**, and mainly for appendicitis. There, X approximates information that a finer (discharge-coded) diagnosis label also carries |
| (2) Practice-pattern heterogeneity | E4: *test ordering* (missingness) carries ≈ 0. Practice variation in the *operative decision itself* cannot be separated from clinical heterogeneity without Q15 | **Not supported for test ordering**; undetermined otherwise |
| (3) Residual context | E1: Δ varies by era (0.008 in 2017–19 vs 0.045 in 2014–16); the temporal holdout does not transport | **Present**: the small signal is era-unstable |
| (4) Noise | The overall Δ interval excludes 0; renal/metabolic and missingness-only are ≈ 0 | **Not pure noise overall**, but small. Its localization (demographics/history, hepatobiliary/pancreatic labs) is modest |

**Main exploratory finding:** under the preregistered additive specification, the residual is small, era-unstable, and partly a proxy for complication status (appendicitis). The large preflight signal depended on **diagnosis-specific** patient-state effects. That is a separate, unregistered hypothesis.
