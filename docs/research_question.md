# Research question

## Primary question

Does forcing a clinical AI system to compress the currently available patient state into a discrete disease-label representation before planning the next examination or treatment action degrade planning quality compared with reasoning directly from a richer patient-state representation?

## Formulation

Let

- `S_t` — the patient information genuinely available at a defined clinical decision time *t* (see staged states below);
- `D_t` — a discrete diagnostic representation at time *t*: a single label or a ranked differential over a fixed label vocabulary;
- `Z_t` — a richer representation of `S_t` that is not constrained to the diagnostic vocabulary;
- `A_{t+1}` — the next clinical action: a next examination/investigation, or a treatment/management plan.

The contrast:

```
Diagnostic bottleneck:   S_t -> D_t -> A_{t+1}      (the planner sees only D_t)
Direct state:            S_t -> Z_t -> A_{t+1}      (the planner sees Z_t)
```

Both arms receive the same `S_t`. No information from after *t* enters either arm. The quantity of interest is the difference in planning quality between the arms at the same *t*, not the accuracy of `D_t`.

### Ideal temporal structure

```
X_t0 -> D_t0 -> exam E_t1 -> X_t1 -> revised D_t1 -> ... -> treatment/management -> D_final
```

`D_final` is the end of this chain. It is never substituted for `D_t` at an earlier *t*.

### Provisional staged states

| Stage | Content | Status |
|---|---|---|
| S0 | History / presenting complaint / HPI | Unverified |
| S1 | S0 + physical examination | Unverified |
| S2 | S1 + initial laboratory data | Unverified |
| S3 | S2 + first imaging or major diagnostic investigation | Unverified |
| S4 | All information legitimately available before the final management decision | Unverified |

These stages are hypotheses about what a dataset can support. Each must be verified against dataset semantics (Phase 0) before use.

## Four kinds of "diagnosis" that must never be conflated

1. **Final/discharge diagnosis** (`D_final`) — formed after tests, specialist review, treatment response, retrospective synthesis, and coding.
2. **Working diagnosis / impression at time t** — what a clinician documented as their leading impression at *t*.
3. **Differential diagnosis at time t** — the documented set of candidates at *t*.
4. **Experimentally imposed bottleneck** — a model-generated `D_t` produced from `S_t` under the experimental condition.

If only (4) is available, every report must say: *`D_t` is an experimentally imposed diagnostic bottleneck, not the historical physician diagnosis.*

## Why this is not "diagnosis is useless"

- The study does not remove diagnosis from the system; the hybrid condition (see [experiment_sketch.md](experiment_sketch.md)) still produces one.
- It asks about **routing**: whether the planner must see the patient *only through* the label.
- A finding that the bottleneck is costly is compatible with diagnosis being accurate, useful for communication, and useful as an additional input.
- A finding of no cost is informative: it would mean the label is a sufficient summary for that decision at that stage.
- The study is not framed as "removing diagnosis improves performance."

## Minimal falsifiable hypothesis

**H1.** At a fixed decision time *t* with a leakage-free `S_t`, a planner restricted to `D_t` produces next-action plans of lower quality than a planner given `Z_t` (or `S_t` directly) on a planning-quality metric that does not reward reconstructing `D_final`.

**Falsified if** Bottleneck ≈ Direct (within a pre-specified equivalence margin), or Bottleneck > Direct, across the validated stages and action types, with adequate power.

**Supporting pattern that is more informative than a global win:** Hybrid > Bottleneck while Hybrid produces a diagnosis of comparable accuracy. This would suggest diagnosis may remain useful while requiring planning to pass through it imposes a cost.

### Provisional temporal hypothesis (not an established claim)

The cost of the bottleneck may depend on state and task:

- Early (S0–S1), when diagnosis is unstable, the cost for **examination planning** may be larger.
- Later, once diagnosis is established, **categorical** decisions may approach equivalence.
- **Patient-specific treatment/control** decisions (dose, timing, intensity, contraindications) may still benefit from richer state even after diagnosis stabilizes.

This matches the conceptual preprint's prediction (equivalence for categorical decisions, advantage for control decisions), but here it is a hypothesis to be tested, not an assumption.

## Optional secondary analysis (not yet authorized)

At each validated stage, estimate how recoverable `D_final` is from `S_t`, and define a conceptual

```
t* = earliest stage at which diagnostic confidence/stability exceeds a pre-specified threshold
```

to characterize when labels become reasonable summaries. This is not the primary endpoint and is not to be implemented until staged states pass G1 and G7.
