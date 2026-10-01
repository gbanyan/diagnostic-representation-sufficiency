# Data gates — ER-REASON

- **Dataset:** ER-REASON: A Benchmark Dataset for LLM-Based Clinical Reasoning in the Emergency Room, PhysioNet v1.0.0 (published 2025-10-23; the only version; DOI 10.13026/55s7-3c27)
- **Evaluated on:** 2026-09-29
- **Phase 0 pass completed:** public documentation + source code only. **No access requested; no rows seen.** Every row-level statement below is unverified.
- **Sources inspected:**
  - PhysioNet project page, `https://physionet.org/content/er-reason/1.0.0/` (sections *Methods*, *Data Description*, *Access*); license page `view-license/1.0.0/`; DUA page `view-dua/1.0.0/` (PN below)
  - Paper arXiv:2505.22919: **v1** (2025-05-28; 72-rationale design; P1 below) and **v3** (2026-05-11; SCT redesign; P3 below). v2 not read separately.
  - Code: `AlaaLab/ER-Reason` @ `4e8036ce` (2026-05-05), cloned to the git-ignored `external/ER-Reason/`. References are `ER:<path>:<line>`. `SCT/` = `Experiments/SCT Reasoning/`, `STD/` = `Experiments/Standard Clincal Tasks/` (the directory name misspells "Clinical"), `V1/` = `ER-Reason-V1-Archive/`.
  - GitHub issues #1–#3 on `AlaaLab/ER-Reason` (read 2026-09-29).
  - PhysioNet news post "Responsible use of MIMIC data with online services like GPT" (2023-04-18).

## P0 — Access

**Status: not requested.** Access is restricted (PN *Access*):

1. PhysioNet credentialed user. The author already has this (see [mimic_cdm.md](mimic_cdm.md) P0).
2. CITI "Data or Specimens Only Research" training, submitted to PhysioNet.
3. Sign the **PhysioNet Contributor Review Health Data Use Agreement 1.5.0**. License: PhysioNet Contributor Review Health Data License 1.5.0.
4. **Submit a project request that the dataset authors review** ("users must have individual studies reviewed by the contributor"). Unlike MIMIC, approval is per study and is not automatic.

The DUA text also requires up-to-date GCP training, which is not the CITI course listed on the page. The two access requirements are inconsistent; ask the contributors which applies.

**External LLM APIs: unresolved. Assume prohibited until the contributors approve in writing.**

- The DUA states: "will not share access to the data with anyone else" (PN DUA, clause 1).
- PhysioNet's 2023 guidance is written for the *Credentialed* DUA (MIMIC). It says sending data through third-party APIs such as OpenAI or ChatGPT is prohibited. It names Azure OpenAI (with the human-review opt-out), Amazon Bedrock, Vertex AI Gemini, and Anthropic Claude as acceptable. Whether this guidance covers *Contributor Review* datasets is **unverified**.
- The authors' current code sends notes through **OpenRouter** with `zdr: True` (ER:`STD/disposition.py:161`; ER:`SCT/sct.py:230`). OpenRouter is not on PhysioNet's list. The V1 code used a UCSF-internal Azure endpoint (ER:`V1/Rationale/Open-AI-Models/er_rationale.ipynb`, cell 0), which is available only to insiders. Neither establishes what an external user may do.
- Plan: state the intended model endpoints in the access request. Default to local open-weight models.

**Release contents are narrower than the paper and code imply (partly verified).** PN *Data Description* documents only `er_reason.csv`. The repo README lists five more files: `icd_10_codes.csv`, `annotated_sct.csv`, `sct-annotations.csv`, `sct_cleaned_annotations.csv`, and `gt_clean.csv` (ER:`README.md:31-38`). GitHub issue #3 (2026-06-08, open, unanswered) comes from a credentialed user who reports that **v1.0.0 ships only `er_reason.csv`**. We have not verified this ourselves. If it is true, **the SCT annotations (194 cases) and the ICD-10 ground truth are not obtainable** through PhysioNet today.

---

## Findings by preflight question

### Q1. Fields and who authored them — **answered (docs + code); counts unverified**

One row per ED encounter in `er_reason.csv` (PN *Data Description*; ER:`ER-Reason_Column_Descriptions.md`).

