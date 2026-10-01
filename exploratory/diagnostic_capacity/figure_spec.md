# Figure specification: diagnostic-capacity curve (EXPLORATORY)

**Status.** A specification only. No graphic has been produced yet. Data come from `results/capacity.json` (aggregate).

**Caption must begin:** "Exploratory, post-hoc analysis (after the confirmatory result); test set reused descriptively."

## Panel A: primary capacity curve (CCSR family only)

**Points:** CCSR body system (20 classes; frozen confirmatory representation, marked as such) and CCSR categories at 52, 94, and 127 classes.
- **Why CCSR only:** the ontology semantics are comparable within one hierarchy (the same body system → category refinement).

**Axes:**
- **x:** number of diagnostic classes, on a log scale.
  - **Alternative x (secondary panel or table column):** the entropy of the class distribution (3.55 / 5.41 / 6.14 / 6.41 bits; robustly estimable from counts).
  - **Not used:** the encoder's captured diagnostic information. It depends on the encoder and mixes representation capacity with estimation quality.
- **y:** residual relative log-loss gain of Model D+X over Model D, (CE_D − CE_DX) / CE_D, with 95% patient-cluster bootstrap CIs.

**Markers and annotations:**
- The 20-class point carries a distinct marker labelled "confirmatory (prespecified)". The others are labelled "exploratory".
- A dashed horizontal line at 10% is labelled "margin prespecified for the confirmatory 20-class representation only". It is a reference, not a test for the other points.
- **No fitted line or extrapolation.** Points are connected only by a light line within the CCSR family, if at all.

**Companion (table or small panel B):**
- Δbits with CIs;
- Model D and Model D+X log loss per point, showing that Model D improves while Model D+X is roughly flat.

## Panel C (separate): cross-ontology robustness points

- **Points:** ICD-10 chapter (23 classes), ICD-10 3-character (92 and 154 classes).
- **Presentation:** a separate panel, or offset markers with a legend "different ontology family". They are **not** placed on the CCSR curve.

## Optional inset: hindsight label reference

- **Points:** the actual visit-diagnosis class at 20 / 127 / 154 classes.
- **Marker and label:** a hollow marker, labelled "not available at 3 h; may encode disposition".
- **Placement:** kept visually separate from the D_hat curves.

## Wording constraints

- **Number of classes** is described as *diagnostic resolution*, not as a pure or causal measure of representational capacity. A finer soft posterior is also a higher-dimensional summary of X, so it can carry non-label information (see the "There Was Never a Bottleneck in CBMs" leakage argument).
- **Required statements:**
  - "The residual gap decreased as diagnostic representations became more granular."
  - "This exploratory pattern suggests that part of the observed information loss is attributable to diagnostic resolution."
- **Forbidden statements:**
  - "finer ontologies are sufficient";
  - "confirmed sufficient below 10%".
