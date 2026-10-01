"""File availability and, for built tables, feature/target coverage.

  python -m src.preflight.coverage --dataset <mimic_cdm|mimiciv_hosp|mimiciv_ed|mimiciv_note|eicu|all>
  python -m src.preflight.coverage --dataset mimic_cdm --table   # missingness in the landmark table

Missing or still-downloading files are reported as such; nothing is substituted.
"""

import argparse
import csv
import math
from collections import defaultdict

from src.preflight import schemas, targets
from src.preflight.reporting import pct, private_dir, write_json


def availability(names):
    out = {}
    for ds in names:
        present, problems = schemas.check(ds)
        out[ds] = {"root": str(schemas.DATA_ROOT / schemas.DATASETS[ds]["root"]),
                   "present": present, "problems": problems}
    return out


def table_coverage(table_path, landmarks):
    with open(table_path, newline="") as f:
        rows = list(csv.DictReader(f))
    out = {"rows": len(rows), "by_landmark": {}}
    for L in landmarks:
        cohort = [r for r in rows if targets._f(r.get(f"cohort_L{L}")) == 1]
        miss = defaultdict(dict)
        for name, feats in targets.feature_sets(L).items():
            for feat in feats:
                n_missing = sum(math.isnan(targets._f(r.get(feat))) for r in cohort)
                miss[name][feat] = pct(n_missing, len(cohort))
        out["by_landmark"][f"L{L}"] = {"cohort": len(cohort), "pct_missing": miss}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, choices=sorted(schemas.DATASETS) + ["all"])
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--private-dir")
    ap.add_argument("--table-name", default="mimic_cdm_landmark_table",
                    help="private table basename (e.g. mimic_cdm_landmark_table_nolabs)")
    ap.add_argument("--out", default="results/phase0/sufficiency")
    args = ap.parse_args(argv)
    if args.table:
        if args.dataset != "mimic_cdm":
            raise SystemExit("--table is implemented for mimic_cdm only")
        table = private_dir(args.private_dir) / f"{args.table_name}.csv"
        if not table.exists():
            raise SystemExit(f"{table} not found; run src.preflight.mimic_cdm_table first")
        write_json(f"{args.out}/mimic_cdm", "table_coverage", table_coverage(table, args.landmarks))
        return
    names = sorted(schemas.DATASETS) if args.dataset == "all" else [args.dataset]
    res = availability(names)
    write_json(args.out, "file_availability", res)
    for ds, v in res.items():
        print(f"{ds}: {len(v['present'])} present, {len(v['problems'])} problems")
        for p in v["problems"]:
            print("  ", p)


if __name__ == "__main__":
    main()
