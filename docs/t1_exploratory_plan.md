# T1 exploratory plan: decomposition and residual-signal heterogeneity

**EXPLORATORY. Written 2026-09-30, after the confirmatory T1 result and before any of these analyses were run.**

- Authorized by the author as option (b), *exploratory only*.
- Nothing here changes the confirmatory result: **T1 did not support the primary hypothesis**.
- No confirmatory p-values are produced. Estimates carry descriptive 95% bootstrap intervals only.
- No subgroup is searched for in order to exceed the 10% threshold.
- The primary target, features, cohort, and model family of the confirmatory analysis are unchanged. Deviations exist **only** inside the listed exploratory configurations.

**Common setup unless stated:**
- Cohort: expanded MIMIC-IV, GREEN-only, landmark 6 h, X1.
- Nested CV as in the preregistration, but with **one outer repeat** (seed 20260929) and 1,000 bootstrap resamples. This saves compute; it is exploratory.
- Relative Δ is reported against both LL(`Model_D`) and the empirical `H(Y|D)`. The preflight used the latter.

## Part 1 — Preflight (≈ 13%) vs confirmatory (3.9%): factorial decomposition

The two specifications differ in five ways:

| Factor | Preflight nested run | Confirmatory |
|---|---|---|
| (I) Diagnosis × X interactions | Yes | No |
| (Cx) Common context | None | Era + diagnosis × era + time of day + weekend |
| (P) Penalty on diagnosis/context coefficients | Shared L2 (penalized with X; `Model_D` tuned) | Unpenalized (partial penalty) |
| (Tm) Timing cohort | RED excluded | GREEN only |
| (Dn) Denominator of relative Δ | Empirical `H(Y|D)` | LL(`Model_D`) |

**Physiologic cleaning** (bounds, log1p, clipping) was **identical** in the preflight nested runs and the confirmatory run. The only pre-cleaning run is the superseded fixed-C X0 run. Cleaning therefore contributes nothing to this difference by construction. It is documented, not re-estimated.

**Factorial (12 runs):** I ∈ {no, yes} × Cx ∈ {none, era main effects, full} × P ∈ {partial, shared}, all on GREEN-only.
- Tm is quantified separately: the preflight-like configuration (I = yes, Cx = none, P = shared) on RED-excluded vs GREEN-only.
- Dn is computed for every run.
- **Attribution:** exact Shapley values over the three binary factors I, Cx (none vs full), and P, plus the one-at-a-time path from the preflight-like to the confirmatory configuration. Era-main is reported as an intermediate context level.

## Part 2 — Exploratory heterogeneity of the residual signal (confirmatory specification unless stated)

| ID | Question | Analysis |
|---|---|---|
| E1 | Where is it? (diagnosis, era) | Δ within each diagnosis and within each era, from the out-of-fold predictions |
| E2 | Diagnosis-specific X effects | Δ per diagnosis under I = yes (read from the Part 1 factorial) |
| E3 | Which physiology or feature groups carry it? | X restricted to one group, and X minus one group. Groups: demographics/history (age, sex, prior admissions, ambulance); triage (8); inflammatory labs (WBC, neutrophils, CRP, lactate); hepatobiliary/pancreatic labs (bilirubin, ALT, AST, ALP, lipase); renal/metabolic labs (creatinine, BUN, glucose, Na, K, bicarbonate, calcium); hematologic/other (Hb, platelets, INR, albumin) |
| E4 | Values or ordering pattern? | X = measured values only (no missing indicators) vs X = missing indicators only (which tests were drawn by T) |
| E5 | Complication status (finer diagnosis) | Add unpenalized diagnosis × complication-subtype indicators to **both** models; compare Δ with and without them |
| E6 | Imaging findings | MIMIC-CDM cohort: X1 vs X2 (X2 = sensitivity analysis 5, already run) |

**E5 complication subtype (rule fixed here).** Derived from the admission's **primary ICD title** (a discharge-coded, hindsight label). It is used only as an explanatory stratifier, never as a time-T feature.
- **Complicated** = the title matches the regex `\bwith\b[^,;]*?(perforation|abscess|peritonitis|gangren|necrosis|obstruction|cholangitis)`. The `\bwith\b` word boundary excludes "without".
- Otherwise uncomplicated.
- **Caveat:** ICD-9 titles (before October 2015) carry less detail (for example, no pancreatitis necrosis codes), so subtype availability is confounded with era.

**Reading guide (fixed before results; categories are not mutually exclusive):**

| If… | …the residual is compatible with |
|---|---|
| E5 absorbs most of Δ | (1) within-diagnosis clinical heterogeneity that a finer diagnosis label captures |
| E4: missing indicators carry most of Δ | (2) practice-pattern heterogeneity (which tests clinicians drew) |
| Δ varies strongly by era or context (E1, Part 1 Cx) | (3) residual context |
| Intervals include 0 | (4) noise |

No clinical interpretation of *why* management differs is made (**Q15 remains DEFERRED**).
