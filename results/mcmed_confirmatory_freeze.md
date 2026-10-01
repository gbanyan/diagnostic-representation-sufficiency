# MC-MED confirmatory result: permanent freeze record

**Status: FROZEN.**
- The confirmatory pipeline and its results are read-only (see [../CONFIRMATORY_FROZEN.md](../CONFIRMATORY_FROZEN.md)).
- Any later analysis is exploratory and lives under `exploratory/`.

**Reproducibility check (2026-10-01).** The primary metrics were recomputed from the immutable private prediction file (SHA-256 `6b02c6c7…0770`). They match the frozen values: L_D 0.125955, L_DX 0.103816, ΔL 0.022139 nats, relative gain 0.175768, AUROC 0.7873 / 0.8699, all within 1e-4 of the recorded values. Nothing was refit.

| # | Item | Frozen value |
|---|---|---|
| 1 | Preregistration tag | `mcmed-confirmatory-prereg-v1` |
| 2 | Preregistration commit | `c04352971fab6d3082cee977edcef8689f5edb33` (2026-10-01 03:33:40 +0800) |
| 3 | Primary-result tag | `mcmed-confirmatory-primary-result` |
| 4 | Primary-result commit | `6c9834ea48919cdcc9990757699897e5aa08179b` (2026-10-01 04:57:08 +0800) |
| 5 | Cohort | 32,404 visits: adult, admitted, decision time > arrival + 3 h, no ICU/critical-care consult by T, CCSR-mappable visit diagnosis. Development 25,834; locked test 6,570 |
| 6 | Patients | 22,558 (development 18,023; test 4,535; no overlap) |
| 7 | Events | ICU disposition 1,109 (3.4%); development 897 (3.5%); test 212 (3.2%) |
| 8 | Diagnosis taxonomy | CCSR body system (AHRQ DXCCSR v2024.1, default OP category, first 3 letters); 20 classes after the < 50 rule; unmapped excluded |
| 9 | Diagnosis encoder | Multinomial L2 logistic regression, C = 0.003. Development OOF log loss 1.731 vs prior 2.463 nats (−29.7%); all 5 folds better; top-1 accuracy 0.448 (majority 0.248); macro-F1 0.301 |
| 10 | D_hat dimensionality | 20-class soft posterior, entered as K − 1 = **19** probability columns (reference SYM) |
| 11 | Model D | logit P(ICU) = intercept + 19 D_hat columns + season (3 indicators); unpenalized except ε = 1e-4 ridge |
| 12 | Model D+X | Model D + X_3h (445 raw columns → 605 model columns after missing indicators); L2 on X only; no interactions; no class weighting; exact Newton solver (amendment 1) |
| 13 | Selected C | **0.003** |
| 14 | Log loss (locked test) | L_D = **0.1260** nats (0.1817 bits); L_DX = **0.1038** nats (0.1498 bits) |
| 15 | ΔL | **0.0221 nats** (95% CI 0.0167–0.0276) |
| 16 | Δbits | **0.0319 bits** (95% CI 0.0241–0.0399) |
| 17 | Relative gain | **17.6%** (95% CI 13.7–21.2%) |
| 18 | Confidence intervals | Patient-cluster bootstrap on the locked test: 2,000 replicates, seed 20261004, percentile |
| 19 | Secondary | AUROC 0.787 → 0.870 (Δ +0.083, CI +0.059 to +0.106); AUPRC 0.118 → 0.336 (Δ +0.218, CI +0.156 to +0.277); Brier 0.0300 → 0.0256; calibration-in-the-large −0.113 / −0.056; calibration slope 1.00 / 1.12 |
| 20 | Prespecified sensitivities (after the freeze; no confirmatory role) | S1 hard top-1: 21.9% (17.8–25.8%). S2 ICD-10 chapter: 15.8% (12.1–19.3%). S3 + race/ethnicity: 17.3% (13.5–21.1%). S4 chronological split: 15.7% (10.5–20.6%). All ΔL CIs > 0 |
| 21 | Success-rule decision | CI lower bound of ΔL 0.0167 > 0 **and** relative gain 17.6% ≥ 10% → **SUPPORTED** |
| 22 | Permitted interpretation | *"At a 3-hour ED landmark, a cross-fitted disease-label representation did not retain all information in the contemporaneous patient state that was predictive of subsequent observed ED-to-ICU disposition."* In the broader program context: *"The results support target-dependent diagnostic sufficiency: diagnostic compression was approximately sufficient for one categorical management target in MIMIC, whereas substantial target-relevant information remained outside the disease-label representation for an escalation-of-care target in an independent cohort."* |
| 23 | Prohibited interpretations | See the list below |

**Prohibited interpretations (row 23):**
- richer representations improve care;
- ICU disposition was optimal;
- disease labels are generally insufficient;
- diagnosis should be abandoned;
- the Diagnosis-as-Interface framework is proven;
- the model identifies causal or treatment effects;
- D_hat is the clinician's working diagnosis;
- MC-MED literally replicates MIMIC T3.

## Protocol amendment

The result was obtained under **[Amendment 1](../docs/amendments/amendment_1_final.md)**, a pre-test change of numerical optimizer. It deviated from the preregistered instruction to stop and seek author review at a convergence failure. Any citation of this result should cite the amendment with it.

## Linked records

- [mcmed_primary_frozen.md](mcmed_primary_frozen.md)
- [mcmed_final_report.md](mcmed_final_report.md)
- [mcmed_pretest_readiness.md](mcmed_pretest_readiness.md)
- [mcmed_diagnosis_encoder_report.md](mcmed_diagnosis_encoder_report.md)
- [../docs/confirmatory_audit_trail.md](../docs/confirmatory_audit_trail.md)
