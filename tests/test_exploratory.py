"""Tests for the exploratory T1 module (synthetic data only)."""

import random
import unittest
from datetime import datetime, timedelta

import numpy as np

from src.confirmatory import target_sufficiency as ts
from src.exploratory import t1_heterogeneity as eh
from src.preflight import targets


class SubtypeRegexTest(unittest.TestCase):
    def test_titles(self):
        c = lambda t: bool(eh.COMPLICATED.search(t))
        self.assertTrue(c("Acute appendicitis with generalized peritonitis"))
        self.assertFalse(c("Acute appendicitis without mention of peritonitis"))
        self.assertTrue(c("Diverticulitis of large intestine with perforation and abscess without bleeding"))
        self.assertFalse(c("Diverticulitis of large intestine without perforation or abscess with bleeding"))
        self.assertFalse(c("Calculus of gallbladder with acute cholecystitis, without mention of obstruction"))
        self.assertTrue(c("Calculus of gallbladder with acute cholecystitis with obstruction"))
        self.assertTrue(c("Biliary acute pancreatitis with infected necrosis"))
        self.assertFalse(c("Acute pancreatitis"))


class ConfigTest(unittest.TestCase):
    def test_configs_and_groups(self):
        cf = eh.configs()
        self.assertEqual(sum(k.startswith("fx_") for k in cf), 12)
        self.assertEqual(eh.group_features("labs_inflammatory", 6)[0], "lab_wbc_L6")
        self.assertEqual(eh.group_features("triage", 6), targets.TRIAGE)
        x1 = set(targets.feature_sets(6)["X1"])
        for g in eh.GROUPS:
            self.assertTrue(set(eh.group_features(g, 6)) <= x1, g)
        self.assertEqual(sum(len(eh.group_features(g, 6)) for g in eh.GROUPS), len(x1))


class RunConfigTest(unittest.TestCase):
    def test_signal_detected_across_specs(self):
        rng = random.Random(5)
        D = ["appendicitis", "cholecystitis", "diverticulitis", "pancreatitis"]
        rows, y = [], []
        for i in range(400):
            d, hr = D[i % 4], rng.gauss(90, 15)
            rows.append({"hadm_id": str(i), "subject_id": str(i), "D": d, "anchor_year_group": ts.ERAS[(i // 4) % 4],
                         "anchor_time": str(datetime(2150, 1, 1) + timedelta(hours=5 * i)),
                         "triage_heartrate": hr, "age": rng.gauss(50, 10)})
            y.append(int(rng.random() < 1 / (1 + np.exp(-0.1 * (hr - 90)))))
        y = np.array(y)
        feats = ["triage_heartrate", "age"]
        for name in ("conf", "fx_I1_none_shared", "missing_only", "values_only"):
            PD, PDX, groups = eh.run_config(rows, y, eh.configs()[name], feats, D, None)
            out = eh.describe(rows, y, PD, PDX, groups)
            if name == "missing_only":   # no missingness in synthetic data -> no information
                self.assertLess(out["delta"], 0.02, name)
            else:
                self.assertGreater(out["delta"], 0.05, name)


if __name__ == "__main__":
    unittest.main()
