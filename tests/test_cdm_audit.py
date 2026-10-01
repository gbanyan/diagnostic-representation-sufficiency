"""Tests for the MIMIC-CDM audit on synthetic data (no patient data)."""

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from audit import cdm_audit, lexicon

FRAMEWORK = Path(__file__).resolve().parent.parent / "external" / "MIMIC-Clinical-Decision-Making-Framework"


def write_csv(path, header, rows, gz=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = (lambda p: gzip.open(p, "wt", newline="")) if gz else (lambda p: open(p, "w", newline=""))
    with opener(path) as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def make_cdm(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pathology_ids.json").write_text(json.dumps(
        {"appendicitis": [1, 2], "cholecystitis": [3], "diverticulitis": [4], "pancreatitis": [5]}))
    write_csv(root / "history_of_present_illness.csv", ["hadm_id", "hpi"], [
        [1, "RLQ pain for 1 day. In the ED, CT showed a dilated appendix."],
        [2, "Periumbilical pain migrating to RLQ."],
        [3, "RUQ pain after fatty meal."],
        [4, "LLQ pain, s/p colonoscopy 2 years ago."],
        [5, "Epigastric pain radiating to back. Lipase 3000."],
    ])
    write_csv(root / "physical_examination.csv", ["hadm_id", "pe"], [
        [1, "Tender RLQ, concerning for ____."], [2, "Name ___ tender RLQ"], [3, "Murphy sign positive"],
        [4, "LLQ tenderness"], [5, "Epigastric tenderness"],
    ])
    write_csv(root / "laboratory_tests.csv", ["hadm_id", "itemid", "valuestr", "charttime"], [
        [1, 51301, "14 K/uL", "2150-01-01 10:00:00"],
        [1, 50889, "5 mg/L", "2150-01-03 10:00:00"],
        [5, 50956, "3000 IU/L", "2150-05-01 09:00:00"],
    ])
    write_csv(root / "microbiology.csv", ["hadm_id", "test_itemid", "valuestr", "charttime"], [])
    write_csv(root / "radiology_reports.csv", ["hadm_id", "note_id", "modality", "region", "exam_name", "text"], [
        [1, "N1", "CT", "Abdomen", "CT ABD", "FINDINGS: dilated appendix, appendicolith."],
        [3, "N3", "Ultrasound", "Abdomen", "US RUQ", "FINDINGS: pericholecystic fluid."],
    ])
    write_csv(root / "discharge_diagnosis.csv", ["hadm_id", "discharge_diagnosis"], [
        [1, "acute appendicitis"], [5, "gallstone pancreatitis, biliary"]])
    write_csv(root / "discharge_procedures.csv", ["hadm_id", "discharge_procedure"], [
        [1, "laparoscopic appendectomy"], [4, "CT-guided drain placement, pelvic abscess"]])
    write_csv(root / "icd_diagnosis.csv", ["hadm_id", "icd_diagnosis"], [[5, "Acute pancreatitis"]])
    write_csv(root / "icd_procedures.csv", ["hadm_id", "icd_code", "icd_version", "icd_title"], [
        [3, "5123", 9, "Laparoscopic cholecystectomy"]])


def make_mimic(root):
    write_csv(root / "ed" / "edstays.csv.gz", ["subject_id", "hadm_id", "stay_id", "intime"], [
        [9, 1, 11, "2150-01-01 08:00:00"], [9, 1, 12, "2150-01-01 09:00:00"]], gz=True)
    write_csv(root / "hosp" / "admissions.csv.gz", ["subject_id", "hadm_id", "admittime", "dischtime", "edregtime"], [
        [9, 1, "2150-01-01 12:00:00", "2150-01-05 12:00:00", ""], [8, 2, "2150-02-01 12:00:00", "2150-02-03 12:00:00", ""],
        [7, 3, "2150-03-01 12:00:00", "2150-03-06 12:00:00", "2150-03-01 07:00:00"],
        [6, 4, "2150-04-01 12:00:00", "2150-04-04 12:00:00", ""],
        [5, 5, "2150-05-01 08:00:00", "2150-05-09 08:00:00", ""]], gz=True)
    lab_header = ["labevent_id", "subject_id", "hadm_id", "itemid", "charttime", "value", "valuenum", "valueuom", "flag", "comments"]
    write_csv(root / "hosp" / "labevents.csv.gz", lab_header, [
        # hadm 1, item 51301: a later row, then the earliest row (no hadm_id, inside window).
        [1, 9, 1, 51301, "2150-01-02 10:00:00", "9", "9", "K/uL", "", ""],
        [2, 9, "", 51301, "2150-01-01 07:30:00", "14", "14", "K/uL", "", ""],
        # Outside the window (more than 1 day before arrival): ignored.
        [3, 9, "", 51301, "2149-12-25 07:30:00", "3", "3", "K/uL", "", ""],
        # Unusable '___' row earlier than the real one: ignored.
        [4, 9, 1, 50889, "2150-01-01 09:00:00", "___", "", "", "", ""],
        [5, 9, 1, 50889, "2150-01-03 10:00:00", "5", "5", "mg/L", "", ""],
        [6, 5, 5, 50956, "2150-05-01 09:00:00", "3000", "3000", "IU/L", "", ""],
    ], gz=True)
    write_csv(root / "note" / "radiology.csv.gz", ["note_id", "charttime", "text"], [
        ["N1", "2150-01-01 11:00:00", "x"], ["N3", "2150-03-04 07:00:00", "y"]], gz=True)
    write_csv(root / "hosp" / "procedures_icd.csv.gz", ["hadm_id", "chartdate", "icd_code"], [
        [1, "2150-01-02", "X"], [3, "2150-03-02", "5123"]], gz=True)


