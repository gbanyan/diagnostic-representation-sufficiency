# Target sufficiency preflight code

This implements [docs/target_sufficiency_framework.md](../../docs/target_sufficiency_framework.md). It is CPU-only and uses numpy + scikit-learn (`requirements-preflight.txt`). It trains no main model, uses no LLMs, and does no tuning.

## Where to run

Run on gbminipc, where the credentialed data live:

```
cd /mnt/SAM1TB/dev/projects/diagnosis-bottleneck
export PREFLIGHT_PRIVATE_DIR=/mnt/SAM1TB/dev/data/diagnosis-bottleneck-private
FW=external/MIMIC-Clinical-Decision-Making-Framework     # pinned e1b4a522
```

- Data root: `PREFLIGHT_DATA_ROOT` (default `/mnt/SAM1TB/dev/data`).
- Patient-level tables go to `PREFLIGHT_PRIVATE_DIR`, which must be outside the repository. The code refuses otherwise.
- Only aggregate JSON, with counts below 10 suppressed, is written under `results/phase0/sufficiency/`.

## Commands

```
.venv/bin/python -m src.preflight.coverage --dataset all                       # which files are usable
.venv/bin/python -m src.preflight.mimic_cdm_table --framework-dir $FW --landmarks 3 6
.venv/bin/python -m src.preflight.leakage_checks --dataset mimic_cdm           # must pass before Stage B
.venv/bin/python -m src.preflight.coverage --dataset mimic_cdm --table         # feature missingness
.venv/bin/python -m src.preflight.target_heterogeneity --dataset mimic_cdm --target T1 T2 T3 T4 T5 T6 T7 T8 T9 --landmark 6
.venv/bin/python -m src.preflight.simple_incremental_models --dataset mimic_cdm --target T1 T2 T3 T4 T5 T8 T9 --features X0 X1 X2 --landmark 6
.venv/bin/python -m src.preflight.simple_incremental_models --dataset mimic_cdm --target T1 --landmark 6 --sensitivity
.venv/bin/python -m src.preflight.procedure_timing classify --framework-dir $FW          # Q14
.venv/bin/python -m src.preflight.medication_targets audit && .venv/bin/python -m src.preflight.medication_targets build   # Q17
.venv/bin/python -m src.preflight.simple_incremental_models --dataset mimic_cdm --nested --target T1 --t1-timing exclude_red --landmark 6
.venv/bin/python -m src.preflight.simple_incremental_models --dataset mimic_cdm --nested --target M1 M2 M3 M4 M5 M6 --landmark 6
.venv/bin/python -m src.preflight.temporal_checks --dataset eicu
```

## Modules

| Module | Role |
|---|---|
| `schemas.py` | File and column registry. `require()` fails with every missing file or column; files still downloading are rejected. |
| `mimic_cdm_table.py` | Landmark table. Anchor = ED arrival. Features are cut at T (labs by `charttime`; radiology by report `storetime`). Targets are strictly after T; OR/PACU and ICU times come from `transfers`. |
| `targets.py` | Pre-specified targets T1–T9 and feature sets X0 ⊂ X1 ⊂ X2. |
| `target_heterogeneity.py` | Stage A: `H(Y|D)`, majority share, within-D variance. |
| `simple_incremental_models.py` | Stage B: `D → Y` vs `D + X + X×D → Y`, with 5-fold subject-grouped CV and a paired subject bootstrap. It refuses examination targets against `D_final`. |
| `leakage_checks.py` | Asserts that no feature falls after T and that targets fall after T. |
| `coverage.py` | File availability; feature missingness in the table. |
| `temporal_checks.py` | eICU: diagnosis save batching, diagnosis–treatment co-timing, landmark coverage, Stage A for E1/E2. |
| `reporting.py` | Private-directory guard, small-cell suppression, JSON output. |
| `procedure_timing.py` | Q14: `vocab` (POE vocabulary, counts only) and `classify` (per-case GREEN/YELLOW/RED ordering for T1; private CSV plus aggregates). |
| `medication_targets.py` | Q17: `audit` (prescription/POE/eMAR timing semantics) and `build` (M1–M6 targets, private table). |
| `review_lists.py` | Q15 (deferred): stratified private case list for a future clinician review. No interpretation. |

Tests (synthetic data only): `.venv/bin/python -m unittest discover -s tests -t .`
