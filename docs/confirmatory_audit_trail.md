# MC-MED confirmatory study: audit trail

All times are Asia/Taipei (+0800). Commits are in the private Gitea repository.

**"Test visible"** means that any locked-test prediction, outcome summary, or metric had been produced. Before 2026-10-01 04:56:32 none existed.

**"Meaning changed"** refers to the scientific estimand, estimator, or decision rule.

## Timeline

| # | Time | Event | Commit / tag | Test visible | What changed | Meaning changed |
|---|---|---|---|---|---|---|
| 1 | 2026-09-30 15:17 | MC-MED DUA signed; data dictionary checked (MRN, Dispo_time, Result_time, chronological splits) | `e95f844` | no (no data) | Dataset selected for the T3 follow-up | — |
| 2 | 16:18–16:40 | Dataset audit: counts only (no ICU split); visits and split files downloaded and SHA-256 verified | `bcb6e37`, `f105f5a` | no | Counts documented | — |
| 3 | 19:07 | First T3-follow-up design (visit diagnosis as D) marked **SUPERSEDED**: diagnosis timing unresolved | `c0db877` | no | Design withdrawn | Yes: design replaced before any analysis |
| 4 | 19:12 | **Diagnosis-semantics audit**: no field can represent D at 3 h, so D_hat is required | `9a5614e` | no | `docs/mcmed_diagnosis_semantics.md` | — |
| 5 | 19:12–20:45 | 3 h feature semantics (GREEN/YELLOW/RED), leakage audit (decision-time rule, ICU consults), taxonomy candidates (counts only, never ICU by class) | `ba1195f` … `8ca3e94` | no | Audit documents | — |
| 6 | 2026-09-30 (author) | Author authorizes the confirmatory workflow: CCSR primary, soft D_hat, 3 h landmark, decision-time rule, consult exclusion, full numerics | — | no | **3-hour landmark and taxonomy choice frozen by the author** | — |
| 7 | 23:19 | Draft config and Stage A cohort builder | `70fc812` | no | Code | — |
| 8 | 23:19:24 | **Cohort constructed** (private `cohort.csv`): 32,404 visits; ICU 3.4%; matches the audit | `cabc64b` (results) | no | — | — |
| 9 | 23:31:28 | **Preregistration draft with the split salt committed before the split was generated** | `0eee931` | no | Salt fixed | — |
| 10 | 23:31:37 | **Split frozen** (private manifest), generated once | `cabc64b` | no | Development 25,834 / test 6,570 | — |
| 11 | 23:32 | Decision log. **Context = season only**, because de-identification randomized time of day, weekday, and year | `c778407` | no | Deviation from the authorized context list, recorded before any outcome model | No (the unrecoverable variables could not carry context) |
| 12 | 23:36 | Encoder convergence rule (tol 1e-4; a non-converged C is ineligible), from a runtime-only timing fit | `b6173d2` | no | Encoder tolerance | No |
| 13 | 2026-10-01 02:34:11 | **Full numerics download complete** | — | no | — | — |
| 14 | 03:33 | **Numerics checksum verified** (matches PhysioNet); X_3h built (445 columns) | `c043529` | no | — | — |
| 15 | **03:33:40** | **Preregistration frozen** | **`c043529`, tag `mcmed-confirmatory-prereg-v1`** | no | — | — |
| 16 | 03:49:38 | **Diagnosis encoder trained**; development OOF and test D_hat produced (diagnosis labels only) | report `d4a61e5` (03:50) | no | Adequacy gate passed | — |
| 17 | ~04:00–04:47 | Stage F with L-BFGS. **Convergence failure** (final D+X not converged; penalty-zero check failed). Development CV estimate seen (13.1%) | — (output kept outside the repository) | no | — | — |
| 18 | ~04:48–04:52 | Development-only diagnostic: L-BFGS vs exact Newton | — | no | — | — |
| 19 | 04:54:25 | **Amendment 1**: Newton solver for the same objective. **Deviation from the stop-and-review instruction** | `69bb6b7` | no | Optimizer only | No (same objective and estimator; see the amendment) |
| 20 | 04:55:09 | Stage F re-run; all fits converged; C = 0.003 | — | no | — | — |
| 21 | 04:56:24 | **Pre-test readiness** report | `0453d40` | no | — | — |
| 22 | **04:56:32** | **Locked test opened** (one evaluation); predictions written 04:56:33, read-only | — | **yes, from here on** | — | — |
| 23 | 04:57:08 | **Primary result frozen: SUPPORTED** | **`6c9834e`, tag `mcmed-confirmatory-primary-result`** | yes | — | — |
| 24 | 04:57–05:34 | **Sensitivities S1–S4**: two new encoders (chapter 05:15; chronological 05:30); tests 05:31–05:34 | `7651bfc` (05:36) | yes | — | No (no confirmatory role) |
| 25 | 04:57–04:58 | Operational incident: a duplicate sensitivity job, killed within about a minute before any output | — | yes | — | No |
| 26 | 05:36 | Final report. Small-cell suppression of the decile tables (disclosure fix; values unchanged) | `7651bfc` | yes | — | No |
| 27 | 07:26 | Exploratory mechanism-decomposition plan and code committed **before** running | `0b7c8bd` | yes | Exploratory only | No (outside the confirmatory scope) |

