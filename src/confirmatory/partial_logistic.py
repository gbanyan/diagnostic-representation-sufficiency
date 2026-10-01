"""Partially penalized logistic / multinomial regression (preregistration section J).

Objective (scikit-learn parameterization, so the C grid means the same thing):

    sum_i NLL_i  +  1/(2C) * ||w_penalized||^2  +  eps/2 * ||w_unpenalized_nonintercept||^2

Column 0 of Z must be the intercept (never penalized, no eps). `penalized` is a boolean mask
over the columns of Z. eps (1e-4) is a fixed numerical-stability ridge on unpenalized
coefficients, identical in every model. Binary targets use one coefficient vector;
multinomial targets use one vector per class (softmax), as in scikit-learn.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, log_softmax

EPS = 1e-4


def _penalty_weights(penalized, C, eps):
    w = np.where(penalized, 1.0 / C, eps).astype(float)
    w[0] = 0.0  # intercept
    return w


class PartialLogistic:
    def __init__(self, C=1.0, eps=EPS, max_iter=10000):
        self.C, self.eps, self.max_iter = C, eps, max_iter

    def fit(self, Z, y, penalized, classes=None):
        Z = np.asarray(Z, float)
        self.classes_ = list(classes) if classes is not None else sorted(set(np.asarray(y).tolist()))
        k = len(self.classes_)
        lam = _penalty_weights(np.asarray(penalized, bool), self.C, self.eps)
        n, p = Z.shape
        if k == 2:
            t = np.array([self.classes_.index(v) for v in y], float)

            def f(w):
                z = Z @ w
                nll = np.sum(np.logaddexp(0, z) - t * z)
                g = Z.T @ (expit(z) - t) + lam * w
                return nll + 0.5 * np.sum(lam * w * w), g
            w0 = np.zeros(p)
        else:
            T = np.zeros((n, k))
            T[np.arange(n), [self.classes_.index(v) for v in y]] = 1.0

            def f(wflat):
                W = wflat.reshape(p, k)
                L = log_softmax(Z @ W, axis=1)
                nll = -np.sum(T * L)
                G = Z.T @ (np.exp(L) - T) + lam[:, None] * W
                return nll + 0.5 * np.sum(lam[:, None] * W * W), G.ravel()
            w0 = np.zeros(p * k)
        res = minimize(f, w0, jac=True, method="L-BFGS-B",
                       options={"maxiter": self.max_iter, "gtol": 1e-8, "ftol": 1e-12})
        self.converged_ = bool(res.success)
        self.coef_ = res.x if k == 2 else res.x.reshape(p, k)
        return self

    def predict_proba(self, Z):
        Z = np.asarray(Z, float)
        if len(self.classes_) == 2:
            p1 = expit(Z @ self.coef_)
            return np.column_stack([1 - p1, p1])
        return np.exp(log_softmax(Z @ self.coef_, axis=1))
