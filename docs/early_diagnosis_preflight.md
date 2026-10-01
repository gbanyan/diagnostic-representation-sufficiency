# Early diagnosis (`D_hat_t`) and diagnosis-formation preflight

**Pre-registered 2026-09-29, before any computation.** Part of the preflight, not the main experiment. It uses no LLM and no human review.

## Purpose

1. **Diagnosis-formation curve:** how recoverable is `D_final` from what is known at each stage? This characterizes when a disease label becomes a reasonable summary (the conceptual *t\** of the original brief, section 11).
2. **Examination-target preflight:** produce an **experimentally imposed** model diagnosis `D_hat_t` so that examination targets can be screened without using `D_final` (which fails G9):

   `G_hat_t = Perf(D_hat_t, X_t → Y) − Perf(D_hat_t → Y)`

**`D_hat_t` is a model-generated experimental bottleneck. It is not a clinician's diagnosis, and it is never described as one.**

## Stages (MIMIC-CDM landmark table; ED-anchored admissions only)

**Cohort (leakage guard, specified before any result):** ED-anchored admissions in the 6 h landmark cohort (alive in hospital, no PACU before 6 h) whose T1 timing class is **not RED**. This keeps any S3h/S6h feature from postdating an operation. T6b uses the same cohort, which is the population in which `D_hat_0` is available.

| Stage | Information |
|---|---|
| S0 (t = ED arrival) | X0 (age, sex, prior admissions, arrival mode, triage vitals, acuity, pain) + the triage **chief complaint** text |
| S3h | S0 + labs ≤ 3 h + imaging flags from reports signed ≤ 3 h (X2 at L3) |
| S6h | Same at 6 h (X2 at L6) |

**Chief complaint:** `ed/triage.chiefcomplaint`. TF-IDF on word unigrams and bigrams, `min_df = 5`, fitted within training folds only. It is recorded at triage, so it is available at S0.

## Diagnosis model

- Multinomial L2 logistic regression.
- Nested CV exactly as in [model_selection_preflight.md](model_selection_preflight.md): outer 5 folds × 3 repeats, inner 4 folds, the same C grid and selection rule. Stratified by `D_final`, grouped by `subject_id`.
- **Cross-fitted:** each patient's `D_hat_t` comes from a model that did not train on that patient.
- **Closed world:** the task is a 4-class problem among cases already known to have one of four pathologies. Recoverability is therefore **optimistic** relative to a real ED differential. It is reported as such.

## Metrics per stage

- log loss in bits, and `H(D_final)` − log loss (information recovered);
- accuracy and macro one-vs-rest AUROC;
- per-class recall;
- mean top-class probability and mean predictive entropy.

**Pre-specified t\*:** the earliest stage at which accuracy ≥ 0.80 **and** mean top-class probability ≥ 0.80. If no stage qualifies, t\* is "not reached by 6 h".

## Examination target T6b (replaces T6 for the `D_hat` design)

- **Y:** the modality of the **first CT / ultrasound / MRI order** (POE `order_type = Radiology`, subtype `CT Scan`, `Ultrasound`, or `MRI`) placed after ED arrival and within 24 h. Classes: CT, US, MRI. MRI is merged into "other" if it has fewer than 50 cases.
- **Decision point:** S0. The cohort is ED-anchored admissions with such an order.
- **The subtype vocabulary** is checked (counts only) before the target is built.

**Comparisons at S0 (nested CV):**

| Condition | Inputs → Y | Role |
|---|---|---|
| (a) Bottleneck | `D_hat_0` one-hot (argmax) | |
| (b) Bottleneck + state | `D_hat_0` + S0 features | **`G_hat_0` = (b) − (a)** |
| (c) Direct | S0 features without `D_hat` | |
| (d) Oracle reference | `D_final` | Reported **only** as an upper reference, labelled oracle; never used as `D_t` |
| (e) Soft differential | `D_hat_0` class probabilities | Secondary |

`D_hat_0` is fixed from the cross-fitted diagnosis model, which never uses Y, so there is no target leakage.

**Classification:** the framework thresholds apply to `G_hat_0`, with `H(Y | D_hat_0)` in place of `H(Y|D)`.

## Not done here

- No LLM-generated `D_hat` (it would need local inference, e.g. on dgx-lab, and a data-location decision).
- No free-text HPI (it is discharge-derived and leaks).
- No main bottleneck architecture.

---

## Results (2026-09-29)

Source: `results/phase0/sufficiency/mimic_cdm/early_diagnosis/`. Cohort: 1,595 ED-anchored admissions after the leakage guard.

### Diagnosis-formation curve (closed-world, 4 classes; `H(D_final)` = 1.80 bits)

| Stage | Accuracy | Information recovered (share of `H(D)`) | Macro AUROC | Mean top-class probability | Recall: appendicitis / cholecystitis / diverticulitis / pancreatitis |
|---|---|---|---|---|---|
| S0 (triage + chief complaint) | 0.60 | 0.40 bits (22%) | 0.79 | 0.61 | 0.86 / 0.54 / 0.12 / 0.31 |
| S3h | 0.75 | 0.86 bits (48%) | 0.90 | 0.76 | 0.88 / 0.72 / 0.20 / 0.76 |
| S6h | 0.79 | 0.97 bits (54%) | 0.92 | 0.79 | 0.90 / 0.78 / 0.25 / 0.76 |

- **t\*: not reached by 6 h** (both criteria must be ≥ 0.80).
- The SD of accuracy across the 3 repeats is ≤ 0.006.

**Reading:**
- Even in this closed-world, outcome-selected setting, which is an **upper bound** on real ED recoverability, the diagnosis is still forming at 6 h.
- Diverticulitis is poorly recovered. The imaging-flag list has no diverticulum-specific term, and the CDM findings text redacts the disease name. This is recorded, not changed after the fact.

### T6b: first CT / US / MRI order modality, decided at S0

Cohort: 1,200 (CT 671, US 468, MRI 61). `H(Y)` = 1.217 bits; `H(Y | D_hat_0)` = 1.158 bits.

| Condition | Log loss (bits) | Macro AUROC |
|---|---|---|
| (a) Bottleneck: `D_hat_0` (hard label) | 1.165 | 0.63 |
| (e) Soft `D_hat_0` probabilities | 1.127 | 0.70 |
| (b) `D_hat_0` + S0 features | 1.088 | 0.73 |
| (c) Direct: S0 features, no `D_hat` | 1.082 | 0.74 |
| (d) Oracle `D_final` (reference only) | 0.991 | 0.76 |

- **`G_hat_0` = (a) − (b) = 0.077 bits** (95% CI 0.040–0.102; repeat-1 subject bootstrap). This is **6.7% of `H(Y | D_hat_0)`**.
- The CI excludes 0, but the value is below the 10% "meaningful" threshold, so it classes as **YELLOW (moderate)**.

**Observations:**
1. Compressing the soft differential to a hard label costs ≈ 0.04 bits: (a) vs (e).
2. `D_hat_0` adds nothing beyond S0: (b) ≈ (c), as expected, because it is derived from S0.
3. The oracle (d) beats every S0-based condition. Clinicians' first imaging choice reflects information that the structured S0 lacks (e.g. physical examination, history).

**Rule 12:** (a) vs (c) is not a capacity-matched bottleneck test, and the `D_hat` model is weak (S0 accuracy 0.60). This is a directional preflight signal only.
