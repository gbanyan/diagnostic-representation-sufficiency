# Target suitability matrix

**Pre-specification (committed before any outcome statistics).** The candidate list, the definitions, and the primary landmark were fixed on 2026-09-29. Cells marked UNKNOWN / NOT YET VERIFIED are filled only from computed evidence, with a pointer to it. The rules are in [target_sufficiency_framework.md](target_sufficiency_framework.md).

## Shared definitions (MIMIC-CDM)

- **Anchor `t0`:** earliest ED arrival (`edstays.intime`). Fallbacks are `admissions.edregtime`, then `admittime`.
- **Primary landmark `T = t0 + 6 h`.** The sensitivity landmark is `t0 + 3 h`.
- **Cohort at T:** alive and in hospital at T, with no OR/PACU transfer before T. For T1, the target procedure's ICD date must not be before T's calendar date.
- **Same-day ambiguity:** an ICD procedure on T's date with no PACU time is retained, and a sensitivity analysis excludes it.
- **D:** `D_final` (the CDM pathology). All MIMIC-CDM Stage B analyses are **post-diagnostic**: "once the diagnosis is established, is it sufficient for Y?"
- **X:** nested sets X0, X1, X2 as defined in the framework. Every feature timestamp must be ≤ T.

## Candidate targets

| ID | Dataset | Target (after T) | Decision type | Diagnosis representation | Within-D heterogeneity | Incremental X\|D value | Clinical relevance | Leakage risk | Proposed role |
|---|---|---|---|---|---|---|---|---|---|
| T1 | MIMIC-CDM | Pathology's definitive procedure (appendectomy / cholecystectomy / colectomy or drainage / ERCP), ICD- or discharge-coded | Categorical treatment: operative vs non-operative | `D_final` | UNKNOWN | UNKNOWN | Plausible (management strategy); NOT YET VERIFIED | Procedure time has day resolution only | UNKNOWN |
| T2 | MIMIC-CDM | Any OR/PACU transfer | Categorical treatment, time-stamped | `D_final` | UNKNOWN | UNKNOWN | As T1; procedure-agnostic | Low (transfer times) | UNKNOWN |
| T3 | MIMIC-CDM | ICU admission | Escalation / deterioration (trajectory) | `D_final` | UNKNOWN | UNKNOWN | Plausible (monitoring / escalation) | Low (transfer times) | UNKNOWN |
| T4 | MIMIC-CDM | Remaining length of stay, log days | Trajectory / resource | `D_final` | UNKNOWN | UNKNOWN | Weak as a decision target | Low | UNKNOWN |
| T5 | MIMIC-CDM | Organ of operation among operated (appendix / gallbladder / colon) | Categorical treatment | `D_final` | UNKNOWN | UNKNOWN | Low; sanity check | Low | Negative-control candidate |
| T6 | MIMIC-CDM | First abdominal imaging modality (US / CT / MRI) | Examination planning | `D_final` as **stratifier only**; needs `D_hat_t` | UNKNOWN | Not evaluable with `D_final` (G9) | Plausible | Imaging order vs report time | UNKNOWN |
| T7 | MIMIC-CDM | Number of abdominal imaging studies during stay | Examination burden | `D_final` as stratifier only | UNKNOWN | Not evaluable with `D_final` | Plausible (test burden) | Includes post-procedure imaging | UNKNOWN |
| T8 | MIMIC-CDM | In-hospital death | Trajectory | `D_final` | UNKNOWN | UNKNOWN | High, but rare | Low | UNKNOWN |
| T9 | MIMIC-CDM | Hours from anchor to first PACU, among operated | Timing (control-like) | `D_final` | UNKNOWN | UNKNOWN | Plausible; provider and OR-availability noise likely | Low | UNKNOWN |
| T10 | MIMIC-CDM | Antibiotic / supportive treatment (rubric items) | Categorical treatment | `D_final` | Cannot evaluate with current data | Cannot evaluate | — | — | Cannot evaluate: needs prescriptions/eMAR (not downloaded) |
| E1 | eICU | Vasopressor infusion start within 24 h after landmark | Treatment escalation | Problem list at landmark (`D_t`-like, entry-time semantics) | UNKNOWN | Cannot evaluate: X (labs, vitals) not downloaded | Plausible | Batch-saved diagnoses (see gate record) | UNKNOWN |
| E2 | eICU | New antibiotic order within 24 h after landmark | Treatment | Problem list at landmark | UNKNOWN | Cannot evaluate yet | Plausible | As E1 | UNKNOWN |
| R1 | ER-REASON | Disposition (admit / discharge) | Management | ED diagnosis | Cannot evaluate: access pending | Cannot evaluate | Plausible | End-of-visit note | Cannot evaluate with current data |
| R2 | ER-REASON | `Treatment_Plan` concepts | Treatment | ED diagnosis | Cannot evaluate: access pending | Cannot evaluate | — | Retrospective annotation | Cannot evaluate with current data |

## Results

*Filled 2026-09-29.* The pre-specified table above is kept unchanged as the audit trail. Sources:
- MIMIC-CDM: `results/phase0/sufficiency/mimic_cdm/` (`stage_a_L6.json`, `full/stage_b_*_L6*.json`, with the 3 h landmark in `*_L3*`).
- eICU: `results/phase0/sufficiency/eicu/`.

