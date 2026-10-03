# Decision log

Author decisions that change scope, criteria, or authorization. Newest last.

## 2026-09-29 — Phase 0 plan approved

- **Decision:** The author approved [phase0_preflight_plan.md](phase0_preflight_plan.md) as proposed.
- **Criteria fixed as written:**
  - residual leakage ≤ 5% of audited cases per stage;
  - audit sample of 50 cases per pathology (200 total), stratified, with the seed recorded;
  - at least 30% of cases with at least one triggered patient-conditional treatment item (Q7);
  - "several hundred paired cases per stage" as the placeholder minimum. This is to be replaced by a power estimate once the effect size and equivalence margin are set (open question Q11).
- **Still not authorized:** modeling, LLM inference on patient data, endpoint computation, clinician annotation, or new reference construction.

## 2026-09-29 — Documentation and code pass completed; row audit blocked

- **Finding:** PhysioNet data use agreements for MIMIC-IV-Ext-CDM, MIMIC-IV (hosp/ED/note), and eICU are not signed. Downloads return 403.
- **Consequence:** The row-dependent questions (Q3, Q5, Q10, and parts of Q2, Q4, Q7) wait for the author to sign those agreements.
- **Interim result:** the existing MIMIC-CDM metrics fail G5 and G9, and the released inputs fail G1 (see [gates/mimic_cdm.md](gates/mimic_cdm.md)). **Pending author decision:** whether to pursue the narrowed, reconstructed MIMIC-CDM path or run the ER-REASON / eICU preflight first.

## 2026-09-29 — Target sufficiency preflight started (author instruction)

- **Scope:** the author asked for a target sufficiency preflight. It may use only lightweight fixed models (`D → Y` vs `D + X → Y`); it may not use main-model training, LLMs, or tuning. The framework, candidate targets, landmarks, and thresholds were committed (`88e34b3`) **before** any outcome statistic was computed.

## 2026-09-29 — Deviation: feature cleaning after the first X0 run

- **What happened:** the first Stage B run with X0 (triage/demographics) gave R² < 0 for T4 and worse log loss despite higher AUROC for T3. Checking the feature ranges (aggregates only) found data-entry errors in triage vitals (SBP max 19,734; DBP max 1,041; temperature min 36, likely °C) and a heavy-tailed `prior_admissions` (max 58). After standardization, these produce extreme linear predictions in held-out folds.
- **Change (applied to every target and feature set):**
  1. Triage values outside physiologic bounds are set to missing: temperature 90–110 °F, HR 20–250, RR 4–60, SpO₂ 50–100, SBP 40–300, DBP 20–200, pain 0–10, acuity 1–5.
  2. `log1p` for right-skewed features: `prior_admissions` and the labs WBC, CRP, lactate, lipase, bilirubin, ALT, AST, ALP, creatinine, BUN, glucose, INR.
  3. Standardized features clipped to ±5.
- **Timing:** made before any X1/X2 (lab or imaging) result existed. Model families, hyperparameters, folds, seeds, and thresholds are unchanged.
- **Record:** the pre-cleaning X0 outputs are kept in `results/phase0/sufficiency/mimic_cdm/x0_superseded_precleaning/` and labelled superseded.

## 2026-09-29 — Author decisions Q13, Q14, Q15, Q17

- **Q13 (model choice):** use nested cross-validation to tune C. **Do not reduce** the legitimate contemporaneous feature set. The same budget and splitting logic apply to `D`-only and `D+X`. Report both AUROC and log loss, and report any disagreement. The design was pre-registered in [model_selection_preflight.md](model_selection_preflight.md) before any nested result.
- **Q14 (procedure timing), high priority:** download MIMIC-IV POE and services data, and classify same-day procedure ordering as GREEN / YELLOW / RED. Primary analyses exclude RED; a sensitivity analysis also excludes YELLOW.
- **Q17 (downloads):** download MIMIC-IV prescriptions now, and `emar` as well, for administration times. **Defer** eICU labs/vitals; no eICU modeling unless MIMIC-CDM feasibility fails or external validation becomes necessary.
- **Q15 (clinician review of non-operative management): DEFERRED — AUTHOR DECISION PENDING.** No clinician review, no LLM substitute, and no clinical interpretation of what X predicts.
- **Still not authorized:** the main diagnostic-bottleneck experiment, neural/foundation models, LLM planners, and clinician simulation.

