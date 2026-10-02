"""MIMIC-IV lab result availability: audit and variant table (see plan.md).

Run on gbminipc from the repo root:
  python -m exploratory.lab_availability.audit [--write-variant]
Writes aggregates to exploratory/lab_availability/results/audit.json. With --write-variant, also
writes the private table <table>_labavail.csv (lab_*_L6 restricted to storetime <= T) and links
the timing-class companion file under the new table name.
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from audit.cdm_audit import open_text
from src.preflight import schemas
from src.preflight import simple_incremental_models as sim
from src.preflight.mimic_cdm_table import LAB_FEATURES, LAB_LOOKBACK_H, parse_time
from src.preflight.reporting import private_dir

TABLE = "mimic_iv_expanded_dxproc_landmark_table"
L = 6
OUT = Path(__file__).resolve().parent / "results" / "audit.json"


def cnt(k):
    return k if k >= 10 else "<10"


def scan(hosp, rows):
    label_to_feat = {(lab, fluid): f for f, lab, fluid in LAB_FEATURES}
    item_to_feat = {}
    for r in csv.DictReader(open_text(hosp["d_labitems.csv.gz"])):
        f = label_to_feat.get((r["label"], r["fluid"]))
        if f:
            item_to_feat[r["itemid"]] = f
    by_subject = defaultdict(list)
    for h, r in rows.items():
        by_subject[r["subject_id"]].append(h)
    orig, avail = {}, {}  # (h, feat) -> (charttime, value, storetime)
    with open_text(hosp["labevents.csv.gz"]) as f:
        rd = csv.reader(f)
        head = next(rd)
        ix = {k: head.index(k) for k in ("subject_id", "hadm_id", "itemid", "charttime", "storetime", "valuenum")}
        for r in rd:
            hs = by_subject.get(r[ix["subject_id"]])
            if not hs:
                continue
            feat = item_to_feat.get(r[ix["itemid"]])
            if not feat:
                continue
            try:
                v = float(r[ix["valuenum"]])
            except ValueError:
                continue
            if math.isnan(v):
                continue
            t, st, rh = parse_time(r[ix["charttime"]]), parse_time(r[ix["storetime"]]), r[ix["hadm_id"]]
            for h in hs:
                if rh and int(float(rh)) != h:
                    continue
                t0 = rows[h]["t0"]; T = t0 + timedelta(hours=L)
                if not (t and t0 - timedelta(hours=LAB_LOOKBACK_H) <= t <= T):
                    continue
                k = (h, feat)
                if k not in orig or t < orig[k][0]:
                    orig[k] = (t, v, st)
                if st and st <= T and (k not in avail or t < avail[k][0]):
                    avail[k] = (t, v, st)
    return orig, avail


def summarize(hs, rows, orig, avail, y=None):
    feats = [f for f, _, _ in LAB_FEATURES]
    used = [(h, f) for h in hs for f in feats if (h, f) in orig]
    late = [(h, f) for h, f in used if orig[(h, f)][2] and orig[(h, f)][2] > rows[h]["t0"] + timedelta(hours=L)]
    nost = [(h, f) for h, f in used if not orig[(h, f)][2]]
    lags = [(orig[k][2] - (rows[k[0]]["t0"] + timedelta(hours=L))).total_seconds() / 3600 for k in late]
    lost = [k for k in used if k not in avail]
    changed = [k for k in used if k in avail and avail[k][1] != orig[k][1]]
    adm_late = {h for h, _ in late}
    out = {"admissions": len(hs), "lab_cells_used": len(used),
           "cells_storetime_after_T": cnt(len(late)), "pct_cells_late": round(100 * len(late) / len(used), 2) if used else None,
           "cells_storetime_missing": cnt(len(nost)),
           "admissions_with_any_late_cell": cnt(len(adm_late)), "pct_admissions_late": round(100 * len(adm_late) / len(hs), 1),
           "late_lag_hours_median_iqr": ([round(q, 2) for q in (statistics.median(lags), *statistics.quantiles(lags, n=4)[::2])]
                                         if len(lags) >= 10 else None),
           "variant_cells_lost": cnt(len(lost)), "variant_cells_value_changed": cnt(len(changed)),
           "per_feature_pct_late": {f: (round(100 * sum(1 for h, g in late if g == f) / n, 1) if (n := sum(1 for h, g in used if g == f)) >= 10 else None)
                                    for f in feats}}
    if y is not None:
        ev = [h for h, yy in zip(hs, y) if yy == 1]
        out["events"] = len(ev)
        out["events_with_any_late_cell"] = cnt(len(adm_late & set(ev)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-variant", action="store_true")
    a = ap.parse_args()
    pdir = private_dir(None)
    table = pdir / f"{TABLE}.csv"
    with open(table, newline="") as f:
        allrows = list(csv.DictReader(f))
    rows = {int(float(r["hadm_id"])): {"subject_id": r["subject_id"], "t0": parse_time(r["anchor_time"])} for r in allrows}
    hosp = schemas.require("mimiciv_hosp", ["d_labitems.csv.gz", "labevents.csv.gz"])
    orig, avail = scan(hosp, rows)
    # consistency with the stored table
    mism = 0
    for r in allrows:
        h = int(float(r["hadm_id"]))
        for feat, _, _ in LAB_FEATURES:
            s = r[f"lab_{feat}_L{L}"]
            stored = float(s) if s not in ("", "nan") else math.nan
            rec = orig.get((h, feat))
            if (math.isnan(stored) and rec) or (not math.isnan(stored) and (not rec or abs(rec[1] - stored) > 1e-9)):
                mism += 1
    res = {"consistency_mismatched_cells_vs_stored_table": mism}
    _, _, _, t1rows, t1y, *_ = sim.prepare(str(table), "T1", L, False, "green_only")
    res["T1_primary"] = summarize([int(float(r["hadm_id"])) for r in t1rows], rows, orig, avail, t1y)
    _, _, _, t3rows, t3y, *_ = sim.prepare(str(table), "T3", L, False, "none")
    res["T3"] = summarize([int(float(r["hadm_id"])) for r in t3rows], rows, orig, avail, t3y)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
    if a.write_variant:
        name = f"{TABLE}_labavail"
        with open(pdir / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
            w.writeheader()
            for r in allrows:
                h = int(float(r["hadm_id"])); r = dict(r)
                for feat, _, _ in LAB_FEATURES:
                    k = (h, feat)
                    r[f"lab_{feat}_L{L}"] = avail[k][1] if k in avail else ""
                w.writerow(r)
        for comp in pdir.glob(f"{TABLE}__*.csv"):
            link = pdir / comp.name.replace(f"{TABLE}__", f"{name}__")
            if not link.exists():
                link.symlink_to(comp.name)
        print("variant written:", name)


if __name__ == "__main__":
    main()
