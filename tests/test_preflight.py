"""Tests for src.preflight on synthetic data (no patient data)."""

import csv
import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from src.preflight import leakage_checks, schemas, simple_incremental_models as sim, targets
from src.preflight.target_heterogeneity import entropy_bits, stage_a
from tests.test_cdm_audit import FRAMEWORK, make_cdm, write_csv


def synthetic_table(path, n=800, seed=1):
    """Two diagnoses; Y_T2 depends on triage_heartrate within D; Y_T3 is pure noise."""
    rng = random.Random(seed)
    cols = (["hadm_id", "subject_id", "D", "cohort_L6", "icu_before_L6", "Y_T2_pacu_L6", "Y_T3_icu_L6"]
            + targets.feature_sets(6)["X2"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i in range(n):
            d = "appendicitis" if i % 2 else "pancreatitis"
            hr = rng.gauss(90, 15)
            base = 1.5 if d == "appendicitis" else -1.0
            p = 1 / (1 + math.exp(-(base + 0.12 * (hr - 90))))
            row = {c: "" for c in cols}
            row.update({"hadm_id": i, "subject_id": i // 2 if i < 100 else i, "D": d, "cohort_L6": 1,
                        "icu_before_L6": 0, "Y_T2_pacu_L6": int(rng.random() < p),
                        "Y_T3_icu_L6": int(rng.random() < 0.3), "triage_heartrate": hr,
                        "age": rng.gauss(50, 15), "female": rng.randint(0, 1)})
            w.writerow(row)


class StageATest(unittest.TestCase):
    def test_entropy(self):
        self.assertAlmostEqual(entropy_bits({0: 5, 1: 5}), 1.0)
        self.assertEqual(entropy_bits({1: 10}), 0.0)

    def test_deterministic_flag(self):
        pairs = [({"D": "a"}, 1)] * 50 + [({"D": "b"}, 0)] * 50
        res = stage_a(pairs, "binary")
        self.assertTrue(res["near_deterministic_given_D"])
        self.assertAlmostEqual(res["I_Y_D_bits"], 1.0)

    def test_continuous(self):
        pairs = [({"D": "a"}, float(x)) for x in range(10)] + [({"D": "b"}, float(x + 100)) for x in range(10)]
        res = stage_a(pairs, "continuous")
        self.assertGreater(res["share_variance_explained_by_D"], 0.95)


class StageBTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.table = Path(cls.tmp.name) / "t.csv"
        synthetic_table(cls.table)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_detects_within_d_signal(self):
        res = sim.run(self.table, "T2", 6, ["X0"])
        fs = res["feature_sets"]["X0"]
        self.assertGreater(fs["overall"]["delta_loss"], 0.05)
        self.assertGreater(fs["ci95"]["overall.delta_loss"][0], 0)
        self.assertGreater(fs["D=appendicitis"]["delta_auroc"], 0.2)

    def test_null_target_has_ci_covering_zero(self):
        res = sim.run(self.table, "T3", 6, ["X0"])
        lo, hi = res["feature_sets"]["X0"]["ci95"]["overall.delta_loss"]
        self.assertLessEqual(lo, 0.0)
        self.assertLess(res["feature_sets"]["X0"]["overall"]["delta_loss"], 0.02)

    def test_extreme_values_are_contained(self):
        import numpy as np
        Xtr = np.array([[120.0], [130.0], [125.0], [19734.0]] * 10)
        Xte = np.array([[1e6]])
        Atr, Ate = sim.fit_transform_x(Xtr, Xte)
        self.assertLessEqual(np.abs(Atr).max(), sim.CLIP_Z)
        self.assertLessEqual(np.abs(Ate).max(), sim.CLIP_Z)
        self.assertEqual(sim.log_columns(["age", "lab_lipase_L6", "prior_admissions"]), [1, 2])

    def test_nested_cv_detects_signal_and_null(self):
        res = sim.run(self.table, "T2", 6, ["X0"], nested=True)
        fs = res["feature_sets"]["X0"]
        self.assertGreater(fs["across_repeats"]["delta_loss"]["mean"], 0.05)
        self.assertEqual(len(fs["repeats"]), 3)
        self.assertEqual(len(fs["repeats"][0]["selected_C"]["DX"]), 5)
        self.assertTrue(all(c in sim.C_GRID for c in fs["repeats"][0]["selected_C"]["D"]))
        self.assertIn("slope", fs["repeats"][0]["calibration_DX"])
        null = sim.run(self.table, "T3", 6, ["X0"], nested=True)["feature_sets"]["X0"]
        self.assertLess(null["across_repeats"]["delta_loss"]["mean"], 0.01)

    def test_d_scale_only_touches_main_effects(self):
        import numpy as np
        D = np.array([[1.0, 0.0], [0.0, 1.0]] * 5)
        X = np.arange(10, dtype=float).reshape(-1, 1)
        idx = np.arange(10)
        try:
            sim.D_SCALE = 100.0
            Ztr, _ = sim._design_for(D, X, idx, idx, ["age"], True)
        finally:
            sim.D_SCALE = 1.0
        self.assertEqual(Ztr[0, 0], 100.0)                       # D main effect scaled
        self.assertTrue(set(np.unique(Ztr[:, 0])) <= {0.0, 100.0})
        Z1, _ = sim._design_for(D, X, idx, idx, ["age"], True)
        np.testing.assert_allclose(Ztr[:, 2:], Z1[:, 2:])         # X and X*D unchanged

    def test_calibration_of_perfectly_calibrated_predictions(self):
        import numpy as np
        rng = np.random.default_rng(0)
        p = rng.uniform(0.05, 0.95, 20000)
        y = (rng.uniform(size=p.size) < p).astype(int)
        cal = sim.calibration(y, p)
        self.assertAlmostEqual(cal["slope"], 1.0, delta=0.1)
        self.assertLess(cal["ece"], 0.02)

    def test_temporal_validation_split(self):
        import csv as _csv
        rows = list(_csv.DictReader(open(self.table)))
        for i, r in enumerate(rows):
            r["anchor_year_group"] = "2014 - 2016" if i % 3 else "2020 - 2022"
        import numpy as np
        y = np.array([int(float(r["Y_T2_pacu_L6"])) for r in rows])
        res = sim.temporal_validate(rows, y, "binary", [0, 1], ["triage_heartrate"], sorted({r["D"] for r in rows}))
        self.assertEqual(res["test_n"], len(rows) // 3 + (1 if len(rows) % 3 else 0))
        self.assertGreater(res["overall"]["delta_loss"], 0.02)

    def test_examination_target_refused(self):
        with self.assertRaises(SystemExit):
            sim.run(self.table, "T6", 6, ["X0"])


class TimingFilterTest(unittest.TestCase):
    def test_filter_keeps_allowed_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "mimic_cdm_landmark_table.csv"
            write_csv(Path(tmp) / "t1_timing_classes.csv", ["hadm_id", "timing_class_L6"],
                      [[1, "GREEN"], [2, "YELLOW"], [3, "RED"]])
            pairs = [({"hadm_id": str(i)}, 1) for i in (1, 2, 3, 4)]
            kept, info = sim.apply_timing_filter(pairs, table, 6, "exclude_red")
            self.assertEqual([r["hadm_id"] for r, _ in kept], ["1", "2"])
            kept, _ = sim.apply_timing_filter(pairs, table, 6, "green_only")
            self.assertEqual([r["hadm_id"] for r, _ in kept], ["1"])
            self.assertEqual(info["before"], 4)


class LeakageAndSchemaTest(unittest.TestCase):
    def test_leakage_flags_late_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.csv"
            write_csv(p, ["cohort_L6", "_max_feature_offset_h_L6", "_pacu_first_h", "Y_T9_hours_to_pacu_L6",
                          "Y_T2_pacu_L6"], [[1, 5.0, "", "", 0], [1, 7.0, "", "", 0], [1, 2.0, 8.0, 8.0, 1]])
            res = leakage_checks.check(p, [6])["L6"]
            self.assertEqual(res["rows_with_feature_after_T"], 1)
            self.assertFalse(res["pass"])

    def test_missing_files_fail_loudly(self):
        with self.assertRaises(schemas.MissingData):
            schemas.require("eicu", root="/nonexistent")

    def test_downloading_file_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_csv(Path(tmp) / "hospital.csv.gz", ["hospitalid"], [[1]], gz=True)
            (Path(tmp) / "hospital.csv.gz.parts").mkdir()
            present, problems = schemas.check("eicu", ["hospital.csv.gz"], root=tmp)
            self.assertEqual(present, [])
            self.assertIn("still downloading", problems[0])


@unittest.skipUnless(FRAMEWORK.exists(), "upstream framework checkout not present")
class TableBuildTest(unittest.TestCase):
    def test_landmark_semantics(self):
        from src.preflight import mimic_cdm_table as mct
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_cdm(root / "cdm")
            hosp, ed, note = root / "hosp", root / "ed", root / "note"
            write_csv(hosp / "admissions.csv.gz",
                      ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime", "edregtime", "hospital_expire_flag"],
                      [[9, 1, "2150-01-01 12:00:00", "2150-01-05 12:00:00", "", "", 0],
                       [9, 90, "2149-01-01 12:00:00", "2149-01-02 12:00:00", "", "", 0],
                       [8, 2, "2150-02-01 12:00:00", "2150-02-03 12:00:00", "", "", 0],
                       [7, 3, "2150-03-01 12:00:00", "2150-03-06 12:00:00", "", "2150-03-01 07:00:00", 0],
                       [6, 4, "2150-04-01 12:00:00", "2150-04-01 14:00:00", "", "", 0],
                       [5, 5, "2150-05-01 08:00:00", "2150-05-09 08:00:00", "", "", 0]], gz=True)
            write_csv(hosp / "patients.csv.gz", ["subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group"],
                      [[9, "F", 40, 2150, "2014 - 2016"], [8, "M", 30, 2150, "2017 - 2019"], [7, "F", 60, 2150, "2017 - 2019"], [6, "M", 70, 2150, "2011 - 2013"], [5, "F", 50, 2150, "2020 - 2022"]], gz=True)
            write_csv(hosp / "transfers.csv.gz", ["subject_id", "hadm_id", "eventtype", "careunit", "intime", "outtime"],
                      [[9, 1, "transfer", "PACU", "2150-01-01 18:00:00", ""],        # +10 h after arrival 08:00
                       [8, 2, "transfer", "PACU", "2150-02-01 14:00:00", ""],        # 2 h after 12:00: excluded at L6
                       [5, 5, "transfer", "Medical Intensive Care Unit (MICU)", "2150-05-02 08:00:00", ""]], gz=True)
            write_csv(hosp / "procedures_icd.csv.gz", ["hadm_id", "chartdate", "icd_code", "icd_version"],
                      [[1, "2150-01-01", "0DTJ4ZZ", 10]], gz=True)
            write_csv(hosp / "d_labitems.csv.gz", ["itemid", "label", "fluid"],
                      [[51301, "White Blood Cells", "Blood"], [50956, "Lipase", "Blood"]], gz=True)
            write_csv(hosp / "labevents.csv.gz", ["labevent_id", "subject_id", "hadm_id", "itemid", "charttime", "value", "valuenum"],
                      [[1, 9, "", 51301, "2150-01-01 09:00:00", "14", "14"],
                       [2, 9, 1, 51301, "2150-01-01 07:30:00", "12", "12"],
                       [3, 9, 1, 50956, "2150-01-01 13:00:00", "30", "30"],     # +5 h: in L6 not L3
                       [4, 9, 90, 51301, "2150-01-01 09:30:00", "99", "99"]], gz=True)  # other admission
            write_csv(ed / "edstays.csv.gz", ["subject_id", "hadm_id", "stay_id", "intime", "outtime", "arrival_transport"],
                      [[9, 1, 11, "2150-01-01 08:00:00", "2150-01-01 15:00:00", "AMBULANCE"]], gz=True)
            write_csv(ed / "triage.csv.gz", ["stay_id", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain", "acuity"],
                      [[11, 99.1, 110, 18, 98, 120, 80, "unable", 2]], gz=True)
            write_csv(note / "radiology.csv.gz", ["note_id", "charttime", "storetime", "text"],
                      [["N1", "2150-01-01 10:00:00", "2150-01-01 15:00:00", "x"],
                       ["N3", "2150-03-01 08:00:00", "2150-03-01 09:00:00", "y"]], gz=True)
            files = lambda d, names: {n: d / n for n in names}
            table, meta = mct.build(root / "cdm",
                                    files(hosp, ["admissions.csv.gz", "patients.csv.gz", "transfers.csv.gz",
                                                 "procedures_icd.csv.gz", "d_labitems.csv.gz", "labevents.csv.gz"]),
                                    files(ed, ["edstays.csv.gz", "triage.csv.gz"]),
                                    files(note, ["radiology.csv.gz"]), FRAMEWORK, [3, 6])
            r1 = table[1]
            self.assertEqual(r1["prior_admissions"], 1)
            self.assertEqual(r1["arrival_ambulance"], 1)
            self.assertTrue(math.isnan(r1["triage_pain"]))
            self.assertEqual(r1["lab_wbc_L3"], 12.0)          # earliest in-window, own admission
            self.assertTrue(math.isnan(r1["lab_lipase_L3"]))  # drawn at +5 h
            self.assertEqual(r1["lab_lipase_L6"], 30.0)
            self.assertEqual(r1["img_done_ct_L6"], 0)         # CT signed at +7 h: not available by L6
            self.assertEqual(r1["Y_T2_pacu_L6"], 1)
            self.assertEqual(r1["Y_T1_procedure_L6"], 1)
            self.assertEqual(r1["T1_same_day_ambiguous_L6"], 0)  # resolved by PACU after T
            self.assertLessEqual(r1["_max_feature_offset_h_L6"], 6)
            self.assertEqual(table[2]["cohort_L6"], 0)        # PACU before T
            self.assertEqual(table[4]["cohort_L6"], 0)        # discharged before T
            self.assertEqual(table[5]["Y_T3_icu_L6"], 1)
            self.assertEqual(meta["attrition"]["L6"]["cdm_admissions"], 5)


if __name__ == "__main__":
    unittest.main()


class ProcedureTimingRulesTest(unittest.TestCase):
    def setUp(self):
        from src.preflight import procedure_timing as pt
        self.pt = pt
        self.saved = {k: list(v) for k, v in pt.MARKERS.items()}
        pt.MARKERS.update({"preop_specific": [r"pre-?op"], "postop": [r"post-?op"], "prep_nonspecific": [r"\bNPO\b"]})
        self.base = {"cohort_L6": "1", "T1_excluded_before_L6": "0", "Y_T1_procedure_L6": "1",
                     "anchor_time": "2150-01-01 08:00:00", "ed_outtime": "2150-01-01 11:00:00"}

    def tearDown(self):
        self.pt.MARKERS.update(self.saved)

    def cls(self, row=None, dates=(), pacu=(), poe=(), services=()):
        from datetime import date, datetime
        r = dict(self.base, **(row or {}))
        return self.pt.classify_case(r, 6, list(dates), list(pacu), list(poe), list(services))[0]

    def test_rules(self):
        from datetime import date, datetime
        dt = lambda h: datetime(2150, 1, 1, h)
        self.assertEqual(self.cls({"Y_T1_procedure_L6": "0"}), "GREEN")                   # no procedure
        self.assertEqual(self.cls(dates=[date(2150, 1, 2)]), "GREEN")                     # dated after T
        self.assertEqual(self.cls(dates=[date(2150, 1, 1)]), "RED")                       # same day, no evidence
        self.assertEqual(self.cls({"ed_outtime": "2150-01-01 15:00:00"}), "GREEN")        # in ED at T (14:00)
        self.assertEqual(self.cls(pacu=[dt(18)]), "GREEN")
        self.assertEqual(self.cls(pacu=[dt(12)]), "RED")                                  # PACU before T
        self.assertEqual(self.cls(poe=[(dt(16), "General Care | Pre-op")]), "GREEN")
        self.assertEqual(self.cls(poe=[(dt(12), "Post-op care"), (dt(16), "Pre-op")]), "RED")  # post-op before T wins
        self.assertEqual(self.cls(poe=[(dt(18), "Post-op care")]), "YELLOW")
        self.assertEqual(self.cls(services=[(dt(15), "SURG")]), "YELLOW")
        self.assertEqual(self.cls(poe=[(dt(15), "Nutrition | NPO")]), "YELLOW")
        self.assertEqual(self.cls({"cohort_L6": "0"}), "NOT_IN_COHORT")


class MedicationCategoryTest(unittest.TestCase):
    def test_categories(self):
        from src.preflight.medication_targets import classify_drug as c
        self.assertEqual(c("Piperacillin-Tazobactam", "IV"), {"antibiotic", "broad", "anaerobic"})
        self.assertEqual(c("CeftriaXONE", "IV"), {"antibiotic"})
        self.assertEqual(c("MetRONIDAZOLE (FLagyl)", "PO"), {"antibiotic", "anaerobic"})
        self.assertEqual(c("Vancomycin Oral Liquid", "PO"), set())          # C. difficile therapy: excluded
        self.assertEqual(c("Vancomycin", "IV"), {"antibiotic", "broad"})
        self.assertEqual(c("Bacitracin Ointment", "TP"), set())             # topical excluded
        self.assertEqual(c("Enoxaparin Sodium", "SC"), {"enoxaparin"})
        self.assertEqual(c("Heparin", "SC"), {"heparin_sc"})
        self.assertEqual(c("Heparin Flush (10 units/ml)", "IV"), set())
        self.assertEqual(c("HYDROmorphone (Dilaudid)", "IV"), {"opioid"})
        self.assertEqual(c("Insulin", "SC"), {"insulin"})
        self.assertEqual(c("HYDROmorphone", "ED"), set())                   # epidural: not systemic
        self.assertEqual(c("Vancomycin", "PB"), {"antibiotic", "broad"})    # IV piggyback: systemic

    def test_companion_names(self):
        self.assertEqual(targets.companion("/p/mimic_cdm_landmark_table.csv", "t1_timing_classes").name,
                         "t1_timing_classes.csv")
        self.assertEqual(targets.companion("/p/expanded.csv", "t1_timing_classes").name,
                         "expanded__t1_timing_classes.csv")

    def test_extra_table_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "mimic_cdm_landmark_table.csv"
            write_csv(t, ["hadm_id", "subject_id", "D", "cohort_L6"], [[1, 1, "appendicitis", 1], [2, 2, "pancreatitis", 1]])
            write_csv(Path(tmp) / "mimic_cdm_med_targets.csv", ["hadm_id", "Y_M1_antibiotic_L6"], [[1, 1], [2, 0]])
            pairs, col = targets.load_rows(t, "M1", 6)
            self.assertEqual(col, "Y_M1_antibiotic_L6")
            self.assertEqual([y for _, y in pairs], [1.0, 0.0])


class EarlyDiagnosisTest(unittest.TestCase):
    def test_nested_proba_and_featurizer_with_text(self):
        import numpy as np
        from src.preflight import early_diagnosis as ed
        rng = random.Random(3)
        rows, y = [], []
        for i in range(300):
            d = ["appendicitis", "cholecystitis"][i % 2]
            cc = ("rlq pain fever" if d == "appendicitis" else "ruq pain nausea") + (" vomiting" if rng.random() < .5 else "")
            rows.append({"hadm_id": str(i), "subject_id": str(i), "cc": cc, "age": str(rng.gauss(50, 10))})
            y.append(d)
        y, groups = np.array(y), np.array([r["subject_id"] for r in rows])
        build = lambda a, b: ed.Featurizer(["age"], True).fit_transform(a, b)
        P, chosen = ed.nested_proba(rows, y, groups, build, ["appendicitis", "cholecystitis"], 1)
        acc = (np.array(["appendicitis", "cholecystitis"])[P.argmax(1)] == y).mean()
        self.assertGreater(acc, 0.95)            # text carries the signal
        self.assertEqual(len(chosen), 5)

    def test_cohort_guard_excludes_red_and_non_cohort(self):
        from src.preflight import early_diagnosis as ed
        table = [{"hadm_id": "1", "has_ed_stay": "1", "cohort_L6": "1"},
                 {"hadm_id": "2", "has_ed_stay": "1", "cohort_L6": "1"},
                 {"hadm_id": "3", "has_ed_stay": "1", "cohort_L6": "0"},
                 {"hadm_id": "4", "has_ed_stay": "0", "cohort_L6": "1"}]
        rows = ed.ed_cohort(table, {"1": "a", "2": "b", "3": "c", "4": "d"}, {"1": "GREEN", "2": "RED"})
        self.assertEqual([r["hadm_id"] for r in rows], ["1"])
