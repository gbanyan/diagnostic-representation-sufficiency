# Descriptive sex distribution (SAGER), plan

**Date:** 2026-10-01. Committed before the script was run.

**Why.** The JBI Guide for Authors asks authors to address sex and gender dimensions (SAGER). No committed aggregate reports the sex distribution of the analysis cohorts. The author approved this count on 2026-10-01.

**What.** Descriptive counts only, with no model fitting and no change to any confirmatory or exploratory result.
- MIMIC-IV primary T1 cohort: the same rows as the confirmatory analysis (`sim.prepare(table, "T1", 6, False, "green_only")`; n = 4,990). Report the count and percentage with `female == 1`, overall and among T1 events.
- MC-MED analytic cohort (`cohort.csv`, n = 32,404), the development set, and the locked test set (split manifest). Sex is the `Gender` field of `visits.csv`, reported per recorded level overall and among ICU-disposition visits.

**Disclosure control.** Any cell below 10, including zero, is reported as "<10"; a small level is merged with the largest non-female level (complementary suppression) so that it cannot be recovered by subtraction. Only aggregates are written to `results/sex_distribution.json`.

**Use.** One clause in the manuscript's Table 2 or Section 4.1 and a supplement line. No inference.
