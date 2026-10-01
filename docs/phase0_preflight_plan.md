# Phase 0: Dataset Semantic Preflight Plan — MIMIC-CDM first

**Status: APPROVED by the author on 2026-09-29, with the proposed thresholds fixed as written** (see [decision_log.md](decision_log.md)). Progress: [gates/mimic_cdm.md](gates/mimic_cdm.md). Phase 0 involves reading documentation and code and inspecting rows. It includes no model training, no LLM inference on patient data, and no endpoint computation.

## Ground rules

- Findings go into `docs/gates/mimic_cdm.md` using the template in [data_gates.md](data_gates.md), with evidence locators (doc URL + section, repo commit + `file:line`, or query + count).
- Raw rows and row-level extracts stay outside Git (local credentialed storage only). Commit only aggregate counts and de-identified, DUA-compliant paraphrases. Do not quote verbatim patient text.
- Record the dataset version and code commit inspected.
- Pass/fail criteria below are proposals. The author fixes them **before** inspection begins; they are not relaxed afterwards.
- Sampling for manual audits: a stratified random sample (by diagnosis), size fixed in advance (proposed: 50 cases per pathology, 200 total), with the random seed recorded.

## Prerequisite P0: access

Confirm credentialed access to MIMIC-IV (hosp, ED, note modules) and MIMIC-IV-Ext-CDM, and record the exact versions. **If access is missing, Phase 0 stops at documentation-only review**, and questions needing rows (Q3, Q5, Q10) remain open.

## Proposed order

1. Documentation and paper pass: Q1, Q2, Q4, Q6.
2. Source-code pass (benchmark framework): Q6, Q7, Q8, Q9.
3. Raw-row audit: Q3, Q5, Q10.
4. Synthesis: Q11, gate decisions, go/stop recommendation.

Early stop: if Q1 plus Q3 show that S0–S2 cannot be built leakage-free **and** Q7/Q8 show that treatment reduces to disease mapping, recommend stopping MIMIC-CDM as the primary dataset before the full audit.

---

## Q1. What is the exact provenance and timing semantics of the diagnosis label?

- **Evidence needed:** how the target label was derived (discharge diagnosis text, ICD codes, primary vs secondary, manual review); inclusion/exclusion rules; whether any case-level early impression exists.
- **Where to look:** PhysioNet dataset page and README; the paper's Methods and supplement; dataset-construction code; label columns in the raw rows.
- **Pass:** the label is fully documented as `D_final`, and it is used only as a terminal reference or explicit oracle arm. (MIMIC-CDM is not expected to pass as an *early* diagnosis source.)
- **Fail:** provenance cannot be determined, or labels were chosen using information that also shaped input fields (for example, cases selected by keywords in the HPI).
- **If it fails:** use MIMIC-CDM only for the treatment-sufficiency oracle experiment, or not at all. Look for early impressions in ER-REASON (Phase 2).

## Q2. What information is available in HPI, PE, labs, imaging, procedures, and treatment fields?

- **Evidence needed:** a field inventory with type, source table/note, per-case coverage, and length distribution.
- **Where to look:** dataset documentation; construction code; raw files (schema and counts).
- **Pass:** each field maps to an identifiable MIMIC-IV source with known timing.
- **Fail:** one or more stage-defining fields have unknown or mixed provenance.
- **If it fails:** drop stages built on those fields and re-scope the stages (for example, S0 = triage chief complaint from MIMIC-IV-ED).

## Q3. Can S0–S4 snapshots be reconstructed without future leakage?

- **Evidence needed:** for each stage, a rule set; a manual audit of sampled cases for post-*t* content (hindsight phrases, diagnosis names, procedure mentions, treatment response); cross-check of lab/imaging timestamps against the ED arrival and admission timeline in raw MIMIC-IV.
- **Where to look:** raw CDM rows; MIMIC-IV `labevents` (charttime/storetime), `radiology` notes (charttime), `edstays`/`triage`; the dataset's own filtering code.
- **Pass (proposed):** after documented automatic cleaning, ≤ 5% of audited cases per stage show residual leakage that names or strongly implies the final diagnosis or treatment, with at least S0/S1 and S2 passing.
- **Fail:** HPI/PE are routinely retrospective, or cleaning would remove clinically essential content.
- **If it fails:** (a) rebuild S0 from time-stamped triage data and S2/S3 from time-stamped labs and radiology in raw MIMIC-IV; (b) restrict to later stages only (S3/S4) plus the treatment-sufficiency question; (c) stop on MIMIC-CDM.

