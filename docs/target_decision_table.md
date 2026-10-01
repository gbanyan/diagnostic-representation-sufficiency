# Target decision table

**Status:** preflight classification, 2026-09-29. **The current classes are in the section "Update after Q13 / Q14 / Q17" at the end.** The earlier sections (fixed C = 1) are kept as the audit trail. Awaiting author approval. **No main diagnostic-bottleneck modeling is authorized.**

- **Rules:** [target_sufficiency_framework.md](target_sufficiency_framework.md), pre-specified in `88e34b3`, plus one logged deviation (feature cleaning; see [decision_log.md](decision_log.md)).
- **Numbers:** `results/phase0/sufficiency/`.
- **Classes:** GREEN = suitable for the main experiment; YELLOW = potentially suitable, needs more; BLUE = negative control; RED = do not use.

**Reading the metrics.** Stage B reports two quantities that disagree here:
- **Δ log loss:** the calibrated information gain under fixed L2 (C = 1) with X×D interactions.
- **Within-D AUROC of `Model_DX`:** ranking within a diagnosis. The `Model_D` reference is 0.5 in principle; its out-of-fold values of 0.40–0.46 come from fold-to-fold base-rate shifts.

With more features, AUROC stays high or rises while Δ log loss falls, sometimes below 0. That is overfitting or miscalibration from the fixed, untuned regularization. It is a property of the screening model, not evidence that no information exists. The pre-specified rule requires **both** criteria, so these targets are classed conservatively.

## MIMIC-CDM (D = `D_final`; post-diagnostic; landmark 6 h, with 3 h checked)

| ID | Target | Stage A: within-D heterogeneity | Stage B: X \| D (best set, 6 h) | Stage C: clinical relevance | Leakage / validity | Class |
|---|---|---|---|---|---|---|
| **T1** | Definitive procedure after T (operative vs non-operative management) | `H(Y|D)` = 0.78 bits (`H(Y)` 0.95). Procedure rate: appendicitis 84%, cholecystitis 72%, diverticulitis 21%, pancreatitis ERCP 34% | **X0:** Δ log loss 0.068 bits (95% CI 0.045–0.091) = 8.7% of `H(Y|D)`. **X1:** 8.5% (CI 0.024–0.105). **X2:** 4.9% (CI crosses 0). Within-D AUROC (X1): appendicitis 0.70, cholecystitis 0.77, diverticulitis 0.75, pancreatitis 0.79. The 3 h landmark is nearly identical | Plausibly high: surgery vs non-operative management within a diagnosis. NOT YET VERIFIED by a clinician | Observed behavior, not optimal care (G11). Procedure dates have day resolution: 622 same-day ambiguous and 325 text-only. The sensitivity cohort keeps within-D AUROC (0.61–0.77), but the log-loss gain falls to 5.7% (X0) and ≤ 0 (X1/X2). The 3 h ≈ 6 h result argues against post-landmark leakage | **YELLOW** |
| T2 | Any OR/PACU transfer after T | `H(Y|D)` = 0.47 | Not run | — | **Semantics fail:** only 120 of 767 coded appendectomies have a PACU transfer. It measures documentation, not surgery | **RED** |
| T3 | ICU admission after T | `H(Y|D)` = 0.30. Events per D: 16 / 46 / 24 / 45 | X0: 2.3% (CI crosses 0). X1/X2: Δ log loss < 0 (CI below 0) despite AUROC 0.64 → 0.76 | Plausible (escalation/monitoring) | Too few events per diagnosis (stopping criterion H); the log loss worsens | **RED in MIMIC-CDM** (re-evaluate in a larger cohort, e.g. eICU) |
| T4 | Remaining length of stay (log days) | D explains 21% of variance | R² 0.21 → 0.35 (X1). Within-D R² (X2): appendicitis 0.22, cholecystitis 0.21, diverticulitis 0.04, pancreatitis 0.07 | Weak as a *decision* target; it is a trajectory/resource outcome | Low; the 3 h landmark is similar | **YELLOW** (secondary trajectory target only) |
| **T5** | Organ operated, among operated | `H(Y|D)` = 0.068 bits; ≥ 96% within every D | Δ log loss < 0 for X0–X2 (CI below 0): X adds nothing and only adds variance | Low by design | Low | **BLUE** (negative control) |
| T6 | First abdominal imaging modality | `H(Y|D_final)` = 1.25 bits: appendicitis CT 77% / US 20%; cholecystitis and pancreatitis mixed | Refused: Stage B against `D_final` would reward reconstructing the final diagnosis (G9) | Plausible (examination planning) | Needs `D_hat_t` and a complaint-level reference | **YELLOW** (needs `D_hat_t` design + reference) |
| T7 | Number of abdominal imaging studies | D explains 3.7% of variance | Refused (G9) | Plausible (test burden) | Includes post-procedure imaging; needs a pre-decision window | **YELLOW** (needs `D_hat_t` + a timed definition) |
| T8 | In-hospital death | `H(Y|D)` = 0.012; 0 deaths in appendicitis and cholecystitis, fewer than 10 in each of the other two diagnoses | Not informative | High but rare | Too few events (criterion H) | **RED** |
| T9 | Hours to first PACU | Among 247 with a PACU record | Not run | Timing is plausible in principle | Same PACU semantics failure as T2; selected subset | **RED** |
| T10 | Antibiotic / supportive treatment | Not evaluated | Not evaluated | — | Needs prescriptions/eMAR (not downloaded) | **Cannot evaluate with current data** |

