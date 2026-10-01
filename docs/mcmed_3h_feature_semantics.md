# MC-MED: what is legitimately known 3 h after arrival

**Date:** 2026-09-30. Landmark T = `Arrival_time` + 3 h. Cohort: admitted adult visits with `Dispo_time > T` (n = 35,127).

**Rules:**
- A lab or imaging result is available **only after `Result_time`**. An order being placed makes nothing available.
- Timestamps are patient-shifted, but within-patient order is preserved (paper, de-identification section).
- Aggregate evidence: `results/t3_followup/mcmed_audit/{cohort,features,leakage}.json`.

**Classes:**
- **GREEN:** legitimate patient state at T.
- **YELLOW:** usable only with a stated rule, or with ambiguous semantics; sensitivity analysis only.
- **RED:** excluded (post-T, post-decision, outcome-derived, or a clinician action, not patient state).

## Visits table

| Field | Class | Rule / reason |
|---|---|---|
| `Age`, `Gender` | GREEN | Known at arrival (paper: "available at the time of patient arrival"). Age is perturbed by 0–2 years in de-identification |
| `Race`, `Ethnicity` | YELLOW | Available at arrival, but **excluded from X by design**, for consistency with MIMIC X (which had none) and to avoid race-based prediction. Author decision |
| `Means_of_arrival` | GREEN | Arrival. It belongs to X, as the ambulance flag does in MIMIC X0 |
| `Triage_Temp` (°C), `Triage_HR`, `Triage_RR`, `Triage_SpO2`, `Triage_SBP`, `Triage_DBP` | GREEN | Triage. Physiologic bounds as in [data_cleaning_rules.md](data_cleaning_rules.md), with temperature converted to °F for the same bounds |
| `Triage_acuity` (ESI) | GREEN | Triage |
| `CC` (chief complaint) | GREEN | Triage. It needs a **pre-specified representation** (e.g. TF-IDF fitted within training folds, as in the MIMIC early-diagnosis work) |
| `Roomed_time` | YELLOW | A time-to-rooming process variable, if rooming occurred ≤ T. It is ED operational state, not patient state: common context at most. Author decision |
| `Payor_class` | RED | Documented among "data summarizing the visit"; socioeconomic, not patient state |
| `Visits`, `Visit_no` | YELLOW | `Visit_no` counts prior visits in the dataset window, so it is prior-utilization information known at arrival. `Visits` (total visits) includes **future** visits and is RED |
| `Dx_ICD9`, `Dx_ICD10`, `Dx_name` | RED as input | Visit-summary diagnosis ([mcmed_diagnosis_semantics.md](mcmed_diagnosis_semantics.md)). **Supervision target only** |
| `ED_dispo`, `Dispo_time` | Outcome | Endpoint definition and cohort rule |
| `Admit_time`, `Admit_service` | RED | Post-decision (`Admit_time` ≥ `Dispo_time` in every eligible visit with a value) |
| `ED_LOS`, `Hosp_LOS`, `DC_dispo`, `Departure_time`, `Hours_to_next_visit`, `Dispo_class_next_visit` | RED | After the visit, or future |

## Other tables

| Table / field | Class | Rule / reason |
|---|---|---|
| **Labs** (`labs.csv`): component values | **GREEN if `Result_time` ≤ T** | First resulted value per pre-specified component, plus missing indicators (resulted by T or not) |
| Labs ordered by T but not resulted by T | RED as a value; YELLOW as an "ordered" indicator | The order reflects clinician suspicion (a behavior), not patient state |
| **Rads** `Impression` | YELLOW | Available if `Result_time` ≤ T, but it is free text that **names diagnoses**. A representation must be pre-specified (e.g. keyword flags as in MIMIC X2). Proposed as a **sensitivity feature set**, not primary |
| **Numerics** (minute-level HR, RR, SpO₂, SBP, DBP, MAP, Temp, Pain, Perf, HRV) | **GREEN if `Time` ≤ T** | Proposed summary: last value and min/max over [arrival, T]. **`LPM_O2` (oxygen flow) is a treatment intensity → RED** (clinician action) |
| **Orders** (`orders.csv`): medication orders and administrations (`First_admin_time`), imaging/lab orders, consults, nursing | RED as primary X | Clinician actions, not patient state. They can encode an escalation already under way (see leakage). **Excluded** from X |
| **PMH** (`Noted_date`) | GREEN if `Noted_date` < visit date; YELLOW if on the same date; RED if after | Comorbidity burden (e.g. counts per CCS group); date-level only |
| **Home meds** (`meds.csv`) | YELLOW | `Start_date` before the visit, but `Active` "thought to be using at the time of the visit" may be updated by reconciliation during the visit. Only `Start_date` < visit date and `Entry_date` < visit date would be GREEN; it is a sensitivity analysis at most |
| Waveforms | Excluded | Out of scope (not needed to answer the question; large) |