## Q4. Which fields derive from discharge summaries?

- **Evidence needed:** field-to-source mapping, especially HPI and PE.
- **Where to look:** paper Methods; construction code (note-section parsing); MIMIC-IV-Note `discharge` table; text matching of CDM fields against discharge notes for sampled cases.
- **Pass:** discharge-derived fields are identified and either excluded from early stages or shown to be admission-time content (for example, an "on admission" PE section with no hindsight markers in the audit).
- **Fail:** early-stage fields are discharge-derived and cannot be separated from hindsight.
- **If it fails:** same as Q3(a)–(c).

## Q5. Which fields contain hindsight information?

- **Evidence needed:** a documented hindsight lexicon (for example "found to have", "s/p", "POD", "was taken to", "diagnosed with", diagnosis names, procedure names); automatic flag rates per field; manual confirmation on the audit sample; radiology report redaction status.
- **Where to look:** raw rows; construction code (any redaction or masking); radiology impressions.
- **Pass:** hindsight is detectable and removable with measured precision/recall on the audit sample, and residual rate meets the Q3 threshold.
- **Fail:** hindsight is pervasive or implicit (for example, PE written with knowledge of the diagnosis) and cannot be removed reliably.
- **If it fails:** exclude affected fields from early stages. If radiology names the diagnosis, treat S3 as near-oracle and state so.

## Q6. How does the original benchmark define treatment quality?

- **Evidence needed:** the exact treatment evaluation logic: reference items per pathology, matching method (keyword, ontology, LLM), and scoring.
- **Where to look:** paper Methods and supplement; framework evaluation code; any rubric files.
- **Pass:** the logic is fully specified and reproducible from code.
- **Fail:** the logic is unspecified, not released, or depends on an unreleased LLM judge.
- **If it fails:** the treatment endpoint must come from elsewhere (patient-specific procedure/medication data plus clinician adjudication), or treatment is dropped as an endpoint for MIMIC-CDM.

## Q7. How patient-specific are the treatment criteria?

- **Evidence needed:** for each pathology, classify each rubric item as disease-level (always required given the diagnosis) or conditional on patient features (severity, complications, comorbidity, contraindication, timing). Compute the share of conditional items and how often they apply across cases.
- **Where to look:** evaluation code and rubric (from Q6); raw rows to count how often conditional branches trigger (for example, cholangitis, perforation, abscess, severe pancreatitis).
- **Pass (proposed):** conditional items make up a meaningful share of the score and apply in a meaningful fraction of cases (thresholds fixed by the author beforehand; a starting proposal is ≥ 30% of cases with at least one triggered conditional item).
- **Fail:** the rubric is essentially `diagnosis → standard treatment`.
- **If it fails:** MIMIC-CDM is unsuitable as the primary control-layer (treatment) endpoint. Keep it for examination planning only, or build a patient-specific treatment reference (Q8 path).

## Q8. Can treatment quality be separated from simple disease-to-guideline mapping?

- **Evidence needed:** a test where an oracle planner given only `D_final` is scored with the existing rubric (conceptually, or by rule-based simulation without an LLM). If the oracle reaches near-maximum scores, the rubric cannot detect bottleneck cost. Also identify candidate patient-specific targets in raw data: actual procedures, timing of surgery, antibiotic choice relative to allergies/renal function, dose adjustments.
- **Where to look:** rubric (Q6/Q7); MIMIC-IV `procedures_icd`, `poe`, `prescriptions`, `emar`, allergy information if available.
- **Pass:** a label-only oracle scores meaningfully below the ceiling, **or** a feasible patient-specific supplementary target exists with defined semantics (G11: observed behavior, not optimal care).
- **Fail:** a label-only oracle saturates the rubric and no patient-specific target is defensible.
- **If it fails:** drop the treatment endpoint on MIMIC-CDM. The treatment-sufficiency question moves to eICU (Phase 3) or requires clinician adjudication.

