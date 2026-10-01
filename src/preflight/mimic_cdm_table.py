"""Build the MIMIC-CDM landmark analysis table (patient-level, private output only).

One row per CDM admission. D = D_final (CDM pathology); every analysis built
on this table is post-diagnostic (docs/target_sufficiency_framework.md).
For each landmark L (hours after the anchor t0), features use only data
timestamped <= t0 + L, and targets are defined strictly after t0 + L.

Usage (on the data host):
  python -m src.preflight.mimic_cdm_table --framework-dir <upstream checkout> \
      --private-dir /mnt/SAM1TB/dev/data/diagnosis-bottleneck-private [--landmarks 3 6]
"""

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from audit.cdm_audit import load_cdm, open_text, parse_time
from src.preflight import schemas
from src.preflight.reporting import private_dir, suppress, write_json

csv.field_size_limit(sys.maxsize)

# Pre-specified lab features: (feature name, d_labitems label, fluid).
LAB_FEATURES = [
    ("wbc", "White Blood Cells", "Blood"), ("neut_pct", "Neutrophils", "Blood"),
    ("hgb", "Hemoglobin", "Blood"), ("plt", "Platelet Count", "Blood"),
    ("crp", "C-Reactive Protein", "Blood"), ("lactate", "Lactate", "Blood"),
    ("lipase", "Lipase", "Blood"), ("tbili", "Bilirubin, Total", "Blood"),
    ("alt", "Alanine Aminotransferase (ALT)", "Blood"), ("ast", "Asparate Aminotransferase (AST)", "Blood"),
    ("alp", "Alkaline Phosphatase", "Blood"), ("creat", "Creatinine", "Blood"),
    ("bun", "Urea Nitrogen", "Blood"), ("glucose", "Glucose", "Blood"),
    ("sodium", "Sodium", "Blood"), ("potassium", "Potassium", "Blood"),
    ("bicarb", "Bicarbonate", "Blood"), ("albumin", "Albumin", "Blood"),
    ("inr", "INR(PT)", "Blood"), ("calcium", "Calcium, Total", "Blood"),
]
LAB_LOOKBACK_H = 1  # labs drawn up to 1 h before ED arrival count as arrival labs

# Pre-specified radiology finding flags (computed on the CDM findings text).
IMAGING_FLAGS = {
    "perforation": r"perforat",
    "abscess_collection": r"abscess|fluid collection|\bcollection\b",
    "free_air": r"free air|pneumoperitoneum|extraluminal (?:gas|air)",
    "gangrene_necrosis": r"gangren|necros|non-?enhanc",
    "free_fluid": r"free fluid|ascites",
    "gallstones": r"cholelithiasis|gallstone|\bstones?\b",
    "cbd_dilation": r"(?:common bile duct|\bCBD\b)[^.]{0,60}dilat|dilat[^.]{0,60}(?:common bile duct|\bCBD\b)|choledocholithiasis",
    "wall_thickening": r"wall thicken|thickened wall|wall is thickened",
    "fat_stranding": r"stranding",
    "phlegmon": r"phlegmon",
    "obstruction": r"obstruct",
}
IMAGING_FLAGS_RE = {k: re.compile(v, re.IGNORECASE) for k, v in IMAGING_FLAGS.items()}

TRIAGE_FIELDS = ["temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain", "acuity"]
# Physiologic plausibility bounds (deviation 2026-09-29, see decision_log.md):
# values outside are data-entry errors (e.g. SBP 19734) and are set to missing.
TRIAGE_BOUNDS = {"temperature": (90, 110), "heartrate": (20, 250), "resprate": (4, 60), "o2sat": (50, 100),
                 "sbp": (40, 300), "dbp": (20, 200), "pain": (0, 10), "acuity": (1, 5)}
PACU_RE = re.compile(r"\bPACU\b", re.IGNORECASE)
ICU_RE = re.compile(r"intensive care|\bICU\b|\bCCU\b|\bSICU\b|\bMICU\b|\bCVICU\b", re.IGNORECASE)

# Pathology-specific definitive procedure (T1), mirroring the upstream rubric.
T1_PROCEDURES = {
    "appendicitis": ["APPENDECTOMY"],
    "cholecystitis": ["CHOLECYSTECTOMY"],
    "diverticulitis": ["COLECTOMY", "DRAINAGE"],
    "pancreatitis": ["ERCP"],
}
ORGAN_OF = {"APPENDECTOMY": "appendix", "CHOLECYSTECTOMY": "gallbladder", "COLECTOMY": "colon"}