| Field | Definition (verbatim or near) | Author / source | Timing | Cases |
|---|---|---|---|---|
| `primarychiefcomplaintname` | Chief complaint on arrival; standardized | Structured EHR | Triage | All (inclusion is not stated to require it) |
| `acuitylevel` | ESI at triage | Structured EHR (triage nurse) | Triage | 3,970 with acuity; 14 unspecified (P3 Table 11) |
| `ED_Provider_Notes_Text` | Current visit's ED provider note | Treating ED clinician | **End of encounter** (Q3) | All (required for inclusion) |
| `One_Sentence_Extracted` | "Key one-liner summary extracted from the current ED provider note" | Clinician text, extracted by an **unknown method** (manual, regex, or LLM) | End-of-encounter document | Unverified |
| `primaryeddiagnosisname` | "Diagnosis given from the ER doctor at the end of current ER visit" | Structured EHR (ED clinician) | ED departure | All (inclusion requires not `*Unspecified`) |
| `eddisposition` | Disposition when leaving the ER | Structured EHR | ED departure | ~All (P3 Table 11: 3,970 tabulated) |
| `Rule_Out` | "Differential diagnosis list made by the physician given the chief complaint, demographics, and one-liner (acts as a mental model for the pre-encounter)" | **Study-recruited EM residents/attendings, retrospective and hypothetical** | Written in the study app, not during care | **72** (P1 §3.2) |
| `Decision_Factors` | "Factors doctors would deploy to narrow down their differential list" | Same annotators | Same | 72 |
| `Treatment_Plan` | "Factors and treatment plan the physician would choose given the history and physical" | Same annotators | Same | 72 |
| `*_Text` (Discharge summary, Progress, H&P, Consult, Imaging, Echo, ECG) | Labelled "Historical: ... from patient's previous hospital encounter" | Clinical notes | **Year only**; see the Q3 leakage flag | Unknown per type |
| `*_Year`, `ArrivalYearKey`, etc. | Years only; `1970` = missing | Structured EHR | Year granularity | — |

- None of the three reasoning fields is LLM-extracted. They are clinician-authored, but by physicians **reading a case retrospectively**, not the treating team. Nothing in any source says whether annotators were blinded to the ED diagnosis or disposition (**unverified**).
- There is **no hospital final/discharge diagnosis field**. `icd_10_codes.csv` ("ground-truth ICD-10 codes per encounter", multiple rows per encounter; ER:`README.md:34`) has undocumented provenance (ED encounter diagnoses? billing?) and is probably not released (P0).
- The internal working file had full date fields (`ArrivalDateKey`, `Discharge_Summary_Date`, `ED_Provider_Notes_Date`, …) and derived columns `ED_Presentations` and `Generated_Summary`. These appear in a committed notebook output (ER:`V1/Rationale/Open-AI-Models/er_rationale.ipynb`, cell 4). The **public release keeps years only** (PN column table).

### Q2. The expert-authored reasoning subsets — **answered at design level**

There are two distinct expert resources. Neither is contemporaneous documentation.

**(a) 72 rationales (paper v1; in `er_reason.csv` per PN).** EM residents and attendings used a "custom application that guided participants through a sequential workflow designed to mirror their real-world reasoning process". The study was IRB-approved and participants were paid (P1 §3.2; PN *Expert Rationales*). What annotators saw, per field definitions and a V1 statement:

- `Rule_Out`: chief complaint, demographics, and one-liner **only**. "Neither the ER physician nor GPT-4o were provided with the patient's presenting symptoms at the time of differential diagnosis" (P1 §4, discussion of Figure 3).
- `Decision_Factors`: same stage. The mirrored LLM prompt says "NOTHING has currently been performed" (ER:`V1/Rationale/Llama/llama_rationale.py:179`).
- `Treatment_Plan`: adds "the history and physical" from the ED note (the `ED_Presentations` pre-MDM section; ER:`V1/Rationale/Llama/llama_rationale.py:196,207`).

Structure from the committed notebook output (ER:`V1/Rationale/Open-AI-Models/er_rationale.ipynb`, cells 2, 5–6): `rationales.csv` has `user_id`, `encounter_id`, `timestamp`, and one-liner quality ratings (`summaries_*`), then `Rule_Out`, `Decision_Factors`, `Column 3`, `Treatment_Plan`, and `Column 5`. There are 72 encounter IDs. This implies **one annotator per case** (unverified whether any IDs repeat). `Column 3` and `Column 5` are undocumented. Unverified: whether annotators could see the rest of the chart, the ED diagnosis, or the disposition.