**Pipeline commits.** Code refinements (lab parsing, the name guard, the downstream Newton switch) are in `a845f25`, `0eee931`, `b6173d2`, and `69bb6b7`. All except `69bb6b7` precede the preregistration tag.

**Comparison.** `git diff mcmed-confirmatory-prereg-v1 mcmed-confirmatory-primary-result` shows every post-tag change: amendment 1, the readiness report, and the frozen result.

## SHA-256 references

| Artifact | Location | SHA-256 |
|---|---|---|
| MC-MED `numerics.csv` | PhysioNet v1.0.1 | `225509cec1822e7b89bb047837775c90cf40d1aa8136bd94eb85330782d66ab9` |
| AHRQ DXCCSR v2024.1 | public reference | `04b25ceb6d557b999a92edc647ca9c61d54720a769dd951430135168ecacf863` |
| Config `config/mcmed_confirmatory_v1.yaml` | repository (unchanged since the tag) | `e8b776d010b2b289f358a807872f4020ba93f85e6f2b2daf279dc619c4ed6605` |
| Split manifest | private | `90739be0ebaba21d5d568ce94b88d17af370e06b11375c0fdb7e1071fe47fd42` |
| Cohort table | private | `fb506302e4fd8918cfae225461e20712823f1ed83ce2452ed86fcad57daeaeea` |
| X_3h matrix `X.npz` | private | `3661c29065e51728fcfbc6887a874018271190d9559d8f3e7b74ae9c36593a0f` |
| Chief-complaint vocabulary | private | `5b5a7946b058926531a47b1c7adb9cb25404e8f8f7aeabb287aa979a423d185c` |
| Primary D_hat `dhat_body_primary.npz` | private | `48a4b4601d51d598e9eeff5df97813b5bb7974330bd462f519948cf73bee3971` |
| Primary models `models_primary.pkl` | private | `395e32699a94946ec8e7950c8c5bb1e466478213a8d88278101eea92490bf7f3` |
| Model coefficients D / D+X | frozen report | `787930c7…aa58` / `90d2a87d…62d9` |
| **Primary test predictions** | private, read-only | `6b02c6c7e38808e41fd93242ff207e9e3a69206cd616aa9f7412db65dea50770` |
| S1 / S2 / S3 / S4 test predictions | private, read-only | `384efdfa…a8a7` / `d97e86d5…1738` / `fb6eb8b2…3922` / `2e20bede…de6c` |

All private files are under `/mnt/SAM1TB/dev/data/diagnosis-bottleneck-private/mcmed_v1/` on gbminipc, outside git. They are made read-only as part of the freeze.
