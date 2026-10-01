"""POST-HOC NUMERICAL ROBUSTNESS AUDIT of the frozen MIMIC T1 confirmatory analysis (600f368).

  PREFLIGHT_PRIVATE_DIR=... python -m audits.mimic_t1_solver_audit

Step 1 (diagnostic): re-run repeat 1 with the ORIGINAL L-BFGS solver, instrumented. For every fit
(inner tuning and outer final) record the scipy success flag and message, max |gradient| of the
preregistered objective, and the gap to the exact Newton optimum of the same objective.
Step 2 (robustness): the identical analysis (cohort, folds, seeds, features, preprocessing,
penalties, C grid, success rule) with the exact Newton solver for the same objective.
Aggregates only. The frozen results file is not touched.
"""

from pathlib import Path

import numpy as np
from scipy.special import expit

import src.confirmatory.target_sufficiency as TS
from src.confirmatory.partial_logistic import PartialLogistic, _penalty_weights
from src.mcmed.newton_logistic import NewtonPartialLogistic
from src.preflight.reporting import private_dir, write_json

OUT = Path(__file__).resolve().parent / "results"
LOG = []


def _grad_obj(Z, t, w, lam):
    z = Z @ w
    return np.abs(Z.T @ (expit(z) - t) + lam * w).max(), np.sum(np.logaddexp(0, z) - t * z) + 0.5 * np.sum(lam * w * w)


class InstrumentedLBFGS(PartialLogistic):
    """The original solver, unchanged; also records how close each fit is to the exact optimum."""

    def fit(self, Z, y, penalized, classes=None):
        super().fit(Z, y, penalized, classes)
        Z = np.asarray(Z, float)
        t = np.array([self.classes_.index(v) for v in y], float)
        lam = _penalty_weights(np.asarray(penalized, bool), self.C, self.eps)
        g, f = _grad_obj(Z, t, self.coef_, lam)
        ref = NewtonPartialLogistic(C=self.C, eps=self.eps).fit(Z, t, penalized)
        LOG.append({"C": self.C, "penalized_cols": int(np.sum(penalized)), "success": self.converged_,
                    "max_grad": float(g), "objective_gap": float(f - ref.objective_),
                    "max_pred_diff": float(np.abs(expit(Z @ self.coef_) - expit(Z @ ref.coef_)).max())})
        return self


class Newton:
    """Same objective, exact Newton solver; drop-in for PartialLogistic in the binary case."""

    def __init__(self, C=1.0, eps=1e-4, max_iter=100):
        self.m = NewtonPartialLogistic(C=C, eps=eps, max_iter=max_iter)

    def fit(self, Z, y, penalized, classes=None):
        self.classes_ = list(classes) if classes is not None else sorted(set(np.asarray(y).tolist()))
        t = np.array([self.classes_.index(v) for v in y], float)
        self.m.fit(Z, t, penalized)
        self.converged_, self.coef_ = self.m.converged_, self.m.coef_
        return self

    def predict_proba(self, Z):
        return self.m.predict_proba(Z)


def main():
    table = private_dir() / f"{TS.PRIMARY_TABLE}.csv"
    args = (table, "T1", 6, "green_only", "full", "X1", False)
    # Step 1: original solver, repeat 1 only (instrumented)
    TS.PartialLogistic = InstrumentedLBFGS
    seeds = TS.OUTER_SEEDS
    TS.OUTER_SEEDS = [seeds[0]]
    orig = TS.run(*args)
    diag = {"fits": len(LOG), "success_false": sum(not r["success"] for r in LOG),
            "max_grad_quantiles": np.quantile([r["max_grad"] for r in LOG], [0.5, 0.9, 0.99, 1.0]).tolist(),
            "objective_gap_max": max(r["objective_gap"] for r in LOG),
            "max_pred_diff_quantiles": np.quantile([r["max_pred_diff"] for r in LOG], [0.5, 0.9, 0.99, 1.0]).tolist(),
            "fits_with_pred_diff_gt_1e-3": sum(r["max_pred_diff"] > 1e-3 for r in LOG),
            "worst_fits": sorted(LOG, key=lambda r: -r["max_pred_diff"])[:5]}
    # Step 2: Newton, all three repeats, identical otherwise
    TS.OUTER_SEEDS = seeds
    TS.PartialLogistic = Newton
    newton = TS.run(*args)
    write_json(OUT, "mimic_t1_solver_audit", {
        "label": "POST-HOC NUMERICAL ROBUSTNESS AUDIT (not a new confirmation)",
        "step1_original_lbfgs_repeat1": {"diagnostics": diag, "repeat": orig["repeats"][0]},
        "step2_newton": {k: newton[k] for k in ("repeats", "across_repeats", "registered_success_criteria", "model_D_columns")}})


if __name__ == "__main__":
    main()
