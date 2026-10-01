# Dataset semantic gates

Every candidate dataset must pass these gates **before any model development**. Gates are recorded per dataset, with evidence locators (documentation section, source file and line, or row-level query and count). A gate cannot be relaxed after it fails; changing a criterion requires a written rationale recorded before re-evaluation.

**Critical gates** (failure blocks modeling on that dataset for the affected arm/action type): G1, G2, G5, G7, G9, G11 for treatment endpoints, and G3 for examination endpoints.

## Checklist

| Gate | Name | Question | Pass requires | Critical |
|---|---|---|---|---|
| G1 | Temporal input validity | Can `X_t` be constructed using only information genuinely available at time *t*? | Documented field provenance and timing; audited sample shows no post-*t* content | Yes |
| G2 | Diagnosis-state validity | Is `D_t` a contemporaneous diagnosis, a differential, a final diagnosis, a billing code, or a model-generated experimental bottleneck? | Explicit classification of every diagnosis variable used; wording in all outputs matches it | Yes |
| G3 | Examination-action availability | Is there a usable next-examination or investigation target? | Defined target per case at each stage used | For exam endpoint |
| G4 | Treatment-action availability | Is there a treatment plan, actual treatment, guideline recommendation, expert recommendation, or only discharge documentation? | Classified source per case | For treatment endpoint |
| G5 | Quality target | Can "better planning" be evaluated independently from diagnosis accuracy? | Metric that can score two plans differently when both imply the same correct diagnosis | Yes |
| G6 | Coverage | What proportion of cases contain all required variables? | Reported proportion per stage and action type | No (feeds G8) |
| G7 | Leakage | Does any note, code, report, or procedure reveal future diagnosis or treatment? | Leakage audit with documented rules; residual leakage rate below a pre-specified threshold | Yes |
| G8 | Effective sample size | After temporal and completeness restrictions, how many usable cases remain? | Count ≥ pre-specified minimum from a power estimate | Yes |
| G9 | Evaluation independence | Does the metric unfairly reward reconstructing the final diagnosis? | Demonstrated that a planner given `D_final` does not trivially maximize the metric, or that this is controlled | Yes |
| G10 | External validation | Is there a second dataset capable of testing the same hypothesis? | Identified dataset with plausible gate passage | No (limits claims) |
| G11 | Treatment-ground-truth semantics | Does the reference represent guideline concordance, actual clinician behavior, expert adjudication, or inferred optimal treatment? | Explicit classification; claims worded accordingly | Yes for treatment |
| G12 | Diagnostic timing semantics | Can we identify when a diagnostic impression was formed or revised? | Timestamp or ordering evidence for documented impressions | No if `D_t` is model-generated only; Yes if claiming clinician `D_t` |

## Recording template

Copy per dataset into `docs/gates/<dataset>.md` when Phase 0 begins.

```text
dataset:
dataset_version:
evaluated_on: YYYY-MM-DD
gate:
status: pass | fail | partial | not_evaluated
evidence:                # doc section / source file:line / query + count
criterion_used:
decision_rationale:
consequence:             # which arm/action/stage is blocked or allowed
open_issues:
```

## Current status

| Gate | MIMIC-CDM | ER-REASON | eICU | Raw MIMIC-IV |
|---|---|---|---|---|
| G1–G12 | docs + code pass done; rows blocked on access — see [gates/mimic_cdm.md](gates/mimic_cdm.md) | not evaluated | not evaluated | not evaluated |
