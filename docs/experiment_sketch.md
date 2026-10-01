# Minimal experiment sketch

**Status: sketch only. Not authorized for implementation.** It depends on Phase 0 gate outcomes. It is not a system design.

## Conditions

At a fixed, validated stage `S_t`, with identical inputs, base model, and compute budget across conditions:

**A. Diagnostic bottleneck**

```
S_t -> discrete diagnosis / differential D_t -> examination or treatment plan
```

The planner receives **only** `D_t`, not `S_t`. The restriction is enforced structurally (separate calls or modules), not by instruction.

**B. Direct state**

```
S_t -> richer internal representation -> examination or treatment plan
```

No diagnostic output is required.

**C. Hybrid**

```
S_t -> richer internal representation -> examination or treatment plan
                                     \-> diagnosis output (separately)
```

A diagnosis is produced, but planning does not have to pass through it.

## Interpretation

| Result | Reading |
|---|---|
| C > A, and C's diagnosis ≈ A's diagnosis in accuracy | Diagnosis may remain useful, but requiring planning to pass through it may impose a cost. The primary result of interest. |
| B ≈ C > A | Cost comes from the bottleneck, not from lacking a diagnosis. |
| A ≈ B ≈ C | No detectable cost at this stage and task: the label is a sufficient summary here. A valid negative result. |
| A > B or A > C | The bottleneck helps, for example as a regularizer. A valid result. |
| Effect varies by stage / action type | Evaluate against the provisional temporal hypothesis in [research_question.md](research_question.md). |

The hypothesis is **not** "removing diagnosis improves performance."

## Optional reference arm (treatment sufficiency, MIMIC-CDM)

`D_final -> treatment plan` versus `S_4 -> treatment plan`. This asks whether the diagnosis is sufficient for treatment **once known**. It uses the final diagnosis as an explicit oracle and must be labelled as such. It is not an early-diagnosis condition.

## Endpoints (not finalized)

The endpoint is planning quality, **not** final-diagnosis accuracy. Candidates, to be finalized only after Phase 0:

- *Examination planning:* critical test coverage; unnecessary test burden; number of tests before an actionable decision; guideline concordance; cost-weighted investigation efficiency; blinded clinician rating.
- *Treatment planning:* appropriateness, completeness, safety, contraindication awareness, dose/intensity appropriateness, timing, personalization, guideline concordance, blinded clinician rating.

Each endpoint must pass G5 and G9. LLM-as-judge is supplementary only.

## Deliberately absent

No adaptive acquisition, value-of-information, closed-loop control, learned representation training, deployment interface, or governance layer. See [future_scope.md](future_scope.md).
