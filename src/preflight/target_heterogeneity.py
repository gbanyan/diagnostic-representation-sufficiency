"""Stage A: residual variability of a target within diagnosis groups.

Categorical/binary Y: H(Y|D) in bits, per-D entropy and majority share.
Continuous Y: within-D variance, IQR, and the share of variance explained by D.

  python -m src.preflight.target_heterogeneity --dataset mimic_cdm --target T1 --landmark 6
"""

import argparse
import math
import statistics
from collections import Counter, defaultdict

from src.preflight import targets
from src.preflight.reporting import count_share, private_dir, suppress, write_json


def entropy_bits(counts):
    n = sum(counts.values())
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c) if n else math.nan


def stage_a(pairs, ytype):
    by_d = defaultdict(list)
    for row, y in pairs:
        by_d[row["D"]].append(y)
    n = len(pairs)
    out = {"n": n, "by_diagnosis": {}}
    if ytype in ("binary", "categorical"):
        overall = Counter(y for _, y in pairs)
        out["H_Y_bits"] = entropy_bits(overall)
        h_cond, all_det = 0.0, True
        for d, ys in sorted(by_d.items()):
            c = Counter(ys)
            h = entropy_bits(c)
            maj = max(c.values()) / len(ys)
            all_det = all_det and maj >= 0.97
            h_cond += len(ys) / n * h
            out["by_diagnosis"][d] = {
                "n": len(ys), "H_bits": h, "majority_share": round(maj, 3),
                "distribution": {str(k): count_share(v, len(ys)) for k, v in sorted(c.items())},
            }
        out["H_Y_given_D_bits"] = h_cond
        out["I_Y_D_bits"] = out["H_Y_bits"] - h_cond
        out["near_deterministic_given_D"] = bool(h_cond < 0.10 or all_det)
    else:
        ys_all = [y for _, y in pairs]
        mean_all = statistics.fmean(ys_all)
        sst = sum((y - mean_all) ** 2 for y in ys_all)
        ssw = 0.0
        for d, ys in sorted(by_d.items()):
            m = statistics.fmean(ys)
            ssw += sum((y - m) ** 2 for y in ys)
            q = statistics.quantiles(ys, n=4) if len(ys) > 1 else [ys[0]] * 3
            out["by_diagnosis"][d] = {"n": suppress(len(ys)), "mean": m,
                                      "var": statistics.pvariance(ys), "q1": q[0], "median": q[1], "q3": q[2]}
        out["var_total"] = sst / len(ys_all)
        out["var_within_D"] = ssw / len(ys_all)
        out["share_variance_explained_by_D"] = 1 - ssw / sst if sst else math.nan
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["mimic_cdm"], required=True)
    ap.add_argument("--target", choices=sorted(targets.TARGETS), nargs="+", required=True)
    ap.add_argument("--diagnosis", default="D", help="diagnosis column (D = D_final for MIMIC-CDM)")
    ap.add_argument("--landmark", type=int, default=6)
    ap.add_argument("--private-dir")
    ap.add_argument("--table-name", default="mimic_cdm_landmark_table",
                    help="private table basename (e.g. mimic_cdm_landmark_table_nolabs)")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm")
    args = ap.parse_args(argv)
    if args.diagnosis != "D":
        raise SystemExit("Only D (= D_final) is available for MIMIC-CDM; no substitution is made.")
    table = private_dir(args.private_dir) / f"{args.table_name}.csv"
    if not table.exists():
        raise SystemExit(f"{table} not found; run src.preflight.mimic_cdm_table first")
    results = {}
    for t in args.target:
        spec = targets.TARGETS[t]
        pairs, col = targets.load_rows(table, t, args.landmark)
        res = {"label": spec["label"], "column": col, "type": spec["type"],
               "diagnosis_object": "D_final",
               "d_role": "post-diagnostic reference" if spec["stage_b"] else "stratifier only (examination target)"}
        res.update(stage_a(pairs, spec["type"]))
        results[t] = res
    write_json(args.out, f"stage_a_L{args.landmark}", results)


if __name__ == "__main__":
    main()
