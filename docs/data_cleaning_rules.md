# Data cleaning rules (preflight feature construction)

**Status:** introduced 2026-09-29 as a logged deviation ([decision_log.md](decision_log.md)), after the first X0 run exposed triage data-entry errors. The rules apply uniformly to every target, feature set, and model.

- **Provenance:** the pre-cleaning run is kept unchanged in `results/phase0/sufficiency/mimic_cdm/x0_superseded_precleaning/`.
- **Code:** `src/preflight/mimic_cdm_table.py` (bounds) and `src/preflight/simple_incremental_models.py` (transforms, clipping).
- **Counts:** per-rule counts are written to `table_build.json` (`triage_out_of_bounds`) and to each Stage B output (`clipping`).

## Three kinds of treatment

| Kind | Meaning | Treatment |
|---|---|---|
| **Impossible / data-entry value** | Outside a physiologically possible range: a typo, a unit error, a misplaced decimal | Set to **missing**. The model's missing indicator then marks it. Counted and reported. |
| **Extreme but possible value** | Inside the bounds but far in the tail (e.g. HR 180, lipase 20,000 U/L) | **Retained.** Compressed by `log1p` where the feature is right-skewed, then clipped at ±5 SD. Values are never removed. |
| **Missing** | Not measured by the landmark | Median-imputed within training folds, plus a missing indicator. Missingness itself is information available at T. |

## 1. Physiologic bounds (triage, applied when the table is built)

Values outside these closed intervals are treated as impossible or data-entry values and set to missing.

| Field | Unit | Bounds | Rationale |
|---|---|---|---|
| `temperature` | °F | 90–110 | Survivable range. MIMIC-ED records °F. Values of 30–45 are probably °C and are **not** converted; they are set to missing, to avoid guessing units. |
| `heartrate` | /min | 20–250 | Excludes 0 and typos (e.g. 1,000+) |
| `resprate` | /min | 4–60 | |
| `o2sat` | % | 50–100 | Values > 100 are impossible; < 50 at triage is implausible for a walk-in record |
| `sbp` | mmHg | 40–300 | Observed maximum 19,734 (a data-entry error) |
| `dbp` | mmHg | 20–200 | Observed maximum 1,041 |
| `pain` | 0–10 scale | 0–10 | Non-numeric entries (e.g. "unable") become missing |
| `acuity` | ESI level | 1–5 | |

**Observed (6 h cohort build, 2,400 admissions; 1,632 with a triage record):**
- pain: 46 values recorded but out of range or non-numeric (e.g. "unable"), set to missing;
- temperature, SBP, DBP: fewer than 10 values each (suppressed);
- heart rate, respiratory rate, SpO₂, acuity: none.

The first run's distortion came from this handful of SBP and DBP values (maximum 19,734 and 1,041). Source: `table_build.json`, `triage_out_of_bounds`.

Labs are **not** bounded. Values come from `labevents.valuenum`, reported by the analyzer. Their tails are handled as extreme-but-possible values (below). A lab range check is recorded in section 5.

## 2. log1p transforms (applied within each training fold, before scaling)

Applied to right-skewed, non-negative features:

- `prior_admissions`
- labs: `wbc`, `crp`, `lactate`, `lipase`, `tbili`, `alt`, `ast`, `alp`, `creat`, `bun`, `glucose`, `inr`

Negative values (none are expected for these) would be floored at 0 before `log1p`. All other features are used on their original scale.

## 3. Clipping (applied within each training fold, after standardization)

After median imputation and standardization (both fitted on training data only), every feature is clipped to **[−5, +5] SD**. Clipping never removes a row or a value. It caps the influence of rare extreme-but-possible values on a linear model. The share of clipped training cells per feature set is reported with each Stage B output.

## 4. Not done

- No outlier-based row deletion.
- No winsorization based on the outcome.
- No feature selection.
- No imputation that uses Y or anything recorded after the landmark.

## 5. Lab range check (2026-09-29, 6 h landmark table, aggregates only)

The first value of each lab before the landmark was checked for physiologically impossible values. **None were found**, so no lab bound was added.

The extremes are possible and are kept as *extreme-but-possible* values (log1p where listed, then ±5 SD clipping):

| Lab | Maximum observed | Note |
|---|---|---|
| Lipase | 28,940 U/L | Plausible in pancreatitis |
| Glucose | 1,061 mg/dL | |
| Potassium | 9.8 mmol/L | Possibly a hemolyzed sample; not removed, because hemolysis cannot be identified reliably |
| ALT | 1,908 U/L | |
| AST | 2,431 U/L | |
| BUN | 251 mg/dL | |
| Total bilirubin | 39.6 mg/dL | |
| INR | 12.0 | |

- **Minima:** all plausible (e.g. sodium 120, hemoglobin 6.2, platelets 12).
- **Coverage:** CRP is measured before the landmark in only 22 of 2,365 cohort admissions, so it contributes almost nothing. Albumin (38%), lactate (47%), INR (59%), and calcium (76%) are missing in a substantial share of cases (denominator: all 2,400 admissions). Missing indicators carry that information.