**(b) SCT set, 194 cases (paper v3; probably not released).** An EM attending wrote each case from the ED provider note, with 3–5 differentials "derived from the patient note" and evidence steps (a lab, imaging, or an updated exam) linked to each differential. Two attendings independently scored each step from −2 to +2; a third adjudicated. There are 787 items and 194 final rankings, 2,555 annotations in total. Exact agreement between physicians was 52.6% (P3 §2.2). The case authors had the **full note, including the outcome**. The evidence order is an author construction ("corresponds to ... triage intake, ER physician evaluation, and admission", P3 §2.2), not the observed order of care. The SCT "FinalDx" target is the **consensus top-ranked differential**, not the patient's recorded diagnosis (ER:`SCT/sct_eval.py:206-223`).

### Q3. Note types and timestamps; reconstructing what was known at time t — **answered: not from timestamps**

- **No intra-encounter timing.** The release has year-level fields only. No order, result, medication, or note timestamps exist, and the only time structure is section order inside the ED note.
- **The ED provider note is an end-of-encounter document.** The inclusion rule takes "the most recent note of each type created before the encounter's discharge date" (PN *Note Selection*), which is the latest signed version. The authors' own leakage handling shows the note contains a "Final Disposition and ED Course" section, which they cut at that header (ER:`STD/final_diagnosis.py:53-71`; ER:`STD/disposition.py:50-64`), and a "Medical Decision" section. The V1 code splits at that header and treats the text before it as "the H&P part of the ED Provider note" (ER:`V1/Diagnosis/o3-mini/o3_diagnosis.ipynb`, cell 3). Triage vitals are embedded in the note ("Triage Vital Signs:" up to "HENT:"; ER:`STD/acuity.py:44-53`); they are not a separate field.
- **Approximate stage proxies:** S0 ≈ chief complaint + age/sex + triage ESI + triage vitals parsed from the note (+ one-liner, audit needed). S1 ≈ text before "Medical Decision" (HPI/ROS/PE). **S2/S3 cannot be separated.** Labs and imaging appear only inside MDM/ED-course free text, un-timed and mixed with interpretation and plan.
- **HPI and PE are written or finalized at the end of the visit.** HPI in ED notes can contain workup results or course (hindsight). The size of this effect needs a row audit.
- **CRITICAL LEAKAGE FLAG: are "historical" notes really historical?** The documentation labels the other seven note types as coming from the *previous* encounter. The selection rule as written ("most recent note of each type created before the encounter's discharge date") would, however, pick up **current-visit** imaging reports, ECGs, and consults created during the ED stay. For admitted patients, if "discharge date" means hospital discharge, it could also pick up the **current admission's H&P, progress notes, and discharge summary**. The authors' own prompts assert that "everything in the notes is from PAST encounters" (ER:`V1/Rationale/Llama/llama_rationale.py:167`). The final-diagnosis task feeds `Discharge_Summary_Text` as "Past Medical History" (ER:`STD/final_diagnosis.py:117-118`). With only years available, this cannot be settled without rows. A content audit is required (for example, does the imaging report match imaging described in the current ED course?).

### Q4. Time-stamped differential or working diagnosis (G12); is the final diagnosis distinct from the ED diagnosis? — **answered**

- There is **no time-stamped clinician differential**. The treating clinician's differential, if any, sits in the MDM free text of the end-of-encounter note, with no timestamp. How often it appears is unknown.
- `Rule_Out` (72 cases) is an **expert-authored, retrospective, hypothetical differential at a controlled information state** (pre-encounter: chief complaint + demographics + one-liner). It is not the historical physician's impression and has no clinical timestamp. Its "time" is defined by what the annotator was shown, which is exactly what makes it useful (Q9).
- `primaryeddiagnosisname` is the **ED diagnosis at ED departure**, made after the full ED workup. It is not a hospital discharge diagnosis, and no hospital discharge diagnosis field exists (see Q3 on whether one leaks in through `Discharge_Summary_Text`). For this study it plays the role of `D_final` *at the ED scale*. It must never be used as `D_t` for triage or initial assessment.

### Q5. Examination and treatment action targets (G3, G4, G11) — **answered: no observed, timed actions**

