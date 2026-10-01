# Validity threats

Each threat lists how it would bias the bottleneck-versus-direct comparison and the relevant gate.

## 1. Hindsight contamination (G1, G7)

Input text written after *t* ("patient was found to have...", "post-op day 1") enters `S_t`. Both arms gain information, but the direct arm may exploit it more because it is not forced through a label vocabulary. This could produce a spurious bottleneck cost.

## 2. Discharge diagnosis leakage (G2, G7, G9)

`D_final` is treated as `D_t`, or appears in the input (diagnosis named in HPI, radiology impression, procedure name). An oracle-label bottleneck is unrealistically strong early in care, which can hide a real bottleneck cost. Leakage into the direct arm inflates it.

## 3. Treatment-response leakage (G1, G7)

Inputs reflect the response to treatment (post-operative findings, repeat labs after antibiotics). The state contains outcome information that the decision at *t* could not have had.

## 4. Note-version leakage (G1, G7)

Notes are amended, addended, or copied forward. A field that looks early may be a later version. Discharge-summary sections labelled "HPI" or "physical exam on admission" are written at discharge.

## 5. Observed treatment ≠ optimal treatment (G4, G11)

Recorded treatment is clinician behavior, shaped by practice variation, resources, and error. Matching it is not evidence of clinical superiority. A planner that matches observed care may simply imitate local habits.

## 6. Clinician documentation ≠ private reasoning (G2, G12)

A documented differential is a communication artifact, often written for billing, handoff, or medico-legal reasons. It is not the clinician's mental state. The study makes no claim about reconstructing mental states.

## 7. LLM-as-judge circularity (G9, G11)

An LLM judging LLM plans may share the planner's biases, prefer label-organized plans, or reward verbosity. The primary endpoint cannot be LLM-judged. Preferred hierarchy:

1. guideline-derived evaluation;
2. patient-specific actual treatment/procedure data as contextual grounding;
3. blinded clinician adjudication for a subset;
4. LLM-based evaluation only as supplementary or exploratory analysis.

## 8. Diagnosis timing ambiguity (G12)

Entry or documentation time is not formation time. A problem-list diagnosis may be entered hours after the clinician suspected it, or retrospectively. Using entry time as formation time misplaces `D_t` on the timeline.

## 9. Guideline generality vs patient-specific care (G5, G9)

If the reference plan is a disease-level guideline, the correct action is a function of the diagnosis, so the bottleneck is correct by construction whenever `D_t` is correct. Such a metric cannot detect a bottleneck cost. A valid metric needs patient-specific elements: contraindications, severity-dependent intensity, timing, comorbidity adjustments.

## 10. Sample attrition after temporal filtering (G6, G8)

Strict leakage exclusion may remove most cases, and not at random: complex, long, or atypical encounters may be more likely to be excluded. This reduces power and shifts the population toward simple cases, where a bottleneck cost is least likely. Report the attrition flow and compare excluded with retained cases.

## Additional threats noted during setup

- **Label vocabulary effect.** With four target diagnoses (MIMIC-CDM), the bottleneck is coarse. Results may not generalize to large vocabularies, and a four-way label is a weak test of "discrete disease labels" in general.
- **Capacity mismatch between arms.** If arms differ in prompt length, number of model calls, or compute, differences may reflect capacity rather than representation. The arms must be matched on base model and compute budget.
- **Prompt-format confound.** An LLM "bottleneck" enforced by prompting may leak `S_t` through free-text reasoning. The bottleneck must be enforced structurally: the planner receives only `D_t`.
