# Procedure timing audit (Q14)

**Part 1 was pre-specified on 2026-09-29, before POE vocabulary or any case-level ordering was inspected.** Part 2 records the vocabulary mapping and results, and is appended afterwards.

## Problem

T1 is "the pathology's definitive procedure after landmark T". The features are cut at T. The claim "features precede the procedure" needs the procedure to be **after T**.
- `procedures_icd.chartdate` has **day** resolution.
- PACU transfers exist for only ~16% of operations.
- At the 6 h landmark, 622 positive cases are dated the same day as T without a resolving PACU time, and 325 are known only from discharge text (no date).

**Within-day order is never inferred from a date alone.**

## Part 1 — Pre-specified evidence rules

### Sources and timestamp semantics

| Source | Field | Semantics | Use |
|---|---|---|---|
| `hosp/procedures_icd` | `chartdate` | Procedure date (day) | Date-level ordering only |
| `hosp/transfers` | `careunit = PACU`, `intime` | Arrival in recovery, i.e. just after the operation ends | Upper bound on the operation's end; an operation after T if the PACU `intime` ≥ T and there is no PACU before T |
| `ed/edstays` | `outtime` | Departure from the ED | A patient still in the ED at T has not been to the OR by T. Assumes operations are not performed inside the ED; a patient leaving for the OR leaves the ED |
| `hosp/poe` (+ `poe_detail`) | `ordertime`, `order_type`, `order_subtype`, detail fields | When a provider placed an order | Pre-/post-operative order markers (vocabulary mapped in Part 2) |
| `hosp/services` | `transfertime`, `curr_service` | Change of responsible service (e.g. to SURG) | Partial evidence only; a service change is not an operation |

**Linkage:** `hadm_id` for `procedures_icd`, `transfers`, `poe`, and `services`; `edstays` via `hadm_id` (earliest ED stay = the anchor stay).

### Classes (per case, per landmark)

Applied to T1-positive cohort cases. T1-negative cases (no procedure recorded) have no procedure to order and are classed **GREEN (no procedure)**.

- **GREEN (ordering established):** any of
  - (a) the procedure date is after T's date;
  - (b) a PACU `intime` ≥ T, with no PACU before T;
  - (c) the ED `outtime` ≥ T, meaning the patient was still in the ED at T;
  - (d) a **specific pre-operative order** for the procedure (Part 2 vocabulary) placed at or after T.

  In every case there must be **no** post-operative evidence before T.
- **RED (ordering not established, or leakage plausible):** either
  - any post-operative evidence (post-op order marker, or PACU) **before** T; or
  - no timing evidence beyond a same-day date or discharge text.
- **YELLOW (partial evidence):** none of the GREEN criteria hold, there is no post-op evidence before T, **and** at least one consistent-but-not-conclusive signal exists:
  - post-operative order markers only after T;
  - a change to a surgical service at or after T;
  - a non-specific surgical preparation order (e.g. NPO) at or after T.

### Analyses

- **Primary:** exclude RED.
- **Sensitivity:** GREEN only.
- **Reference:** unfiltered (earlier runs).

Attrition is reported per landmark and per diagnosis. The earlier superseded run is retained unchanged.

## Part 2 — Vocabulary mapping and results

### 2a. POE vocabulary mapping (fixed before `classify` was run)

Source: `procedure_timing vocab` on the cohort's admissions, counts only (`poe_vocabulary.json`).

| Class | POE marker (order type / subtype or detail) | Cohort order count |
|---|---|---|
| Post-operative | `ADT orders \| Postop` | 1,596 |
| Post-operative | `Admit category=Place in PACU`; `PACU Boarder` | < 10 each |
| Post-operative | Drain-care details: closed suction drain, wound sump, biliary T-tube | 139; 13; < 10 |
| Non-specific preparation | `Nutrition \| NPO/Diet for Procedure` | 1,020 |
| Non-specific preparation | Consults: Acute Care Surgery; ERCP/Advanced Endoscopy; HPB Surgery | 26; 29; < 10 |
| Non-specific preparation | `Admit to=Surgery`; `Transfer to=Surgery` | 3,241; 253 |
| **Pre-operative, specific** | **None exists** (no pre-op, consent, or OR-booking order in the vocabulary) | — |