## ER-REASON (no row access)

| ID | Target | Class | Reason |
|---|---|---|---|
| R1 | Disposition given ED diagnosis, from S1 | **Cannot evaluate → YELLOW candidate** | Access pending; needs the historical-note leakage audit and a label-only oracle test |
| R2 | `Treatment_Plan` concepts | **RED** as a primary target | 72 hypothetical single-annotator plans |
| R3 | `Decision_Factors` as S0 exam reference | **YELLOW (validation only)** | 72 cases; differential-organized, which biases toward the bottleneck arm |

## eICU

Full data (200,859 stays, 208 hospitals); see [eicu_sufficiency_preflight.md](eicu_sufficiency_preflight.md).

| ID | Target | Stage A | Stage B | Class | Reason |
|---|---|---|---|---|---|
| E1 | Vasopressor start within 24 h after T = 6 h | `H(Y|D)` = 0.237 of `H(Y)` = 0.245; within-D rate 0.9–15.1% | Cannot evaluate (no X downloaded) | **YELLOW** | Control-like escalation target with large within-D variability; needs X, a site-completeness filter, and a full-data entry-lag audit |
| E1 (24 h) | Same at 24 h | Events 0.6–3.5% | Cannot evaluate | **YELLOW** (likely underpowered per D) | Rare events |
| E2 | New antibiotic within 24 h after T | `I(Y;D)` = 0.004 bits | Cannot evaluate | **YELLOW** | Pre-ICU antibiotics are invisible; documentation completeness varies |
| — | `treatment` table | — | — | **RED** | 99.9% co-saved with problem-list entries |

## Negative controls and positive candidates

- **Negative control (BLUE):** T5, the organ operated. Diagnosis is effectively sufficient, and X adds nothing. It is a weak control, because it is nearly trivial.
  - A stronger control would be a *non-trivial* decision that the diagnosis still settles. None was found among the currently observable MIMIC-CDM targets.
  - Candidates for later: disposition in near-uniform diagnoses (ER-REASON), and antibiotic class given diagnosis (needs prescriptions).
- **Positive candidate (best available):** T1, operative vs non-operative management. It has substantial within-diagnosis variability and consistent within-diagnosis discrimination from contemporaneous state, stable across landmarks. The calibrated gain is below the pre-set threshold, and the reference is observed behavior.
- **Not a positive candidate yet:** no *control-like* target (dose, timing, intensity, escalation) is currently evaluable with valid semantics. T9 (timing) failed on PACU semantics, and T3 (escalation) is underpowered here.

## What would move T1 from YELLOW to GREEN (author decisions needed)

