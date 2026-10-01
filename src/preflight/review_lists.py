"""Prepare case lists for the DEFERRED clinician review (Q15). No interpretation.

Writes to the private directory only:
  q15_t1_review_sample.csv : stratified sample (D x T1 outcome), fixed seed, with hadm_id,
                             D, outcome, and timing class. No clinical fields are summarized.
and an aggregate count file (stratum sizes) to --out.

Q15 status: DEFERRED - AUTHOR DECISION PENDING. This script does not perform, simulate, or
substitute clinician review, and no LLM is involved.
"""

import argparse
import csv
import random
from collections import defaultdict

from src.preflight.reporting import private_dir, suppress, write_json
from src.preflight.targets import _f

SEED = 20260929


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--landmark", type=int, default=6)
    ap.add_argument("--per-stratum", type=int, default=15)
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm/q15_prep")
    args = ap.parse_args(argv)
    priv = private_dir(args.private_dir)
    L = args.landmark
    with open(priv / "t1_timing_classes.csv", newline="") as f:
        timing = {r["hadm_id"]: r[f"timing_class_L{L}"] for r in csv.DictReader(f)}
    strata = defaultdict(list)
    with open(priv / "mimic_cdm_landmark_table.csv", newline="") as f:
        for r in csv.DictReader(f):
            if _f(r.get(f"cohort_L{L}")) != 1 or _f(r.get(f"T1_excluded_before_L{L}")) == 1:
                continue
            cls = timing.get(r["hadm_id"])
            if cls == "RED":
                continue  # not part of the primary cohort
            y = int(_f(r[f"Y_T1_procedure_L{L}"]))
            strata[(r["D"], y)].append((r["hadm_id"], cls))
    rng = random.Random(SEED)
    rows = []
    for (d, y), members in sorted(strata.items()):
        for h, cls in rng.sample(sorted(members), min(args.per_stratum, len(members))):
            rows.append({"hadm_id": h, "D": d, "T1_procedure": y, "timing_class": cls})
    with open(priv / "q15_t1_review_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hadm_id", "D", "T1_procedure", "timing_class"])
        w.writeheader()
        w.writerows(rows)
    write_json(args.out, "q15_review_sample_strata", {
        "status": "DEFERRED - AUTHOR DECISION PENDING; list prepared only, not reviewed or interpreted",
        "landmark_h": L, "seed": SEED, "per_stratum": args.per_stratum,
        "stratum_sizes": {f"{d}|procedure={y}": suppress(len(m)) for (d, y), m in sorted(strata.items())},
        "sampled": len(rows),
    })


if __name__ == "__main__":
    main()