- **Observed actions:** none structured. There are no orders, lab or imaging order times, or medication administrations. What was done is recoverable only from MDM/ED-course free text: un-timed, clinician-summarized, and not complete.
- **Structured decisions:** `acuitylevel` (triage ESI) and `eddisposition` (10 categories; P3 §2.3). Both record observed clinician or nurse behavior (G11), not optimal care. Disposition is a management decision, not an exam or treatment.
- **Hypothetical expert plans (72):**
  - `Decision_Factors` is a pre-encounter **examination/investigation plan** (history items, exam findings, labs/imaging, consults) aimed at ruling out the annotator's own differential.
  - `Treatment_Plan` is an initial treatment and disposition plan given the H&P.
  - Semantics (G11): one physician's free-text recommendation per case, retrospective and hypothetical. It is neither guideline-derived nor adjudicated, and it is not what happened.
- **Benchmark scoring of these plans:** the proportion of UMLS CUIs (via cTAKES) from the physician rationale that also appear in the model output (P1 §3.3.3). This is **recall-only**, so verbose outputs are not penalized, just as with MIMIC-CDM's rubric.

### Q6. Can a planning-quality metric avoid rewarding reconstruction of the final diagnosis (G5, G9)? — **existing metrics: no; one constructible path**

- **Existing tasks fail G5/G9 as planning endpoints.**
  - Final diagnosis is diagnosis accuracy.
  - The disposition task **feeds the ED diagnosis to the model as input** (ER:`STD/disposition.py:111-112`), so it is diagnosis-conditioned by design.
  - SCT metrics score belief updating toward a physician consensus on a differential.
  - Treatment planning is CUI recall against one physician's text.
- **Constructible path A (exam planning at S0).** Use `Decision_Factors` as an S0 examination reference. The authoring physician did not see the presenting symptoms (Q2). If they were also blind to the ED diagnosis (**unverified**), the reference does not encode `D_final`, and a `D_final`-oracle planner is *not* guaranteed to maximize agreement.
  - **Caveat 1:** the reference was produced *through* the annotator's own differential ("items necessary to rule out diagnoses on the differential"). It is differential-organized and may favor the bottleneck arm. A measured bottleneck cost would be conservative; a null result would be uninterpretable.
  - **Caveat 2:** n = 72 with a single annotator is a clinician-adjudication-sized subset, not a primary endpoint (G8).
  - **Caveat 3:** the metric must be precision-aware, not CUI recall.
- **Constructible path B (disposition at S1).** Target: observed `eddisposition`. Input: S1 text with MDM and later removed. G9 check (feasible on rows): measure how well `primaryeddiagnosisname` alone predicts disposition. If a label-only oracle nearly saturates it, the target cannot detect a bottleneck cost. Disposition depends on severity, comorbidity, and social factors beyond the label, so it may not saturate (**unverified**). It remains observed behavior (G11), and it is a management endpoint, not an exam or treatment.
- No patient-specific treatment reference (dose, timing, contraindications) exists at scale.

### Q7. Leakage (G7) — **open; high risk**

- **Historical versus current notes:** see the Q3 critical flag. This is the dominant risk.
- **ED note:**
  - End-of-encounter authorship.
  - Truncation depends on literal headers ("Final Disposition and ED Course", "Medical Decision"). The authors' script warns when the header is missing (ER:`STD/final_diagnosis.py:65-66`), so it is not universal.
  - Redaction replaces only the exact `primaryeddiagnosisname` string, case-insensitive (ER:`STD/final_diagnosis.py:68-69`). Synonyms, abbreviations, and ICD text still leak.
  - HPI and PE may embed results.
- **One-liner:** taken from the current ED note. One-liners can carry findings ("… found to have …"). It is an input to `Rule_Out` and to every SCT case, so leakage there contaminates the "pre-encounter" state.
- **SCT evidence:** authored by physicians who had the full note.

### Q8. Coverage (G6) and effective sample (G8) — **open (rows needed); plausible ranges**

- **Full corpus:** 3,984 encounters and 3,437 patients. There are 25,174 notes, about 7 per encounter, at most one per type. 395 chief complaints; the top three are abdominal pain, shortness of breath, and chest pain (PN; P3 §2.1). An ED note is present by construction; the inclusion rule also requires a discharge summary.
- **Unknown until rows are checked:** how many notes have parseable "Medical Decision" and "Final Disposition" headers, how many "historical" notes are truly prior-encounter, and per-type note availability. Plausible S1 + disposition sample: low thousands, if header parsing and the historical-note audit hold up. Note that patients repeat (3,984 encounters from 3,437 patients).
- **Expert subsets:** 72 (rationales; one annotator each). 194 SCT cases, probably unavailable (P0).
- **Adequacy for a primary endpoint:** 72 is too small; ~3,900 could be adequate if a valid target exists. There is no power estimate yet.