def rows(p, required):
    with open_text(p) as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise schemas.MissingData(f"{p} lacks columns {sorted(missing)}")
        yield from reader


def num(x):
    try:
        v = float(str(x).strip())
    except (TypeError, ValueError):
        return math.nan
    return v if math.isfinite(v) else math.nan


def hours(a, b):
    return (a - b).total_seconds() / 3600.0


def procedure_codes(m):
    """ICD procedure code sets per procedure family, from the pinned upstream mappings."""
    return {
        "APPENDECTOMY": (set(m.APPENDECTOMY_PROCEDURES_ICD9), set(m.APPENDECTOMY_PROCEDURES_ICD10),
                         m.APPENDECTOMY_PROCEDURES_KEYWORDS),
        "CHOLECYSTECTOMY": (set(m.CHOLECYSTECTOMY_PROCEDURES_ICD9), set(m.CHOLECYSTECTOMY_PROCEDURES_ICD10),
                            m.CHOLECYSTECTOMY_PROCEDURES_KEYWORDS),
        "COLECTOMY": (set(m.COLECTOMY_PROCEDURES_ICD9), set(m.COLECTOMY_PROCEDURES_ICD10),
                      m.COLECTOMY_PROCEDURES_KEYWORDS),
        "DRAINAGE": (set(m.DRAINAGE_PROCEDURES_ICD9),
                     set(m.DRAINAGE_PROCEDURES_ALL_ICD10) | set(m.DRAINAGE_PROCEDURES_PANCREATITIS_ICD10),
                     []),  # keyword drainage needs a location match; ICD only here
        "ERCP": (set(m.ERCP_PROCEDURES_ICD9), set(m.ERCP_PROCEDURES_ICD10), m.ERCP_PROCEDURES_KEYWORDS),
    }


def code_key(code, version):
    code = code.strip()
    return int(code) if version == "9" and code.isdigit() else code


def read_first_labs(labevents_path, table, item_to_feat, max_l):
    """First value per (admission, lab feature) charted in [t0 - 1 h, t0 + max_l].

    Rows with another admission's hadm_id are skipped; rows without hadm_id are
    attributed by subject and time window.
    """
    by_subject = defaultdict(list)
    for h, row in table.items():
        by_subject[str(row["subject_id"])].append(h)
    first_lab = {}
    with open_text(labevents_path) as f:
        reader = csv.reader(f)
        head = next(reader)
        ix = {k: head.index(k) for k in ("subject_id", "hadm_id", "itemid", "charttime", "valuenum")}
        for r in reader:
            hs = by_subject.get(r[ix["subject_id"]])
            if not hs:
                continue
            feat = item_to_feat.get(r[ix["itemid"]])
            if not feat:
                continue
            v = num(r[ix["valuenum"]])
            if math.isnan(v):
                continue
            t = parse_time(r[ix["charttime"]])
            rh = r[ix["hadm_id"]]
            for h in hs:
                if rh and int(float(rh)) != h:
                    continue
                t0 = table[h]["_t0"]
                if t and t0 - timedelta(hours=LAB_LOOKBACK_H) <= t <= t0 + timedelta(hours=max_l):
                    k = (h, feat)
                    if k not in first_lab or t < first_lab[k][0]:
                        first_lab[k] = (t, v)
    return first_lab


