# Data gates — eICU Collaborative Research Database

- **Dataset:** eICU-CRD v2.0 (PhysioNet `eicu-crd/2.0`; data released 2018-05-17, PhysioNet page dated 2019-04-15). 200,859 unit stays, 139,367 patients, 208 hospitals, 335 units, 2014–2015.
- **Evaluated on:** 2026-09-29
- **Phase 0 pass completed:** documentation, public code, published literature, and an **aggregate-only** look at the open-access demo (`eicu-crd-demo` v2.0.1, ODbL). **No credentialed data accessed.** Full-data row audit not started (see P0).
- **Sources inspected:**
  - Pollard TJ et al. *Sci Data* 2018;5:180178, doi:10.1038/sdata.2018.178 (full text via Europe PMC, PMC6132188). Cited as `SD:<section>`.
  - PhysioNet project page https://physionet.org/content/eicu-crd/2.0/ and demo page https://physionet.org/content/eicu-crd-demo/2.0.1/.
  - `MIT-LCP/eicu-code` @ `34cece8c` (2024-12-19), cloned to git-ignored `external/eicu-code`. This repo contains the source of the documentation site eicu-crd.mit.edu (`website/content/`) and the per-table notebooks, whose saved outputs were run on the **full** database. Cited as `EC:<path>:<line>` or `EC:<notebook> cell N`.
  - GitHub issues on `MIT-LCP/eicu-code`: #49, #114, #170, #171, #172, #245, #250. Cited as `issue #N`.
  - O'Halloran HM et al. "Characterizing the Patients, Hospitals, and Data Quality of the eICU CRD." *Crit Care Med* 2020, doi:10.1097/CCM.0000000000004633 (PMID 33044284; abstract only read).
  - PhysioNet LLM-use posts: https://physionet.org/news/post/llm-responsible-use/ (2025-09-24) and https://physionet.org/news/post/gpt-responsible-use/ (2023-04-18); PhysioNet Credentialed Health Data License 1.5.0.
  - Demo tables `patient`, `diagnosis`, `treatment`, `admissionDx`, `note`, `medication`, `infusiondrug`, `lab`, `carePlanGeneral`, `physicalExam`, `pastHistory`, `microLab`, `hospital`, fetched individually from `https://physionet.org/files/eicu-crd-demo/2.0.1/` into git-ignored `external/eicu-crd-demo/`. Cited as `DEMO`. Only aggregates are reported. The demo has 2,520 stays and 186 `hospitalid` values, so demo per-hospital figures rest on very small per-hospital counts.
- Claims marked *(unverified)* have no primary-source confirmation.

## P0 — Access

**Status: available (updated 2026-09-29).** The author signed the data use agreement; `eicu-crd/2.0` now returns HTTP 200 from gbminipc. Full data not downloaded; the row audit has not started. Earlier the account returned HTTP 403 (see [mimic_cdm.md](mimic_cdm.md), P0). Access needs: PhysioNet credentialing (done), CITI "Data or Specimens Only Research" training, and signing the PhysioNet Credentialed Health Data Use Agreement 1.5.0 on the eICU project page (PhysioNet page, "Access"). The DUA forbids sharing access with anyone else (clause 3) and requires releasing code for publications (clause 8). Pollard et al. also mention a non-re-identification clause covering **institutions** (`SD: Usage Notes/Data access`).

**LLM use.** PhysioNet's 2025-09-24 post covers "credentialed and restricted data on PhysioNet, including MIMIC-III, MIMIC-IV, MIMIC-CXR, and their derivatives." eICU-CRD is credentialed PhysioNet data, so the post applies *(the post does not name eICU explicitly)*. The post:

- prohibits "sharing access to the data with third parties, including sending it through APIs or using it on online platforms";
- strongly recommends locally deployed LLMs;
- allows cloud services only if the researcher verifies zero data retention, no training use, and no human review;
- warns that zero-retention claims may be insufficient;
- names and endorses no services.

