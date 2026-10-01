# eICU-CRD — target sufficiency preflight

- **Date:** 2026-09-29
- **Data:** eICU-CRD 2.0 full data, downloaded to gbminipc with checksums verified: `patient`, `hospital`, `diagnosis`, `treatment`, `medication`, `infusionDrug`, `admissionDx`, `pastHistory`, `carePlanGeneral`.
- **Not downloaded:** `lab`, `vitalPeriodic`, `vitalAperiodic`, `nurseCharting` (about 4 GB together). These are the contemporaneous X.
- **Code and results:** `src.preflight.temporal_checks`; aggregates in `results/phase0/sufficiency/eicu/temporal_checks_T{360,1440}min.json`, with counts below 10 suppressed.
- **Background:** the documentation and demo analysis are in [gates/eicu.md](gates/eicu.md).

**Diagnosis object:** the *latest primary problem-list entry saved by landmark T* (3-level `diagnosisstring`; top 15 groups, the rest pooled as "other"). This is `D_t`-like with **entry-time semantics**: when the entry was saved, not when the diagnosis was formed. It must be reported as "problem list as documented by T", never as the clinician's working diagnosis.

**Landmarks:** T = 6 h and 24 h after unit admission.

## Answers to the preflight questions

1. **Does the diagnosis timestamp plausibly approximate diagnosis availability?** Only loosely.
   - The first problem-list entry comes a median of 53 min after unit admission. 5.1% of stays have none by 6 h, and 0.6% none by 24 h.
   - Entries arrive in batches: a median of 2 distinct save times per stay (90th percentile 6).
   - **99.9% of `treatment` rows (3,683,942 of 3,688,745) share an exact timestamp with a diagnosis save in the same stay.** The problem list and the treatment list are saved together as care-plan events. The timestamp marks documentation, not diagnosis formation.
2. **Is diagnosis entry delayed relative to the clinical decision?**
   - On the demo, the gate record found sepsis entries after the first antibiotic order in 76% of 86 stays, and norepinephrine entries after the infusion start in 74%.
   - **NOT YET VERIFIED on the full data** (not re-run at scale).
   - On admission: 29% of antibiotic orders predate ICU admission (demo).
3. **Can treatment actions be aligned after a frozen time point?**
   - **`medication`** (`drugstartoffset` or `drugorderoffset`) and **`infusionDrug`** (`infusionoffset`): yes. They are recorded independently of problem-list saves.
   - **`treatment`: no.** It is co-saved with the diagnoses, so "treatment after T" largely means "care plan saved after T".
4. **Is there enough repeated diagnosis/treatment evolution to estimate temporal sufficiency?** Limited. With a median of 2 problem-list saves per stay, a trajectory of `D_t` over several stages exists only for longer stays. A two-landmark design (6 h, 24 h) is feasible; finer staging is not established.
5. **Within a diagnosis, how heterogeneous are the subsequent actions?**

   | Target | Landmark | Cohort | `H(Y)` | `H(Y|D)` | `I(Y;D)` | Range of within-D event rates |
   |---|---|---|---|---|---|---|
   | E1: vasopressor infusion start within 24 h after T (none by T) | 6 h | 110,596 | 0.245 | 0.237 | 0.008 | 0.9% (DKA) – 15.1% (septic shock) |
   | E1 | 24 h | 81,616 | 0.104 | 0.103 | 0.001 | ≤ 0.6% (two groups have < 10 events, suppressed) – 3.5% |
   | E2: new systemic antibiotic within 24 h after T (none by T) | 6 h | 95,913 | 0.293 | 0.289 | 0.004 | 3.0% – 9.8% |
   | E2 | 24 h | 70,558 | 0.192 | 0.191 | 0.002 | 0.8% – 5.3% |

   The documented diagnosis explains very little of these actions (`I(Y;D)` ≤ 3% of `H(Y)`). Events are infrequent, especially at 24 h. Much variability remains *within* diagnosis, but whether it is recoverable from X is unknown (Q6). Documentation completeness is a confounder: a "0" can mean not charted. No per-hospital completeness filter has been applied yet.
6. **Can richer contemporaneous X predict that heterogeneity?** **Cannot evaluate with current data.** `lab` and `vitalPeriodic` are not downloaded. APACHE variables are first-24-h aggregates, which leak for T < 24 h and are excluded.
7. **How many hospitals and patients remain after temporal filtering?**
   - Stays alive in the unit at 6 h: 184,398. With a primary diagnosis by 6 h: 121,446 (65.9%). At 24 h: 132,783 and 95,789 (72.1%).
   - Hospitals with any infusion rows: 146 of 208. With any medication rows: 174 of 208.
   - A per-hospital completeness filter (not yet applied) will reduce these.

## Candidate targets

| ID | Target | Stage A | Stage B | Stage C | Leakage / validity | Class |
|---|---|---|---|---|---|---|
| E1 | Vasopressor start within 24 h after T = 6 h | Large within-D variability; D almost uninformative (`I` = 0.008 bits) | Cannot evaluate (X not downloaded) | Plausible (escalation; a control-like decision) | Problem-list entry lags actions; documentation completeness varies by site; observed behavior (G11) | **YELLOW**: needs X, a per-site completeness filter, and an entry-lag audit at scale |
| E1 (24 h) | Same, T = 24 h | Events 0.6–3.5%; `H(Y|D)` = 0.10 | Cannot evaluate | Plausible | As above | **YELLOW / likely underpowered per diagnosis** |
| E2 | New antibiotic within 24 h after T | Moderate; D uninformative (`I` = 0.004) | Cannot evaluate | Plausible | As E1; "new" = none started by T within this ICU stay (pre-ICU antibiotics are invisible) | **YELLOW** |
| — | `treatment` table as target | — | — | — | **Co-saved with diagnoses (99.9%)** | **RED** |

**Negative-control candidate:** none identified yet. Diagnosis is weakly informative for every action examined.

## What eICU could add, if the author approves

A test of the control-layer arm on a management-phase target (E1 at 6 h), with X from `lab` and `vitalPeriodic` cut at T. This needs:
1. Downloading `lab` (517 MB) and `vitalPeriodic` (1.8 GB). Cloud access would be faster.
2. A per-hospital documentation-completeness filter, pre-specified.
3. The full-data entry-lag audit (Q2).
4. The same fixed-model Stage B as MIMIC-CDM.

It would **not** address early diagnosis or examination planning.