## 2026-09-29 — Q13 / Q14 / Q17 executed; status for the next gate

- **Q13:** nested CV was pre-registered (`e15301a`) and run. The earlier AUROC-vs-log-loss disagreement disappears for the informative targets. For the low-signal targets (M1, M4), small AUROC gains (~+0.04) remain alongside ~0 log-loss gain. This is reported, not resolved.
- **Q14:** POE/services were downloaded; no pre-op order type exists.
  - At 6 h: 59 of 1,458 T1-positives are RED, 362 YELLOW, 1,037 GREEN.
  - T1 recovers 13.5% of `H(Y|D)` in the primary cohort (RED excluded) and 11.2% in the GREEN-only cohort.
- **Q17:** prescriptions, `poe`, and `emar` were downloaded.
  - Order times are observed for 99.5% of prescriptions. eMAR covers only 46.5% of admissions.
  - Negative controls found: M5 (non-trivial), M3, M1, T5.
  - Positive candidates: T1, M6 (non-diagnosis-specific), M2 (borderline), T3 (underpowered within D).
- **Q15:** remains **DEFERRED**. No target is GREEN.
- **Process note:** one commit (`medication_targets` route update) was pushed with a failing test; the next commit fixed it. Commits are now gated on the test summary showing `OK`.

## 2026-09-29 — Process note: BLAS oversubscription on the shared host

- **What happened:** the Q19 runs (3 parallel processes) each used ~31 BLAS/OpenMP threads, reaching a load average of ~56 on 16 cores. The runs were slow and the shared machine was saturated.
- **Fix:** `src/preflight/__init__.py` now defaults to one thread per process (`PREFLIGHT_THREADS` overrides). The oversubscribed runs were stopped and relaunched. Numerical results are unaffected (same models, folds, and seeds). The T5 Q19 output, completed before the fix, is kept.
- **Also:** the ICD-only expanded-cohort **T1** runs were dropped from the queue (invalid; see [expanded_cohort_preflight.md](expanded_cohort_preflight.md)). The corrected T1 runs after the `discharge` download completes.

## 2026-09-30 — Author decision: primary positive targets

- **Decision:** both **T1** (definitive procedure after T: operative vs non-operative management) and **T3** (ICU admission after T: escalation) are carried forward as primary positive candidates.
- **Carried forward with them:**
  - **Negative control:** M5 (non-trivial); T5 and M3 as trivial checks.
  - **Model specification (Q19):** unpenalized diagnosis main effects.
  - **T1 temporal-transport caveat:** within-period design or period-specific recalibration.
- **Implications for a future pre-registration (not yet drafted or authorized):**
  - Two primary targets need a declared multiplicity rule (e.g. Holm across T1/T3, or a pre-declared hierarchy).
  - T3 mixes decision and trajectory (an ICU transfer reflects both an escalation decision and deterioration). Its semantics must be stated as observed escalation, not optimal care.
- **Still open:** item 3 (guideline-derived Stage C proxy; touches Q15); the realistic-differential `D_hat` variant; Q15 (DEFERRED); Q20 (M6 scope).
- **Not authorized:** the main diagnostic-bottleneck experiment.

## 2026-09-30 — Author decisions: confirmatory design (supersedes the co-primary note above)

