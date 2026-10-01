# Addendum: paired bootstrap differences along the CCSR granularity curve

**Status:** EXPLORATORY, post-confirmatory. Written 2026-10-01 **before running**, at the author's request (JBI v1.1 review item B-D5-5; author decision 4).

**What it adds.** Paired 95% CIs for the **differences** between granularity levels. The marginal CIs per level already exist in `results/capacity.json`.

**Scope.** CCSR family only: R2 (20, frozen primary), R3 (52), R4 (94), R5 (127). ICD-10 points and the hindsight reference are not included.

**Procedure.**
1. **Refit each level** with the D̂ already produced by `run.py`, the same reference class, and the `C_selected` recorded in `capacity.json`. This is the exact Newton fit on development data, evaluated on the already-opened test set. No re-tuning.
2. **Reproduction gate.** Each level's L_D, L_DX (bits), and marginal Δbits CI must reproduce `capacity.json` to 1e-4 bits. If any level fails, stop and report; no differences are reported.
3. **One patient-cluster bootstrap shared by all four levels.** 1,000 replicates, seed 20261006, the same scheme as `src/mcmed/metrics.bootstrap`. Each replicate draws one set of test patients, and all four levels are evaluated on that draw.
4. **Reported differences** (percentile 95% CIs):
   - relative gain(K) − relative gain(20);
   - Δbits(K) − Δbits(20);
   - L_D(K) − L_D(20);
   - L_DX(K) − L_DX(20).
   K ∈ {52, 94, 127}.

**Not done.**
- No trend test or p-value.
- No cutoff search.
- The 10% margin is not applied to any finer level.
- No sufficiency label is attached to any finer level.

**Output.** Aggregate JSON only: `results/capacity_paired_diff.json`.