1. **Model specification:** pre-register a regularization choice (e.g. nested CV over C), or a smaller pre-declared feature set, **before** re-running. Tuning after seeing results is not allowed.
2. **Timing:** resolve procedure timing below day resolution. Candidates are MIMIC-IV `poe` order times (e.g. surgery or pre-op orders) or `services` transfers to a surgical service. Otherwise, restrict T1 to decisions on day ≥ 1 and state the resulting selection.
3. **Clinical relevance (Stage C):** clinician review of what drives non-operative management in each diagnosis. This tests whether the recovered information is decision-relevant or reflects provider preference (stopping criterion B).
4. **Semantics statement (G11):** T1 is agreement with observed surgical decisions, not with optimal care.


---

## Update after Q13 / Q14 / Q17 (current classification)

Changes behind this update:
- **Q13:** nested cross-validation, pre-registered in `e15301a` ([model_selection_preflight.md](model_selection_preflight.md)).
- **Q14:** procedure-timing classes ([procedure_timing_audit.md](procedure_timing_audit.md)).
- **Q17:** prescription targets ([prescription_target_audit.md](prescription_target_audit.md)).
- **Cleaning:** [data_cleaning_rules.md](data_cleaning_rules.md).
- **Q15 (clinical relevance, Stage C): DEFERRED — AUTHOR DECISION PENDING.** No target can be GREEN while Stage C is unassessed.

Shares are of `H(Y|D)`, at the 6 h landmark with 3 h in brackets, using X1.

| ID | Target | Stage A | Stage B (nested) | Stage C | Validity | Class |
|---|---|---|---|---|---|---|
| **T1** | Definitive procedure after T (operative vs non-operative) | `H(Y|D)` 0.77 | **Primary (RED excluded, n 2,270): 13.5%** (CI 0.072–0.129 bits) [12.1%]. GREEN-only: 11.2% [10.7%]. AUROC 0.758 → 0.849. Within-D 0.66–0.79, with ≥ 50 per class in every D. Calibration slope ≈ 1 | **Deferred (Q15)** | Timing: 59 RED excluded; 362 YELLOW retained in the primary cohort; robust when YELLOW is dropped. Observed behavior (G11) | **YELLOW — Stage A/B pass; pending Q15.** Most promising disease-specific positive candidate |
| **M6** | Insulin order after T | `H(Y|D)` 0.47; D nearly uninformative (`I(Y;D)` 0.015) | **25.3%** [24.8%]. AUROC 0.619 → 0.850. Within-D 0.78–0.89; ≥ 50 events in 3 of 4 D | Not assessed | Order semantics (includes sliding-scale orders); administration unverifiable for 53% | **YELLOW — strong Stage B.** The recovered information does not depend on the diagnosis at all |
| T3 | ICU admission after T | `H(Y|D)` 0.30 | 19.0% (CI 0.037–0.071). AUROC 0.634 → 0.843 | Not assessed | < 50 events in every D (within-D criterion not assessable) | **YELLOW — underpowered within diagnosis** (was RED under fixed C) |
| M2 | Broad-spectrum antibiotic order after T | `H(Y|D)` 0.43 | 9.8% (X2 10.0%) [9.0%]. AUROC 0.62 → 0.76 | Not assessed | Includes ED continuations | **YELLOW — borderline** |
| T4 | Remaining length of stay | D explains 21% | R² 0.21 → 0.41 | Trajectory, not a decision | Low | **YELLOW — secondary trajectory target** |
| **M5** | Anaerobic coverage among antibiotic orders | `H(Y|D)` 0.44 | **≈ 0** (CI includes 0) [≈ 0] | — | Non-event counts 22–49 per D (limited power) | **BLUE — non-trivial negative control** |
| M3 | Enoxaparin vs SC heparin | `H(Y|D)` 0.067 (near-constant) | ≈ 0 | — | Protocol | **BLUE (trivial)**; downgraded from positive candidate |
| T5 | Organ operated | `H(Y|D)` 0.068 | < 0 (no information; shared-penalty artifact documented) | — | — | **BLUE (trivial)** |
| M1 | New antibiotic order after T | `H(Y|D)` 0.92 | 1.4% (CI touches 0) [0.3%] | — | Mostly order-entry workflow | **BLUE (null control)**, with a semantics caveat |
| M4 | Opioid order after T | `H(Y|D)` 0.75 | 2.5% (CI above 0) [1.6%, CI includes 0] | — | — | **RED**: neither negligible nor meaningful |
| T2 / T9 | PACU transfer / time to PACU | — | — | — | PACU covers ~16% of operations | **RED** |
| T8 | In-hospital death | Too rare | — | — | — | **RED** |
| T6 / T7 | First imaging modality / imaging count | — | Refused against `D_final` (G9) | — | Needs `D_hat_t` | **YELLOW — needs a `D_hat_t` design** |
| T10 | Antibiotic/supportive rubric items | — | — | — | Superseded by M1/M5 | **Superseded** |
| E1 / E2 | eICU vasopressor / antibiotic | See the eICU section | Not evaluated (X deferred by Q17) | — | — | **YELLOW, deferred** |
| R1–R3 | ER-REASON | — | — | — | No access | Unchanged |