- **T1 is the single primary endpoint.** T3 (observed ICU transfer / escalation of care) is a pre-specified **secondary confirmatory** endpoint under hierarchical interpretation. T3 cannot rescue a failed T1.
- **Q19 formulation:** partially penalized models. Diagnosis main effects and common context are unpenalized; only patient-state X is L2-penalized. No D×X interactions.
- **Metrics:** log loss is primary; AUROC is secondary. Calibration, Brier score, and uncertainty are also reported.
- **Era drift:** a calendar-era variable is common context in both models. Folds are patient-grouped and era-balanced. A temporal-holdout sensitivity analysis is preregistered.
- **Timing policy:** GREEN only is primary, RED is excluded, and GREEN + YELLOW is the sensitivity analysis.
- **Negative controls:** M5, T5, M3 only.
- **Q15:** DEFERRED. **Q20 (M6):** out of scope.
- **Deliverable:** [main_experiment_preregistration.md](main_experiment_preregistration.md) was drafted. **It has not been run.** It awaits author approval of the five open decisions listed at its end.

## 2026-09-30 — Preregistration approved

- The author approved [main_experiment_preregistration.md](main_experiment_preregistration.md). The **binding version is commit `600f368`**.
- Approval covers the drafted recommendations for all five open decisions.
- The wording of the diagnosis × era term was corrected to the saturated form (3 × 3 interactions plus main effects; the same model space) in the binding commit, before anything was run.

## 2026-09-30 — Confirmatory analysis run (preregistration `600f368`)

- **Execution:** the partial-penalty validation tests passed, derived tables were rebuilt, and the leakage checks passed. All preregistered analyses ran. Results are in [main_experiment_results.md](main_experiment_results.md).
- **Primary T1: NOT SUPPORTED.**
  - Δ = 0.028 bits (CI 0.020–0.036) > 0.
  - Relative Δ = 3.9% (CI 2.8–5.0%) < 10%.
  - Sensitivity analyses 1–3 and 5 fall at 3.7–4.8%. The temporal holdout is ≈ 0.
- **T3:** exploratory only, because of the hierarchy. Relative Δ = 16.3%.
- **Controls:** M5 and T5 ≈ 0 (T5 has one non-convergence flag). M3 is small but positive (5.1%, 58 events).
- **No re-specification was made.** The post-hoc observations (D × X heterogeneity; the change in M3) are labelled as such.
- **Next step: author decision.** Options are listed at the end of the results document.

## 2026-09-30 — Process note: oversubscription recurred (exploratory package)

- The fix of 2026-09-29 lived in `src/preflight/__init__.py`. The new `src/exploratory` package loaded numpy before importing it, so the exploratory runs used about 31 threads each (load average ~164 on 16 cores).
- **Fix:** `src/exploratory/__init__.py` now sets the limits first. The running jobs were stopped, and only unfinished configurations were relaunched. The 10 completed outputs are kept; thread count does not change the numerics.
- **Rule going forward:** every new analysis package must import `src.preflight` in its `__init__`.

## 2026-09-30 — T1 exploratory decomposition done

- **Decomposition:** removing diagnosis × X interactions accounts for −9.7 of the −9.0 percentage-point drop (Shapley). The other terms are context −0.9, partial penalty +1.6, and timing and denominator ≈ 0; cleaning is 0 by construction. See [t1_preflight_vs_confirmatory.md](t1_preflight_vs_confirmatory.md).
- **Residual 3.9%:**
  - partly a proxy for complication status (appendicitis);
  - not a test-ordering pattern;
  - era-unstable;
  - not pure noise, but small.

  See [t1_exploratory_results.md](t1_exploratory_results.md).
- **All of this is exploratory.** The confirmatory T1 conclusion is unchanged.

## 2026-09-30 — MC-MED external confirmatory workflow authorized

- **Author decisions:**
  - primary taxonomy CCSR body system (unmapped visits excluded);
  - soft D_hat primary (hard top-1 = S1; ICD-10 chapter = S2);
  - decision-time rule and early ICU/critical-care consult exclusion as audited;
  - full numerics in X; race/ethnicity excluded from primary X (S3);
  - locked 80/20 hash patient split;
  - success criterion unchanged (CI lower > 0 and relative gain ≥ 10%).
