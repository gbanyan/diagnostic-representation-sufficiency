# Amendment 1: author decision

**Date:** 2026-10-01.

**Decision.** The author **accepts Amendment 1** as part of the study record.

**How it must continue to be described:**
> a documented pre-test protocol amendment that deviated from the preregistered stop rule.

**Not permitted:**
- removing it;
- describing the preregistration as perfectly untouched;
- describing it as post-result model switching.

**Unchanged:** the frozen primary conclusion (MC-MED: SUPPORTED, 17.6%).

**Corroboration (post-hoc).** The MIMIC T1 solver audit ([../../audits/mimic_t1_solver_audit.md](../../audits/mimic_t1_solver_audit.md)) found that the original L-BFGS fits converged and that the Newton solver reproduces T1 exactly. This supports the claim that the solver change does not alter the estimator where the original optimizer converged.

**Records:** [amendment_1_final.md](amendment_1_final.md), [2026-10-01-newton-solver.md](2026-10-01-newton-solver.md).
