"""Validation tests required by preregistration section J (synthetic data only).

1. Fully penalized (all non-intercept columns) -> matches scikit-learn LogisticRegression.
2. C -> infinity -> matches the unpenalized maximum-likelihood fit.
3. C -> 0 -> penalized coefficients -> 0 and predictions equal Model_D (fit without X).
Plus: the multinomial case matches scikit-learn, and unpenalized blocks are unaffected by C.
"""

import unittest
import warnings

import numpy as np
from sklearn.linear_model import LogisticRegression

from src.confirmatory.partial_logistic import PartialLogistic


def data(n=600, seed=0, k=2):
    rng = np.random.default_rng(seed)
    D = np.eye(4)[rng.integers(0, 4, n)][:, 1:]           # 3 non-reference diagnosis columns
    X = rng.normal(size=(n, 5))
    logits = D @ np.array([1.0, -1.0, 0.5]) + X @ np.array([0.8, -0.5, 0.0, 0.3, 0.0])
    if k == 2:
        y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logits))).astype(int)
    else:
        y = np.digitize(logits + rng.normal(scale=0.5, size=n), [-0.5, 0.5])
    Z = np.column_stack([np.ones(n), D, X])
    pen = np.array([False] * 4 + [True] * 5)
    return Z, y, pen


class PartialLogisticValidation(unittest.TestCase):
    def test_1_fully_penalized_matches_sklearn(self):
        Z, y, _ = data()
        allpen = np.array([False] + [True] * (Z.shape[1] - 1))
        for C in (0.03, 0.5, 5.0):
            ours = PartialLogistic(C=C).fit(Z, y, allpen).predict_proba(Z)[:, 1]
            sk = LogisticRegression(C=C, max_iter=20000, tol=1e-10).fit(Z[:, 1:], y).predict_proba(Z[:, 1:])[:, 1]
            self.assertLess(np.abs(ours - sk).max(), 1e-4, f"C={C}")

    def test_2_large_C_equals_unpenalized_mle(self):
        Z, y, pen = data()
        ours = PartialLogistic(C=1e8, eps=0.0).fit(Z, y, pen).predict_proba(Z)[:, 1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mle = LogisticRegression(C=1e10, max_iter=20000, tol=1e-12).fit(Z[:, 1:], y).predict_proba(Z[:, 1:])[:, 1]
        self.assertLess(np.abs(ours - mle).max(), 1e-3)

    def test_3_small_C_recovers_model_D(self):
        Z, y, pen = data()
        m = PartialLogistic(C=1e-8).fit(Z, y, pen)
        self.assertLess(np.abs(m.coef_[pen]).max(), 1e-5)
        mD = PartialLogistic(C=1.0).fit(Z[:, ~pen], y, pen[~pen])
        self.assertLess(np.abs(m.predict_proba(Z)[:, 1] - mD.predict_proba(Z[:, ~pen])[:, 1]).max(), 1e-4)

    def test_unpenalized_block_not_shrunk(self):
        Z, y, pen = data()
        strong = PartialLogistic(C=1e-6).fit(Z, y, pen)
        mD = PartialLogistic(C=1.0).fit(Z[:, ~pen], y, pen[~pen])
        np.testing.assert_allclose(strong.coef_[~pen], mD.coef_, atol=1e-3)  # D effects keep full size

    def test_multinomial_fully_penalized_matches_sklearn(self):
        Z, y, _ = data(k=3)
        allpen = np.array([False] + [True] * (Z.shape[1] - 1))
        ours = PartialLogistic(C=0.5).fit(Z, y, allpen, classes=[0, 1, 2]).predict_proba(Z)
        sk = LogisticRegression(C=0.5, max_iter=20000, tol=1e-10).fit(Z[:, 1:], y).predict_proba(Z[:, 1:])
        self.assertLess(np.abs(ours - sk).max(), 1e-4)

    def test_converges(self):
        Z, y, pen = data()
        self.assertTrue(PartialLogistic(C=0.1).fit(Z, y, pen).converged_)


if __name__ == "__main__":
    unittest.main()
