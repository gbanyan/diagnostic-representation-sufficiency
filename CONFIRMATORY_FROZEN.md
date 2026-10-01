# CONFIRMATORY ANALYSIS FROZEN

**Frozen on 2026-10-01.** The MIMIC confirmatory analysis (preregistration `600f368`, results in `docs/main_experiment_results.md`) and the MC-MED confirmatory analysis (tags `mcmed-confirmatory-prereg-v1` and `mcmed-confirmatory-primary-result`) are **frozen and read-only**.

**Read-only paths:**
- `config/mcmed_confirmatory_v1.yaml`
- `src/mcmed/`, `src/confirmatory/`
- `docs/mcmed_confirmatory_preregistration.md`, `docs/main_experiment_preregistration.md`, `docs/amendments/`
- `results/mcmed/`, `results/mcmed_*.md`, `results/main/`

**Private artifacts.** The private artifacts on gbminipc (`.../diagnosis-bottleneck-private/mcmed_v1/`) have write permission removed.

**Code guards.**
- The Stage A, C, E, and G entry points refuse to overwrite an existing cohort, split, feature matrix, D_hat, or opened test.
- `downstream test` evaluates each analysis once.

**Not allowed on the confirmatory pipeline:**
- changing features, taxonomy, C grid, solver, interactions, landmark, cohort, threshold, or outcome;
- re-running alternative models and presenting them as confirmation;
- tuning on test-set results.

**New analyses** go under `exploratory/`, are labelled **EXPLORATORY**, and may import the confirmatory code only read-only.

**Changes to a frozen document** can be made only as a dated file in `docs/amendments/`, stating whether results had been seen.

**Records:**
- [results/mcmed_confirmatory_freeze.md](results/mcmed_confirmatory_freeze.md)
- [docs/confirmatory_audit_trail.md](docs/confirmatory_audit_trail.md)
- [docs/amendments/amendment_1_final.md](docs/amendments/amendment_1_final.md)
