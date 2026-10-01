"""MC-MED confirmatory pipeline helpers (synthetic data only)."""

import math
import unittest

import numpy as np

from src.mcmed import metrics
from src.mcmed.features import lab_flag, lab_value, summarize
from src.mcmed.split import assign


class Split(unittest.TestCase):
    def test_deterministic_and_fraction(self):
        a = [assign(str(i), "salt", 0.2) for i in range(20000)]
        self.assertEqual(a, [assign(str(i), "salt", 0.2) for i in range(20000)])
        self.assertAlmostEqual(a.count("test") / len(a), 0.2, delta=0.01)
        self.assertNotEqual(a, [assign(str(i), "other", 0.2) for i in range(20000)])


class Numerics(unittest.TestCase):
    def test_summaries(self):
        s = summarize(np.array([2.0, 0.0, 1.0]), np.array([30.0, 10.0, 20.0]))
        self.assertEqual((s["first"], s["last"], s["min"], s["max"], s["median"], s["count"]), (10, 30, 10, 30, 20, 3))
        self.assertAlmostEqual(s["slope_per_hour"], 10.0)

    def test_single_observation_slope_undefined(self):
        s = summarize(np.array([1.0]), np.array([5.0]))
        self.assertTrue(math.isnan(s["slope_per_hour"]))
        self.assertEqual(s["count"], 1)


class Labs(unittest.TestCase):
    def test_censored_and_flags(self):
        self.assertEqual(lab_value("<0.01"), 0.01)
        self.assertEqual(lab_value(">=500"), 500)
        self.assertTrue(math.isnan(lab_value("Negative")))
        self.assertEqual((lab_flag("Normal"), lab_flag("Abnormal High"), lab_flag("Critical")), (0.0, 1.0, 1.0))
        self.assertTrue(math.isnan(lab_flag("")))


class Metrics(unittest.TestCase):
    def test_summary_and_bootstrap(self):
        rng = np.random.default_rng(0)
        n = 3000
        x = rng.normal(size=n)
        y = (rng.uniform(size=n) < 1 / (1 + np.exp(-(x - 2)))).astype(int)
        pD = np.full(n, y.mean())
        pDX = 1 / (1 + np.exp(-(x - 2)))
        s = metrics.summary(y, pD, pDX)
        self.assertGreater(s["delta_L_nats"], 0)
        self.assertAlmostEqual(s["delta_bits"], s["delta_L_nats"] / math.log(2))
        self.assertAlmostEqual(s["relative_gain"], s["delta_L_nats"] / s["L_D_nats"])
        self.assertAlmostEqual(s["calibration_DX"]["slope"], 1.0, delta=0.25)
        ci = metrics.bootstrap(y, pD, pDX, np.arange(n) // 2, 200, 1)
        self.assertLess(ci["delta_L_nats"]["lo"], s["delta_L_nats"])
        self.assertGreater(ci["delta_L_nats"]["hi"], s["delta_L_nats"])


if __name__ == "__main__":
    unittest.main()


class NewtonSolver(unittest.TestCase):
    """Amendment 1: the Newton solver optimizes the same objective as PartialLogistic."""

    def test_matches_partial_logistic_and_sklearn(self):
        from sklearn.linear_model import LogisticRegression
        from src.confirmatory.partial_logistic import PartialLogistic
        from src.mcmed.newton_logistic import NewtonPartialLogistic
        from tests.test_partial_logistic import data
        Z, y, pen = data()
        for C in (0.01, 1.0, 100.0):
            a = NewtonPartialLogistic(C=C).fit(Z, y, pen)
            b = PartialLogistic(C=C).fit(Z, y, pen)
            self.assertTrue(a.converged_)
            np.testing.assert_allclose(a.predict_proba(Z), b.predict_proba(Z), atol=1e-5)
        allpen = np.array([False] + [True] * (Z.shape[1] - 1))
        a = NewtonPartialLogistic(C=0.5).fit(Z, y, allpen).predict_proba(Z)[:, 1]
        sk = LogisticRegression(C=0.5, max_iter=20000, tol=1e-10).fit(Z[:, 1:], y).predict_proba(Z[:, 1:])[:, 1]
        self.assertLess(np.abs(a - sk).max(), 1e-5)

    def test_small_C_recovers_model_D(self):
        from src.mcmed.newton_logistic import NewtonPartialLogistic
        from tests.test_partial_logistic import data
        Z, y, pen = data()
        m = NewtonPartialLogistic(C=1e-8).fit(Z, y, pen)
        mD = NewtonPartialLogistic(C=1.0).fit(Z[:, ~pen], y, pen[~pen])
        self.assertLess(np.abs(m.predict_proba(Z) - mD.predict_proba(Z[:, ~pen])).max(), 1e-5)
