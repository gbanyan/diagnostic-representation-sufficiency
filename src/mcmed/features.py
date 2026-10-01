"""X_3h: legitimate patient state at T = arrival + 3 h (GREEN features only).

  python -m src.mcmed.features extract   # raw per-visit extraction (no selection), private
  python -m src.mcmed.features build     # development-derived vocabularies -> private X matrix

Timing rules enforced (and asserted): lab values only if Result_time <= T; numerics only if
Time <= T; PMH only if Noted_date < arrival date. Orders, consults, treatments, oxygen flow,
imaging text, home medications, and every post-decision field are never read here.
Selection rules (coverage thresholds, vocabularies, log1p) use development visits only and
never the outcome.
"""

import argparse
import csv
import math
import pickle
import statistics
from array import array
from collections import Counter, defaultdict

import numpy as np
from scipy.stats import skew

from src.mcmed.common import OUT, config, data_path, private, read_cohort, read_split, ts
from src.preflight.reporting import count_share, write_json

TRIAGE = {"Triage_HR": "HR", "Triage_RR": "RR", "Triage_SpO2": "SpO2", "Triage_SBP": "SBP", "Triage_DBP": "DBP"}
EXCLUDED_LAB_SUBSTRINGS = ("AFRICAN AMERICAN",)  # race-based calculations (race is excluded from primary X)
FORBIDDEN = ("Dx_", "Admit", "Dispo", "ED_dispo", "Payor", "Race", "Ethnicity", "LPM_O2", "consult", "order",
             "Roomed", "Visits", "Visit_no", "Hosp_LOS", "ED_LOS", "Departure", "DC_dispo", "next_visit")


