"""Leakage assertions on the MIMIC-CDM landmark table (stopping criterion D).

For each landmark L, verify on every cohort row:
  - no feature is timestamped after T = t0 + L;
  - every positive time-stamped target (T2, T9) occurs at or after T;
  - no cohort row has a PACU stay before T.
Any violation fails the check; the report lists counts only.

  python -m src.preflight.leakage_checks --dataset mimic_cdm --landmarks 3 6
"""

import argparse
import csv

from src.preflight.reporting import private_dir, write_json
from src.preflight.targets import _f


def check(table_path, landmarks):
    out = {}
    with open(table_path, newline="") as f:
        rows = list(csv.DictReader(f))
    for L in landmarks:
        sfx = f"_L{L}"
        cohort = [r for r in rows if _f(r.get(f"cohort{sfx}")) == 1]
        feat_late = sum(_f(r.get(f"_max_feature_offset_h{sfx}")) > L + 1e-9 for r in cohort)
        pacu_early = sum(_f(r.get("_pacu_first_h")) < L for r in cohort)
        t9_early = sum(_f(r.get(f"Y_T9_hours_to_pacu{sfx}")) < L for r in cohort)
        t2_inconsistent = sum(_f(r.get(f"Y_T2_pacu{sfx}")) == 1 and not _f(r.get(f"Y_T9_hours_to_pacu{sfx}")) >= L
                              for r in cohort)
        out[f"L{L}"] = {
            "cohort_rows": len(cohort),
            "rows_with_feature_after_T": feat_late,
            "rows_with_pacu_before_T": pacu_early,
            "rows_with_T9_before_T": t9_early,
            "rows_with_T2_positive_without_post_T_pacu": t2_inconsistent,
            "pass": feat_late == 0 and pacu_early == 0 and t9_early == 0 and t2_inconsistent == 0,
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["mimic_cdm"], required=True)
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--private-dir")
    ap.add_argument("--table-name", default="mimic_cdm_landmark_table",
                    help="private table basename (e.g. mimic_cdm_landmark_table_nolabs)")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm")
    args = ap.parse_args(argv)
    table = private_dir(args.private_dir) / f"{args.table_name}.csv"
    if not table.exists():
        raise SystemExit(f"{table} not found; run src.preflight.mimic_cdm_table first")
    res = check(table, args.landmarks)
    write_json(args.out, "leakage_checks", res)
    if not all(v["pass"] for v in res.values()):
        raise SystemExit("LEAKAGE CHECK FAILED: see leakage_checks.json")


if __name__ == "__main__":
    main()
