"""Expanded MIMIC-IV cohort (docs/expanded_cohort_preflight.md).

All admissions whose PRIMARY billing diagnosis (diagnoses_icd.seq_num = 1) matches one of the
four pathologies, with a linked ED stay. D = D_icd (primary billing code; a D_final-type object,
not D_t). The landmark table is built with the same builder as MIMIC-CDM, without imaging
flags (X2) or discharge-procedure text.

  python -m src.preflight.expanded_cohort --framework-dir <upstream> [--landmarks 3 6]
"""

import argparse
import csv
import json
from collections import Counter

from audit.cdm_audit import open_text
from src.preflight import schemas
from src.preflight.mimic_cdm_table import build, write_table
from src.preflight.reporting import private_dir, suppress, write_json

TABLE_NAME = "mimic_iv_expanded_landmark_table"
PATTERNS = {"acute appendicitis": "appendicitis", "acute cholecystitis": "cholecystitis",
            "diverticulitis": "diverticulitis", "acute pancreatitis": "pancreatitis"}


def select(hosp, ed):
    titles = {}
    for r in csv.DictReader(open_text(hosp["d_icd_diagnoses.csv.gz"])):
        titles[(r["icd_code"].strip(), r["icd_version"].strip())] = r["long_title"]
    primary, multi = {}, 0
    for r in csv.DictReader(open_text(hosp["diagnoses_icd.csv.gz"])):
        if r["seq_num"].strip() != "1":
            continue
        title = titles.get((r["icd_code"].strip(), r["icd_version"].strip()), "")
        hits = {p for s, p in PATTERNS.items() if s in title.lower()}
        if len(hits) == 1:
            primary[int(r["hadm_id"])] = hits.pop()
        elif len(hits) > 1:
            multi += 1
    with_ed = set()
    for r in csv.DictReader(open_text(ed["edstays.csv.gz"])):
        if r["hadm_id"]:
            with_ed.add(int(float(r["hadm_id"])))
    cohort = {h: p for h, p in primary.items() if h in with_ed}
    return cohort, {"primary_matches": len(primary), "multi_pathology_titles_excluded": multi,
                    "without_ed_stay_excluded": len(primary) - len(cohort)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--framework-dir", required=True)
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_iv_expanded")
    ap.add_argument("--with-discharge-procedures", action="store_true",
                    help="add procedures from the discharge-summary procedure section (as in MIMIC-CDM)")
    ap.add_argument("--table-name", default=TABLE_NAME)
    args = ap.parse_args(argv)
    hosp = schemas.require("mimiciv_hosp", ["admissions.csv.gz", "patients.csv.gz", "transfers.csv.gz",
                                             "procedures_icd.csv.gz", "d_labitems.csv.gz", "labevents.csv.gz",
                                             "diagnoses_icd.csv.gz", "d_icd_diagnoses.csv.gz"])
    ed = schemas.require("mimiciv_ed")
    note = schemas.require("mimiciv_note", ["radiology.csv.gz"]
                           + (["discharge.csv.gz"] if args.with_discharge_procedures else []))
    cdm = schemas.require("mimic_cdm", ["pathology_ids.json"])
    priv = private_dir(args.private_dir)

    cohort, attrition = select(hosp, ed)
    cdm_ids = {int(h): p for p, hs in json.load(open(cdm["pathology_ids.json"])).items() for h in hs}
    cases = {h: {"pathology": p, "labs": [], "micro": [], "radiology": [], "icd_diagnosis": [],
                 "procedures_discharge": [], "procedures_icd9": [], "procedures_icd10": []}
             for h, p in cohort.items()}
    if args.with_discharge_procedures:
        # Same extraction as MIMIC-CDM (pinned upstream function), so T1 has the same definition:
        # ICD procedure code OR a procedure named in the discharge "Major Surgical or Invasive
        # Procedure" section. The section text is used only to define the target, never as a feature.
        import sys
        sys.path.insert(0, str(args.framework_dir))
        from dataset.procedures import extract_procedure_from_discharge_summary  # noqa: E402
        found = 0
        for r in csv.DictReader(open_text(note["discharge.csv.gz"])):
            if r["hadm_id"] and int(float(r["hadm_id"])) in cases:
                cases[int(float(r["hadm_id"]))]["procedures_discharge"] = extract_procedure_from_discharge_summary(r["text"])
                found += 1
        attrition["with_discharge_summary"] = found
    table, meta = build(None, hosp, ed, note, args.framework_dir, args.landmarks, cases=cases)
    for h, row in table.items():
        row["in_cdm"] = int(h in cdm_ids)
    write_table(table, priv / f"{args.table_name}.csv")
    overlap = {h for h in cohort if h in cdm_ids}
    agree = sum(cdm_ids[h] == cohort[h] for h in overlap)
    meta.update({
        "cohort_definition": "diagnoses_icd seq_num=1 long_title substring match; linked ED stay",
        "diagnosis_object": "D_icd (primary billing diagnosis; D_final-type, not D_t)",
        "attrition": {**meta.get("attrition", {}), **attrition, "cohort": len(cohort)},
        "by_diagnosis": {p: suppress(n) for p, n in Counter(cohort.values()).items()},
        "overlap_with_cdm": {"cdm_admissions": len(cdm_ids), "in_both": len(overlap),
                             "same_pathology_label": agree,
                             "cdm_not_in_expanded": len(set(cdm_ids) - set(cohort))},
        "anchor_year_group": {k: suppress(v) for k, v in
                              Counter(r.get("anchor_year_group", "") for r in table.values()).items()},
        "note": ("X2 (imaging flags) not built; T1 from ICD procedures "
                 + ("OR discharge procedure section (as MIMIC-CDM)" if args.with_discharge_procedures
                    else "only (INVALID: ICD capture misses ~30% of operations; see expanded_cohort_preflight.md)")),
    })
    write_json(args.out, "table_build", meta)
    print(f"wrote private table ({len(table)} rows) to {priv}")


if __name__ == "__main__":
    main()
