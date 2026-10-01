# Diagnostic representational capacity: exploratory plan (fixed before any modeling)

**EXPLORATORY.** Post-confirmatory, written 2026-10-01 after the MC-MED primary result was seen. It **cannot replace or modify the frozen primary result**, which remains the CCSR body-system soft D_hat, 17.6%.

- **No success thresholds.**
- **Every ontology run is reported,** whatever its result.
- **No ontology is selected by the ICU outcome.**

**Reviewer threat addressed.** The primary disease-label space (20 CCSR body systems) is coarse. Does the residual information I(Y; X | D_hat) shrink materially when the disease-label representation is finer?

## Ontologies (from the counts-only audit `results/ontology_audit.json`)

Chosen on semantics and sample adequacy. Every class has ≥ 30 development visits, so a 5-fold cross-fitted multinomial encoder is feasible.

| ID | Ontology | Classes | Pooled share | Source of D_hat |
|---|---|---|---|---|
| R1 | ICD-10 chapter | 23 | 0.1% | frozen S2 encoder (reused, read-only) |
| R2 | CCSR body system (**frozen primary**) | 20 | 0.1% | frozen primary encoder (reused, read-only) |
| R3 | CCSR category, ≥ 300 visits (rest pooled within body system) | 52 | 39% | new |
| R4 | CCSR category, ≥ 100 | 94 | 18% | new |
| R5 | CCSR category, ≥ 50 (finest CCSR) | 127 | 11% | new |
| R6 | ICD-10 3-character, ≥ 100 (rest pooled within chapter) | 92 | 32% | new |
| R7 | ICD-10 3-character, ≥ 50 (finest ICD) | 154 | 18% | new |

**Pooling rule.** Pooled groups with < 50 visits go to a global OTHER, the same rule as the frozen primary.

## Procedure per ontology (identical to the frozen pipeline except where stated)

1. **Encoder.**
   - Multinomial L2 logistic regression on X_3h;
   - 5-fold patient-grouped cross-fitting in development (seed 20261001) with an inner 4-fold CV;
   - final encoder fit on all development data → test D_hat;
   - selection by diagnosis log loss only.
   - **Deviation for runtime:** the encoder C grid is restricted to {1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3}. Every frozen encoder chose C = 0.003. If 0.3 is selected, that is reported as an edge selection.
2. **Encoder quality.** OOF log loss vs class prior (bits of diagnostic information captured), top-1 accuracy, macro-F1.
3. **Downstream.** Model D (soft D_hat, K − 1 columns, reference = largest development class; season; unpenalized, ε = 1e-4) versus Model D+X (L2 on the frozen X).
   - Tuning: the full frozen C grid, 4-fold development CV, exact Newton solver.
   - Evaluation on the already-opened test set (descriptive), with a 1,000-replicate patient-cluster bootstrap (seed 20261006).
4. **Reported:**
   - Model D test log loss;
   - Δbits;
   - relative gain with CI;
   - AUROC;
   - the encoder's diagnostic information;
   - number of classes.

**Hindsight label reference** (descriptive only, **not** a legitimate 3 h representation):
- For R2, R5, and R7, Model D uses the **actual visit-diagnosis class** (one-hot, K − 1) instead of D_hat.
- **Caveat:** the visit diagnosis is assigned at or after disposition and may encode the disposition itself.
- The reference shows how much residual would remain even if the final label of that granularity were known. It is **not** a sufficiency estimate.

**Capacity curve.** Residual Δbits (and relative gain) against:
- (a) number of classes;
- (b) diagnostic information captured by the encoder (prior log loss − OOF log loss, bits).

The soft-D_hat and hindsight points are plotted separately.

## Interpretation rules (fixed now)

- **A.** If the residual shrinks materially as granularity increases, part of the insufficiency reflects diagnostic resolution.
- **B.** If it stays substantial at 127–154 classes, escalation-relevant state is not captured by finer disease labels in this setting.
- **No preference.** Neither outcome is preferred. "Materially" is described with the CIs, not with a threshold.
- **Model D capacity caveat.** With K − 1 up to 153 unpenalized columns, Model D may overfit in development (897 events). Its test log loss is reported so that this is visible. The D block is kept unpenalized, as in the frozen design.
- **Not done:** no stronger encoder families (boosting, neural, LLM) and no further ontologies are added after results are seen.
