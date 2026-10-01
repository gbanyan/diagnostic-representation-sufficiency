# MC-MED mechanism decomposition: exploratory plan (fixed before any run)

**EXPLORATORY.** This plan was written and committed on 2026-10-01, **after** the MC-MED primary result (SUPPORTED, relative gain 17.6%) and the sensitivities S1–S4 were seen. Nothing here is confirmatory, and nothing here can change the frozen confirmatory result.

- **Success thresholds:** none. Results are descriptive.
- **Frozen confirmatory pipeline:** read-only. This analysis imports it and changes none of it.

**Question.** Which information classes in X_3h account for the confirmed incremental information about observed ED-to-ICU disposition beyond the soft disease-label representation? In particular, how much is patient physiology, and how much is measurement-process intensity?

**The goal is not to find the combination with the largest gain.**

## Fixed elements (identical to the confirmatory analysis)

**Data and representation:**
- cohort, frozen split, and outcome;
- soft D_hat (19 columns, reference SYM) plus season, unpenalized (ε = 1e-4);
- exact Newton solver.

**Tuning:**
- C grid {1e-4 … 100};
- 4-fold patient-grouped development CV (seed 20261003), lowest mean log loss, ties go to the smaller C;
- refit on all development data.

**Evaluation:** once per family model on the frozen test set.
- The test set was already opened for the primary analysis. It is **reused here for description only**.
- Patient-cluster bootstrap: 1,000 replicates, seed 20261005.

**Reported per model:** L_D, L_(D+F), ΔL, Δbits, relative gain (with 95% CI), AUROC D → D+F, and the selected C.

## Feature families

All columns come from the frozen X_3h (445 raw columns; `results/mcmed/stageA_features_build.json`).

**Presentation change.** In the confirmatory model, missing indicators were added automatically by the imputer. Here they are made an explicit block, so that the "measured or not" information can be separated from the measured values.

**Value columns.** Median-imputed (from the training data), standardized, and clipped to ±5 SD, **without** indicators.

| Family | Content | Raw columns |
|---|---|---|
| **A. Physiology / vital state** | Triage temperature, HR, RR, SpO₂, SBP, DBP. For the 11 numerics measures: first, last, min, max, median, slope (values only) | 6 + 66 |
| A1 (component of A) | Triage vitals only | 6 |
| A2 (component of A) | Numerics value summaries only | 66 |
| **B. Laboratory state** | First lab values resulted by T (84 components) and the 3 qualitative abnormal flags | 87 |
| **C. Medical history** | Prior PMH CCS indicators (175) and the prior-code count | 176 |
| **D. Presenting context** | Age, sex, arrival mode, ESI, chief-complaint tokens (91) | 99 |
| **E. Measurement-process intensity** | Numerics measurement counts (11), plus a "not measured / not resulted by T" indicator for every raw column with missing values: 87 labs, 66 numerics summaries, 6 triage vitals, and ESI | 11 + 160 indicators |
| **F. Clinical state without measurement intensity** | A ∪ B ∪ C ∪ D (values only; no counts, no indicators) | 434 |
| **ALL** | A ∪ B ∪ C ∪ D ∪ E: the same information as confirmatory X, re-presented with explicit indicators | 445 + 160 |

## Models (13; each compared with the same Model D)

1. **Single families:** D + A, D + A1, D + A2, D + B, D + C, D + D, D + E, D + F.
2. **Leave-one-family-out:** D + ALL − A, D + ALL − B, D + ALL − C, D + ALL − D. (D + ALL − E is D + F.)
3. **Reconstruction check:** D + ALL, which should approximately reproduce the confirmatory 17.6%.

**Physiology-only question (Part F):** D + A, with A1 and A2 as components.
**Measurement-process question:** D + E versus D + F.

## Interpretation rules (fixed now)

- **No thresholds and no "success".** Families are compared descriptively, with their CIs.
- **Overlap.** Single-family and leave-one-out gains overlap because the families are correlated. The two views are reported together, and gains are **not** summed into shares.
- **Measurement-process signals are not relabelled leakage.** E contains only information legitimately available by T. It is interpreted as clinician concern or monitoring intensity reflected in the record, not as patient physiology.
- **No further subdivision on the test set.** If the families raise questions, subgroups or finer splits are future work, not additions to this analysis.
- **No new confirmatory claims.** Nothing here tests the anatomic-locality hypothesis ([../../notes/future_hypotheses/anatomic_action_coupling.md](../../notes/future_hypotheses/anatomic_action_coupling.md)).
