# MC-MED diagnosis encoder report (Stage E)

**Preregistration:** `mcmed-confirmatory-prereg-v1`, section 10.

**Source:** `results/mcmed/stageE_encoder_body_primary.json`.

**Scope.** Development data only. The encoder saw only X_3h and the frozen visit-diagnosis class. It never saw the ICU outcome, the disposition, or post-T data. **No ICU model had been fit when this was produced.**

D_hat_3h is an **experimentally generated disease-label representation**. It is not the clinician's working diagnosis.

## Setup

- **Ontology:** CCSR body system, 20 classes.
- **Input:** X_3h, 445 raw columns (plus missing indicators).
- **Development:** 25,834 visits; out-of-fold D_hat from 5-fold patient-grouped cross-fitting, with an inner 4-fold CV for C.
- **Locked test:** 6,570 visits; D_hat produced once by the encoder fit on all development patients (C* = 0.003).
- **Selected C:** [0.003, 0.003, 0.003, 0.003, 0.003] per fold; C* = 0.003.
- **Convergence:** non-converged fits: 0; final encoder converged: True.

## Adequacy gate (prespecified)

| Criterion | Value | Required | Met |
|---|---|---|---|
| Relative OOF log-loss reduction vs class prior | 29.7% (1.7307 vs 2.4626 nats) | ≥ 10% | yes |
| Every fold beats its prior | 5 / 5 | all | yes |
| Top-1 accuracy vs majority-class share | 0.448 vs 0.247 | greater | yes |

**Gate: PASSED.** The workflow proceeds to Stage F.

## Other diagnostics (development OOF)

- **Log loss:** 2.497 bits (prior baseline 3.553 bits).
- **Macro-F1:** 0.301.
- **Top-label expected calibration error:** 0.023 (10 bins).

| Fold | C | Log loss | Prior log loss |
|---|---|---|---|
| 0 | 0.003 | 1.7271 | 2.4626 |
| 1 | 0.003 | 1.7357 | 2.4625 |
| 2 | 0.003 | 1.7420 | 2.4625 |
| 3 | 0.003 | 1.7278 | 2.4627 |
| 4 | 0.003 | 1.7208 | 2.4627 |

### Class-wise recall (top-1)

| Class | Development visits | Recall |
|---|---|---|
| SYM | 6393 | 0.562 |
| CIR | 3701 | 0.567 |
| DIG | 3440 | 0.595 |
| INJ | 1988 | 0.585 |
| GEN | 1545 | 0.329 |
| RSP | 1057 | 0.206 |
| MUS | 1025 | 0.343 |
| NEO | 998 | 0.124 |
| END | 959 | 0.186 |
| INF | 870 | 0.302 |
| MBD | 792 | 0.650 |
| NVS | 761 | 0.230 |
| SKN | 607 | 0.214 |
| BLD | 488 | 0.262 |
| XXX | 482 | 0.042 |
| FAC | 373 | 0.008 |
| EYE | 210 | 0.305 |
| PRG | 58 | 0.017 |
| EAR | 57 | 0.000 |
| OTHER | 30 | 0.000 |

## Reading

**The representation clearly carries diagnostic information:** 30% less uncertainty than the prior, and 45% top-1 accuracy over 20 classes.

**It is far from a perfect label**, as expected at 3 h with a 20-class open ED ontology. Rare or heterogeneous classes are rarely recovered as top-1:
- EAR, OTHER, PRG, FAC, and XXX have recall ≤ 0.05;
- NEO is 0.12.

That is why the **soft** posterior is primary. The downstream test asks whether the patient state carries escalation information beyond this estimated disease-label distribution. It does not ask about the true visit diagnosis.

**No ICU information was used.** None was computed by class.
