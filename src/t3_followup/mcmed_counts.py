"""MC-MED counts-only step (docs/t3_followup_design.md checklist item 2).

Reports cohort sizes needed to fix the design BEFORE registration. It never splits the
admitted group by ICU vs non-ICU: admitted = Inpatient + Observation + ICU, reported combined.

  python -m src.t3_followup.mcmed_counts --root /mnt/SAM1TB/dev/data/mc-med/1.0.1
"""

import argparse
import csv
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.preflight.reporting import suppress, write_json

ADMITTED = {"Inpatient", "Observation", "ICU"}
ABDOMINAL = {"appendicitis": "appendicitis", "cholecystitis": "cholecystitis",
             "diverticulitis": "diverticulitis", "acute pancreatitis": "pancreatitis"}


def ts(v):
    try:
        return datetime.fromisoformat((v or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def split_map(root):
    m = {}
    for name in ("train", "val", "test"):
        p = root / "data" / f"split_chrono_{name}.csv"
        with open(p, newline="") as f:
            r = csv.reader(f)
            head = next(r)
            col = head.index("CSN") if "CSN" in head else 0
            for row in r:
                m[row[col]] = name
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="results/t3_followup/mcmed_counts")
    args = ap.parse_args(argv)
    root = Path(args.root)
    splits = split_map(root)
    total = adults = admitted = 0
    mrns, adm_mrns = set(), set()
    hours, chapters, cats, abd, split_ct, split_ct_elig = [], Counter(), Counter(), Counter(), Counter(), Counter()
    elig3 = elig6 = missing_times = 0
    with open(root / "data" / "visits.csv", newline="") as f:
        for r in csv.DictReader(f):
            total += 1
            mrns.add(r["MRN"])
            try:
                age = float(r["Age"])
            except ValueError:
                continue
            if age < 18:
                continue
            adults += 1
            if r["ED_dispo"] not in ADMITTED:
                continue
            admitted += 1
            adm_mrns.add(r["MRN"])
            split_ct[splits.get(r["CSN"], "unassigned")] += 1
            a, d = ts(r["Arrival_time"]), ts(r["Dispo_time"])
            if not (a and d):
                missing_times += 1
                continue
            h = (d - a).total_seconds() / 3600
            hours.append(h)
            if h > 6:
                elig6 += 1
            if h <= 3:
                continue
            elig3 += 1
            split_ct_elig[splits.get(r["CSN"], "unassigned")] += 1
            code = (r["Dx_ICD10"] or "").strip()
            chapters[code[:1] or "missing"] += 1
            cats[code[:3] or "missing"] += 1
            name = (r["Dx_name"] or "").lower()
            for key, lab in ABDOMINAL.items():
                if key in name:
                    abd[lab] += 1
    q = statistics.quantiles(hours, n=20) if len(hours) > 20 else None
    write_json(args.out, "counts", {
        "note": "counts only; admitted = Inpatient + Observation + ICU combined; ICU not examined",
        "visits": total, "patients": len(mrns), "adult_visits": adults,
        "admitted_adult_visits": admitted, "admitted_patients": len(adm_mrns),
        "admitted_missing_arrival_or_dispo_time": suppress(missing_times),
        "hours_arrival_to_dispo_decision": {"p5": q[0], "p25": q[4], "median": q[9], "p75": q[14], "p95": q[18]} if q else None,
        "admitted_with_dispo_after_3h": elig3, "admitted_with_dispo_after_6h": elig6,
        "chrono_split_admitted": {k: suppress(v) for k, v in split_ct.items()},
        "chrono_split_eligible_3h": {k: suppress(v) for k, v in split_ct_elig.items()},
        "eligible_3h_by_icd10_chapter": {k: suppress(v) for k, v in chapters.most_common()},
        "eligible_3h_top_icd10_3char": {k: suppress(v) for k, v in cats.most_common(40)},
        "eligible_3h_four_abdominal": {k: suppress(v) for k, v in abd.items()},
    })


if __name__ == "__main__":
    main()