def build(cdm_dir, hosp, ed, note, framework_dir, landmarks, skip_labs=False, cases=None):
    if cases is None:
        cases, _ = load_cdm(cdm_dir)
    hadm_ids = set(cases)
    sys.path.insert(0, str(framework_dir))
    import icd.procedure_mappings as m  # noqa: E402  (pinned upstream)
    families = procedure_codes(m)

    # --- anchors and ED stay -------------------------------------------------
    ed_stay = {}
    for r in rows(ed["edstays.csv.gz"], {"hadm_id", "stay_id", "intime"}):
        if not r["hadm_id"]:
            continue
        h = int(float(r["hadm_id"]))
        t = parse_time(r["intime"])
        if h in hadm_ids and t and (h not in ed_stay or t < ed_stay[h]["t"]):
            ed_stay[h] = {"t": t, "stay_id": r["stay_id"], "arrival_transport": r.get("arrival_transport", ""),
                          "outtime": parse_time(r.get("outtime"))}

    adm, subj_admits = {}, defaultdict(list)
    for r in rows(hosp["admissions.csv.gz"], {"subject_id", "hadm_id", "admittime", "dischtime"}):
        s, h = int(r["subject_id"]), int(r["hadm_id"])
        subj_admits[s].append(parse_time(r["admittime"]))
        if h in hadm_ids:
            adm[h] = {"subject_id": s, "admittime": parse_time(r["admittime"]),
                      "dischtime": parse_time(r["dischtime"]), "deathtime": parse_time(r.get("deathtime")),
                      "edregtime": parse_time(r.get("edregtime")),
                      "expire": r.get("hospital_expire_flag", "0") == "1"}

    table = {}
    for h in sorted(hadm_ids):
        a = adm.get(h)
        if not a:
            continue
        if h in ed_stay:
            t0, src = ed_stay[h]["t"], "ed_intime"
        elif a["edregtime"]:
            t0, src = a["edregtime"], "edregtime"
        else:
            t0, src = a["admittime"], "admittime"
        table[h] = {"hadm_id": h, "subject_id": a["subject_id"], "D": cases[h]["pathology"],
                    "anchor_source": src, "_t0": t0, "_disch": a["dischtime"], "_death": a["deathtime"],
                    "Y_T8_death": int(a["expire"]),
                    "prior_admissions": sum(1 for t in subj_admits[a["subject_id"]] if t and t < t0),
                    "arrival_ambulance": int("AMBULANCE" in (ed_stay.get(h, {}).get("arrival_transport") or "").upper()),
                    "has_ed_stay": int(h in ed_stay),
                    # Private columns used by the procedure-timing audit (Q14).
                    "anchor_time": str(t0),
                    "ed_outtime": str(ed_stay[h]["outtime"]) if h in ed_stay and ed_stay[h]["outtime"] else ""}

    # --- demographics ---------------------------------------------------------
    subjects = {r["subject_id"] for r in table.values()}
    for r in rows(hosp["patients.csv.gz"], {"subject_id", "gender", "anchor_age", "anchor_year"}):
        s = int(r["subject_id"])
        if s in subjects:
            for row in (x for x in table.values() if x["subject_id"] == s):
                row["age"] = num(r["anchor_age"]) + (row["_t0"].year - int(r["anchor_year"]))
                row["female"] = int(r["gender"] == "F")
                row["anchor_year_group"] = r.get("anchor_year_group", "")

    # --- triage (arrival state) -----------------------------------------------
    stay_to_h = {v["stay_id"]: h for h, v in ed_stay.items() if h in table}
    out_of_bounds, recorded = Counter(), Counter()
    for r in rows(ed["triage.csv.gz"], {"stay_id", *TRIAGE_FIELDS}):
        h = stay_to_h.get(r["stay_id"])
        if h is not None:
            for f in TRIAGE_FIELDS:
                v = num(r[f])
                if (r[f] or "").strip():
                    recorded[f] += 1
                lo, hi = TRIAGE_BOUNDS[f]
                if not (lo <= v <= hi):
                    if (r[f] or "").strip():
                        out_of_bounds[f] += 1  # recorded but impossible / non-numeric
                    v = math.nan
                table[h][f"triage_{f}"] = v

    # --- transfers: PACU (proxy for operation end) and ICU times --------------
    pacu, icu, careunits = defaultdict(list), defaultdict(list), Counter()
    for r in rows(hosp["transfers.csv.gz"], {"hadm_id", "careunit", "intime"}):
        if not r["hadm_id"]:
            continue
        h = int(float(r["hadm_id"]))
        if h not in table:
            continue
        cu, t = r["careunit"] or "", parse_time(r["intime"])
        careunits[cu] += 1
        if t and PACU_RE.search(cu):
            pacu[h].append(t)
        if t and ICU_RE.search(cu) and not PACU_RE.search(cu):
            icu[h].append(t)

    # --- ICD procedure dates per family ----------------------------------------
    proc_dates = defaultdict(lambda: defaultdict(list))
    for r in rows(hosp["procedures_icd.csv.gz"], {"hadm_id", "chartdate", "icd_code", "icd_version"}):
        h = int(r["hadm_id"])
        if h not in table:
            continue
        key, d = code_key(r["icd_code"], r["icd_version"].strip()), parse_time(r["chartdate"])
        for fam, (c9, c10, _) in families.items():
            if (key in c9) or (key in c10):
                proc_dates[h][fam].append(d.date() if d else None)

    # Discharge-text procedure mentions (no timestamp) as a fallback signal.
    text_proc = defaultdict(set)
    for h, c in cases.items():
        txt = " ".join(p for p in c["procedures_discharge"] if isinstance(p, str)).lower()
        for fam, (_, _, kws) in families.items():
            if any(k.lower() in txt for k in kws):
                text_proc[h].add(fam)

    # --- labs: first value per feature in [t0 - 1h, t0 + max(L)] ---------------
    label_to_feat = {(lab, fluid): f for f, lab, fluid in LAB_FEATURES}
    item_to_feat = {}
    for r in rows(hosp["d_labitems.csv.gz"], {"itemid", "label", "fluid"}):
        f = label_to_feat.get((r["label"], r["fluid"]))
        if f:
            item_to_feat[r["itemid"]] = f
    first_lab = {} if skip_labs else read_first_labs(hosp["labevents.csv.gz"], table, item_to_feat,
                                                        max(landmarks))

    # --- radiology: note times from MIMIC-IV-Note, findings text from CDM -----
    note_ids = {r["note_id"] for c in cases.values() for r in c["radiology"]}
    # charttime = exam time (orders the studies); storetime = report signed, i.e.
    # when the findings became available to the team (used for the landmark cut).
    note_time, note_avail = {}, {}
    for r in (rows(note["radiology.csv.gz"], {"note_id", "charttime", "storetime"}) if note_ids else ()):
        if r["note_id"] in note_ids:
            note_time[r["note_id"]] = parse_time(r["charttime"])
            note_avail[r["note_id"]] = parse_time(r["storetime"]) or note_time[r["note_id"]]

    # --- assemble per landmark -------------------------------------------------
    meta = {"careunits_seen": {k: suppress(v) for k, v in careunits.items()}, "landmarks_h": landmarks, "attrition": {},
            "triage_recorded": recorded, "triage_bounds": TRIAGE_BOUNDS,
            "triage_out_of_bounds": {k: suppress(v) for k, v in out_of_bounds.items()},
            "labs": "skipped (labevents unavailable); X1/X2 lab features are all missing" if skip_labs else "labevents"}
    for h, row in table.items():
        t0 = row["_t0"]
        c = cases[h]
        abd = sorted(((note_time.get(r["note_id"]), r) for r in c["radiology"]
                      if r["region"] == "Abdomen" and note_time.get(r["note_id"])), key=lambda x: x[0])
        abd_after_anchor = [(t, r) for t, r in abd if t >= t0 - timedelta(hours=LAB_LOOKBACK_H)]
        row["Y_T6_first_modality"] = abd_after_anchor[0][1]["modality"] if abd_after_anchor else ""
        row["Y_T7_n_abd_imaging"] = len(abd_after_anchor)
        pac = sorted(pacu.get(h, []))
        row["_pacu_first_h"] = hours(pac[0], t0) if pac else math.nan
        # T5: organ operated (any time), only for exactly one organ family recorded.
        organs = {ORGAN_OF[fam] for fam in ("APPENDECTOMY", "CHOLECYSTECTOMY", "COLECTOMY")
                  if proc_dates[h].get(fam)}
        row["Y_T5_organ"] = organs.pop() if len(organs) == 1 else ""
        for L in landmarks:
            T = t0 + timedelta(hours=L)
            sfx = f"_L{L}"
            alive_in_hosp = row["_disch"] and row["_disch"] > T and not (row["_death"] and row["_death"] <= T)
            pacu_before = any(t < T for t in pac)
            icu_before = any(t < T for t in icu.get(h, []))
            # T1 target family status relative to T.
            fams = T1_PROCEDURES[row["D"]]
            dates = [d for fam in fams for d in proc_dates[h].get(fam, []) if d]
            before = any(d < T.date() for d in dates)
            same_day = any(d == T.date() for d in dates)
            after = any(d > T.date() for d in dates)
            pac_after = [t for t in pac if t >= T]
            if same_day and pac_after and not pacu_before:
                # A PACU stay after T on the same day resolves the ambiguity for surgical families.
                same_day_resolved = fams != ["ERCP"]
            else:
                same_day_resolved = False
            text_only = (not dates) and bool(text_proc[h] & set(fams))
            row[f"cohort{sfx}"] = int(bool(alive_in_hosp) and not pacu_before)
            row[f"T1_excluded_before{sfx}"] = int(before)
            row[f"T1_same_day_ambiguous{sfx}"] = int(same_day and not same_day_resolved and not after)
            row[f"T1_text_only{sfx}"] = int(text_only)
            row[f"Y_T1_procedure{sfx}"] = int(after or same_day or text_only)
            row[f"Y_T2_pacu{sfx}"] = int(bool(pac_after))
            row[f"icu_before{sfx}"] = int(icu_before)
            row[f"Y_T3_icu{sfx}"] = int(any(t >= T for t in icu.get(h, [])))
            row[f"Y_T4_log_los_days{sfx}"] = (math.log1p(hours(row["_disch"], T) / 24.0)
                                              if alive_in_hosp else math.nan)
            row[f"Y_T9_hours_to_pacu{sfx}"] = hours(pac_after[0], t0) if pac_after else math.nan
            # Labs (X1) and imaging (X2) at this landmark.
            max_t = t0 - timedelta(hours=LAB_LOOKBACK_H)
            for feat, _, _ in LAB_FEATURES:
                v = first_lab.get((h, feat))
                row[f"lab_{feat}{sfx}"] = v[1] if v and v[0] <= T else math.nan
                if v and v[0] <= T:
                    max_t = max(max_t, v[0])
            seen = [(t, r) for t, r in abd_after_anchor if note_avail[r["note_id"]] <= T]
            for mod in ("CT", "Ultrasound", "MRI"):
                row[f"img_done_{mod.lower()}{sfx}"] = int(any(r["modality"] == mod for _, r in seen))
            text = " ".join(r["text"] for _, r in seen)
            for k, rx in IMAGING_FLAGS_RE.items():
                row[f"img_{k}{sfx}"] = int(bool(rx.search(text)))
            if seen:
                max_t = max([max_t] + [note_avail[r["note_id"]] for _, r in seen])
            row[f"_max_feature_offset_h{sfx}"] = hours(max_t, t0)
    for L in landmarks:
        sfx = f"_L{L}"
        vals = list(table.values())
        meta["attrition"][f"L{L}"] = {
            "cdm_admissions": len(cases),
            "with_admission_record": len(vals),
            "alive_in_hospital_at_T_and_no_pacu_before_T": sum(r[f"cohort{sfx}"] for r in vals),
            "T1_excluded_procedure_before_T_date": sum(r[f"cohort{sfx}"] and r[f"T1_excluded_before{sfx}"] for r in vals),
            "T1_same_day_ambiguous": sum(r[f"cohort{sfx}"] and r[f"T1_same_day_ambiguous{sfx}"] for r in vals),
            "T1_text_only_evidence": sum(r[f"cohort{sfx}"] and r[f"T1_text_only{sfx}"] for r in vals),
            "icu_before_T": sum(r[f"cohort{sfx}"] and r[f"icu_before{sfx}"] for r in vals),
        }
    meta["anchor_source"] = Counter(r["anchor_source"] for r in table.values())
    meta["lab_itemids_matched"] = Counter(item_to_feat.values())
    return table, meta