## Q9. Can early examination planning be evaluated independently of final diagnosis?

- **Evidence needed:** the benchmark's lab/imaging request scoring. Is the reference set defined per final diagnosis? Is there a diagnosis-independent reference for the presenting complaint (for example, abdominal pain workup guidelines)?
- **Where to look:** framework evaluation code; the guidelines cited in the paper; general abdominal pain workup guidance (for example ACR Appropriateness Criteria).
- **Pass:** a reference can be defined from `S_t` alone (presenting-complaint-level guidance plus critical "must-not-miss" tests), so the metric does not reward guessing `D_final`.
- **Fail:** the only available reference is final-diagnosis-specific.
- **If it fails:** construct a complaint-level reference (requires a clinician), or report the examination endpoint as diagnosis-conditional and restrict claims accordingly. Both options require author approval.

## Q10. What sample size survives after all leakage exclusions?

- **Evidence needed:** an attrition flow per stage and action type: total → access/version → field completeness → leakage exclusions → endpoint availability. Compare retained and excluded cases by pathology and complexity proxies (length of stay, complications).
- **Where to look:** raw rows plus the rules from Q3–Q5 and Q9.
- **Pass (proposed):** the retained count meets a minimum from a power estimate for a paired comparison. The author fixes the effect size and margin beforehand (open question Q11). As a placeholder, several hundred paired cases per stage.
- **Fail:** too few cases, or attrition is strongly selective.
- **If it fails:** combine stages, restrict to a single stage and action, or stop on MIMIC-CDM.

## Q11. Do we need clinician annotation for early diagnostic impressions?

- **Evidence needed:** outcomes of Q1, Q3, Q9, and whether ER-REASON provides documented early differentials.
- **Where to look:** Phase 0 findings; ER-REASON documentation.
- **Pass (no annotation needed):** the study is framed purely with a model-generated `D_t` as an experimentally imposed bottleneck, and the examination reference does not need clinician input.
- **Fail (annotation needed):** claims require realistic clinician-level early impressions, or the examination reference needs expert construction.
- **If needed:** scope a small blinded annotation subset (frozen `S_t` snapshots, differential + next tests) with protocol, annotators, and budget. This requires separate author approval and possibly ethics review.

## Q12. Which questions require inspecting source code, dataset documentation, or raw rows?

| Question | Documentation / paper | Source code | Raw rows (credentialed) | Clinician input |
|---|---|---|---|---|
| Q1 label provenance | ✓ | ✓ | ✓ | |
| Q2 field inventory | ✓ | ✓ | ✓ | |
| Q3 stage reconstruction | | ✓ | ✓ (+ raw MIMIC-IV) | |
| Q4 discharge derivation | ✓ | ✓ | ✓ (+ MIMIC-IV-Note) | |
| Q5 hindsight content | | ✓ | ✓ | optional |
| Q6 treatment quality definition | ✓ | ✓ | | |
| Q7 patient specificity | | ✓ | ✓ | ✓ recommended |
| Q8 separable from mapping | | ✓ | ✓ (+ raw MIMIC-IV) | ✓ recommended |
| Q9 exam eval independence | ✓ | ✓ | | ✓ if a new reference is needed |
| Q10 surviving sample | | | ✓ | |
| Q11 annotation need | ✓ | | | decision |

## Phase 0 outputs

1. `docs/gates/mimic_cdm.md`: G1–G12 with evidence.
2. Field provenance inventory (aggregate only).
3. Leakage lexicon and audit results (rates, not text).
4. Treatment rubric analysis (disease-level vs conditional items).
5. Attrition flow.
6. A go / narrow / stop recommendation for Phase 1, for author decision.

## Possible Phase 0 outcomes

- **Go:** examination and/or treatment endpoints pass critical gates at one or more stages.
- **Narrow:** only the treatment-sufficiency oracle experiment, or only later stages, or only examination planning is supported.
- **Stop (MIMIC-CDM):** move the preflight to ER-REASON or eICU. A documented negative feasibility finding is a legitimate outcome.
