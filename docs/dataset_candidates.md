# Dataset candidates

**Evidence status.** Descriptions below come from recollection of published descriptions and from the author's brief. **None has been verified against dataset documentation, source code, or raw rows in this repository.** Statements marked *(verify)* are Phase 0 checks, not established facts. Access to each dataset (PhysioNet credentialing, data use agreements) has not been confirmed.

---

## A. MIMIC-IV-Ext Clinical Decision Making (MIMIC-CDM)

**Source (verify).** Hager et al., *Nature Medicine* 2024, "Evaluation and mitigation of the limitations of large language models in clinical decision-making"; dataset on PhysioNet as MIMIC-IV-Ext-CDM; evaluation framework code on GitHub.

**Recalled content (verify).** About 2,400 emergency admissions with abdominal pain and four target pathologies (appendicitis, cholecystitis, diverticulitis, pancreatitis). Per-case HPI, physical examination, laboratory results, microbiology, radiology reports, procedures, and discharge diagnosis. The framework lets a model request physical examination, labs, and imaging step by step.

**Strengths**

- Designed for sequential clinical decision-making.
- Separates HPI, PE, labs, imaging, procedures, treatment-related information.
- Supports interactive examination requesting.
- Has existing diagnostic and treatment evaluation logic.
- A natural candidate for a controlled proof-of-concept.

**Weaknesses and critical concerns**

- The target disease label is largely the **final / primary discharge diagnosis**. It is suitable as a terminal reference diagnosis and for post-diagnostic treatment-sufficiency experiments. It is **not** automatically a valid early diagnostic impression.
- HPI and PE may be extracted from **discharge summaries** *(verify)*. If so, they can contain hindsight language ("was found to have...", "taken to OR") and may not reflect what was known at presentation.
- Only four diagnoses, all abdominal. Treatment may collapse to disease-level mappings (appendicitis → appendectomy). If the treatment rubric is mostly that mapping, it cannot distinguish a bottleneck from a direct-state planner, because the label already determines the correct answer.
- Examination-request evaluation may be defined relative to the final diagnosis *(verify)*. That would reward reconstructing `D_final` and fail G9.
- Radiology reports may name the diagnosis. Whether and how the dataset redacts them is unknown *(verify)*.

**Temporal semantics.** Stage ordering (HPI → PE → labs → imaging) is imposed by the benchmark design. Whether the content of each field respects that ordering is unknown. Lab and radiology timestamps in the underlying MIMIC-IV may allow independent checks *(verify)*.

**Possible uses**

1. *Treatment sufficiency:* `D_final → treatment plan` versus `richer patient state → treatment plan`. This asks whether diagnosis alone is sufficient **once diagnosis is known**. It does not need an early diagnosis.
2. *Controlled diagnostic bottleneck:* `S_t → model-generated D_t → next examination` versus `S_t → richer state → next examination`, where `D_t` is explicitly an experimentally imposed bottleneck.

**Likely role.** Phase 1 proof-of-concept, **conditional** on passing G1, G5, G7, G9, and G11.

---

## B. ER-REASON

**Source (verify).** An emergency-department clinical reasoning benchmark (2025) built from de-identified ED records, with notes across the encounter and a smaller subset of physician-authored reasoning rationales. Access route and licence unconfirmed.

**Fields named in the brief (verify exact names and definitions):** `Rule_Out`, `Decision_Factors`, `Treatment_Plan`, primary ED diagnosis, disposition, and an expert-authored reasoning subset.

**Strengths**

- Contains explicit differential ("rule out") and decision-factor fields, which may approximate a documented early differential.
- Links initial state, differential, decision factors, treatment plan, and final diagnosis.
- May allow validating whether model-generated early impressions resemble physician reasoning.

**Weaknesses and critical concerns**

- Full high-quality reasoning annotation covers only a limited subset.
- ED notes may contain retrospective or end-of-encounter information.
- Documentation is not the clinician's internal mental state.
- Whether rationales were written prospectively or reconstructed from the full record is unknown *(verify)*.

**Temporal semantics.** Must be audited per note type. Do not treat notes as clean prospective reasoning trajectories without timing evidence.

**Likely role.** Phase 2: validation of early differential reasoning and of model-generated `D_t` against documented reasoning. Not the primary proof-of-concept.

---

## C. eICU Collaborative Research Database

**Source (verify).** Pollard et al., *Scientific Data* 2018. Multicenter US ICU database (about 200k ICU stays, 2014–2015). Structured tables including `diagnosis` (with offset from unit admission, priority, active-upon-discharge flag), `treatment` (with offset), care-plan tables, medications, infusions, labs, and periodic vitals.

**Strengths**

- Large and multicenter.
- Time-stamped structured problem-list diagnoses and treatments.
- Care-plan documentation.
- Potential for frozen-time-point designs: `X_≤t, D_≤t → next treatment/action`.

**Weaknesses and critical concerns**

- A problem-list entry is not a full differential diagnosis.
- **Entry time ≠ formation time.** A diagnosis may be entered after it was formed, or in batches.
- Recorded treatment is observed behavior, not optimal treatment.
- Documentation density varies widely by hospital *(verify)*.
- The ICU setting shifts the question: most diagnostic work may already have occurred before ICU admission.

**Temporal semantics.** Offsets exist. Their meaning (charting time versus clinical time) must be audited, for example by comparing diagnosis offsets with the offsets of related orders and results.

**Likely role.** Phase 3: temporal and multicenter validation. Not the first proof-of-concept.

---

## D. Raw MIMIC-IV

**Content (verify).** Hospital module: provider order entry (`poe`), labs, prescriptions, pharmacy, eMAR, procedures, and ICD diagnoses. ED module (MIMIC-IV-ED): triage (chief complaint, vitals, acuity) and ED diagnoses. Note module: discharge summaries and radiology reports.

**Strengths**

- Rich, time-stamped action-side data: orders, administrations, procedures.
- ED triage chief complaint and vitals are recorded at triage. They may serve as a leakage-resistant S0 anchor for cross-checking MIMIC-CDM's HPI-derived S0 *(verify)*.
- Lab and radiology timestamps can audit stage ordering.

**Major danger**

- `diagnoses_icd` codes are **discharge / billing** codes. Raw MIMIC-IV must not be used to build `early diagnosis → later treatment` unless the diagnosis timing semantics are independently validated.
- Discharge summaries are retrospective by construction.

**Likely role.** Supporting source for auditing timing and action targets (for example, whether an order preceded a result). Not a source of early diagnoses.

---

## Summary

| | MIMIC-CDM | ER-REASON | eICU | Raw MIMIC-IV |
|---|---|---|---|---|
| Early diagnosis source | None (model-generated only) *(verify)* | Documented differential, subset *(verify)* | Problem list with entry offsets | None |
| Final diagnosis | Discharge-derived | ED primary diagnosis | Problem list at discharge | ICD billing |
| Exam action target | Benchmark exam requests | Unknown | Orders/labs | Orders |
| Treatment target | Guideline rubric *(verify)* | Documented plan | Recorded treatments | Orders/eMAR |
| Main role | Phase 1 PoC (conditional) | Phase 2 validation | Phase 3 validation | Timing audit support |