## Measured availability (`results/t3_followup/mcmed_audit/features.json`; the n = 35,127 Dispo_time cohort)

**Labs**
- **33,750 (96.1%)** of visits have at least one lab result by T.
- **842 (2.4%)** have labs ordered by T with no result by T; those values are not usable.
- Resulted by T: complete blood count ≈ 31,500 visits (≈ 90%); basic metabolic panel (Na, K, Cl, CO₂, BUN, creatinine, glucose, Ca) ≈ 30,000 (≈ 86%); hepatic panel (bilirubin, AST, ALT, ALP, albumin, protein) ≈ 29,800 (≈ 85%); automated differential ≈ 28,200 (≈ 80%).
- Order-to-result time: median 54 min (IQR 23–91; p95 212).
- **Data-quality note:** at least 5% of lab rows show `Result_time` **before** the labs-table `Order_time` (p5 = −6 min). The paper states that the labs-table order time may differ from the orders table because the laboratory may modify orders. Availability uses `Result_time` only.

**Other tables**
- **Imaging:** 14,459 (41.2%) of visits have an imaging result by T.
- **Orders placed by T:** lab ≈ 259,500 rows; nursing ≈ 116,400; medications ≈ 101,400; imaging ≈ 73,800; isolation ≈ 46,200; and others. All are clinician actions and excluded from X.
- **PMH rows, relative to visit dates:** 649,203 noted before the visit date (GREEN); 89,233 on the same date (YELLOW); 296,878 after (RED).
- **Numerics** (**sample only**: the first 100 MB of `numerics.csv`, 1,159 eligible visits fully contained; `numerics_sample.json`):
  - by T, HR, RR, SpO₂, and blood pressure are present in ≈ 99.5% of visits, temperature in 96.3%, pain in 84.1%, perfusion index in 81.6%, HRV in ≈ 70%;
  - `LPM_O2` (a treatment, RED) is present in 10.6%;
  - rows are mostly monitor-derived (≈ 709,000 Monitor vs ≈ 48,000 Chart rows).
  - The full file (2.76 GB) is not downloaded. Full coverage must be measured before registration if numerics are part of X.

## Outcome-leakage audit (`leakage.json`, `decision_time.json`)

1. **`Admit_time`** is never at or before T in the eligible cohort. It is at or after `Dispo_time` in 35,052 visits; 75 are missing.
2. **Disposition decided at or before 3 h** (`Dispo_time ≤ T`): 13,011 admitted visits excluded (ICU 10.0% among them).
3. **ADT orders precede `Dispo_time`.** In 15.4% of admitted visits (7,421 / 48,138), an Admission/Transfer order ("ADMIT TO INPATIENT", "PLACE IN OBSERVATION", "CHANGE LEVEL OF CARE/TRANSFER PATIENT") is placed **before** the documented `Dispo_time`. By T this happens in **858 visits** of the `Dispo_time` cohort; the level-of-care decision is then already partly made.
   - **Proposed rule: decision time = min(`Dispo_time`, first ADT order time); eligible if decision time > T.**
   - Resulting cohort: **34,269 visits / 23,480 patients; ICU 1,408 (4.1%).**
4. **ICU / critical-care consults by T.** "CONSULT TO ICU" (175 visits) and "CONSULT TO NEURO CRITICAL CARE SRVC" (69 visits); 230 visits in the decision-time cohort. **61.3% of them end in ICU disposition**, against 3.7% in the other 34,039. Escalation is visibly under way at T.
   - Orders are excluded from X, so this is not feature leakage.
   - But the prediction problem for these visits is nearly settled.
   - **Proposed:** exclude in the primary analysis (n = 34,039; ICU 1,267 = 3.7%); include in a sensitivity analysis. **Author decision.**
5. **Admitting-team consults by T** (for example "CONSULT TO MEDICINE UNIVERSITY ADMIT RESIDENT", 1,460 visits; "CONSULT ONCOLOGY ADMIT SERVICE", 768). These show that admission is expected, but they do not set the level of care. The cohort is admitted patients anyway, so they are not outcome leakage. As orders, they are excluded from X.
6. **Treatments by T** (for example oxygen administration, medications) are clinician actions and excluded from X. `LPM_O2` in numerics is RED.
7. **Keyword false positives** (for example "RETICULOCYTE" matching "icu", "TRANSFERRIN" matching "transfer") were identified by reviewing names and ignored.
