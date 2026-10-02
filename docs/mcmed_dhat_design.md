# MC-MED: experimental diagnostic-bottleneck design (`D_hat_3h`)

> **Superseded for execution (2026-09-30)** by [mcmed_confirmatory_preregistration.md](mcmed_confirmatory_preregistration.md), after the author's decisions. Differences include: unmapped CCSR visits are excluded rather than kept as a class; a locked 80/20 hash split replaces repeated outer CV; and the context is season only, because time of day, weekday, and year are not recoverable. This file is kept unchanged below as the design record.

**Status: DESIGN ONLY. Not preregistered, not run.** No diagnosis encoder or outcome model has been trained. It replaces the superseded [t3_followup_design.md](t3_followup_design.md). It returns to the author before any preregistration.

## Why

No MC-MED field can legitimately represent the diagnosis available 3 h after arrival ([mcmed_diagnosis_semantics.md](mcmed_diagnosis_semantics.md)). The diagnosis must therefore be generated experimentally from pre-3 h information:

```
D_hat_3h = f(X_≤3h)
```

It is **an experimentally generated disease-label representation**, never the clinician's working diagnosis.

## Cohort (counts from `results/t3_followup/mcmed_audit/cohort.json`)

- **Adult ED visits admitted to the hospital** (`ED_dispo` ∈ {Inpatient, Observation, ICU}): [redacted].
- **Landmark T = `Arrival_time` + 3 h. Eligible = disposition decision after T** (`Dispo_time > T`): **35,127 visits / 23,964 patients.**
- **Excluded: disposition decided at or before 3 h: 13,011.** The outcome is already determined before the prediction landmark, so these visits are not predictable at T. Their ICU share (10.0%) is far above the eligible cohort's (4.2%). The landmark therefore **selects away rapidly escalated patients**, and the estimand is explicitly conditional on "disposition not yet decided at 3 h".
- **Endpoint prevalence (eligible):** ICU disposition **1,467 / 35,127 = 4.2%**.
- `Admit_time` is after `Dispo_time` in every eligible visit with a value (35,052; 75 missing), so no admission order precedes T.
- **Refinement after the leakage audit** ([mcmed_3h_feature_semantics.md](mcmed_3h_feature_semantics.md)): ADT orders precede `Dispo_time` in 15.4% of admitted visits. The proposed **decision time is min(`Dispo_time`, first ADT order)**, which gives an eligible cohort of **34,269 visits / 23,480 patients; ICU 1,408 (4.1%)**. The proposed primary analysis also excludes the 230 visits with an ICU or critical-care consult by T, giving **34,039; ICU 1,267 (3.7%)**. Including them is a sensitivity analysis. Author decision.
- The taxonomy counts below were computed on the 35,127 `Dispo_time` cohort. They will be recomputed (counts only) on the final cohort before registration.

## Endpoint wording

- **MC-MED outcome:** *observed ED-to-ICU disposition*.
- **MIMIC outcome (T3):** *observed later ICU transfer / escalation during the stay*.

These are different endpoints. This study is **an independent confirmation of the escalation-of-care target class** (a conceptually matched external confirmation), **not** a replication of MIMIC T3. ICU disposition is observed care, not optimal care.

## Diagnosis ontology (candidates; chosen by semantics and sample adequacy, never by ICU results)

Counts are for the eligible cohort (n = 35,127), from `results/t3_followup/mcmed_audit/taxonomy.json`. **ICU information by class was not computed.** The supervision label is the visit `Dx_ICD10`, mapped with AHRQ DXCCSR v2024.1 ("Default CCSR category OP").

| Candidate | Classes | Class size min / median / max | Classes < 50 | Pooled / unmapped | Symptom-class share | Interpretability | Sparsity risk |
|---|---|---|---|---|---|---|---|
| **B. CCSR body system (22)** | 22 | <10 / 1,078 / 8,242 | 2 | 0% pooled; 4.9% unmapped ICD codes (their own class) | 23.5% (SYM) | High: organ-system level, standard | Low. Merge the 2 classes with < 50 visits into "other" (rule fixed now) |
| A. ICD-10 chapter | 26 | <10 / 702 / 10,596 | 3 | 0.5% | 30.2% (chapter R) | Moderate: chapters mix mechanism and organ | Low |
| C. CCSR category, ≥ 300 visits (else pooled within body system) | 54 | <10 / 541 / 1,877 | 2 | **42.3%** in pooled "other" classes | 24.8% | High for the named classes; the pooled classes are heterogeneous | Moderate |
| D. ICD-10 3-character, ≥ 200 (else pooled by chapter) | 66 | <10 / 424 / 2,506 | 3 | **45.2%** pooled | ~30% | Moderate | Moderate |

