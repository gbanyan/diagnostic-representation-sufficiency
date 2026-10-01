# MIMIC-CDM Phase 0 audit

Scripts for the row-level parts of the [Phase 0 plan](../docs/phase0_preflight_plan.md): Q2 inventory, Q3 timing, Q5 hindsight flags, Q7 treatment-rubric prevalence, and the Q3/Q5 manual-audit sample. The Python standard library is enough (3.10+). These scripts do no modeling and no LLM calls.

## Data handling

- Input data stays in credentialed storage on gbminipc and is never copied into this repository.
- `--out` receives **aggregate JSON only** (counts, rates, quantiles). Commit it under `results/phase0/` after checking it contains no free text or identifiers.
- `--private-dir` receives the manual-audit sample (admission IDs). The script refuses a path inside the repository.

## Prerequisites

1. Sign the PhysioNet data use agreements for `mimic-iv-ext-cdm` 1.1, `mimiciv` 3.1, `mimic-iv-ed` 2.2, and `mimic-iv-note` 2.2.
2. Download to gbminipc (PhysioNet credentials are in `~/.netrc` there; use `wget`):

   ```
   /mnt/SAM1TB/dev/data/mimic-iv-ext-cdm/1.1/
   /mnt/SAM1TB/dev/data/mimiciv/3.1/{hosp,ed,note}/   # only the tables listed below
   ```

   Timing needs `hosp/admissions`, `hosp/procedures_icd`, `ed/edstays`, and `note/radiology`.
3. Copy the upstream framework checkout pinned in [docs/gates/mimic_cdm.md](../docs/gates/mimic_cdm.md) (`e1b4a522`), which supplies the treatment procedure mappings.

## Run (on gbminipc)

```
python3 -m audit.cdm_audit all \
  --cdm-dir /mnt/SAM1TB/dev/data/mimic-iv-ext-cdm/1.1 \
  --mimic-dir /mnt/SAM1TB/dev/data/mimiciv/3.1 \
  --framework-dir <path>/MIMIC-Clinical-Decision-Making-Framework \
  --out results/phase0/mimic_cdm \
  --private-dir /mnt/SAM1TB/dev/data/diagnosis-bottleneck-private
```

The sample seed defaults to `20260929`, with 50 cases per pathology (fixed in [decision_log.md](../docs/decision_log.md)).

## Tests

```
python3 -m unittest discover -s tests -t . -v
```

Tests run locally on synthetic data. The upstream-mapping test is skipped if `external/` is absent.

## Known approximations

- `keyword_positive` approximates the upstream spaCy + negex check with a negation-cue window. Q7 prevalence can differ slightly from what the upstream evaluator would compute.
- Procedure dates in `procedures_icd` have day resolution. Items on the procedure day are reported separately as ambiguous.
- Lexicon flags are screening signals for manual review, not leakage verdicts.
