# Prescription target audit (Q17)

**Part 1 was pre-specified on 2026-09-29, before any medication row was inspected.** Part 2 (timing-semantics audit) and Part 3 (target results) are appended afterwards.

## Sources

| Table | Key time fields | Semantics (to be verified in Part 2) |
|---|---|---|
| `hosp/prescriptions` | `starttime`, `stoptime`; `poe_id` | A pharmacy-dispensed order. `starttime` = the intended start of the order, not proof of administration |
| `hosp/poe` | `ordertime` (via `poe_id`) | When the provider **placed** the order (the decision time) |
| `hosp/emar` | `charttime`, `event_txt`, `scheduletime`, `storetime` | Bedside **administration** record. Coverage may be incomplete for earlier years |

**Decision time for a medication target** = `poe.ordertime` when the order links to POE; otherwise `prescriptions.starttime`, flagged as a proxy.

Four categories are kept apart and never merged:
1. ordered before the decision point (≤ T);
2. ordered after T (the target window);
3. administered (eMAR `charttime`, administered events only);
4. discharge medication. Discharge medications are *not* in `prescriptions`; they appear only in discharge-summary text, which is not used.

## Leakage rules

- Features are unchanged: X0–X2, cut at T. **No medication, and no post-treatment response variable, is used as a predictor.**
- A target counts orders **placed after T** within the stated window.
- Orders already active before T are recorded in a separate flag. They do not count as a post-T decision, except where a definition says so ("continuation" semantics below).

## Pre-specified candidate targets

Landmark T = 6 h (sensitivity 3 h). Cohort = the landmark cohort (alive in hospital at T, no PACU before T). D = `D_final` (post-diagnostic).

| ID | Target | Window | Drug definition (regex on `drug`, systemic routes only) | Pre-registered expectation (to be tested, not assumed) |
|---|---|---|---|---|
| M1 | Any systemic antibiotic order placed | (T, T+24 h] | The antibiotic list below; routes IV/PO/IM/NG | Diagnosis-sufficient for appendicitis, cholecystitis, and diverticulitis; variable in pancreatitis. **Negative-control candidate** |
| M2 | Broad-spectrum escalation: piperacillin-tazobactam, cefepime, ceftazidime, meropenem, imipenem, ertapenem, IV vancomycin | (T, T+48 h] | As listed | Severity-dependent within D. **Positive candidate** |
| M3 | VTE prophylaxis agent: enoxaparin (vs subcutaneous unfractionated heparin), among patients with either | (T, T+48 h] | `enoxaparin` vs `heparin` with route SC | Renal function / weight dependent, with little dependence on D. **Positive candidate** (agent choice) |
| M4 | Any opioid analgesic order placed | (T, T+24 h] | morphine, hydromorphone, oxycodone, fentanyl, tramadol, hydrocodone | Near-universal. **Negative-control candidate** |
| M5 | Anaerobic coverage (metronidazole, piperacillin-tazobactam, carbapenem, ampicillin-sulbactam), among patients with any antibiotic order in the window | (T, T+24 h] | As listed | Protocolized by D (intra-abdominal infection). **Negative-control candidate** |
| M6 | Any insulin order placed | (T, T+24 h] | `insulin` | Glucose / diabetes dependent, with little dependence on D. **Positive candidate** |

**Antibiotic list (M1):** cef-, ceph-, -penem, piperacillin, ampicillin, amoxicillin, nafcillin, penicillin, vancomycin (IV), levofloxacin, ciprofloxacin, moxifloxacin, azithromycin, doxycycline, metronidazole, clindamycin, linezolid, daptomycin, gentamicin, tobramycin, aztreonam, sulfamethoxazole/trimethoprim, nitrofurantoin, tigecycline.
- Topical, ophthalmic, and otic routes are excluded.
- Oral vancomycin is excluded from M1 (it targets *C. difficile*, not systemic infection).

## Analysis

- **Stage A:** `H(Y|D)` and majority share per D.
- **Stage B:** nested CV exactly as in [model_selection_preflight.md](model_selection_preflight.md), feature sets X0 / X1 / X2.
- **Classification:** thresholds as in the framework.
- **BLUE (negative control):** a target is BLUE if condition A holds, **or** if Stage B recoverability is negligible (the 95% CI of Δ log loss includes 0, or Δ < 2% of `H(Y|D)`) for a clinically sensible reason. A BLUE target is retained, not discarded.
- **Reference semantics:** observed ordering is **clinician behavior, not optimal care** (G11).

**Route vocabulary note (added after inspecting route codes, before any target was built).** The whole-string non-systemic list is in `medication_targets.EXCLUDED_ROUTES`.
- `ED` = **epidural** (bupivacaine, epidural opioid bags) and is excluded. Epidural opioids therefore do **not** count toward M4.
- `PB` (IV piggyback) is systemic.
- `NS` (nasal) and other local, regional, or device routes are excluded.

## Part 2 — Timing-semantics audit (2026-09-29)

**Files acquired** (MIMIC-IV 3.1 hosp, checksums verified): `prescriptions`, `poe`, `poe_detail`, `emar`. `pharmacy` and `emar_detail` were not needed.

Source: `results/phase0/sufficiency/mimic_cdm/medications/prescription_timing_audit.json`, cohort = 2,400 CDM admissions.