| ID | Dataset | Target | Decision type | Diagnosis representation | Within-D heterogeneity | Incremental X\|D value | Clinical relevance | Leakage risk | Proposed role |
|---|---|---|---|---|---|---|---|---|---|
| T1 | MIMIC-CDM | Definitive procedure after T | Categorical treatment | `D_final` (post-diagnostic) | `H(Y|D)` = 0.78 bits; rates 84 / 72 / 21 / 34% | Δ log loss 8.7% of `H(Y|D)` (X0), 8.5% (X1), 4.9% (X2, CI crosses 0). Within-D AUROC 0.70–0.79 | Needs clinician review | Day-resolution timing (622 same-day, 325 text-only). Stable at 3 h vs 6 h. Sensitivity: AUROC kept, log-loss gain ≤ 5.7% | Needs clinician review; **YELLOW** positive candidate |
| T2 | MIMIC-CDM | Any PACU after T | Categorical treatment | `D_final` | `H(Y|D)` = 0.47 | Not run | — | PACU present for only 120 / 767 coded appendectomies | **Unsuitable (RED)** |
| T3 | MIMIC-CDM | ICU admission after T | Escalation | `D_final` | `H(Y|D)` = 0.30; 16–46 events per D | Δ log loss ≤ 2.3% (X0); < 0 with X1/X2 | Plausible | Low | **Unsuitable here (RED)**; underpowered |
| T4 | MIMIC-CDM | Remaining LOS | Trajectory | `D_final` | D explains 21% of variance | R² 0.21 → 0.35; within-D up to 0.22 | Weak as a decision | Low | **Exploratory (YELLOW)** |
| T5 | MIMIC-CDM | Organ operated | Categorical treatment | `D_final` | `H(Y|D)` = 0.068 bits (near-deterministic) | Δ < 0 (no information) | Low | Low | **Negative control (BLUE)** |
| T6 | MIMIC-CDM | First imaging modality | Examination | `D_final` as stratifier only | `H(Y|D_final)` = 1.25 bits | Not evaluable with `D_final` (G9) | Plausible | Order vs report time | **Needs `D_hat_t` design (YELLOW)** |
| T7 | MIMIC-CDM | Imaging count | Examination burden | `D_final` as stratifier only | D explains 3.7% of variance | Not evaluable with `D_final` (G9) | Plausible | Post-procedure studies included | **Needs `D_hat_t` + timed definition (YELLOW)** |
| T8 | MIMIC-CDM | In-hospital death | Trajectory | `D_final` | `H(Y|D)` = 0.012 | — | High | — | **Unsuitable (RED)**: too rare |
| T9 | MIMIC-CDM | Hours to PACU | Timing | `D_final` | n = 247 | Not run | Plausible | PACU semantics fail | **Unsuitable (RED)** |
| T10 | MIMIC-CDM | Antibiotic / supportive treatment | Categorical treatment | `D_final` | — | — | — | — | **Cannot evaluate with current data** |
| R1–R3 | ER-REASON | See the ER-REASON preflight | — | — | Cannot evaluate (no access) | Cannot evaluate | — | High | See [er_reason_sufficiency_preflight.md](er_reason_sufficiency_preflight.md) |
| E1–E2 | eICU | See the eICU preflight | — | Problem list at landmark | See the eICU preflight | Cannot evaluate (X not downloaded) | — | Batch-saved diagnoses | See [eicu_sufficiency_preflight.md](eicu_sufficiency_preflight.md) |

## Update after Q13 / Q14 / Q17 (2026-09-29)

The current classes are in [target_decision_table.md](target_decision_table.md) (section "Update after Q13 / Q14 / Q17"). Medication targets added from [prescription_target_audit.md](prescription_target_audit.md):

| ID | Dataset | Target | Decision type | Diagnosis representation | Within-D heterogeneity | Incremental X\|D value (nested CV, 6 h, X1) | Clinical relevance | Leakage risk | Proposed role |
|---|---|---|---|---|---|---|---|---|---|
| M1 | MIMIC-CDM | New systemic antibiotic order after T | Categorical treatment | `D_final` | `H(Y|D)` 0.92 | 1.4% of `H(Y|D)`, CI touches 0 | Low: order-entry workflow | Low (order times via POE, 99.5% linked) | Negative control (null) |
| M2 | MIMIC-CDM | Broad-spectrum order after T | Treatment intensity | `D_final` | 0.43 | 9.8% (X2 10.0%) | Not assessed | Includes ED continuations | Exploratory (borderline) |
| M3 | MIMIC-CDM | Enoxaparin vs SC heparin | Agent choice | `D_final` | 0.067 (near-constant) | ≈ 0 | Protocol | Low | Negative control (trivial) |
| M4 | MIMIC-CDM | Opioid order after T | Categorical treatment | `D_final` | 0.75 | 2.5% (6 h), 1.6% (3 h) | Low | Low | Unsuitable |
| M5 | MIMIC-CDM | Anaerobic coverage among antibiotic orders | Treatment class | `D_final` | 0.44 | ≈ 0 | Protocol-like | Low | **Negative control (non-trivial)** |
| M6 | MIMIC-CDM | Insulin order after T | Control-like (glycemic) | `D_final` (nearly uninformative) | 0.47 | **25.3%** | Not assessed | Order semantics | Needs clinician review |

T1 after timing filtering (primary, RED excluded): 13.5% of `H(Y|D)`. T3 with nested CV: 19.0%, but underpowered within diagnosis.
