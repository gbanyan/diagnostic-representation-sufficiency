"""Exact Newton solver for the preregistered partial-penalty binary logistic objective (amendment 1).

Objective (identical to src/confirmatory/partial_logistic.py, preregistration section 19):

    sum_i NLL_i + 1/(2C) * ||w_penalized||^2 + eps/2 * ||w_unpenalized_nonintercept||^2

Column 0 is the intercept (unpenalized). Newton steps use the exact Hessian with a backtracking
(Armijo) line search; convergence = max |gradient| < GTOL. The problem is strictly convex, so
the solution is the unique optimum that L-BFGS failed to reach on the MC-MED design (near-collinear
soft D_hat columns plus ~600 penalized columns).
"""

import numpy as np
from scipy.special import expit

from src.confirmatory.partial_logistic import EPS, _penalty_weights

GTOL = 1e-6


class NewtonPartialLogistic:
    def __init__(self, C=1.0, eps=EPS, max_iter=100):
        self.C, self.eps, self.max_iter = C, eps, max_iter

    def fit(self, Z, y, penalized, classes=(0, 1)):
        Z = np.asarray(Z, float)
        t = np.asarray(y, float)
        lam = _penalty_weights(np.asarray(penalized, bool), self.C, self.eps)
        w = np.zeros(Z.shape[1])

        def obj(w):
            z = Z @ w
            return np.sum(np.logaddexp(0, z) - t * z) + 0.5 * np.sum(lam * w * w)
        f = obj(w)
        for self.n_iter_ in range(1, self.max_iter + 1):
            p = expit(Z @ w)
            g = Z.T @ (p - t) + lam * w
            if np.abs(g).max() < GTOL:
                break
            H = (Z * (p * (1 - p))[:, None]).T @ Z
            H[np.diag_indices_from(H)] += lam
            step = np.linalg.solve(H, g)
            s = 1.0
            while True:
                fn = obj(w - s * step)
                if fn <= f - 1e-4 * s * (g @ step) or s < 1e-12:
                    break
                s /= 2
            w, f = w - s * step, fn
        p = expit(Z @ w)
        self.max_grad_ = float(np.abs(Z.T @ (p - t) + lam * w).max())
        self.converged_ = self.max_grad_ < GTOL
        self.coef_, self.objective_, self.classes_ = w, f, list(classes)
        return self

    def predict_proba(self, Z):
        p1 = expit(np.asarray(Z, float) @ self.coef_)
        return np.column_stack([1 - p1, p1])