| Check | Result | Consequence |
|---|---|---|
| Admissions with any prescription | 2,381 (99.2%) | Coverage is adequate |
| Prescription rows linked to `poe.ordertime` | 79,068 of 79,448 (99.5%) | The **decision time is observed** for almost every order. `starttime` is used as a proxy for only 0.5% of rows |
| `starttime − ordertime` | Median +41 min (IQR 15–66). 5th percentile −40 h (renewals / back-entered orders); 95th percentile +9.8 h | `starttime` is the planned start, not the decision. Targets use `ordertime` |
| Orders placed before ED arrival | 171 rows (0.2%) | Negligible |
| Admissions with any eMAR row | 1,117 (46.5%) | **Administration cannot be established for about half the cohort** (likely eMAR rollout period). No target uses administration |
| eMAR administered before its order | 412 of 73,863 (0.6%) | A small timestamp anomaly |
| Discharge medications | Not in `prescriptions` (discharge text only, not used) | Excluded by design |

The four categories were kept apart:
1. **ordered before T:** recorded in flags, never a feature;
2. **ordered after T:** the targets;
3. **administered:** eMAR, not used for targets because of the 46.5% coverage;
4. **discharge medication:** not used.

**No medication and no post-treatment response variable is a predictor.**

## Part 3 — Results (nested CV; [model_selection_preflight.md](model_selection_preflight.md))

Sources:
- `medications/stage_a_L{3,6}.json`
- `medications/nested/stage_b_M*_L{3,6}_nested.json`

Values are for X1 (X2 is similar); Δ = Δ log loss in bits.

| Target | n (6 h) | `H(Y)` / `H(Y|D)` | Δ at 6 h (95% CI), share of `H(Y|D)` | Share at 3 h | AUROC D → DX (6 h) | Within-D AUROC (appendicitis / cholecystitis / diverticulitis / pancreatitis) | Class |
|---|---|---|---|---|---|---|---|
| M1 new systemic antibiotic order in (T, T+24 h] | 2,365 | 1.00 / 0.92 | 0.013 (−0.000–0.036), 1.4% | 0.3% (CI includes 0) | 0.661 → 0.700 | 0.63 / 0.63 / 0.59 / 0.63 | **BLUE (null control)**. Caveat: the target mostly reflects order-entry workflow (re-entry at admission, continuations) |
| M2 broad-spectrum order in (T, T+48 h] | 2,365 | 0.45 / 0.43 | 0.042 (0.029–0.060), 9.8% (X2: 10.0%) | 9.0% (X2: 9.2%) | 0.621 → 0.763 | 0.73 / 0.78 / 0.67 / 0.72; events 46 / 74 / 48 / 51 | **YELLOW (borderline)**. Includes continuations of ED broad-spectrum antibiotics, so it is not purely escalation |
| M3 enoxaparin vs SC heparin (VTE prophylaxis) | 1,729 | 0.076 / 0.067 | 0.003 (−0.003–0.011) | 5.7% (CI includes 0) | 0.740 → 0.776 | — | **BLUE (trivial)**. Near-constant (≥ 96% SC heparin): an institutional protocol. The pre-registered positive candidate is **downgraded** (condition A) |
| M4 opioid order in (T, T+24 h] | 2,365 | 0.80 / 0.75 | 0.019 (0.005–0.034), 2.5% | 1.6% (CI includes 0) | 0.658 → 0.710 | 0.60 / 0.64 / 0.58 / 0.64 | **RED**. Neither negligible (6 h) nor meaningful: not usable as a control or as a positive target |
| M5 anaerobic coverage, among antibiotic orders in (T, T+24 h] | 1,240 | 0.48 / 0.44 | −0.008 (−0.020–0.011), ≈ 0 | ≈ 0 (CI includes 0) | 0.675 → 0.675 | 0.44 / 0.53 / 0.73 / 0.56; non-events 24 / 33 / 22 / 49 | **BLUE (non-trivial negative control)**. The class choice is protocol-like by diagnosis (89–95% in three diagnoses, 68% in pancreatitis), and X adds nothing. Power is limited by the small non-event counts |
| M6 insulin order in (T, T+24 h] | 2,365 | 0.48 / 0.47 | 0.118 (0.091–0.146), **25.3%** | 24.8% | 0.619 → 0.850 | 0.89 / 0.82 / 0.78 / 0.81; events 55 / 63 / 34 / 93 | **YELLOW (strong Stage A/B)**. The diagnosis is nearly uninformative (`I(Y;D)` = 0.015 bits). Stage C not assessed. "Order placed" includes sliding-scale protocols. Administration is unverifiable for half the cohort |

**Negative-control search, answered:** P(Y | D, X) ≈ P(Y | D) was found, after nested CV and with leakage control, for:
- **M5 (anaerobic coverage):** non-trivial, protocol-like;
- **M3 (VTE agent):** trivial, near-constant;
- **M1 (order-entry workflow):** a null control;
- **T5 (organ operated):** trivial.

Under the identical pipeline, T1 (13.5% of `H(Y|D)`) and M6 (25%) show large gains while M5 and M1 show none: **a dissociation**.

**Observed ordering ≠ optimal care** (G11) for every M target.