- **Stage A cohort** (`results/mcmed/stageA_cohort.json`): it matches the audit (34,039; ICU 1,267). After excluding the 1,635 visits (4.8%) without a CCSR mapping: **32,404 visits / 22,558 patients; ICU 1,109 (3.4%)**. The excluded unmapped visits have ICU 9.7%.
- **Ontology.** 20 final classes. MAL and PNL (< 50 visits) became OTHER. CCSR's own "XXX111 Unacceptable DX1" category (606 visits) is kept as assigned.
- **Context deviation (conservative, recorded before any outcome modeling).** Arrival hour and weekday are uniformly distributed in MC-MED: de-identification randomized them. Calendar year is not recoverable, and chronological-split membership is incomplete (11%) and depends on future visits. **Context = season only.** Temporal drift is examined by S4.
- **Feature-rule refinements before freezing** (from a dry run on the 100 MB numerics sample; no outcome used):
  - censored lab values take their limit;
  - qualitative components get an abnormal flag;
  - race-based eGFR ("EGFR FOR AFRICAN AMERICAN") is excluded.
- **Split** generated once (Stage C): development 25,834 visits / 18,023 patients / ICU 897 (3.5%); test 6,570 / 4,535 / ICU 212 (3.2%). Manifest SHA-256 `90739be0…fd42`. The salt was committed before generation (`0eee931`).
- **Environment note.** Python 3.14 defaults to forkserver on Linux, so the encoder requests `fork` explicitly.

## 2026-10-01 — MC-MED preregistration frozen

- **Tag:** `mcmed-confirmatory-prereg-v1` at commit `c04352971fab6d3082cee977edcef8689f5edb33`. Tagged before any encoder training or ICU modeling.
- **Numerics:** full file verified (SHA-256 `225509ce…6ab9`, matches PhysioNet). The file is complete, but 12% of cohort visits have no numerics rows in the released data.
- **X_3h:** 445 raw columns. All 11 numerics measures pass the ≥ 25% development-coverage rule.
- **From here on:** the preregistration is not edited in place. Changes go to `docs/amendments/`.

## 2026-10-01 — Stage E passed; amendment 1 (solver)

- **Encoder adequacy gate passed:**
  - out-of-fold log loss 29.7% below the class prior;
  - better in all 5 folds;
  - top-1 accuracy 0.448 vs majority share 0.248.
- **Stage F stop gate 9 (convergence).** The first run hit it: L-BFGS did not reach the optimum on the MC-MED design. [Amendment 1](amendments/2026-10-01-newton-solver.md) switches the solver to exact Newton on the identical objective. It was made before the test was opened, and the development-CV result that had been seen is disclosed.

## 2026-10-01 — MC-MED primary result and sensitivities

- **Stage F** (after amendment 1): all fits converged; C = 0.003; penalty-zero property verified.
- **Stage G** (one-shot locked test, 6,570 visits, 212 ICU):
  - ΔL = 0.0221 nats (95% CI 0.0167–0.0276), 0.032 bits;
  - relative gain 17.6% (13.7–21.2%);
  - AUROC 0.787 → 0.870.
- **Result: SUPPORTED.** Frozen and tagged `mcmed-confirmatory-primary-result` (`6c9834e`) before the sensitivities.
- **Stage I, relative gain:**
  - S1 (hard top-1) 21.9%;
  - S2 (ICD-10 chapter) 15.8%;
  - S3 (+ race/ethnicity) 17.3%;
  - S4 (chronological) 15.7%.
- **Post-freeze fix:** decile calibration cells with 1–9 events were suppressed (disclosure only). An earlier commit (`6c9834e`) contains the unsuppressed decile rates in the private repository's history. Rewriting that history needs author authorization.
- **Final report:** [results/mcmed_final_report.md](../results/mcmed_final_report.md). **STOP. Awaiting author review.**

## 2026-10-01 — Confirmatory freeze; exploratory mechanism decomposition; manuscript skeleton