def write_table(table, out_path):
    cols = sorted({k for r in table.values() for k in r if not k.startswith("_") or k.startswith("_max_feature")})
    cols += sorted({k for r in table.values() for k in r if k.startswith("_pacu")})
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in table.values():
            w.writerow({k: r.get(k, "") for k in cols})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--framework-dir", required=True)
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm")
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--data-root", help="override PREFLIGHT_DATA_ROOT")
    ap.add_argument("--skip-labs", action="store_true",
                    help="build without labevents (lab features left missing; for Stage A / X0 only)")
    args = ap.parse_args(argv)
    if args.data_root:
        schemas.DATA_ROOT = Path(args.data_root)
    cdm = schemas.require("mimic_cdm")
    hosp_names = ["admissions.csv.gz", "patients.csv.gz", "transfers.csv.gz", "procedures_icd.csv.gz",
                  "d_labitems.csv.gz"] + ([] if args.skip_labs else ["labevents.csv.gz"])
    hosp = schemas.require("mimiciv_hosp", hosp_names)
    ed = schemas.require("mimiciv_ed")
    note = schemas.require("mimiciv_note", ["radiology.csv.gz"])
    priv = private_dir(args.private_dir)
    table, meta = build(cdm["pathology_ids.json"].parent, hosp, ed, note, args.framework_dir, args.landmarks,
                        skip_labs=args.skip_labs)
    name = "mimic_cdm_landmark_table" + ("_nolabs" if args.skip_labs else "")
    write_table(table, priv / f"{name}.csv")
    print(f"wrote private table ({len(table)} rows) to {priv}")
    write_json(args.out, "table_build", meta)


if __name__ == "__main__":
    main()
