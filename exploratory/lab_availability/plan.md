# MIMIC-IV laboratory result availability: audit and sensitivity analysis, plan

**Date:** 2026-10-02. Committed before any run. Author-approved on 2026-10-02.

**Why.** The prespecified MIMIC X1 used the first value of each of 20 laboratory tests with `labevents.charttime ∈ [t0 − 1 h, T]` (protocol §F, line 95). `charttime` approximates specimen collection; `storetime` is when the result became available in the laboratory system. A test drawn before T can be resulted after T, so the claim that X contained only information available at the landmark was not fully implemented. MC-MED used `Result_time ≤ T` and is not affected. An external pre-submission review raised this on 2026-10-02.

**Status.** Post-confirmatory sensitivity analysis. The confirmatory results and their verdicts are unchanged and remain the reported primary results.

## 1. Audit (descriptive)

Reconstruct exactly the lab cells used at L6 (same itemid mapping, window, first-by-`charttime` rule), and check that they match the stored table. For the T1 primary cohort (n = 4,990) and the T3 cohort, report:
- number of non-missing lab cells;
- cells with `storetime` > T, and cells with missing `storetime`;
- results per feature;
- admissions with at least one late cell, overall and among events;
- the median and IQR of the lag (storetime − T) among late cells, in hours.

## 2. Sensitivity analysis (run regardless of the audit result)

**Variant table.** For each admission and feature, take the first value by `charttime` in [t0 − 1 h, T] among rows with `storetime` ≤ T. A row with missing `storetime` counts as unavailable. If no such row exists, the cell is missing, and the existing missingness indicator applies. Only the `lab_*_L6` columns change.

**Rerun.** Use the unchanged confirmatory pipeline (`src.confirmatory.target_sufficiency`) for T1 (green_only, full context, X1) and for T3, with the same seeds, folds, penalties and bootstrap.

**Report.** ΔL in bits and the fractional reduction with 95% CIs, next to the confirmatory values. No new margin decision: the analysis is labelled sensitivity, and the 10% margin is shown for reference only.

## Disclosure control

Only aggregates leave gbminipc; cells below 10 are shown as "<10". The variant table stays in the private directory.