class LexiconTest(unittest.TestCase):
    def test_redaction_marker_distinguishes_upstream_from_deid(self):
        self.assertIn("redaction_marker", lexicon.flags("concerning for ____."))
        self.assertNotIn("redaction_marker", lexicon.flags("Name ___ tender"))
        self.assertNotIn("redaction_marker", lexicon.flags("long _____ line"))

    def test_categories(self):
        self.assertIn("ed_results_in_history", lexicon.flags("In the ED, CT showed a dilated appendix"))
        self.assertIn("ed_results_in_history", lexicon.flags("Lipase 3000"))
        self.assertIn("course_hindsight", lexicon.flags("POD #2, tolerating diet"))
        self.assertIn("diagnosis_shorthand", lexicon.flags("s/p lap chole"))
        self.assertEqual(lexicon.flags("RLQ pain for one day"), set())


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_cdm(self.root / "cdm")
        make_mimic(self.root / "mimic")
        self.cases, self.columns = cdm_audit.load_cdm(self.root / "cdm")

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_mismatch_fails_loudly(self):
        write_csv(self.root / "cdm" / "physical_examination.csv", ["hadm_id", "exam"], [[1, "x"]])
        with self.assertRaises(SystemExit):
            cdm_audit.load_cdm(self.root / "cdm")

    def test_inventory(self):
        inv = cdm_audit.cmd_inventory(self.cases, self.columns)["by_pathology"]
        self.assertEqual(inv["appendicitis"]["cases"], 2)
        self.assertEqual(inv["appendicitis"]["lab_charttime_present"]["n"], 2)
        self.assertEqual(inv["cholecystitis"]["radiology_per_case"]["max"], 1)

    def test_hindsight_rates(self):
        h = cdm_audit.cmd_hindsight(self.cases)["by_pathology"]
        self.assertEqual(h["appendicitis"]["hpi"]["ed_results_in_history"]["n"], 1)
        self.assertEqual(h["appendicitis"]["pe"]["redaction_marker"]["n"], 1)
        self.assertEqual(h["appendicitis"]["radiology"]["diagnosis_shorthand"]["n"], 1)
        self.assertEqual(h["pancreatitis"]["hpi"]["ed_results_in_history"]["pct"], 100.0)

    def test_sample_is_deterministic_and_private_dir_guarded(self):
        a = cdm_audit.cmd_sample(self.cases, 1, seed=7)
        b = cdm_audit.cmd_sample(self.cases, 1, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(len(a["hadm_ids"]["appendicitis"]), 1)
        with self.assertRaises(SystemExit):
            cdm_audit.assert_outside_repo(Path(__file__).resolve().parent / "private")

    def test_timing(self):
        t = cdm_audit.cmd_timing(self.cases, self.root / "mimic")
        self.assertEqual(t["anchor_source"], {"ed_intime": 1, "edregtime": 1, "admittime": 3})
        app = t["by_pathology"]["appendicitis"]
        # Anchor = earliest ED intime 08:00; labs at +2 h and +50 h.
        self.assertEqual(app["labs"]["offset_hours"]["min"], 2.0)
        self.assertEqual(app["labs"]["items_gt_24h"]["n"], 1)
        self.assertEqual(app["labs"]["cases_with_any_item_gt_24h"]["n"], 1)
        self.assertEqual(app["relative_to_first_icd_procedure_date"]["labs_after_procedure_day"], 1)
        chole = t["by_pathology"]["cholecystitis"]
        self.assertEqual(chole["radiology"]["offset_hours"]["min"], 72.0)
        self.assertEqual(chole["relative_to_first_icd_procedure_date"]["radiology_after_procedure_day"], 1)

    def test_lab_times_reconstructed_when_release_lacks_them(self):
        write_csv(self.root / "cdm" / "laboratory_tests.csv", ["hadm_id", "itemid", "valuestr"], [
            [1, 51301, "14.0 K/uL"], [1, 50889, "5.0 mg/L"], [5, 50956, "3000.0 IU/L"]])
        cases, _ = cdm_audit.load_cdm(self.root / "cdm")
        t = cdm_audit.cmd_timing(cases, self.root / "mimic")
        self.assertEqual(t["lab_time_source"], "mimic-iv labevents (reconstructed)")
        self.assertEqual((t["lab_items_timed"], t["lab_items_value_match"]), (3, 3))
        app = t["by_pathology"]["appendicitis"]["labs"]
        # 51301 earliest usable in-window row at 07:30 (-0.5 h); 50889 at +50 h.
        self.assertEqual(app["offset_hours"]["min"], -0.5)
        self.assertEqual(app["items_gt_24h"]["n"], 1)

    def test_conditional_items_with_stub_mappings(self):
        m = SimpleNamespace(
            APPENDECTOMY_PROCEDURES_ICD9=[4701], APPENDECTOMY_PROCEDURES_ICD10=["0DTJ4ZZ"],
            APPENDECTOMY_PROCEDURES_KEYWORDS=["appendectomy"],
            CHOLECYSTECTOMY_PROCEDURES_ICD9=[5123], CHOLECYSTECTOMY_PROCEDURES_ICD10=[],
            CHOLECYSTECTOMY_PROCEDURES_KEYWORDS=["cholecystectomy"],
            DRAINAGE_PROCEDURES_ICD9=[], DRAINAGE_PROCEDURES_ALL_ICD10=[],
            DRAINAGE_PROCEDURES_PANCREATITIS_ICD10=[], DRAINAGE_PROCEDURES_KEYWORDS=["drain"],
            DRAINAGE_LOCATIONS_DIVERTICULITIS=["pelvic"], DRAINAGE_LOCATIONS_PANCREATITIS=["pancrea"],
            COLECTOMY_PROCEDURES_ICD9=[], COLECTOMY_PROCEDURES_ICD10=[], COLECTOMY_PROCEDURES_KEYWORDS=["colectomy"],
            ERCP_PROCEDURES_ICD9=[], ERCP_PROCEDURES_ICD10=[], ERCP_PROCEDURES_KEYWORDS=["ERCP"],
        )
        hits = {h: cdm_audit.conditional_items(c, m) for h, c in self.cases.items()}
        self.assertEqual(hits[1], ["appendectomy"])
        self.assertEqual(hits[2], [])
        self.assertEqual(hits[3], ["cholecystectomy"])
        self.assertEqual(hits[4], ["drainage"])
        self.assertEqual(hits[5], ["cholecystectomy_biliary"])

    def test_small_cells_suppressed_on_output(self):
        out = cdm_audit.suppress_small({"a": cdm_audit.share(3, 100), "b": [cdm_audit.share(40, 100)]})
        self.assertEqual(out["a"], {"n": "<10", "of": 100, "pct": None})
        self.assertEqual(out["b"][0]["n"], 40)

    def test_negated_keyword_not_counted(self):
        self.assertFalse(cdm_audit.keyword_positive("no appendectomy was performed", "appendectomy"))
        self.assertTrue(cdm_audit.keyword_positive("laparoscopic appendectomy", "appendectomy"))

    @unittest.skipUnless(FRAMEWORK.exists(), "upstream framework checkout not present")
    def test_upstream_mappings_load(self):
        t = cdm_audit.cmd_treatment(self.cases, FRAMEWORK)
        self.assertEqual(t["by_pathology"]["appendicitis"]["per_item"]["appendectomy"]["n"], 1)

    def test_cli_all_writes_only_aggregates_to_out(self):
        out, private = self.root / "out", self.root / "private"
        cdm_audit.main(["all", "--cdm-dir", str(self.root / "cdm"), "--mimic-dir", str(self.root / "mimic"),
                        "--framework-dir", str(FRAMEWORK), "--out", str(out), "--private-dir", str(private),
                        "--per-pathology", "1"]) if FRAMEWORK.exists() else self.skipTest("no framework")
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["hindsight.json", "inventory.json", "sample.json", "timing.json", "treatment.json"])
        self.assertNotIn("hadm_ids", json.loads((out / "sample.json").read_text()))
        self.assertIn("hadm_ids", json.loads((private / "audit_sample.json").read_text()))


if __name__ == "__main__":
    unittest.main()