---

## Gate status

| Gate | Status | Basis |
|---|---|---|
| G1 Temporal input validity | **fail as released; partial repair possible** | No intra-encounter timestamps; the ED note is an end-of-encounter document. S0/S1 can be approximated only by section parsing. S2/S3 are not separable. "Historical" notes may include current-visit content (Q3). |
| G2 Diagnosis-state validity | **pass (classified)** | `primaryeddiagnosisname` = ED-departure diagnosis (`D_final` at ED scale). `Rule_Out` = expert retrospective hypothetical differential at a controlled S0 information state (72). SCT differentials = expert-constructed from the full note (194, probably unreleased). There is no contemporaneous clinician `D_t`, so any experimental `D_t` is model-generated. |
| G3 Examination-action availability | **partial** | No observed, timed orders. `Decision_Factors` = a hypothetical expert S0 exam plan for 72 cases. |
| G4 Treatment-action availability | **partial** | `Treatment_Plan` = hypothetical expert plan (72). `eddisposition` observed for ~all. Actual treatments exist only as un-timed ED-course free text. |
| G5 Quality target independent of diagnosis | **fail (existing metrics); candidate paths A and B** | Q6. |
| G6 Coverage | open | Rows needed (header parse rate, true-historical rate). |
| G7 Leakage | **open, high risk** | Q3 flag; end-of-encounter note; exact-string redaction only; one-liner provenance. |
| G8 Effective sample size | open; **fails for expert-reference endpoints** | 72 (one annotator each) is too small for a primary endpoint. ~3,900 possible for disposition, after audit. |
| G9 Evaluation independence | **fail (existing metrics)**; path A plausible, pending a blinding check; path B pending the label-only oracle test | The disposition task feeds the ED diagnosis; SCT targets a physician-consensus differential; CUI recall rewards verbosity. |
| G10 External validation | partial | Could serve as a weak second site to MIMIC-CDM for a model-generated `D_t` design at S0/S1. Neither dataset has timed action targets. |
| G11 Treatment-ground-truth semantics | **classified** | Hypothetical single-physician recommendation (72); observed disposition and ESI (all). Not guideline-derived, not adjudicated, not optimal. |
| G12 Diagnostic timing semantics | **fail for clinician `D_t`; not applicable to a model-generated `D_t`** | No timestamps. `Rule_Out`'s "time" is an information state set by the design, not a clinical time. |

## Interim assessment (not a final Phase 0 decision)

- **ER-REASON cannot serve as a primary test of H1.** It has no timed actions, no separable S2/S3, and an end-of-encounter ED note as the main input. It also carries an unresolved risk that "historical" notes contain current-visit content.
- **The Phase 2 role in the candidate list is weaker than assumed.** The "documented differential / rule-out at time t" is not contemporaneous documentation. It is a **72-case, single-annotator, retrospective hypothetical differential** written at a controlled pre-encounter information state. The larger SCT resource (194 cases, adjudicated) is **probably not in the public release**.
- **What it can support, narrowly and conditional on access and audit:**
  1. **Face-validity check of model-generated `D_t` at S0.** Compare the model's S0 differential with `Rule_Out` (72). Report this as agreement with a retrospective expert differential, never as agreement with the treating physician's impression.
  2. **Small blinded exam-planning reference (path A).** Use `Decision_Factors` as a supplementary, clinician-authored check on S0 exam plans. It must be scored with a precision-aware metric. Its differential-organized construction must be declared as a bias toward the bottleneck arm.
  3. **Candidate management endpoint (path B).** Plan disposition from S1, with MDM and later sections removed. It is conditional on the label-only oracle test (G9) and the historical-note audit (G7), and must be worded as agreement with observed disposition.
- **Before requesting access:** confirm with the contributors
  - (i) which files v1.0.0 contains, including the SCT set and `icd_10_codes.csv`;
  - (ii) what annotators saw in the rationale app, including whether the ED diagnosis was hidden;
  - (iii) whether the "historical" notes can include the current visit or admission;
  - (iv) whether an external LLM endpoint may be used, and which one.

  If (iii) is "yes" and cannot be filtered, the note corpus beyond the ED note is unusable for any early-state input.