- **Confirmatory analysis frozen** ([CONFIRMATORY_FROZEN.md](../CONFIRMATORY_FROZEN.md)):
  - freeze record [results/mcmed_confirmatory_freeze.md](../results/mcmed_confirmatory_freeze.md) (primary metrics re-verified from the stored predictions);
  - [amendment 1 final record](amendments/amendment_1_final.md), which states the deviation from the stop-and-review rule;
  - [audit trail](confirmatory_audit_trail.md);
  - overwrite guards in `src/mcmed`; private artifacts made read-only.
- **Exploratory decomposition** (plan `0b7c8bd` before running; results `b0dbd75`; test set reused descriptively):
  - measurement-process block alone 15.2%;
  - clinical-state values without it 13.9%;
  - physiology alone 6.8% (numerics 6.4%, triage vitals ≈ 1%);
  - removing physiology from ALL: no change.
- **Post-hoc hypothesis recorded, untested:** [future_hypotheses/anatomic_action_coupling.md](future_hypotheses/anatomic_action_coupling.md).
- **Manuscript material:**
  - [manuscript/empirical_paper_outline.md](../manuscript/empirical_paper_outline.md);
  - [overlap statement](../manuscript/overlap_statement.md);
  - [reproducibility/README.md](../reproducibility/README.md);
  - [results/target_dependent_sufficiency_summary.md](../results/target_dependent_sufficiency_summary.md).
- **STOP. Awaiting author review.**

## 2026-10-01 — Prior-art audit, novelty narrowed, diagnostic-capacity analysis (exploratory)

- **Integrity check.** Since the primary tag, the only changes to frozen result files are the decile small-cell suppressions (already disclosed). All primary metrics are identical.
- **Prior-art audit.** A nearest-neighbor, non-systematic audit was done ([../notes/prior_art_positioning.md](../notes/prior_art_positioning.md)).
- **Novelty claim narrowed.** It is now the operationalization of diagnosis as a cross-fitted soft concept bottleneck from the same contemporaneous state, with target-specific prespecified testing. Concept incompleteness and residual concept bottlenecks are prior work. Wording: "We did not identify an equivalent prior study in the current audit."
- **Confirmatory result unchanged.**
- **Authorized as exploratory:** the mechanism decomposition and the diagnostic-capacity robustness analysis. No new confirmatory endpoints are authorized.
- **Diagnostic-capacity result** (plan `0e5879b`; all 7 ontologies reported):
  - the residual shrinks with granularity, from 17.6% (20 classes) to 12.0% (52), 9.6% (94), and 8.1% (127); ICD-10 3-character 9.6% (92) and 9.2% (154);
  - the CI excludes 0 at every granularity;
  - the hindsight visit-label reference stays at 19–24%;
  - **the confirmed 17.6% is specific to the coarse representation.** This is now a central interpretive issue for the paper.
- **Anatomic/systemic hypothesis:** explicitly post-hoc, and moved to [../notes/future_hypotheses/](../notes/future_hypotheses/anatomic_action_coupling.md).
- **Notes created:** [../notes/current_findings_2026-10-01.md](../notes/current_findings_2026-10-01.md), [chronology](../notes/conceptual_preprint_chronology.md), [novelty map](../notes/conceptual_novelty_map.md).
- **STOP. Awaiting author review.**

## 2026-10-01 — Consolidation phase: amendment accepted, T1 solver audit, structured prior-art audit

- **Working interpretation frozen.** Sufficiency is conditional on the target (confirmatory) and on diagnostic resolution (exploratory). It is not a binary property, and no two-dimensional law is claimed.
- **Amendment 1 accepted by the author** ([amendments/amendment_1_author_acceptance.md](amendments/amendment_1_author_acceptance.md)).
- **MIMIC T1 post-hoc numerical robustness audit** ([../audits/mimic_t1_solver_audit.md](../audits/mimic_t1_solver_audit.md)):
  - original L-BFGS fits converged; inner-fit status had not been recorded but was verified;
  - the Newton rerun reproduces 3.9% exactly;
  - **T1 unchanged.**
