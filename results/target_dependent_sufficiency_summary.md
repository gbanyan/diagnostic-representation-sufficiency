# Target-dependent diagnostic sufficiency: summary across targets

**Sources:**
- MIMIC: [../docs/main_experiment_results.md](../docs/main_experiment_results.md), preregistration `600f368`.
- MC-MED: [mcmed_confirmatory_freeze.md](mcmed_confirmatory_freeze.md), tags `mcmed-confirmatory-prereg-v1` and `mcmed-confirmatory-primary-result`, with [amendment 1](../docs/amendments/amendment_1_final.md).

**Relative gain** = (CE_D − CE_D+X) / CE_D on held-out data. The MIMIC and MC-MED models differ in cohort, diagnosis representation, landmark, and endpoint.

| Dataset | Target | Status | Relative gain (95% CI) | Δ (bits) | Interpretation |
|---|---|---|---|---|---|
| MIMIC-IV (4 acute abdominal diagnoses; 6 h) | **T1** operative vs non-operative management | **Confirmatory, negative** (primary hypothesis not supported) | **3.9%** (2.8–5.0%) | 0.028 (0.020–0.036) | Incremental information is detectable but small. Diagnosis + common context is **approximately sufficient under the prespecified 10% criterion** |
| MIMIC-IV (same cohort) | **T3** later ICU transfer during the stay | **Exploratory** (confirmatory status lost after T1 failed) | 16.3% (12.9–19.5%) | 0.045 (0.035–0.056) | Hypothesis-generating escalation-of-care signal |
| MIMIC-IV | **M5** anaerobic-coverage prescription | **Negative control** | 0.4% (−0.7 to 1.1%) | 0.0014 (−0.003 to 0.004) | Approximately null, as expected |
| MIMIC-IV | **T5** organ operated (multinomial) | **Negative control** | −0.5% (−3.9 to 1.6%) | −0.0006 (−0.005 to 0.002) | Approximately null, as expected. One of three repeats had a non-convergence flag |
| MIMIC-IV | **M3** enoxaparin vs SC heparin | Negative-control candidate: **small positive** | 5.1% (1.1–9.4%) | 0.006 (0.001–0.011) | 58 events. Imprecise and **inconclusive**; not interpreted clinically |
| **MC-MED** (Stanford ED; 3 h landmark; cross-fitted 20-class CCSR D_hat) | **Observed ED-to-ICU disposition** | **Independent confirmatory, positive** (SUPPORTED; pre-test amendment 1) | **17.6% (13.7–21.2%)** | **0.032 (0.024–0.040)** | The disease-label representation **did not retain all target-relevant predictive information** in the contemporaneous state |

**MC-MED sensitivities** (no confirmatory role):
- S1 hard top-1: 21.9%;
- S2 ICD-10 chapter: 15.8%;
- S3 + race/ethnicity: 17.3%;
- S4 chronological: 15.7% (10.5–20.6%).

## Reading

- **Sufficiency depended on the target.** For a categorical, largely protocolized management decision (T1), diagnosis plus context was approximately sufficient under the prespecified criterion. For escalation-of-care targets, substantial predictive information remained outside the disease-label representation: exploratorily in MIMIC (T3), and confirmed in an independent cohort (MC-MED).
- **MIMIC T3 and MC-MED are conceptually matched escalation-of-care targets. They are not identical outcomes.**
  - MIMIC T3 is a later inpatient ICU transfer in patients with one of four observed diagnoses, at 6 h.
  - MC-MED is a direct ED-to-ICU disposition in a general admitted ED population. Its diagnosis representation is estimated from the 3 h state, and the cohort is conditional on the disposition being undecided at 3 h.
  - MC-MED is therefore an **independent confirmation of the escalation-of-care target class**, not a replication of T3.
- **Negative controls behaved as expected** (M5, T5 ≈ 0). M3 is small and imprecise.
- **What the data do not show:**
  - that richer representations improve care;
  - that observed dispositions were optimal;
  - that disease labels are generally insufficient;
  - any causal effect.
- **The within-label heterogeneity / anatomic-locality idea is post-hoc and untested** ([../notes/future_hypotheses/anatomic_action_coupling.md](../notes/future_hypotheses/anatomic_action_coupling.md)).
