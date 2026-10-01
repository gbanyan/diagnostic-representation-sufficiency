# Data gates — MIMIC-IV-Ext-CDM

- **Dataset:** MIMIC-IV-Ext Clinical Decision Making, PhysioNet v1.1 (2024-07-08)
- **Evaluated on:** 2026-09-29
- **Phase 0 pass completed:** documentation + source code only. **Raw-row audit not started** (no access; see P0).
- **Code inspected** (third-party checkouts in the git-ignored `external/`):
  - `paulhager/MIMIC-Clinical-Decision-Making-Dataset` @ `4d33f98b`
  - `paulhager/MIMIC-Clinical-Decision-Making-Framework` @ `e1b4a522`
  - `paulhager/MIMIC-Clinical-Decision-Making-Analysis` @ `99a0cc9a`
- File references below are `<repo>:<path>:<line>` with repo abbreviations `DS`, `FW`, and `AN`.

## P0 — Access

**Status: resolved 2026-09-29.** The author signed the data use agreements. MIMIC-IV-Ext-CDM, MIMIC-IV, MIMIC-IV-ED, MIMIC-IV-Note, and eICU return HTTP 200. ER-REASON still returns 403 (study approval by the dataset's authors is pending). The history below is kept for the record. **Earlier status: blocked.** The author's PhysioNet credentials (stored on gbminipc) download MIMIC-CXR-JPG 2.1.0 successfully. The same credentials get HTTP 403 for `mimic-iv-ext-cdm/1.1`, `mimiciv/3.1`, `mimiciv/2.2`, `mimic-iv-note/2.2`, `mimic-iv-ed/2.2`, and `eicu-crd/2.0`. The account is credentialed, but the project-specific data use agreements for these datasets have not been signed. Only the author can sign them, on each PhysioNet project page.

Consequence: Q3, Q5, and Q10, and the row-dependent parts of Q2, Q4, and Q7, remain open.

---

## Findings by preflight question

### Q1. Diagnosis label provenance and timing — **answered: `D_final` only**

- Candidate admissions were selected where an ICD `long_title` contains the pathology string (DS:`dataset/dataset.py:30-69`).
- The target is then restricted to cases where the pathology appears in the **primary (first-listed) discharge diagnosis** parsed from the discharge summary (DS:`CreateDataset.py:213-221`; DS:`dataset/dataset.py:667-680`, which requires the name to appear before a "secondary" header).
- Four admissions with more than one target pathology were removed manually (DS:`CreateDataset.py:200-201`).
- No case-level early impression, working diagnosis, or differential exists in the dataset.
- **Selection effect:** a case is invalidated if its HPI contains the disease or procedure string (DS:`dataset/dataset.py:683-700`; for example "appendicitis" or "appendectomy"). Cases whose HPI names the diagnosis are removed. Cases whose HPI describes diagnostic findings *without* the name are kept.

**Gate implication (G2, G12):** the label is a final/discharge diagnosis. MIMIC-CDM can provide `D_t` only as a model-generated experimental bottleneck. G12 is not applicable to the dataset; there is no diagnostic timing.

### Q2. Field inventory — **partially answered (documentation + code)**

| Field | Source | Time information | Evidence |
|---|---|---|---|
| Patient History | Discharge summary, from the "History of Present Illness" header up to the physical exam header (so it likely also includes PMH, social, and family history, depending on note section order; verify on rows) | None; written at discharge | DS:`dataset/discharge.py:43-` |
| Physical Examination | Discharge summary PE section, truncated at "discharge" keywords | None; written at discharge | DS:`dataset/discharge.py:129-168` |
| Laboratory Tests | `labevents`: first value per `itemid` within [first transfer − 1 day, last transfer `intime`] | `charttime` is documented as present in `laboratory_tests.csv`; the framework loader drops it | DS:`dataset/labs.py:15-26`; DS:`dataset/dataset.py:341-387`; DS:`ConvertPhysionet.py` |
| Microbiology | First instance per test, same window | Same caveat | DS:`dataset/labs.py:29-` |
| Radiology | **All** reports in the window; sections such as IMPRESSION, INDICATION, HISTORY, COMPARISON, and CONCLUSION are stripped | `note_id` retained, so a join to MIMIC-IV-Note `radiology.charttime` is possible | DS:`dataset/radiology.py:32-62` |
| Discharge Diagnosis / Procedures | Discharge summary | Discharge | PhysioNet page |
| ICD diagnoses / procedures | `diagnoses_icd`, `procedures_icd` | Billing, at discharge | PhysioNet page |

The row-level part (per-field coverage and length distribution) is still to be done.

### Q3. Leakage-free S0–S4 reconstruction — **open (blocked); strong risk signals from code**

- **S0/S1:** HPI and PE are discharge-summary text. In MIMIC discharge summaries the HPI section often contains the ED course, including lab and imaging results. The code only screens for the literal disease or procedure name. HPIs that report "CT showed a dilated appendix with fat stranding" pass unchanged. *(Needs row audit.)*
- **S2:** "First instance per test" is taken across the **whole admission**. A test first drawn on hospital day 3 (for example after surgery, or a lipase added after imaging) is presented as if it were an initial lab. It is not a snapshot of initial labs. The PhysioNet authors note: "response to treatment is not properly captured."
- **S3:** All admission radiology is included, and repeat requests return later scans in chronological order (FW:`tools/Actions.py:136-170`). This can surface post-operative or follow-up imaging.
- **Redaction** covers only the listed strings (DS:`CreateDataset.py:32,50,68,88`). For example, cholecystitis cases redact "cholecystostomy" but not "cholecystectomy". Synonyms and abbreviations ("appy", "lap chole", "s/p") are not redacted.

**Feasible repair path:** S2/S3 can be time-cut. `charttime` exists for labs, and `note_id` allows joining radiology times. Both need an anchor time (ED arrival or admission) from MIMIC-IV `admissions`/`edstays`, so MIMIC-IV access is needed. S0 could be rebuilt from MIMIC-IV-ED triage (chief complaint, vitals) as a leakage-resistant alternative.

### Q4. Fields derived from discharge summaries — **answered**

HPI, PE, discharge diagnosis, and free-text discharge procedures are parsed from discharge summaries (PhysioNet page; DS:`dataset/discharge.py`). All early-stage free text (S0, S1) is therefore written at discharge. Whether the PE is admission-time content depends on the note's section labelling (the truncation heuristic at DS:`dataset/discharge.py:162-166`). This needs a row audit.

### Q5. Hindsight content — **open (blocked)**

Needs a row audit. The lexicon and design are in the Phase 0 plan. Code-level risks are listed under Q3.

### Q6. How the benchmark defines treatment quality — **answered**

- The evaluator is chosen by the **ground-truth pathology** (FW:`run.py:25-37`).
- Treatment is keyword or procedure-code matching of the model's free-text "Treatment:" section against a per-pathology dictionary of **Treatment Required** flags (FW:`evaluators/*_evaluator.py`, `score_treatment`).
- The paper's analysis scores treatment **only for correctly diagnosed patients** and reports the per-item rate at which required treatments were requested (AN:`benchmark.ipynb`, cell 17).
- Treatments that are requested but not required are **not penalized**. There is no scoring of harm, contraindications, drugs, doses, or timing. The colonoscopy timing check is commented out and was "confirmed manually" (FW:`evaluators/diverticulitis_evaluator.py`, `score_treatment`).

### Q7. Patient specificity of treatment criteria — **answered at code level; prevalence open**

| Pathology | Always required (disease-level) | Conditional | Condition source |
|---|---|---|---|
| Appendicitis | Antibiotics, Support | Appendectomy | Observed procedure (ICD / discharge text) |
| Cholecystitis | Antibiotics, Support | Cholecystectomy | Observed procedure |
| Diverticulitis | Colonoscopy, Antibiotics, Support | Drainage, Colectomy | Observed procedure |
| Pancreatitis | Support (fluids + analgesia + monitoring) | Drainage, ERCP; Cholecystectomy | Observed procedure; **"biliary" in discharge diagnosis** |

The only patient-specific content is (a) whether the patient actually received a procedure, which is observed behavior, not optimal care (G11), and (b) one diagnosis sub-type (biliary). There are no conditions on severity, comorbidity, allergy, renal function, pregnancy, or timing. How often the conditional items trigger requires rows.

### Q8. Can treatment quality be separated from disease-to-guideline mapping? — **answered: no, with the existing rubric**

Because the score is recall-only over required items with no penalty for extra items, a planner that sees **only the pathology label** can reach the maximum by listing every item in that pathology's dictionary: "antibiotics, IV fluids, analgesia, monitoring, appendectomy". The rubric is therefore saturated by a label-only oracle and **cannot detect a bottleneck cost** (fails G5 and G9 for treatment). This is shown by construction and does not need rows. Scoring only correctly diagnosed patients adds further conditioning on diagnosis.

Surviving path: build a patient-specific treatment reference from raw MIMIC-IV action data (`poe`, `prescriptions`, `emar`, `procedures_icd` with times). It would be framed explicitly as **observed clinician behavior** (G11), with **precision as well as recall**, plus blinded clinician adjudication on a subset. This is new construction and needs author approval and MIMIC-IV access.

### Q9. Can early examination planning be evaluated independently of the final diagnosis? — **answered: not with the existing scoring**

- Required lab categories and preferred imaging are defined **per final pathology**. For example, appendicitis awards 2 points for ultrasound first, while diverticulitis awards 2 for CT (FW:`evaluators/*_evaluator.py`, `required_lab_tests`, `score_imaging`). "Unnecessary" tests are also relative to the true pathology's lists.
- Scoring a bottleneck or direct planner against these lists rewards reconstructing `D_final` (fails G9).
- **Surviving path:** a presenting-complaint-level reference that depends only on `S_t`. Examples are an abdominal-pain workup panel and imaging appropriateness by pain location (ACR Appropriateness Criteria style), plus "must-not-miss" tests. Building it needs clinician input. Actual orders from MIMIC-IV `poe` with timestamps could serve as contextual grounding.

### Q10. Surviving sample size — **open (blocked)**

The starting cohort is 2,400 (appendicitis 957, cholecystitis 648, diverticulitis 257, pancreatitis 538). Selection already required HPI, PE ≥ 40 characters, labs, abdominal imaging, and a primary-diagnosis match (DS:`dataset/dataset.py:606-664`), so the cohort is pre-filtered toward complete records. Diverticulitis (257) is the binding stratum for per-pathology analyses.

### Q11. Clinician annotation needed? — **provisional answer: yes, for a limited purpose**

- **Not needed** for `D_t` itself: MIMIC-CDM can only support a model-generated bottleneck, so the study is framed that way.
- **Needed** for any diagnosis-independent examination reference (Q9), and for adjudicating a patient-specific treatment reference (Q8). Both are prerequisites for primary endpoints on this dataset.
- Existing resource: an 80-case physician-evaluation subset (20 per pathology; DS:`CreateDataset.py:101-173`). It was used for comparing physicians and models on diagnosis with full information. It is not early-impression annotation.

### Q12. Evidence-source matrix — unchanged from the plan

---

## Row-level results, part 1 (2026-09-29)

These results come from the release only, via `audit.cdm_audit` (inventory, hindsight, treatment, sample) run on gbminipc. The aggregates are in `results/phase0/mimic_cdm/`. Timing (Q3) is still waiting on the MIMIC-IV downloads.

**Q2: the release has no lab or microbiology timestamps.** `laboratory_tests.csv` has only `hadm_id, itemid, valuestr, ref_range_lower, ref_range_upper`. `microbiology.csv` has only `hadm_id, test_itemid, valuestr, spec_itemid`. The PhysioNet page lists `charttime` for labs, but the release does not include it. Lab timing must be rebuilt from MIMIC-IV `labevents` (`audit.cdm_audit.load_lab_times`, which mirrors the upstream selection and checks that values match). All 2,400 cases have HPI and PE. The median is 52–60 lab items and 1–2 radiology reports per case; the maximum is 89 reports.

**Q5: lexicon screening rates** (share of cases with at least one flag; screening only, the manual audit decides):

| Pathology | HPI any flag | PE any flag | Radiology any flag | Radiology contains the upstream `____` redaction marker |
|---|---|---|---|---|
| Appendicitis | 29.2% | 0.9% | 69.9% | 42.1% |
| Cholecystitis | 64.5% | 2.9% | 84.0% | 26.9% |
| Diverticulitis | 73.5% | 3.5% | 91.1% | 51.0% |
| Pancreatitis | 85.3% | 3.5% | 77.3% | 33.5% |

- **PE (S1):** the flag rate is low (≤ 3.5%), which is encouraging.
- **HPI (S0):** the flag rate is high. Pancreatitis HPIs flag test results in 63.4% of cases, for example lipase values or ED imaging. This supports the concern that S0 already contains S2/S3 information.
- **Radiology (S3):** 27–51% of cases have a report that originally named the target disease (the redaction marker). Imaging is close to an oracle for the diagnosis.

**Q7: prevalence of patient-conditional treatment items** (items the rubric requires only for some patients):

| Pathology | At least one conditional item | Items |
|---|---|---|
| Appendicitis | 84.4% | appendectomy 84.4% |
| Cholecystitis | 71.8% | cholecystectomy 71.8% |
| Diverticulitis | 23.7% | colectomy 15.2%, drainage 12.8% |
| Pancreatitis | 44.8% | ERCP 36.4%, biliary cholecystectomy 19.3%, drainage 3.2% |
| **Overall** | **65.6%** | |

This passes the pre-set 30% threshold numerically. It does **not** rescue the existing rubric: Q8 still fails, because unrequired items are not penalized, so a label-only planner that lists every item still saturates it.

It does reveal a candidate endpoint. Whether the patient received a procedure is a decision that varies within each diagnosis: operative vs non-operative management, and ERCP or not. Scored with precision **and** recall, a label-only planner is limited to the base rate. For appendicitis, "always operate" is right 84.4% of the time; for pancreatitis, "always ERCP" is right 36.4% of the time. A richer-state planner can beat that only by using patient-specific information. This is a clean form of the treatment-sufficiency question (`D_final` → procedure vs richer state → procedure).

Under G11 it is **observed clinician behavior**, not optimal care. Timing also matters: the procedure decision has to be predicted from information available before the procedure (see the Q3 timing results).

**Q10 (partial):** the manual-audit sample has been drawn (50 per pathology, seed 20260929, IDs kept in the private directory on gbminipc).

## Row-level results, part 2 (2026-09-29): Q3 timing

Source: `results/phase0/mimic_cdm/timing.json`, `audit.cdm_audit timing`. Lab times were reconstructed from `labevents`. Counts below 10 are suppressed.

- **Anchors:** ED arrival 1,638; ED registration 667; admission 95. No case lacks an anchor.
- **Radiology** (all release reports timed via MIMIC-IV-Note):
  - median report time after arrival: 3.6 h (appendicitis), 5.3 h (cholecystitis), 18.6 h (diverticulitis), 21.9 h (pancreatitis);
  - reports more than 24 h after arrival: 21 / 33 / 47 / 48%.
- **Labs:** 95.2% of release items timed, 80.2% with value agreement. Median 0.9–1.5 h; 2.5–12% more than 24 h after arrival.
- **G1 conclusion:** the released S2/S3 are whole-admission sets, not stage snapshots. Time-cut reconstruction is **feasible**: the landmark table in `src/preflight` does it, and leakage assertions pass at 3 h and 6 h.

## Gate status

| Gate | Status | Basis |
|---|---|---|
| G1 Temporal input validity | **fail as released; repair possible** | Discharge-derived S0/S1; whole-admission "first" labs; all-admission radiology (Q3). Repair needs MIMIC-IV timestamps and a row audit. |
| G2 Diagnosis-state validity | **pass (classified)** | Label = `D_final`; any `D_t` must be model-generated (Q1). |
| G3 Examination-action availability | partial | Framework supports lab/imaging requests; only a diagnosis-specific reference exists (Q9). |
| G4 Treatment-action availability | partial | Rubric plus observed procedures; no plan-level or dose/timing reference (Q6/Q7). |
| G5 Quality target independent of diagnosis | **fail (existing metrics)** | Q8, Q9. |
| G6 Coverage | open | Rows needed. |
| G7 Leakage | open, high risk | Q3, Q5. |
| G8 Effective sample size | open | Q10. |
| G9 Evaluation independence | **fail (existing metrics)** | Evaluator keyed to true pathology; treatment scored only if correctly diagnosed; label-only oracle saturates treatment. |
| G10 External validation | not evaluated | Depends on ER-REASON / eICU preflight. |
| G11 Treatment-ground-truth semantics | classified: guideline-derived dictionary + observed procedures | Not optimal care; not patient-level guideline adjudication. |
| G12 Diagnostic timing semantics | not applicable | No clinician early diagnosis in the dataset. |

## Interim assessment (not a final Phase 0 decision)

MIMIC-CDM **as released and as scored cannot test the hypothesis**. Its examination and treatment metrics are keyed to the final diagnosis, and its early-stage inputs are not time-cut. The hypothesis is not refuted; the dataset simply cannot discriminate.

What remains is a **narrowed** use that requires new construction:

1. Time-cut S2/S3 using MIMIC-IV timestamps, and an audited or triage-based S0/S1.
2. A diagnosis-independent examination reference at the presenting-complaint level (needs a clinician).
3. Optionally, a patient-specific treatment reference from time-stamped MIMIC-IV orders, framed as observed behavior and adjudicated on a subset.

Whether this is worth building depends on the row audit (Q3, Q5, Q10). It also depends on whether ER-REASON or eICU offer a cheaper route to a diagnosis-independent planning target.
