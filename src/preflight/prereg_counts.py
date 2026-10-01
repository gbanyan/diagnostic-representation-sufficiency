"""Aggregate cohort counts for docs/main_experiment_preregistration.md (no modeling).

For a landmark table: counts per diagnosis x outcome x era for T1 (GREEN-only primary and
exclude-RED sensitivity), T3, and the negative controls T5 / M3 / M5. Counts < 10 suppressed.

  python -m src.preflight.prereg_counts --table-name mimic_iv_expanded_dxproc_landmark_table \
      --med-table mimic_iv_expanded_landmark_table__mimic_cdm_med_targets
"""

import argparse
import csv
from collections import Counter, defaultdict

from src.preflight import targets
from src.preflight.reporting import private_dir, suppress, write_json


def load_csv(path):
    with open(path, newline="") as f:
        return {r["hadm_id"]: r for r in csv.DictReader(f)}


def tabulate(rows, ycol):
    by = defaultdict(Counter)
    era = Counter()
    for r in rows:
        y = targets._f(r.get(ycol))
        by[r["D"]]["events" if y == 1 else "non_events"] += 1
        era[r.get("anchor_year_group") or "missing"] += 1
    total_ev = sum(c["events"] for c in by.values())
    return {"n": len(rows), "events": suppress(total_ev),
            "by_diagnosis": {d: {k: suppress(v) for k, v in c.items()} for d, c in sorted(by.items())},
            "era": {k: suppress(v) for k, v in sorted(era.items())}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table-name", required=True)
    ap.add_argument("--med-table", help="companion medication-target table (hadm_id-keyed)")
    ap.add_argument("--landmark", type=int, default=6)
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/phase0/prereg")
    args = ap.parse_args(argv)
    priv = private_dir(args.private_dir)
    table_path = priv / f"{args.table_name}.csv"
    table = load_csv(table_path)
    timing = load_csv(targets.companion(table_path, "t1_timing_classes"))
    med = load_csv(priv / f"{args.med_table}.csv") if args.med_table else {}
    L, sfx = args.landmark, f"_L{args.landmark}"
    base = [r for r in table.values() if targets._f(r.get(f"cohort{sfx}")) == 1]
    t1 = [r for r in base if targets._f(r.get(f"T1_excluded_before{sfx}")) != 1]
    cls = lambda r: timing.get(r["hadm_id"], {}).get(f"timing_class{sfx}")
    out = {
        "table": args.table_name, "landmark_h": L,
        "landmark_cohort": len(base),
        "T1_all": tabulate(t1, f"Y_T1_procedure{sfx}"),
        "T1_primary_green_only": tabulate([r for r in t1 if cls(r) == "GREEN"], f"Y_T1_procedure{sfx}"),
        "T1_sensitivity_exclude_red": tabulate([r for r in t1 if cls(r) in ("GREEN", "YELLOW")],
                                               f"Y_T1_procedure{sfx}"),
        "T1_timing_classes_positives": {k: suppress(v) for k, v in Counter(
            cls(r) for r in t1 if targets._f(r.get(f"Y_T1_procedure{sfx}")) == 1).items()},
        "T3": tabulate([r for r in base if targets._f(r.get(f"icu_before{sfx}")) != 1], f"Y_T3_icu{sfx}"),
        "T5_operated_organ": {"n": suppress(sum(1 for r in base if r.get("Y_T5_organ"))),
                              "by_diagnosis_x_organ": {f"{d}|{o}": suppress(n) for (d, o), n in sorted(Counter(
                                  (r["D"], r["Y_T5_organ"]) for r in base if r.get("Y_T5_organ")).items())}},
    }
    if med:
        for key, col in (("M3_enoxaparin", f"Y_M3_enoxaparin{sfx}"), ("M5_anaerobic", f"Y_M5_anaerobic{sfx}")):
            rows = [{**r, **med[r["hadm_id"]]} for r in base
                    if r["hadm_id"] in med and med[r["hadm_id"]].get(col) not in ("", None)]
            out[key] = tabulate(rows, col)
    write_json(args.out, f"counts_{args.table_name}_L{L}", out)


if __name__ == "__main__":
    main()