- **Structured nearest-neighbor audit** ([../literature/nearest_neighbor_audit.md](../literature/nearest_neighbor_audit.md)):
  - sources: PubMed, arXiv, Crossref, and Semantic Scholar (partial; rate-limited despite parallel direct and proxy retries); no Google Scholar, Scopus, or WoS;
  - 1,792 records; 1,375 unique screened; 16 extracted; 11 full texts;
  - **no equivalent study found.**
  - **Closest:** PCBM-h, Yeh completeness, Wang 2026 (control-sufficient compression with a predeclared margin), Yoshimura 2026 (ED disposition and process indicators), and Yang & Chung 2026 (concurrent convergence with the conceptual preprint).
- **Capacity-curve figure specification:** CCSR family only; ICD shown separately. No new experiments.
- **STOP. Awaiting author review.**

## 2026-10-01 — Second-round nearest-neighbor prior-art search (no experiments)

- **Search scope:**
  - 125 queries in 7 strata (dataset/endpoint, representation, true-neighbor, disconfirming, granularity, conceptual, dataset-specific);
  - PubMed, arXiv, Crossref, and OpenAlex complete (OpenAlex via the proxy lane after 429s);
  - Semantic Scholar **search** unavailable, though its citation endpoint supplied forward citations of Koh/Yeh/PCBM/CEM/Res-CBM;
  - Google Scholar, Scopus, and WoS not accessible.
- **Screening:** 10,691 unique records; 1,590 titles screened manually after a relevance filter, plus all with triage score ≥ 3; 32 extracted; 16 full texts reviewed in total.
- **No equivalent study found. Stop condition not triggered.** The highest structural score among prior works is 4/10 (Marcinkevičs 2023: a clinical CBM with a residual channel and a management target, whose concepts are imaging findings, not diagnoses).
- **New closest works:**
  - Marcinkevičs 2023;
  - Wang 2026 and Murray 2026 (action/control-sufficient compression with predeclared margins; after the preprint);
  - Kansal 2021 (diagnosis-code grouping × target interaction; granularity precedent).
- **Claims classification** (`literature/nearest_neighbor_round2.md` §6):
  - "foundation models remove the need for human-readable internal representations" must be **removed**;
  - incompleteness, richer-state gain, and lossy labels are prior art;
  - target and granularity dependence are safe only with qualification;
  - the same-state cross-fitted diagnostic bottleneck is the most distinctive element.
- **Not changed:** frozen results and evidence status.
- **STOP. Awaiting author review.**

## 2026-10-01 — JBI manuscript: author decisions (writing stage; no experiments except one exploratory addendum)

Recorded retrospectively from the conversation; commits cited for traceability.

1. **Wording: "prespecified", never "preregistered".** Protocols were committed and tagged in Git before the confirmatory analyses but not registered externally. The title drops the preregistration claim (`c1c582f`).
2. **T1 name: "index procedural intervention",** defined as receipt of a prespecified diagnosis-specific index procedure. ERCP and percutaneous drainage are not operations (`c1c582f`).
3. **Negative controls: descriptive names in the main text.** Internal codes M5/T5/M3 appear only at first mention and in the supplement mapping (`c1c582f`).
4. **Granularity paired-bootstrap CIs.**
   - Run as a post-confirmatory exploratory analysis. The plan addendum `a9e7776` was committed before the results in `c1c582f`.
   - No trend test, and the 10% margin is not applied to finer levels.
   - Result: relative gain vs 20 classes was −5.5 / −8.0 / −9.5 points at 52 / 94 / 127 classes, all paired CIs excluding 0, driven by Model D.
5. **CBM references.**
   - Added after full-text verification (`1f549eb`): Mahinpei, Havasi, Espinosa Zarlenga, Margeloiu.
   - Hayashi & Sawada not needed.
