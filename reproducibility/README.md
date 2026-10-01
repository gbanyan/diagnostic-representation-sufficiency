# Reproducibility package: what can and cannot be released

**Governing rules:**
- the PhysioNet credentialed data use agreements (MIMIC-IV family, MC-MED);
- this repository's rule that nothing patient-level is committed.

**Environment of record:**
- gbminipc, Linux x86-64, Python 3.14.2 ([requirements-lock-gbminipc.txt](requirements-lock-gbminipc.txt)), OpenBLAS (scipy-openblas 0.3.34);
- one BLAS/OpenMP thread per process (set in `src/preflight/__init__.py`);
- multiprocessing with the `fork` start method.

## Public (releasable)

| Item | Location |
|---|---|
| Analysis code | `src/` (preflight, confirmatory, mcmed), `exploratory/` |
| Frozen configuration | `config/mcmed_confirmatory_v1.yaml` (SHA-256 `e8b776d0…6605`) |
| Preregistrations | `docs/main_experiment_preregistration.md` (`600f368`); `docs/mcmed_confirmatory_preregistration.md` (tag `mcmed-confirmatory-prereg-v1`) |
| Amendments | `docs/amendments/` (amendment 1 and its final record) |
| Audit trail and decision log | `docs/confirmatory_audit_trail.md`, `docs/decision_log.md` |
| Semantic audits and data rules | `docs/mcmed_diagnosis_semantics.md`, `docs/mcmed_3h_feature_semantics.md`, `docs/data_cleaning_rules.md`, and others |
| Aggregate results (counts < 10 suppressed) | `results/` (JSON and Markdown) |
| Tests on synthetic data | `tests/` (54 tests; no real data) |
| Environment lock | `reproducibility/requirements-lock-gbminipc.txt`, `requirements-preflight.txt` |
| Schemas | The expected input tables are the PhysioNet releases themselves. Column-level schemas are in the audit documents and the code (for example `src/mcmed/features.py`). Synthetic example inputs are built in `tests/test_mcmed.py` and in the smoke-test pattern described below |
| Plotting code | None produced yet. Figures are specified in `manuscript/empirical_paper_outline.md` and will be generated from aggregate results only |
| Public reference file | AHRQ DXCCSR v2024.1 (obtain from AHRQ; SHA-256 `04b25ceb…f863`) |

## Protected (not public)

| Item | Why | Where |
|---|---|---|
| Raw MIMIC-IV / MIMIC-IV-ED / MIMIC-IV-Ext-CDM / MC-MED files | Credentialed PhysioNet data | `/mnt/SAM1TB/dev/data/` on gbminipc |
| Derived patient-level tables: cohort, X matrices, D_hat, raw features | Patient-level, derived from credentialed data | `/mnt/SAM1TB/dev/data/diagnosis-bottleneck-private/` (outside git, read-only) |
| Split manifests (MRN → set) | Identifiable linkage | Private; SHA-256 committed |
| Test predictions (per-visit y, p_D, p_DX) | Patient-level | Private, read-only; SHA-256 committed |
| Chief-complaint vocabulary | Free-text-derived | Private; SHA-256 committed |
| Fitted model objects | Low risk, but derived from credentialed data | Private; coefficient hashes committed. They could be released only if the DUA permits |
| Clinical notes | Not used; MC-MED releases none | — |

## Re-running (for a credentialed user)

1. Obtain credentialed access and download the datasets. Verify them against PhysioNet `SHA256SUMS.txt`. The numerics hash is recorded in the audit trail.
2. Create the environment from the lock file.
3. Set `config/mcmed_confirmatory_v1.yaml → data` paths. Keep the private directory outside the repository.
4. **MC-MED:** run
   ```
   python -m src.mcmed.cohort
   python -m src.mcmed.split
   python -m src.mcmed.features extract|build
   python -m src.mcmed.encoder
   python -m src.mcmed.downstream develop|test
   ```
   The split is a deterministic hash of MRN plus the salt, so it is reproducible without the manifest.
5. **Checks:**
   - compare the aggregate JSONs in `results/mcmed/` and the private hashes in `docs/confirmatory_audit_trail.md`;
   - the one-shot guards make a second `test` refuse to run on the same private directory;
   - a replication should use a fresh private directory.

**MIMIC analyses:** `src/preflight/*` and `src/confirmatory/target_sufficiency.py`, as described in `docs/main_experiment_preregistration.md` (execution order).