def fnum(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return math.nan
    return x if math.isfinite(x) else math.nan


def lab_value(v):
    """Numeric lab value; censored results such as '<0.01' or '>500' take the limit value."""
    v = (v or "").strip().lstrip("<>=").strip()
    return fnum(v)


def lab_flag(v):
    """Component_abnormal: Normal -> 0; Abnormal/Critical (any direction) -> 1; blank -> missing."""
    v = (v or "").strip()
    return math.nan if not v else (0.0 if v == "Normal" else 1.0)


def bounded(x, b):
    return x if (not math.isnan(x) and b[0] <= x <= b[1]) else math.nan


def bound_key(measure):
    return "HRV" if measure.endswith("HRV") else ("Temp_F" if measure == "Temp" else measure)


def esi(v):
    v = (v or "").strip()
    return float(v[0]) if v[:1].isdigit() else math.nan


def cc_tokens(v):
    return sorted({t.strip().upper() for t in (v or "").split(",") if t.strip()})


# --- extraction (all cohort visits; no selection) ---------------------------------------

def extract(cfg):
    rows = read_cohort(cfg)
    by = {r["CSN"]: r for r in rows}
    A = {c: ts(r["Arrival_time"]) for c, r in by.items()}
    T = {c: ts(r["T"]) for c, r in by.items()}
    b = cfg["features"]["bounds"]
    base, counts = {}, Counter()
    with open(data_path(cfg, "visits.csv"), newline="") as f:
        for v in csv.DictReader(f):
            if v["CSN"] not in by:
                continue
            temp_c = fnum(v["Triage_Temp"])
            d = {"age": fnum(v["Age"]), "sex": v["Gender"] or "MISSING", "arrival_mode": v["Means_of_arrival"] or "MISSING",
                 "triage_Temp": bounded(temp_c * 9 / 5 + 32, b["Temp_F"]) if not math.isnan(temp_c) else math.nan,
                 "triage_ESI": bounded(esi(v["Triage_acuity"]), b["ESI"]), "cc": cc_tokens(v["CC"]),
                 "race": v["Race"] or "MISSING", "ethnicity": v["Ethnicity"] or "MISSING"}
            for src, m in TRIAGE.items():
                x = fnum(v[src])
                d[f"triage_{m}"] = bounded(x, b[m])
                counts[f"triage_{m}_out_of_bounds"] += int(not math.isnan(x) and math.isnan(d[f"triage_{m}"]))
            base[v["CSN"]] = d
    assert len(base) == len(by)

    labs = defaultdict(dict)  # csn -> component -> (result_time, value, abnormal flag); first result by T
    with open(data_path(cfg, "labs.csv"), newline="") as f:
        for l in csv.DictReader(f):
            c = l["CSN"]
            if c not in by:
                continue
            rt = ts(l["Result_time"])
            if rt is None or rt > T[c]:
                continue
            comp = l["Component_name"]
            if any(s in comp.upper() for s in EXCLUDED_LAB_SUBSTRINGS):
                counts["lab_rows_excluded_race_based"] += 1
                continue
            val, flag = lab_value(l["Component_value"]), lab_flag(l["Component_abnormal"])
            counts["lab_rows_resulted_by_T_non_numeric"] += int(math.isnan(val))
            prev = labs[c].get(comp)
            if prev is None or rt < prev[0]:
                labs[c][comp] = (rt, val, flag)
    for c, comps in labs.items():
        assert all(rt <= T[c] for rt, _, _ in comps.values())
    labs = {c: {k: (v, fl) for k, (_, v, fl) in comps.items()} for c, comps in labs.items()}

    pmh_by_mrn = defaultdict(list)
    mrns = {r["MRN"] for r in rows}
    with open(data_path(cfg, "pmh.csv"), newline="") as f:
        for p in csv.DictReader(f):
            if p["MRN"] in mrns:
                d = ts(p["Noted_date"])
                if d is not None:
                    pmh_by_mrn[p["MRN"]].append((d.date(), p["CCS"] or "", p["Code"]))
    pmh = {}
    for c, r in by.items():
        day = A[c].date()
        prior = [(ccs, code) for d, ccs, code in pmh_by_mrn.get(r["MRN"], ()) if d < day]
        pmh[c] = {"ccs": sorted({ccs for ccs, _ in prior if ccs}), "n_codes": len({code for _, code in prior})}

    measures = set(cfg["features"]["numerics_measures"])
    excluded = set(cfg["features"]["numerics_excluded"])
    Tz = {c: t.strftime("%Y-%m-%dT%H:%M:%SZ") for c, t in T.items()}
    series = defaultdict(lambda: (array("d"), array("d")))
    ncount = Counter()
    seen_any, last_csn, blocks = set(), None, Counter()
    with open(data_path(cfg, "numerics.csv")) as f:
        head = f.readline().strip().split(",")
        assert head == ["CSN", "Source", "Measure", "Value", "Time"], head
        for line in f:
            ncount["rows"] += 1
            s = line.rstrip("\n").split(",")
            if len(s) != 5:
                ncount["malformed_rows"] += 1
                continue
            c = s[0]
            if c != last_csn:
                blocks[c] += 1
                last_csn = c
            if c not in Tz:
                continue
            seen_any.add(c)
            m, t = s[2], s[4]
            if m in excluded:
                ncount["excluded_measure_rows"] += 1
                continue
            if m not in measures:
                ncount["unknown_measure_rows"] += 1
                continue
            if not (len(t) == 20 and t.endswith("Z")):
                tt = ts(t)
                if tt is None:
                    ncount["unparsed_time_rows"] += 1
                    continue
                t = tt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if t > Tz[c]:
                continue
            x = bounded(fnum(s[3]), b[bound_key(m)])
            if math.isnan(x):
                ncount[f"{m}_out_of_bounds_or_non_numeric_by_T"] += 1
                continue
            hrs = (ts(t) - A[c]).total_seconds() / 3600
            tv, vv = series[(c, m)]
            tv.append(hrs)
            vv.append(x)
    assert all(max(series[k][0]) <= 3.0 + 1e-9 for k in series)
    numerics = defaultdict(dict)
    for (c, m), (tv, vv) in series.items():
        numerics[c][m] = summarize(np.frombuffer(tv), np.frombuffer(vv))
    noncontig = sum(1 for v in blocks.values() if v > 1)
    stats = {"rows": ncount["rows"], "counts": dict(ncount),
             "cohort_visits_with_any_numerics_row": count_share(len(seen_any), len(by)),
             "cohort_visits_with_numerics_by_T": count_share(len(numerics), len(by)),
             "csns_in_file": len(blocks), "csns_non_contiguous": noncontig}
    with open(private(cfg) / "features_raw.pkl", "wb") as f:
        pickle.dump({"base": base, "labs": labs, "pmh": pmh, "numerics": dict(numerics)}, f)
    write_json(OUT, "stageA_features_extract", {"triage_and_lab_counts": dict(counts), "numerics": stats,
                                                "cohort_visits_with_lab_result_by_T": count_share(len(labs), len(by))})


def summarize(t, v):
    order = np.argsort(t, kind="stable")
    t, v = t[order], v[order]
    slope = math.nan
    if len(t) >= 2 and np.ptp(t) > 0:
        slope = float(np.polyfit(t, v, 1)[0])
    return {"first": float(v[0]), "last": float(v[-1]), "min": float(v.min()), "max": float(v.max()),
            "median": float(np.median(v)), "slope_per_hour": slope, "count": float(len(v))}


# --- build (development-derived selection) -----------------------------------------------

def build(cfg):
    fc = cfg["features"]
    rows = read_cohort(cfg)
    split = read_split(cfg)
    # features_raw.pkl is written by `extract` above into the private directory (never external input).
    with open(private(cfg) / "features_raw.pkl", "rb") as f:
        raw = pickle.load(f)
    base, labs, pmh, num = raw["base"], raw["labs"], raw["pmh"], raw["numerics"]
    dev = [r["CSN"] for r in rows if split[r["MRN"]] == "dev"]
    nd = len(dev)

    cat_levels = {k: sorted({base[c][k] for c in dev}) for k in ("sex", "arrival_mode")}
    s3_levels = {k: sorted({base[c][k] for c in dev}) for k in ("race", "ethnicity")}
    cc_n = Counter(t for c in dev for t in base[c]["cc"])
    cc_vocab = sorted(t for t, n in cc_n.items() if n >= fc["cc_min_dev_visits"])
    pmh_n = Counter(x for c in dev for x in pmh[c]["ccs"])
    pmh_vocab = sorted(x for x, n in pmh_n.items() if n / nd >= fc["pmh_min_dev_prevalence"])
    lab_n = Counter(k for c in dev for k in labs.get(c, {}))
    lab_vocab = sorted(k for k, n in lab_n.items() if n / nd >= fc["lab_min_dev_coverage"])
    # Qualitative components (< 50% numeric first results by T in development) also get the abnormal flag.
    lab_numeric = Counter(k for c in dev for k, (v, _) in labs.get(c, {}).items() if not math.isnan(v))
    lab_flagged = [k for k in lab_vocab if lab_numeric[k] / lab_n[k] < 0.5]
    num_n = Counter(m for c in dev for m in num.get(c, {}))
    num_vocab = [m for m in fc["numerics_measures"] if num_n[m] / nd >= fc["numerics_min_dev_coverage"]]
    summaries = fc["numerics_summaries"]

    names, groups = [], []

    def add(name, group):
        names.append(name)
        groups.append(group)
    add("age", "demographics")
    for k, lv in cat_levels.items():
        for level in lv:
            add(f"{k}={level}", "demographics")
    for m in ("Temp", "HR", "RR", "SpO2", "SBP", "DBP", "ESI"):
        add(f"triage_{m}", "triage")
    for t in cc_vocab:
        add(f"cc_tok_{cc_vocab.index(t)}", "chief_complaint")
    add("cc_other_token", "chief_complaint")
    add("cc_missing", "chief_complaint")
    for x in pmh_vocab:
        add(f"pmh_ccs={x}", "pmh")
    add("pmh_n_codes", "pmh")
    for k in lab_vocab:
        add(f"lab={k}", "labs")
    for k in lab_flagged:
        add(f"lab_abnormal={k}", "labs")
    for m in num_vocab:
        for s in summaries:
            add(f"num_{m}_{s}", "numerics")
    # Structural guard: no feature may be built from a forbidden visits/orders field. Lab component and
    # PMH category names are values drawn from GREEN tables (e.g. a "trace" lab would match "race"), so
    # they are exempt from the substring check.
    structural = [n for n in names if not n.startswith(("lab=", "lab_abnormal=", "pmh_ccs="))]
    assert not any(any(bad.lower() in n.lower() for bad in FORBIDDEN) for n in structural), "forbidden feature name"

    ccset = set(cc_vocab)

    def vec(c):
        b = base[c]
        v = [b["age"]]
        for k, lv in cat_levels.items():
            v += [1.0 if b[k] == level else 0.0 for level in lv]
        v += [b[f"triage_{m}"] for m in ("Temp", "HR", "RR", "SpO2", "SBP", "DBP", "ESI")]
        toks = set(b["cc"])
        v += [1.0 if t in toks else 0.0 for t in cc_vocab]
        v += [1.0 if toks - ccset else 0.0, 0.0 if toks else 1.0]
        ps = set(pmh[c]["ccs"])
        v += [1.0 if x in ps else 0.0 for x in pmh_vocab] + [float(pmh[c]["n_codes"])]
        lc = labs.get(c, {})
        v += [lc[k][0] if k in lc else math.nan for k in lab_vocab]
        v += [lc[k][1] if k in lc else math.nan for k in lab_flagged]
        nc = num.get(c, {})
        for m in num_vocab:
            sm = nc.get(m)
            v += [(sm[s] if sm else (0.0 if s == "count" else math.nan)) for s in summaries]
        return v

    csns = [r["CSN"] for r in rows]
    X = np.array([vec(c) for c in csns], float)
    S3 = np.array([[1.0 if base[c][k] == level else 0.0 for k, lv in s3_levels.items() for level in lv] for c in csns])
    s3_names = [f"{k}={level}" for k, lv in s3_levels.items() for level in lv]
    is_dev = np.array([split[r["MRN"]] == "dev" for r in rows])
    binary = np.array([set(np.unique(X[is_dev, j][~np.isnan(X[is_dev, j])])) <= {0.0, 1.0} for j in range(X.shape[1])])
    log_cols = []
    for j in range(X.shape[1]):
        col = X[is_dev, j]
        col = col[~np.isnan(col)]
        if binary[j] or len(col) < 3 or col.min() < 0:
            continue
        if skew(col) > 2:
            log_cols.append(j)
    for j in log_cols:
        X[:, j] = np.log1p(X[:, j])
    np.savez_compressed(private(cfg) / "X.npz", X=X, S3=S3, csn=np.array(csns), names=np.array(names),
                        s3_names=np.array(s3_names), groups=np.array(groups))
    (private(cfg) / "cc_vocab.txt").write_text("\n".join(cc_vocab))
    import hashlib
    write_json(OUT, "stageA_features_build", {
        "development_visits": nd, "n_features": len(names),
        "features_by_group": dict(Counter(groups)),
        "cc_vocab": {"size": len(cc_vocab), "sha256": hashlib.sha256("\n".join(cc_vocab).encode()).hexdigest(),
                     "rule": f">= {fc['cc_min_dev_visits']} development visits; tokens kept private"},
        "pmh_ccs_categories": pmh_vocab, "lab_components": {k: round(lab_n[k] / nd, 3) for k in lab_vocab},
        "lab_components_with_abnormal_flag": lab_flagged,
        "numerics_coverage_dev": {m: round(num_n[m] / nd, 3) for m in fc["numerics_measures"]},
        "numerics_included": num_vocab,
        "categorical_levels": {k: len(v) for k, v in cat_levels.items()},
        "s3_levels": {k: len(v) for k, v in s3_levels.items()},
        "log1p_columns": [names[j] for j in log_cols],
        "missing_share_dev": {n: round(float(np.isnan(X[is_dev, j]).mean()), 3) for j, n in enumerate(names)
                              if np.isnan(X[is_dev, j]).any()},
        "timing_assertions": "lab Result_time <= T; numerics Time <= T; PMH Noted_date < arrival date; forbidden names absent",
    })


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["extract", "build"])
    a = ap.parse_args(argv)
    cfg = config()
    if (private(cfg) / "dhat_body_primary.npz").exists():
        raise SystemExit("CONFIRMATORY ANALYSIS FROZEN: X_3h is fixed once D_hat exists")
    extract(cfg) if a.command == "extract" else build(cfg)


if __name__ == "__main__":
    main()