6. **Central reposition** (`fec8b78`; refined in v1.5).
   - **Trigger:** round-2 finding A2-I4-1. The absolute log-loss reductions were similar (0.028 vs 0.032 bits/observation), while the fractional reductions differed (3.9% vs 17.6%) because Model D's loss differed about 4×.
   - **New title:** "Operationalizing Diagnostic Representation Sufficiency for Clinical Prediction: A Two-Cohort Study".
   - **New framing:** sufficiency is an operational property of representation, target, model family, and scale, not an intrinsic property of a diagnosis.
   - **Terminology:** the relative gain is described as the "fractional log-loss reduction"; "approximately sufficient" is used only in the operational sense.
   - **Scope limits:**
     - the prespecified fractional criterion and both confirmatory verdicts are unchanged;
     - the absolute-scale comparison across targets is labelled as not prespecified.
- **Not changed:** frozen results, features, taxonomy, solver, thresholds, outcomes, and evidence status.

## 2026-10-01 — Back matter and code release (author decisions)

- **Funding and competing interests:** none declared.
- **Authors:** Jing-Rung Huang (corresponding) and Wen-Hsiang Lu, NCKU CSIE, taken from the author's other projects (title pages of perspective-AI-mental-model and perspective-diagnosis-evolve). CRediT follows those papers.
- **Code release on GitHub via gh CLI:**
  - scope: code, protocols, and aggregates, as a fresh history, with the manuscript and internal reviews excluded;
  - visibility: private now, public at submission;
  - license: MIT;
  - counts below 10, including zeros, suppressed in the release copy only.
  - Details: `docs/public_release.md`. Repository: https://github.com/gbanyan/diagnostic-representation-sufficiency (private).
- **NCKU IRB:** the author is asking NCKU; the statement remains AUTHOR TO CONFIRM.



## 2026-10-02: Local ethics statement (author decision)

- **Decision:** the author chose to state a statutory exemption under the Human Subjects Research Act, Art. 5, and the MOHW announcement 1010265075 (2012-07-05), item 2, giving the legal basis and the data protections.
- **Inputs:** the NCKU ethics office reply of 2026-10-02 did not classify this study. The full record, including the weaknesses and the practice survey, is in `docs/ethics_determination.md`.
- **Manuscript:**
  - new back-matter "Ethics statement" section;
  - Section 3.14 points to it;
  - the [AUTHOR TO CONFIRM] placeholder has been removed;
  - the NCKU reply is not cited.

## 2026-10-02: Lab result availability sensitivity analysis (author approval)

The author approved a descriptive audit of MIMIC lab result times (`storetime`) and a post-confirmatory sensitivity analysis restricted to results available by the landmark (`exploratory/lab_availability/`). The confirmatory analysis stays primary. Results are in Round 9 of `manuscript/JBI_internal_review.md`.

## 2026-10-02: Release-copy redaction (author decision B)

The author chose to redact the pre-check admitted total ([redacted]) in the public release copy, including the release copy of the frozen MC-MED protocol, with a README note. See `docs/public_release.md`.

## 2026-10-03: Robustness follow-up analyses 1, 2 and 5 (author approval)

The author approved three exploratory, post-confirmatory MC-MED analyses (`exploratory/robustness_followup/`; plan `68ed39d`, committed before the run): dimension-matched granularity, Model D flexibility with D̂ fixed, and a MIMIC-matched comparator.

**Results.**
- The granularity decline was not reproduced at matched dimension: 18.8% (summed) and 19.8% (PCA), and 18.2% for the 20-class encoder at C = 0.01, against the frozen 17.6%. The compressions also discard finer label information, so added columns are not distinguished from finer diagnostic detail; this was corrected in round 17.
- A more flexible Model D gave 12.5% and 11.2%.
- A MIMIC-like comparator gave 10.4%.

The confirmatory result is unchanged. The manuscript reports the follow-up as exploratory in §3.12, §4.7, §5.1, §5.3, §5.4, §5.5, §5.9, the Abstract, Table 1 and the Conclusion, with full results in Supplementary Note S11.