**Proposal (fixed before any outcome modeling):**
- **Primary ontology: B, CCSR body system.** Classes with < 50 eligible visits are merged into `OTHER`, and unmapped codes form `UNMAPPED`. That gives about 21 classes.
- **Sensitivity ontology: C** (finer granularity).
- **Symptom-level diagnoses (SYM) stay a class.** They are the label the ED actually assigned. Excluding them would condition on diagnostic certainty.

**Feasibility at 3 h.** Not yet measured; measuring it requires training the encoder, which this design phase does not do. Reference point: in the MIMIC closed-world 4-class task, accuracy was 0.75 at 3 h (22% information recovered at S0 → 48% at 3 h). A 21-class open ED ontology will be much harder. That is why the **soft** representation is primary: it does not force premature commitment.

## Bottleneck representation

- **Primary:** the soft disease-label distribution `p_hat(D | X_≤3h)`, a probability vector over the fixed ontology (≈ 21 classes).
- **Sensitivity:** the hard top-1 label (one-hot argmax).

## Diagnosis encoder

- **Model:** multinomial L2 logistic regression on `X_≤3h` (the same feature set as the outcome model's X).
- **Supervision target:** the visit `Dx_ICD10` → ontology class.
- **Tuning:** nested CV over the same C grid, selecting on multinomial log loss for diagnosis. **It never sees the ICU outcome.**

## Cross-fitting (no target leakage)

Patient-grouped (`MRN`) folds are shared by both models.

1. **Outer loop** (5 folds × 3 repeats; confirmatory estimate): for outer fold k, the training set is `Tr_k` and the test set `Te_k`.
2. **Inside `Tr_k`**, the diagnosis encoder is cross-fitted with an inner 5-fold split. Each training visit receives `p_hat` from an encoder that did **not** train on that visit's patient. This gives the outcome model training features of the same quality it will see at test time.
3. **For `Te_k`**, `p_hat` comes from an encoder fit on all of `Tr_k`. Test patients' diagnosis labels and outcomes are never used.
4. **Outcome-model C** is selected by an inner 4-fold split within `Tr_k`, reusing the cross-fitted `p_hat` of step 2.
   - **Declared limitation:** those `p_hat` values came from encoders trained partly on other inner folds' diagnosis labels (**not** outcomes).
5. **Temporal sensitivity:** the dataset's chronological split (train+val → test). The encoder and outcome model are fit on the earlier period only.

## Outcome models (the proposed confirmatory comparison)

```
Model_D : logit P(ICU) = context (unpenalized) + p_hat_3h (unpenalized)
Model_DX: logit P(ICU) = context (unpenalized) + p_hat_3h (unpenalized) + X_≤3h (L2)
```

**Kept identical to preregistration `600f368`:**
- the partial penalty (unpenalized diagnosis representation and context; L2 on X only);
- no D×X interactions;
- the nested C grid {1e-4 … 100};
- minimum inner log loss, ties to the smaller C;
- log loss primary, AUROC secondary; calibration and Brier score also reported;
- a 2,000-resample patient bootstrap.

**Common context (both arms):**
- arrival time-of-day block and weekend;
- season (quarter; preserved by the de-identification).

Means of arrival belongs to X (patient state), as the ambulance-arrival feature does in MIMIC X0.

Calendar year is **not** recoverable, because dates are shifted per patient. Temporal robustness therefore comes from the chronological split.

**Oracle reference (descriptive only, never an input at 3 h):** the actual visit-diagnosis class replacing `p_hat` in `Model_D`. It is labelled hindsight.

## Proposed confirmatory estimand

In adult ED visits admitted to hospital whose disposition was not decided within 3 h of arrival:

```
Δ = CE(ICU | context, p_hat(D | X_≤3h)) − CE(ICU | context, p_hat(D | X_≤3h), X_≤3h)
```

CE is the held-out cross-entropy in bits; also reported as Δ / CE(`Model_D`).

It asks whether contemporaneous patient state contains predictive information about **observed ED-to-ICU disposition** that is **lost when the same state is compressed into a disease-label representation** over the fixed ontology.

**Proposed success criterion:** the same as `600f368`, i.e. 95% CI lower bound of Δ > 0 **and** relative Δ ≥ 10%. Author decision at registration.

## Feature set `X_≤3h`

See [mcmed_3h_feature_semantics.md](mcmed_3h_feature_semantics.md). **Only GREEN features.**

## Remaining risks

See section 10 of [mcmed_3h_feature_semantics.md](mcmed_3h_feature_semantics.md) and the author report.
