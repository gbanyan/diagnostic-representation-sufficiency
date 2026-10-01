# Diagnostic representational capacity: results (EXPLORATORY)

**Plan:** [plan.md](plan.md), committed before running (`0e5879b`).

**Status:**
- **Exploratory, post-confirmatory.** The already-opened test set (6,570 visits, 212 ICU) is reused descriptively.
- 1,000-replicate patient-cluster bootstrap.
- **All seven ontologies are reported.**
- All encoder and downstream fits converged. Every new encoder selected C = 0.01, an interior value of the restricted grid.
- **The frozen confirmatory result (R2, 17.6%) is unchanged and is not replaced by anything here.**

**Source:** `results/capacity.json`. R1 and R2 reuse the frozen encoders and reproduce S2 (15.8%) and the primary (17.6%) through this code path.

## Soft D_hat (the legitimate 3 h representation)

| Ontology | Classes | Pooled share | Diagnostic information captured, bits (relative to prior) | Encoder top-1 | Model D log loss (bits) | Model D+X log loss (bits) | Δbits (95% CI) | Relative gain (95% CI) | AUROC D → D+X |
|---|---|---|---|---|---|---|---|---|---|
| R1_icd10_chapter | 23 | 0% | 1.01 (28.5%) | 0.448 | 0.1778 | 0.1498 | 0.0280 (0.0206–0.0347) | **15.8%** (11.9%–19.3%) | 0.807 → 0.870 |
| R2_ccsr_body_system | 20 | 0% | 1.06 (29.7%) | 0.448 | 0.1817 | 0.1498 | 0.0319 (0.0243–0.0393) | **17.6%** (13.7%–21.2%) | 0.787 → 0.870 |
| R3_ccsr_category_min300 | 52 | 39% | 1.75 (32.4%) | 0.329 | 0.1706 | 0.1500 | 0.0206 (0.0147–0.0268) | **12.0%** (8.7%–15.2%) | 0.821 → 0.867 |
| R4_ccsr_category_min100 | 94 | 18% | 1.96 (32.0%) | 0.292 | 0.1684 | 0.1523 | 0.0161 (0.0104–0.0221) | **9.6%** (6.4%–12.9%) | 0.829 → 0.863 |
| R5_ccsr_category_min50 | 127 | 11% | 2.07 (32.3%) | 0.293 | 0.1646 | 0.1513 | 0.0134 (0.0090–0.0178) | **8.1%** (5.7%–10.6%) | 0.842 → 0.868 |
| R6_icd10_3char_min100 | 92 | 32% | 1.90 (31.1%) | 0.279 | 0.1654 | 0.1495 | 0.0159 (0.0103–0.0215) | **9.6%** (6.5%–12.9%) | 0.842 → 0.871 |
| R7_icd10_3char_min50 | 154 | 18% | 2.10 (31.2%) | 0.271 | 0.1640 | 0.1489 | 0.0151 (0.0098–0.0204) | **9.2%** (6.2%–12.4%) | 0.846 → 0.874 |

## Hindsight label reference (NOT a 3 h representation; descriptive only)

Model D uses the **actual visit-diagnosis class** (one-hot).

**Caveat:** the visit diagnosis is assigned at or after disposition and may encode the disposition or ICU course. It is not available at 3 h.

| Ontology | Classes | Model D log loss | Model D+X log loss | Δbits (95% CI) | Relative gain (95% CI) | AUROC D → D+X |
|---|---|---|---|---|---|---|
| R2_ccsr_body_system | 20 | 0.1884 | 0.1424 | 0.0460 (0.0364–0.0555) | 24.4% (20.2%–28.3%) | 0.739 → 0.902 |
| R5_ccsr_category_min50 | 127 | 0.1594 | 0.1288 | 0.0306 (0.0225–0.0386) | 19.2% (14.8%–23.6%) | 0.832 → 0.918 |
| R7_icd10_3char_min50 | 154 | 0.1701 | 0.1378 | 0.0323 (0.0239–0.0404) | 19.0% (14.7%–23.1%) | 0.826 → 0.900 |

## Reading (descriptive, per the plan's rules)

1. **The residual shrinks materially with granularity** (interpretation A in the plan, at least in part).
   - **Size of the shrinkage:**

     | Ontology | Relative gain (95% CI) | Δbits |
     |---|---|---|
     | 20 CCSR body systems | 17.6% (13.7–21.2%) | 0.032 |
     | 52 CCSR categories | 12.0% | 0.021 |
     | 94 CCSR categories | 9.6% | 0.016 |
     | 127 CCSR categories | 8.1% (5.7–10.6%) | 0.013 |

   - **ICD-10 3-character groupings behave the same way:** 9.6% at 92 classes and 9.2% at 154.
   - **What closes the gap is a better Model D.** Its test log loss falls from 0.1817 to 0.1646 bits, and its AUROC rises from 0.787 to 0.842. Model D+X stays about the same (≈ 0.149–0.152 bits).
   - **The CIs of the finest representations lie largely or entirely below the 20-class estimate.** The coarse ontology accounts for roughly half of the confirmed residual.
2. **A residual remains at every granularity.**
   - The Δbits CI excludes 0 for every ontology.
   - At ≥ 94 classes, the point estimate is **below the 10% margin used in the confirmatory rule**. This is not a test; no threshold applies here.
3. **Why the shrinkage happens is ambiguous.** A finer soft posterior is a higher-dimensional summary of X: 126–153 probability columns, unpenalized in Model D. It can carry severity information that is correlated with diagnosis classes but not diagnostic in itself. The hindsight reference speaks to this.
   - **With the actual visit label** (no estimation error), the residual is **19–24%** at 20, 127, and 154 classes.
   - **This is larger than with the estimated D_hat.** At 127 classes, Model D with the true label reaches 0.159 bits, while D+X still gains 0.031 bits.
   - **Reading:** even perfectly known fine-grained disease labels leave substantial escalation-relevant information in X_3h. The shrinkage seen with fine soft D_hat partly reflects the posterior absorbing non-label information from X, not the labels themselves becoming sufficient.
   - **Uncertainty in this reading:** the hindsight label is not a 3 h quantity, and its relation to the disposition is unknown.
4. **Model D capacity caveat.** With up to 153 unpenalized columns, Model D could overfit. Its test log loss still improved with granularity, so overfitting did not dominate. The comparison is nonetheless not at equal parameter counts.

## Consequence for the empirical paper

- **The confirmed 17.6% is specific to the 20-class body-system representation.**
  - With the finest feasible disease-label posteriors (127–154 classes), the residual is about 8–9%. It is still clearly positive, but **below the prespecified substantive margin**.
- **The paper must report this curve prominently.** It answers the "your ontology is too coarse" threat, and the answer is: **partly yes**.
- **The defensible statement:**

  > The coarse disease-label representation did not retain all target-relevant information (confirmatory). Finer disease-label representations recovered roughly half of the residual, but a residual of about 0.013–0.016 bits per visit (8–10%) remained at the finest feasible granularity. With the actual visit labels, the residual was about 19%.
- **Diagnosis granularity and representation capacity are now central interpretive issues.** They are not footnotes.