**Consequence:** GREEN rule (d) is **unavailable**. GREEN can come only from (a) the procedure date is after T's date, (b) a PACU stay after T, or (c) the patient was still in the ED at T. Timestamp semantics: `poe.ordertime` is when the order was placed. A post-op order placed before T therefore implies the operation ended before T.


### 2b. Classification results

Source: `results/phase0/sufficiency/mimic_cdm/timing/procedure_timing_classes.json`. Counts below 10 are suppressed. The per-case classes are in the private file `t1_timing_classes.csv` on gbminipc.

**T1-positive cases (procedure recorded) by class**

| Landmark | Positives | GREEN | YELLOW | RED |
|---|---|---|---|---|
| 6 h (primary) | 1,458 | 1,037 | 362 | 59 |
| 3 h | 1,510 | 1,281 | 204 | 25 |

**6 h: evidence behind each class**
- **GREEN:** procedure dated after T 420; still in the ED at T 451; PACU after T 166.
- **YELLOW:**
  - post-op orders only after T, with a surgical service and/or non-specific preparation after T: 314;
  - non-specific preparation only: 36;
  - other combinations: < 10 each.
- **RED:** post-op evidence before T 29; no evidence beyond a same-day date or discharge text 30.

**6 h: what happened to the earlier ambiguous groups**

| Earlier status | → GREEN | → YELLOW | → RED |
|---|---|---|---|
| Same-day ambiguous (622) | 258 | 315 | 49 |
| Discharge-text only (325) | 276 | 43 | < 10 |
| Dated / PACU-resolved (511) | 503 | < 10 | < 10 |

So **258 of the 622 same-day ambiguities were resolved to GREEN**, 315 remain partially resolved (YELLOW), and 49 are unresolved or plausibly leaked (RED).

**RED and YELLOW by diagnosis (6 h)**

| Diagnosis | RED | YELLOW |
|---|---|---|
| Appendicitis | 25 | 221 |
| Cholecystitis | < 10 | 95 |
| Diverticulitis | < 10 | 11 |
| Pancreatitis | 25 | 35 |

**Attrition caused by timing filtering (T1 cohort)**

| Landmark | Unfiltered | Primary (exclude RED) | Sensitivity (GREEN only) |
|---|---|---|---|
| 6 h | 2,329 | 2,270 (−59) | 1,908 (−421) |
| 3 h | 2,381 | 2,356 (−25) | 2,152 (−229) |

Cases without a procedure are GREEN by definition, since there is no procedure to order. The GREEN-only sensitivity cohort therefore removes positives selectively, and the event rate falls: GREEN-only is **not** a random subsample. Most YELLOW positives are appendicitis cases that left the ED before T and whose only evidence is post-op orders after T.

### 2c. Remaining limitations

1. **No order specific to an operation exists** (rule (d) unavailable). Within-day ordering for patients who left the ED before T rests on post-op order times (an upper bound on the end of the operation) and PACU records (~16% coverage).
2. **The "still in the ED at T" rule assumes operations are not performed inside the ED**, and that the ED `outtime` marks departure. Both are standard, but unverified here.
3. **Post-op orders after T are consistent with, but do not prove, an operation after T.** An operation could end before T with the post-op order written later. Those cases are YELLOW, not GREEN.
4. **"Dated" means an ICD `chartdate` after T's date.** A multi-procedure admission with an earlier undated procedure is not detectable.
5. **ERCP (pancreatitis) has no PACU or post-op order semantics comparable to surgery.** Pancreatitis has the highest RED share (25 of 179 positives).
