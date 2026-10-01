"""End-to-end tests of the confirmatory runner on synthetic data (no patient data)."""

import csv
import math
import random
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.confirmatory import target_sufficiency as ts
from src.preflight import targets

D_LEVELS = ["appendicitis", "cholecystitis", "diverticulitis", "pancreatitis"]


def synthetic_table(path, n=480, seed=2):
    """T3 depends on heart rate within D; T2 (reused as a null column) is noise. Era shifts base rates."""
    rng = random.Random(seed)
    cols = ["hadm_id", "subject_id", "D", "cohort_L6", "icu_before_L6", "Y_T3_icu_L6", "anchor_time",
            "anchor_year_group"] + targets.feature_sets(6)["X1"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(n):
            d = D_LEVELS[i % 4]
            era = ts.ERAS[(i // 4) % 4]
            hr = rng.gauss(90, 15)
            logit = -1.0 + 0.4 * ts.ERAS.index(era) + 0.09 * (hr - 90)
            row = {c: "" for c in cols}
            row.update({"hadm_id": i, "subject_id": i, "D": d, "cohort_L6": 1, "icu_before_L6": 0,
                        "Y_T3_icu_L6": int(rng.random() < 1 / (1 + math.exp(-logit))),
                        "anchor_time": str(datetime(2150, 1, 1) + timedelta(hours=7 * i)),
                        "anchor_year_group": era, "triage_heartrate": hr, "age": rng.gauss(50, 15)})
            w.writerow(row)


class ContextTest(unittest.TestCase):
    def test_context_columns(self):
        rows = [{"D": d, "anchor_year_group": e, "anchor_time": "2150-01-04 23:00:00"}
                for d in D_LEVELS for e in ts.ERAS]
        C, names = ts.context_matrix(rows, D_LEVELS, "full")
        self.assertEqual(C.shape[1], 3 + 9 + 2 + 1)
        self.assertEqual(ts.context_matrix(rows, D_LEVELS, "era_main")[0].shape[1], 3 + 2 + 1)
        self.assertEqual(ts.context_matrix(rows, D_LEVELS, "no_era")[0].shape[1], 2 + 1)
        self.assertEqual(ts.tod_block(datetime(2150, 1, 1, 7)), "night")
        self.assertEqual(ts.tod_block(datetime(2150, 1, 1, 16)), "evening")


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.table = Path(cls.tmp.name) / "mimic_cdm_landmark_table.csv"
        synthetic_table(cls.table)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_detects_signal_and_reports_criteria(self):
        res = ts.run(self.table, "T3", 6, "green_only", "full", "X1", False)
        a = res["across_repeats"]
        self.assertGreater(a["delta"]["mean"], 0.02)
        self.assertEqual(len(res["repeats"]), 3)
        self.assertEqual(len(res["repeats"][0]["selected_C_DX"]), 5)
        self.assertIn("success", res["registered_success_criteria"])
        self.assertTrue(all(r["converged"] for r in res["repeats"]))
        self.assertEqual(res["repeats"][0]["bootstrap_ci"]["resamples"], ts.N_BOOT)

    def test_temporal_holdout(self):
        res = ts.run(self.table, "T3", 6, "green_only", "full", "X1", True)["temporal_holdout"]
        self.assertEqual(res["test_n"], 120)
        self.assertEqual(res["train_n"], 360)
        self.assertIn("recalibrated", res)


if __name__ == "__main__":
    unittest.main()