**Downgraded because diagnosis (or protocol) appears sufficient:** M3 (pre-registered as a positive candidate; near-constant). M5 and M1 were pre-registered as negative-control candidates and behave as such. No positive candidate was downgraded on the basis of Stage B except M4 (small effect).

**Dissociation under one pipeline:** T1 (+13.5%) and M6 (+25%) versus M5 (≈ 0) and M1 (≈ 0). This supports the preflight premise that the pipeline returns Δ ≈ 0 where state carries no target information. It is **not** evidence about the bottleneck architecture (rule 12).


---

## Update after items 1, 2, 4 (early diagnosis, expanded cohort, Q19)

Author-approved items: [early_diagnosis_preflight.md](early_diagnosis_preflight.md), [expanded_cohort_preflight.md](expanded_cohort_preflight.md), and Q19 in [model_selection_preflight.md](model_selection_preflight.md). Item 3 (a guideline-derived Stage C proxy) awaits the author. Q15 remains DEFERRED.

| ID | CDM (primary) | Q19: unpenalized D | Expanded cohort | CDM-independent | Temporal (≤ 2016 → 2017–2019) | Class |
|---|---|---|---|---|---|---|
| **T1** | 13.5% | **16.6%** | 13.2% (corrected definition) | 12.0% | 5.8%, CI includes 0; AUROC +0.08; both models miscalibrated (slope 0.65) | **YELLOW**: Stage B passes and replicates; temporal-transport caveat; Stage C deferred |
| **T3** | 19.0% (underpowered within D) | 18.5% | 17.1%, within-D criteria **met** (≥ 50 events in 3 D) | 17.1% | **19.6%**, slope 1.11 | **YELLOW, upgraded**: Stage B passes, replicates, and transports; Stage C not assessed |
| **M6** | 25.3% | 25.2% | 26.8% | 24.7% | **21.5%**, slope 1.20 | **YELLOW**: strongest and most robust, but the diagnosis is irrelevant to it (`I(Y;D)` ≈ 0); scope decision Q20 |
| M2 | 9.8% | 9.9% | 8.9% | — | — | **YELLOW, borderline** (below 10% in the expanded cohort) |
| **M5** | ≈ 0 | +1.3% (CI includes 0) | −2.5% (penalty artifact) | −2.8% (CI includes 0) | +0.2% (CI includes 0) | **BLUE**, confirmed across all analyses |
| T5 | < 0 | **+0.2%** (≈ 0) | < 0 (artifact) | — | — | **BLUE** (trivial) |
| **T6b** | `G_hat_0` = 6.7% of `H(Y|D_hat_0)` (CI 0.040–0.102) | — | — | — | — | **YELLOW, moderate**: examination planning under a model-generated `D_hat_0`. The hard label loses ≈ 0.04 bits against the soft differential |

**Diagnosis formation:** t\* is not reached by 6 h (S0 accuracy 0.60, 6 h 0.79). This is a closed-world upper bound.

**Author decision (2026-09-30):** T1 and T3 are both carried forward as primary positive candidates, with M5 as the negative control. See [decision_log.md](decision_log.md).

## Confirmatory result (2026-09-30; preregistration `600f368`)

- **T1 (single primary): NOT SUPPORTED as preregistered.** Relative Δ = 3.9% (CI 2.8–5.0%) is below the 10% threshold, although Δ > 0. See [main_experiment_results.md](main_experiment_results.md).
- **T3:** exploratory only, because T1 failed. Relative Δ = 16.3%.
- **Negative controls:** M5 and T5 ≈ 0. M3 is small but positive.
