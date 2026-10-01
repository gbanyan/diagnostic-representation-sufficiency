# Measurement-process audit of X_3h (EXPLORATORY; interpretation only)

**Scope.** This file lists every X_3h element that encodes, fully or partly, *whether* or *how often* something was measured or investigated, rather than *what* the patient's value was.

**Everything listed was legitimately available by T = arrival + 3 h**, and nothing here is reclassified as leakage. The aim is to be explicit about how the confirmed incremental signal should be interpreted.

**Classes:**
- **Direct patient state:** a measured value of the patient.
- **Measurement-process signal:** mainly reflects clinician ordering, monitoring intensity, or documentation. It is information about the care process at T.
- **Mixed:** both.

| Variable(s) in X_3h | Count | Encodes | Class | Interpretation |
|---|---|---|---|---|
| Lab values (first result by T) | 84 | Analyzer value | Direct patient state | — |
| Lab abnormal flags (ABO/RH, antibody screen, WAM DIFTYP) | 3 | Qualitative result | Direct patient state (mostly empty) | Type-and-screen *being resulted* is a transfusion or procedure preparation signal (see indicators) |
| **Lab missing indicators** ("not resulted by T") | 87 | Whether each test was ordered **and** resulted within 3 h | **Measurement-process signal** | Reflects the clinician's choice of work-up and laboratory turnaround. Not a patient value |
| Numerics value summaries (first, last, min, max, median, slope) | 66 | Monitored physiology | Direct patient state | Monitor-derived values, e.g. HRV and perfusion index, are also patient state |
| **Numerics missing indicators** ("measure not observed by T") | 66 | Whether the patient was on a monitor, or had that parameter charted, by T | **Measurement-process signal** | Placement on continuous monitoring is a clinician decision |
| **Numerics counts** (per measure) | 11 | Number of observations by T | **Mixed** | Driven mainly by monitoring mode (minute-level monitor vs intermittent charting) and time on the monitor. It partly reflects instability, since unstable patients are charted more often |
| Triage vitals | 6 | Values at triage | Direct patient state | — |
| Triage vital missing indicators | 6 | Vital not recorded at triage | Measurement-process signal (documentation) | Rare |
| ESI (triage acuity) | 1 | Triage nurse's acuity category | **Mixed** | A clinician judgment of severity based on patient state. It is part of presenting context, not a raw physiologic value |
| ESI missing indicator | 1 | ESI not recorded | Measurement-process signal | Rare |
| Arrival mode (EMS, self, other) | 3 | How the patient arrived | Mixed | Partly a severity marker, partly social or logistic |
| Chief-complaint tokens | 91 | Presenting complaint(s) | Direct patient state (reported symptoms) | Recorded by the triage nurse |
| PMH CCS indicators | 175 | Documented prior conditions | Direct patient state (history) | Presence also depends on prior contact with the health system |
| PMH prior-code count | 1 | Number of distinct prior codes | **Mixed** | Comorbidity burden and documentation or utilization intensity |
| Age, sex | 4 | Demographics | Direct patient state | — |

**Not in X** (excluded by the preregistration, so they cannot contribute to the confirmed signal):
- orders of any kind (including imaging and consult orders);
- medication administrations; oxygen flow;
- imaging reports;
- rooming time;
- visit counts.

## Consequences for interpretation

1. **Share of X.** 160 of the 605 confirmatory model columns are missing indicators, plus 11 count columns. Together these are family **E** in the decomposition.
2. **Two possible sources.** If the incremental information is carried mainly by E, the confirmed result would indicate that the disease-label representation fails to preserve **severity or uncertainty signals already expressed in clinician behavior**, for example the decision to monitor or to send certain tests. The alternative source is that it fails to preserve raw physiology.
3. **Both readings stay within the permitted claim.** In either case, contemporaneous information outside the label is predictive of observed escalation. The decomposition refines *which kind* of information.
4. **Uncertainty in the attribution.** Many indicators are also correlated with the values they gate. A patient without lactate differs in both work-up and likely physiology. The decomposition therefore reports single-family and leave-one-out views together.
