# Diagnostic representation sufficiency

Analysis code, prespecified analysis protocols, decision logs, and aggregate results for the study **"Operationalizing Diagnostic Representation Sufficiency for Clinical Prediction: A Two-Cohort Study"** (Jing-Rung Huang and Wen-Hsiang Lu, National Cheng Kung University; manuscript in preparation for the *Journal of Biomedical Informatics*).

The study asks whether a diagnostic representation retains the target-relevant information in the contemporaneous patient state. For each target it compares held-out log loss of a model given the diagnostic representation and common context (Model D) with a model that also receives the patient state (Model D+X). The reduction is reported in bits per observation and as a fraction of Model D's loss, judged against a prespecified 10% margin. The two confirmatory analyses use MIMIC-IV (receipt of a diagnosis-specific index procedure for acute abdominal conditions) and MC-MED (emergency department to ICU disposition, with a cross-fitted disease-label posterior generated from the 3-hour patient state).

## Contents

| Path | Contents |
|---|---|
| `src/` | Cohort construction, feature building, cross-fitted diagnosis encoder, downstream models (exact Newton solver), metrics and bootstrap |
| `exploratory/` | Post-confirmatory exploratory analyses (diagnostic granularity, feature-family decomposition), with plans committed before running and aggregate results |
| `tests/` | Tests on synthetic data (no real data) |
| `config/` | Frozen configuration for the MC-MED confirmatory analysis |
| `docs/` | Prespecified analysis protocols, amendment record, audit trail, decision log, semantic and timing audits |
| `audit/`, `audits/` | Data-semantics audits and the post-hoc MIMIC solver audit |
| `results/` | Aggregate results only |
| `reproducibility/` | Environment lock and re-running instructions for credentialed users |
| `figures/` | Script that renders the manuscript figures from the aggregate results, and the panel-to-source map |

## Data access

No patient-level data are included. MIMIC-IV, MIMIC-IV-ED, MIMIC-IV-Note, MIMIC-IV-Ext-CDM, and MC-MED are available from [PhysioNet](https://physionet.org) to credentialed users who complete the required training and sign the applicable data use agreement. Patient-level derived files (cohort tables, feature matrices, diagnosis posteriors, predictions, split manifests, fitted models) are treated as sensitive under those agreements and are not distributed; their SHA-256 hashes are recorded in the documentation. Paths in `config/` and in the code point to the authors' private analysis server and must be changed by other users.

The AHRQ HCUP CCSR for ICD-10-CM v2024.1 reference file must be obtained from AHRQ (SHA-256 recorded in `docs/mcmed_confirmatory_preregistration.md`).

## Small-cell suppression in this release

All counts below 10, including zeros, appear as `"<10"`, and observed proportions for such cells are omitted. In a few result files (MC-MED calibration deciles for sensitivity analyses SA1, SA2, SA4; the MC-MED attrition record; some phase-0 inventory counts) this release copy is therefore more suppressed than the authors' frozen working record, so the SHA-256 of those files differs from the hashes in the internal audit trail. No reported estimate is affected.

## Protocol naming

Internal file names and tags use the word "preregistration". These analysis protocols were prespecified and committed to version control before the corresponding confirmatory analyses; they were not registered in an external registry. One pre-test amendment (exact Newton solver) is documented in `docs/amendments/`.

## Running

See `reproducibility/README.md`. Analyses were run on Linux x86-64 with Python 3.14 (lock file in `reproducibility/`). Tests (unittest, synthetic data): `python -m unittest discover -s tests -t .`. Figures: `python figures/make_figures.py`.

## Citation

See `CITATION.cff`. Please cite the article once published.

## License

Code is released under the MIT License (`LICENSE`). Data are not included and remain subject to their source agreements.
