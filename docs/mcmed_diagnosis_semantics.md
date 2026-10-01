# MC-MED diagnosis semantics audit

**Date:** 2026-09-30.

**Sources:**
- the PhysioNet data dictionary (`data-dictionary.md`, v1.0.1);
- the README;
- Kansal A, Chen E, Jin BT, Rajpurkar P, Kim DA. *MC-MED, multimodal clinical monitoring in the emergency department.* Sci Data 12, 1094 (2025), Methods → "Visits", "PMH", "Orders", "Labs", and the de-identification section;
- the dataset authors' public repository `dkimlab/MCMED` @ `bae387b` (documentation and plotting utilities only; no extraction code).

Timing is **not inferred** where the documentation is silent.

## Documented structure of the visits table (paper, Methods → Visits)

> "Data available at the time of patient arrival include: patient demographics …, means of arrival …, triage vital signs …, triage acuity … and chief complaint ("CC"). **Data summarizing the visit itself include ED disposition ("ED_dispo"), ED length of stay …, class of primary visit payor …, and primary diagnosis, by ICD9 … and ICD10 … codes, accompanied by free-text descriptions ("Dx_name").** For patients admitted to the hospital, the table includes admitting service ("Admit_service") …"

The EHR source is STARR (Stanford's clinical data warehouse, fed from Epic). Timestamps are shifted per patient and preserve within-patient order.

## Field-by-field classification

| Field | Provenance (documented) | Temporal meaning (documented) | Semantic class | Timestamp | Usable as a 3 h input? |
|---|---|---|---|---|---|
| `Dx_ICD9`, `Dx_ICD10`, `Dx_name` | Visits table; "primary visit diagnosis" | Listed among fields "**summarizing the visit itself**", alongside disposition and length of stay | **Visit-level (final/visit) diagnosis.** Whether it was entered as a clinical impression at disposition or abstracted for billing is **not documented** | **None** | **No.** Its assignment time is unknown and is documented as a visit summary, so using it as `D_3h` risks hindsight. **It may serve only as a supervision target or an explanatory stratifier** |
| PMH (`pmh.csv`: `Code`, `Desc10`, `CCS`, `Noted_date`) | Patient-level problem history (by MRN) | "`Noted_date` gives the shifted date when the diagnosis was recorded, and can be used to identify known diagnoses at the time of a given visit" | **Prior medical history** (chronic/background conditions), not the current acute diagnosis | **Date only** (no time) | **As a comorbidity feature only:** GREEN if `Noted_date` is before the visit date; YELLOW if on the same date (it may have been recorded during the visit); RED if after. **Never as `D_3h`**: it describes history, not the working diagnosis |
| `CC` (chief complaint) | Visits table; triage | "Data available at the time of patient arrival" | **Presenting complaint** (symptom level), not a diagnosis | Implicit (triage ≈ arrival) | GREEN **as a patient-state input** (part of X). Not a disease label |
| `Admit_service` | Visits table; "for patients admitted" | Assigned with the admission decision | **Disposition-level** (post-decision) | None (it accompanies `Admit_time`, which is after `Dispo_time` in 35,052 of 35,127 eligible visits; 75 missing) | **No.** RED: it is determined with, or after, the disposition decision |
| `ED_dispo` | Visits table | Disposition from the ED | **Outcome** (endpoint source) | `Dispo_time` = "time of disposition decision" | Outcome only |
| `DC_dispo`, `Hosp_LOS`, `ED_LOS`, `Departure_time`, `Hours_to_next_visit`, `Dispo_class_next_visit` | Visits table | After the visit | Post-outcome | — | **No** (RED) |
| Radiology `Impression` (`rads.csv`) | Radiologist report | `Result_time` = when the result was reported | A result that may **name** diagnoses | `Result_time` | Only as patient-state X if `Result_time` ≤ T, with a pre-specified representation. **Not** a diagnosis field and not `D_3h` |
| Orders (`orders.csv`), e.g. consults | Orders "placed by the ED physician during the visit" | `Order_time`, `First_admin_time`, `Result_time` | Clinician actions; they may reflect working suspicions **implicitly** | Yes | **Not a diagnosis.** See [mcmed_3h_feature_semantics.md](mcmed_3h_feature_semantics.md) for their status as X |

## Can any observed field legitimately represent `D_3h`?

**NO.**
- The only acute diagnosis fields (`Dx_ICD9`/`Dx_ICD10`/`Dx_name`) are documented as visit-summary fields without a timestamp.
- PMH is prior history.
- The chief complaint is a symptom-level complaint.
- `Admit_service` is a post-decision field.
- No working diagnosis, clinical impression, or differential with a time stamp exists in the released tables. MC-MED releases no free-text clinical notes.

**Therefore an experimentally generated representation `D_hat_3h` is required** ([mcmed_dhat_design.md](mcmed_dhat_design.md)). It must always be described as **an experimentally generated disease-label representation**, never as the clinician's working diagnosis.

## Consequences

1. `Dx_ICD10` may be used **only** as the *supervision target* of the diagnosis encoder, fit on training folds, and as a descriptive stratifier. It is never an input at the 3 h decision point.
2. The superseded design ([t3_followup_design.md](t3_followup_design.md)) used `Dx_ICD10` as D at 3 h. It is retained for the record and must not be executed.