The older 2023-04-18 post named Azure OpenAI, Amazon Bedrock, Vertex AI Gemini, and Anthropic Claude as options. It is still online and not marked as superseded. **Which post governs is unverified.** Treat the 2025 post as binding and plan for a local model or an explicitly verified zero-retention deployment.

---

## Findings by question

### Q1. `diagnosis` table — semantics

| Column | Documented meaning | Evidence |
|---|---|---|
| `diagnosisOffset` | "number of minutes from unit admit time that the diagnosis was **entered**" | EC:`website/content/eicutables/diagnosis.md:38` |
| `diagnosisString` | Path from the eCareManager pick-list hierarchy, e.g. `pulmonary\|respiratory failure\|hypoxemia` | same:39 |
| `ICD9Code` | Mapped ICD-9 **and** ICD-10; absent when the pick-list node is too general | same:40; EC:`notebooks/diagnosis.ipynb` cells 0, 6–9 |
| `diagnosisPriority` | Pick-list value: Primary / Major / Other. The page says "Sequence does indicate relative severity" and that priority "is not required" | same:15, 41 |
| `activeUponDischarge` | Whether the diagnosis was active at unit discharge | same:36; issue #114 |

- **Source and author.** Rows come from the "Active Diagnosis/Treatment sections of the eCareManager medical record" (same:23), built from `patientDxRx*` source tables (EC:`website/content/gettingstarted/overview.md:38`). The documentation says they are "documented in the ICU stay by clinical staff" (diagnosis.md:27). It does not say whether bedside or remote tele-ICU staff enter them. *(Unverified: author role.)* The eICU program is a tele-ICU that supplements bedside teams (`SD: Background`). Most encounters were managed by non-intensivists (O'Halloran 2020).
- **Scope.** The table excludes diagnoses documented before or after the ICU stay. It "does not indicate which diagnoses were resolved or ruled-out nor … when/if a diagnosis was removed" (diagnosis.md:27).
- **Recording pattern: re-saved snapshots.** In the documentation's worked example, the same problem set is written at 48 min, re-written at 2153 min, and re-written at 2159 min with `activeUponDischarge=True` (EC:`notebooks/diagnosis.ipynb` cell 6). The maintainers describe the parallel `treatment` table as a pick-list "continually recorded … until the final record" (issue #171). Aggregates from the demo:
  - 59% of (stay, problem) pairs appear more than once.
  - 49% of stays with diagnoses have a single entry batch; the median is 2 batches per stay.
  - 98.4% of `activeUponDischarge=True` rows sit at the stay's last diagnosis offset. The flag is therefore a property of the final save.
- **Revision is visible only implicitly.** In demo stays with at least 2 batches:
  - 32% of distinct problems first appear after the first batch;
  - in 19% of stays, some first-batch problem is missing from the last batch;
  - the Primary problem string changes between the first and last batch in 22% of stays that have Primary entries in at least 2 batches.

  Disappearance can be inferred from snapshot differences, but no removal time exists. Any removal happened somewhere between two saves.
- **Entry timing.** Demo medians:
  - first diagnosis entry per stay: 0.87 h after unit admission (p90 3.8 h);
  - first appearance of each distinct problem: 1.6 h (p90 25.6 h);
  - the last diagnosis save comes a median 21.9 h before unit discharge.

  Pollard et al. report that 86% of patients have an active problem documented within the first 24 h (`SD: Care documentation/diagnosis`). An open issue asks whether offsets for acute conditions approximate onset or diagnosis time; it has no answer (issue #245).
- **Entry time lags care actions (demo; small n; first-order evidence only).**
  - In 86 stays with both a sepsis problem and an IV antibiotic order, the first sepsis entry **followed** the first IV antibiotic order in 76% (median +38 min). In 29% of these stays, the antibiotic order predates ICU admission.
  - For norepinephrine, the first `treatment` entry followed the first `infusiondrug` record in 74% of 86 stays (median +68 min).

  Problem-list entry time is therefore neither formation time nor decision time. It often follows the action that a diagnosis would be expected to motivate.

**`admissionDx` (APACHE admission diagnosis).**

- It is "the primary diagnosis for admission to the ICU per the APACHE scoring criteria." It can be entered from the Care Plan or Admission/Readmission/Progress notes "for the first 36 hours after ICU admission," and is then locked (EC:`website/content/eicutables/admissiondx.md:15, 42`).
- It is selected by "clinicians trained on the APACHE methodology" under APACHE rules: OR or recovery admissions **must** get a surgical diagnosis (same:46–48). Sepsis after surgery is coded as the surgery, so the diagnosis is "specific, but not necessarily sensitive" (EC:`notebooks/admissiondx.ipynb` cell 18).
- The table has about 426 distinct diagnoses (same, cell 17) and one entry offset per stay. In the demo the median entry offset is 0.6 h, 1.2% are entered after 24 h, and no stay has more than one entry offset.
- APACHE prediction also needs the diagnosis to be documented within the first day (`SD: Data Records`).
- **Classification:** a single, early, rule-constrained severity-scoring category. It is not a working diagnosis and has no revisions.

### Q2. Differential or working impression with a formation time? (G2, G12)

**No.**

- The problem list stores asserted active problems. Uncertainty qualifiers are almost absent: in the demo, 0.36% of diagnosis rows contain "suspect", 0.13% "r/o", and 0% "rule out" or "possible".
- Narrative note text, including HPI and assessment prose, was removed during deidentification (EC:`website/content/eicutables/note.md:24`; `SD: note`). The demo `note` table has no HPI rows. Its Assessment-and-Plan rows are view settings ("System View", "Include Rx"), not diagnoses. It also has no `…/Organ System dx(s) and rx(s)/…/Dx` rows, although the documentation gives that path as an example (note.md:35). *(Full-data presence unverified.)*
- Brief Progress Notes carry structured tele-ICU "Interventions" such as "Sepsis – evaluation and management" and "Clinical assessment – ordering diagnostic tests". These are categorical problem tags with no candidate set.

### Q3. Action and context tables — offsets, provenance, coverage

Hospital coverage bands are from `SD: Table 8`, as % of 208 hospitals: none 0% / low 0–20% / medium 20–60% / high 60–80% / excellent 80–100% of stays with any row.

| Table | Offset semantics | Provenance | Coverage (hospitals) | Evidence |
|---|---|---|---|---|
| `diagnosis` | entry | clinician pick-list | none 0.5 / excellent 76.0 | Q1 |
| `treatment` | entry ("was entered") | clinician pick-list, co-saved with diagnosis; "absence … should not be used as evidence a specific treatment was not administered" | none 6.3 / excellent 65.9 | EC:`eicutables/treatment.md:25, 34` |
| `medication` | `drugOrderOffset`, `drugStartOffset`, `drugStopOffset`; **orders**, pharmacist-verified via HL7; administration not guaranteed; `drugOrderCancelled` flag | pharmacy interface; manual subset at sites without an interface | none 16.3 / excellent 72.1 | EC:`eicutables/medication.md:15, 23, 31–42`; `SD: medication` |
| `infusionDrug` | one offset per record (charting of rate) | nursing flowsheet, manual or interfaced | none 26.9 / excellent 6.7; 152 of 208 hospitals have any data | EC:`eicutables/infusionDrug.md:15, 43`; `SD: infusionDrug` |
| `lab` | `labResultOffset` = time drawn; `labResultRevisedOffset` = time a revised value was entered; **no order time, no result-available time** | lab interface; about 158 mapped tests | excellent 96.2 | EC:`eicutables/lab.md:31, 38`; `SD: lab` |
| `microLab` | culture taken | manual; "not populated for a significant number of hospitals" | none 89.4 | `SD: microLab` |
| `carePlanGeneral` | item entry; items carried forward from a previous unit within 24 h | pick-list (ventilation, DVT/stress-ulcer prophylaxis, sedation, code status…) | excellent 96.6 | EC:`eicutables/carePlanGeneral.md:36, 44` |
| `carePlanGoal` / `EOL` / `InfectiousDisease` | entry | pick-list | none 63.0 / 53.9 / 53.9 | `SD: Table 8`; EC:`notebooks/careplan.ipynb` cell 8 |
| `note` | `noteOffset` (date of service) and `noteEnteredOffset` | structured pick-lists only; narrative removed | excellent 79.8 | EC:`eicutables/note.md:24, 32–33` |
| `physicalExam` | entry only | structured pick-lists; free text removed | excellent 77.4 | `SD: physicalExam` |
| `nurseCharting`, `respiratoryCharting`, `nurseCare` | chart time and entry time | flowsheet | varies | `SD` sections |

- There is **no imaging or radiology table and no order table** for labs or imaging. Imaging appears only as documented `treatment` strings, for example "radiologic procedures / bronchoscopy", "CT scan", or "chest x-ray". In the demo each of these appears in at most about 10% of stays.
- Demo stay-level coverage: `lab` 97%, `carePlanGeneral` 97%, `note` 90%, `diagnosis` 86%, `treatment` 76%, `medication` 74%, `infusiondrug` 33%, `microLab` 2.5%.
- Full-data notebook examples of per-hospital variation:
  - diagnosis completion at large hospitals ranges from 54% to 99% (hospital 73: 53.8%; hospital 167: 63.9%) (EC:`notebooks/diagnosis.ipynb` cell 16);
  - some ICUs do not routinely record `activeUponDischarge` problems (same, cells 19–21);
  - `infusionDrug`: more than 100 hospitals have no data (EC:`notebooks/infusiondrug.ipynb` cell 10).
- Pollard et al.: "reliability and completion of data elements varies on a hospital and/or ICU level" (`SD: Technical Validation`).
- O'Halloran 2020: rates of ventilation, intubation, and dialysis vary with the query method (ventilation 20–33%).

### Q4. Frozen time points without future leakage (G1, G7)

Offsets exist in every table, so a cut at *t* is mechanically possible. Semantic pitfalls:

1. **Entry ≠ event.** Diagnosis, treatment, and physical-exam offsets are entry times. In the demo, treatment and diagnosis entries lag the actual order or infusion (Q1). A CABG `treatment` entry appears about 1 h after ICU admission for OR admits (demo median), so the entry documents a past event (issue #172).
2. **Co-saving.** 99.8% of demo `treatment` rows share (stay, offset) with a `diagnosis` row, and 96.5% of diagnosis rows in stays with both are co-timed with a treatment row. The problem list and the active treatments are saved as one Dx/Rx event. **At entry resolution, `D_t` and the documented action are simultaneous.** The treatment table cannot supply an "action after `D_t`" target without a lag rule.
3. **Future-only fields must be excluded:** `activeUponDischarge` (set on the final save); patient discharge fields; `apachePatientResult`, `apacheApsVar`, and `apachePredVar`, which are computed from the first 24 h (`SD: APACHE data`) and leak for *t* < 24 h; and `admissionDx` if it is entered after *t* (it can be entered up to 36 h).
4. **Offset-0 artifact.** Null dates were converted to offset 0, which looks like ICU admission. This affects 4.0% of `medication` rows (mostly stop times), 1.3% of `carePlanGeneral`, and 47% of `carePlanEOL` (issue #49, full-data counts). Offset 0 must be treated as unknown.
5. **Care Plan carry-forward.** Items are copied from the previous unit within 24 h (carePlanGeneral.md:44), so the entry offset may not be the documentation time.
6. **Lab availability.** The draw time precedes result availability. The revised-entry offset is a median 31 min after draw in the demo (p95 141 min). The conservative cut uses `labResultRevisedOffset` ≤ *t*.
7. **Note lag.** `noteEnteredOffset − noteOffset` has a median of 12 min, and 18% of rows exceed 60 min (demo). Use the entered offset.
8. **Pre-ICU data.** 22% of demo lab rows have negative offsets. Pre-ICU diagnoses, treatments, and imaging are not included (diagnosis.md:27).

The leakage-free rule set is definable **from documentation alone**. A residual-leakage estimate needs full rows.

### Q5. Examination / investigation action targets (G3)

- **Labs:** draw events are observed, so "which labs were drawn next" is a possible target. Orders, and orders later cancelled, are not recorded. A draw is the only event, and many draws are standing orders or protocols *(unverified: proportion)*.
- **Imaging / other diagnostics:** only as documented `treatment` strings (sparse, entry-timed, co-saved with the diagnosis). No indications, no results.
- **Microbiology:** absent at about 89% of hospitals.
- Result: G3 can give only a **coarse, observed lab-draw target**. There is no usable imaging or diagnostic-procedure target. It is also debatable whether next-lab-draw in an ICU reflects diagnostic planning rather than monitoring.

### Q6. Treatment action targets and semantics (G4, G11)

Candidate targets, in decreasing timing fidelity:

1. `infusionDrug` rate starts and changes (flowsheet charting; administration-level; one-third of stays in the demo);
2. `medication` new orders (pharmacist-verified orders with order and start offsets, dose, route, and frequency; cancellations flagged; not administration);
3. `respiratoryCharting` / `carePlanGeneral` ventilation and prophylaxis status;
4. `treatment` pick-list (entry-timed, co-saved with the problem list, absence ≠ not done).

All of these are **observed clinician behavior** at a tele-ICU-covered site, not optimal or guideline-adjudicated treatment. Items 1–2 carry dose and timing, which the temporal hypothesis's "control decision" arm needs.

### Q7. Planning metric that does not reward reconstructing the final diagnosis (G5, G9)

- The `treatment` hierarchy is **organized by diagnosis category**, for example `neurologic|ICH/ cerebral infarct|thrombolytics|tenecteplase` (treatment.md:26). It is also co-saved with the problem list. A metric that matches predicted items against `treatmentString` rewards naming the right problem and then its guideline treatments. This is the same failure as MIMIC-CDM, Q8.
- **Surviving design:** next-window medication orders or infusion changes, scored with precision and recall on drug class plus dose and timing. The reference is patient-specific (it depends on weight, renal function, current infusions, and prior orders). Whether it escapes G9 must be **shown empirically**: compare a planner given the final problem list (last diagnosis batch) with planners given `S_t`. That needs full rows. Status: plausible, not demonstrated.
- Pitfall: at many *t*, the "next" action is continuation of current therapy. A metric must separate new actions and changes from continuations, or copying current orders will saturate it.

### Q8. Coverage and effective sample (G6, G8)

- **Full data.** 200,859 stays. Problem-list coverage is excellent at 76% of hospitals. `medication` has no data at 16% of hospitals, and `infusionDrug` at 27% (`SD: Table 8`).
- **Demo.** 49% of stays with diagnoses have only one diagnosis batch. For a design that needs a documented problem-list change between *t* and *t + Δ*, only about half of stays have any re-save. Of those, about half add a new problem.
- Hospital heterogeneity is large and documented. The binding constraint is likely **site-level documentation practice**, not raw N. A per-site inclusion rule (for example, sites with high medication and diagnosis completion) is required.
- G8 cannot be computed without the design and the full rows. Even strong filters are unlikely to leave fewer than several thousand stays *(estimate, unverified)*.

### Q9. Does the ICU setting fit the question?

**Only for the late / management part of the question.**

- In the demo, 52% of stays are admitted from the ED. The median hospital-admission-to-ICU time is 4.5 h (quartiles 1.5–19.6 h).
- The first problem-list save comes a median 0.9 h after ICU arrival, and 29% of septic patients with an antibiotic order had it ordered before ICU admission (Q1).
- The early diagnostic work (S0–S3 in [research_question.md](../research_question.md)) happened before the data start and is not recorded, apart from pre-ICU labs.

eICU can therefore at best test the provisional hypothesis that, **once a problem list exists, patient-specific treatment/control decisions benefit from richer state**. It cannot test early examination planning.

---

## Gate status

| Gate | Status | Basis |
|---|---|---|
| G1 Temporal input validity | **partial (docs + demo)** | Offsets everywhere, but diagnosis, treatment, and PE offsets are entry times. Rules needed for APACHE, `activeUponDischarge`, offset-0, Care Plan carry-forward, and lab availability (Q4). Full-row audit needed. |
| G2 Diagnosis-state validity | **pass (classified)** | `diagnosis` = snapshot-saved **documented active problem list** (entry-timed, no differential, no removal time). `admissionDx` = APACHE severity-scoring admission category (rule-constrained, locked after 36 h). Neither is a working diagnosis or differential. Clinician `D_t` must be worded as "problem list as documented by *t*". |
| G3 Examination-action availability | **fail for imaging/diagnostics; weak partial for labs** | No order tables, no imaging table, microbiology mostly absent; only lab draw events (Q5). |
| G4 Treatment-action availability | **partial** | Orders (`medication`), administration (`infusionDrug`), status (`carePlanGeneral`, respiratory), documented list (`treatment`); site-dependent (Q3, Q6). |
| G5 Quality target independent of diagnosis | **fail with `treatment` strings; open with orders/infusions** | `treatment` is diagnosis-keyed and co-saved (Q7). |
| G6 Coverage | **partial (docs + demo)** | Hospital-level coverage published; demo stay-level rates in Q3; design-specific proportions need rows. |
| G7 Leakage | **open, moderate–high risk** | Rule set definable (Q4); co-saving of D and treatment and entry-after-action lags are the main hazards; residual rate needs rows. |
| G8 Effective sample size | open | Likely not binding in absolute N; site heterogeneity is (Q8). |
| G9 Evaluation independence | **fail for `treatment`-string metric; open for order-based metric** | Needs an empirical final-problem-list oracle test (Q7). |
| G10 External validation | not evaluated | eICU could serve as the multicenter replication for a raw MIMIC-IV ICU order-based design. Not the reverse for exam planning. |
| G11 Treatment-ground-truth semantics | **classified: observed behavior** | Orders ≠ administration; `treatment` absence ≠ not done; not guideline-adjudicated or optimal. |
| G12 Diagnostic timing semantics | **fail for formation time; partial for documentation ordering** | Offsets are documented as entry times. Entries often follow the related action (demo: sepsis after antibiotics 76%, norepinephrine treatment after infusion 74%). There are no removal times. Ordering of saved snapshots is available. |

## Interim assessment (not a final Phase 0 decision)

eICU **cannot supply a clinician early diagnosis** or an **examination-planning target**. It cannot serve the early-stage (S0–S3) arm of the study. Its problem list is an ICU-arrival snapshot of diagnostic work already done, and its entry times often trail the actions it would be used to predict.

What survives is a **narrow, management-phase role**:

- At frozen ICU time points *t* (≥ 24 h, or with APACHE fields excluded), compare Bottleneck (`S_t` → problem-list-style `D_t`) against Direct (`S_t`) for **next-window new medication orders and infusion changes**. Score with precision and recall on class, dose, and timing, against observed behavior.
- Restrict to sites with high medication, infusion, and diagnosis completion.
- The documented problem list at *t* may serve as a *documented-label* condition, reported as "problem list as documented by *t*". It must not be described as the clinician's working diagnosis.

This would test only the provisional "control decisions still benefit from richer state" arm. It is not a Phase 1 candidate, and its G5 and G9 status depends on an oracle test that needs full rows. Next steps, if pursued:

1. Sign the eICU DUA.
2. Run a full-data audit of co-saving, entry-lag, and per-site completion, extending the demo aggregates.
3. Prototype the order-based metric and the final-problem-list oracle check.

## Unverified / open items

- Who enters `diagnosis`/`treatment` rows (bedside team vs tele-ICU staff) and whether this varies by site.
- Whether the full-data `note` table contains the `…/Dx` Assessment-and-Plan rows shown in the documentation example (absent from the demo).
- Whether demo patterns (co-saving 99.8%, entry-after-action ~75%) hold across the full database and per site. The demo n for the timing checks is 86 stays each.
- Which PhysioNet LLM post (2023 vs 2025) governs, and whether eICU is explicitly in scope.
- The demo page's description of the demo's hospital sample (observed: 186 `hospitalid` values).
- O'Halloran et al. 2020: only the abstract was read.
