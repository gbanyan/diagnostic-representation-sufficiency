"""Early diagnosis D_hat_t and diagnosis-formation curve; examination target T6b at S0.

Pre-registered in docs/early_diagnosis_preflight.md. D_hat_t is a model-generated experimental
bottleneck, NOT a clinician diagnosis. No LLM is used.

  python -m src.preflight.early_diagnosis vocab        # POE radiology subtype counts (cohort)
  python -m src.preflight.early_diagnosis formation    # D_final recoverability at S0 / S3h / S6h
  python -m src.preflight.early_diagnosis t6b          # G_hat_0 for first CT/US/MRI order modality
"""

import argparse
import csv
import math
import sys
import warnings
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

from audit.cdm_audit import open_text, parse_time
from src.preflight import schemas, targets
from src.preflight.reporting import count_share, private_dir, suppress, write_json
from src.preflight.simple_incremental_models import (C_GRID, OUTER_SEEDS, LN2, bootstrap, fit_transform_x,
                                                     log_columns)

csv.field_size_limit(sys.maxsize)

STAGES = {"S0": ("X0", None), "S3h": ("X2", 3), "S6h": ("X2", 6)}
IMAGING_SUBTYPES = {"CT Scan": "CT", "Ultrasound": "US", "MRI": "MRI"}


# --- data ---------------------------------------------------------------------

def load_table(priv):
    with open(priv / "mimic_cdm_landmark_table.csv", newline="") as f:
        return [r for r in csv.DictReader(f)]


def chief_complaints(ed_dir, hadm_ids):
    """Chief complaint of the earliest ED stay per admission (the anchor stay)."""
    first = {}
    for r in csv.DictReader(open_text(ed_dir / "edstays.csv.gz")):
        if r["hadm_id"]:
            h = str(int(float(r["hadm_id"])))
            t = parse_time(r["intime"])
            if h in hadm_ids and t and (h not in first or t < first[h][0]):
                first[h] = (t, r["stay_id"])
    stay_to_h = {v[1]: h for h, v in first.items()}
    cc = {}
    for r in csv.DictReader(open_text(ed_dir / "triage.csv.gz")):
        h = stay_to_h.get(r["stay_id"])
        if h:
            cc[h] = (r.get("chiefcomplaint") or "").lower()
    return cc


def stage_features(stage):
    set_name, landmark = STAGES[stage]
    return targets.feature_sets(landmark or 6)[set_name] if landmark else targets.X0


# --- featurizer (structured + chief-complaint TF-IDF, fit on training rows only) ----------

class Featurizer:
    def __init__(self, feats, use_text):
        self.feats, self.use_text = feats, use_text

    def _x(self, rows):
        return np.array([[targets._f(r.get(f)) for f in self.feats] for r in rows])

    def fit_transform(self, rows_tr, rows_te):
        Atr, Ate = fit_transform_x(self._x(rows_tr), self._x(rows_te), log_columns(self.feats))
        if not self.use_text:
            return Atr, Ate
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=5)
        Ttr = vec.fit_transform([r["cc"] for r in rows_tr]).toarray()
        Tte = vec.transform([r["cc"] for r in rows_te]).toarray()
        return np.hstack([Atr, Ttr]), np.hstack([Ate, Tte])


def onehot(labels, levels):
    return np.array([[1.0 if l == v else 0.0 for v in levels] for l in labels])


def fit_proba(Ztr, ytr, Zte, C, classes):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = LogisticRegression(C=C, max_iter=5000).fit(Ztr, ytr)
    p = m.predict_proba(Zte)
    full = np.full((len(Zte), len(classes)), 1e-12)
    for j, c in enumerate(m.classes_):
        full[:, classes.index(c)] = p[:, j]
    return full / full.sum(axis=1, keepdims=True)


def logloss_bits(y, P, classes):
    idx = np.array([classes.index(v) for v in y])
    return -np.log(np.clip(P[np.arange(len(y)), idx], 1e-12, 1)) / LN2


def nested_proba(rows, y, groups, build, classes, seed):
    """Nested CV; build(rows_tr, rows_te) -> (Ztr, Zte). Returns cross-fitted probabilities and chosen C."""
    n = len(rows)
    P = np.zeros((n, len(classes)))
    chosen = []
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(outer.split(np.zeros(n), y, groups))
    for k, (tr, te) in enumerate(splits):
        inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed + k)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            isplits = list(inner.split(np.zeros(len(tr)), y[tr], groups[tr]))
        tot = np.zeros(len(C_GRID))
        for itr, ite in isplits:
            a, b = tr[itr], tr[ite]
            Za, Zb = build([rows[i] for i in a], [rows[i] for i in b])
            for c_i, C in enumerate(C_GRID):
                tot[c_i] += logloss_bits(y[b], fit_proba(Za, y[a], Zb, C, classes), classes).mean()
        best = C_GRID[int(np.flatnonzero(tot <= tot.min() + 1e-12)[0])]  # ties -> smaller C
        chosen.append(best)
        Ztr, Zte = build([rows[i] for i in tr], [rows[i] for i in te])
        P[te] = fit_proba(Ztr, y[tr], Zte, best, classes)
    return P, chosen


def entropy_bits(counts):
    n = sum(counts.values())
    return -sum(c / n * math.log2(c / n) for c in counts.values() if c)


# --- diagnosis formation -----------------------------------------------------------

def ed_cohort(table, cc, timing=None):
    """ED-anchored admissions. With `timing`, also restricted to the 6 h landmark cohort and to
    T1 timing class != RED, so no S3h/S6h feature can postdate an operation (leakage guard)."""
    rows = []
    for r in table:
        if r["hadm_id"] not in cc or r.get("has_ed_stay") != "1":
            continue
        if timing is not None and (targets._f(r.get("cohort_L6")) != 1 or timing.get(r["hadm_id"]) == "RED"):
            continue
        rows.append({**r, "cc": cc[r["hadm_id"]]})
    return rows


def formation(rows, out, priv):
    classes = sorted({r["D"] for r in rows})
    y = np.array([r["D"] for r in rows])
    groups = np.array([r["subject_id"] for r in rows])
    H = entropy_bits(Counter(y.tolist()))
    res = {"cohort": len(rows), "classes": classes, "H_D_bits": H, "closed_world_note":
           "4-class problem among confirmed cases; optimistic relative to a real ED differential",
           "stages": {}}
    dhat = {}
    for stage in STAGES:
        feats = stage_features(stage)
        build = lambda a, b, feats=feats: Featurizer(feats, True).fit_transform(a, b)
        reps = []
        for i, seed in enumerate(OUTER_SEEDS):
            P, chosen = nested_proba(rows, y, groups, build, classes, seed)
            ll = logloss_bits(y, P, classes).mean()
            pred = np.array(classes)[P.argmax(axis=1)]
            top = P.max(axis=1)
            ent = -(P * np.log2(np.clip(P, 1e-12, 1))).sum(axis=1)
            auc = np.mean([roc_auc_score((y == c).astype(int), P[:, j]) for j, c in enumerate(classes)])
            reps.append({"seed": seed, "logloss_bits": ll, "info_recovered_bits": H - ll,
                         "accuracy": float((pred == y).mean()), "macro_auroc": float(auc),
                         "mean_top_prob": float(top.mean()), "mean_entropy_bits": float(ent.mean()),
                         "recall": {c: float((pred[y == c] == c).mean()) for c in classes},
                         "selected_C": chosen})
            if i == 0:
                dhat[stage] = P
        agg = {k: float(np.mean([r[k] for r in reps])) for k in
               ("logloss_bits", "info_recovered_bits", "accuracy", "macro_auroc", "mean_top_prob", "mean_entropy_bits")}
        agg["sd_accuracy"] = float(np.std([r["accuracy"] for r in reps], ddof=1))
        res["stages"][stage] = {"features": f"{STAGES[stage][0]} + chief complaint", "mean": agg, "repeats": reps}
    tstar = next((s for s in STAGES if res["stages"][s]["mean"]["accuracy"] >= 0.80
                  and res["stages"][s]["mean"]["mean_top_prob"] >= 0.80), "not reached by 6 h")
    res["t_star"] = tstar
    # Cross-fitted D_hat (repeat 1) to the private directory for T6b.
    with open(priv / "dhat_crossfit.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hadm_id", "stage"] + [f"p_{c}" for c in classes] + ["dhat"])
        for stage, P in dhat.items():
            for r, p in zip(rows, P):
                w.writerow([r["hadm_id"], stage] + [f"{v:.6f}" for v in p] + [classes[int(p.argmax())]])
    write_json(out, "diagnosis_formation", res)


# --- T6b: first CT/US/MRI order modality at S0 ---------------------------------------

def first_imaging_orders(hosp, table_by_h):
    first = {}
    for r in csv.DictReader(open_text(hosp["poe.csv.gz"])):
        h = r["hadm_id"]
        if h not in table_by_h or r.get("order_type") != "Radiology":
            continue
        mod = IMAGING_SUBTYPES.get(r.get("order_subtype"))
        t = parse_time(r["ordertime"])
        if not mod or not t:
            continue
        t0 = parse_time(table_by_h[h]["anchor_time"])
        if t0 <= t <= t0 + timedelta(hours=24) and (h not in first or t < first[h][0]):
            first[h] = (t, mod)
    return first


def cmd_vocab(hosp, table_by_h, out):
    c = Counter()
    for r in csv.DictReader(open_text(hosp["poe.csv.gz"])):
        if r["hadm_id"] in table_by_h and r.get("order_type") == "Radiology":
            c[r.get("order_subtype") or ""] += 1
    write_json(out, "radiology_order_vocabulary", {k: suppress(v) for k, v in c.most_common()})


def t6b(rows, hosp, priv, out):
    by_h = {r["hadm_id"]: r for r in rows}
    first = first_imaging_orders(hosp, by_h)
    dh = defaultdict(dict)
    with open(priv / "dhat_crossfit.csv", newline="") as f:
        for r in csv.DictReader(f):
            if r["stage"] == "S0":
                dh[r["hadm_id"]] = r
    cohort = [r for r in rows if r["hadm_id"] in first and r["hadm_id"] in dh]
    ymod = [first[r["hadm_id"]][1] for r in cohort]
    counts = Counter(ymod)
    y = np.array([m if counts[m] >= 50 else "other" for m in ymod])
    classes = sorted(set(y.tolist()))
    groups = np.array([r["subject_id"] for r in cohort])
    dhat = [dh[r["hadm_id"]]["dhat"] for r in cohort]
    dfin = [r["D"] for r in cohort]
    pcols = [k for k in dh[cohort[0]["hadm_id"]] if k.startswith("p_")]
    soft = np.array([[float(dh[r["hadm_id"]][k]) for k in pcols] for r in cohort])
    levels = sorted(set(dfin))
    feats = targets.X0

    def with_x(D, a, b, ia, ib):
        Atr, Ate = Featurizer(feats, True).fit_transform(a, b)
        inter = lambda Dm, A: np.hstack([Dm, A] + [A * Dm[:, [k]] for k in range(Dm.shape[1])])
        return inter(D[ia], Atr), inter(D[ib], Ate)

    index = {id(r): i for i, r in enumerate(cohort)}
    Dhat, Dfin = onehot(dhat, levels), onehot(dfin, levels)
    conds = {
        "a_bottleneck_Dhat": lambda a, b: (Dhat[[index[id(r)] for r in a]], Dhat[[index[id(r)] for r in b]]),
        "b_Dhat_plus_S0": lambda a, b: with_x(Dhat, a, b, [index[id(r)] for r in a], [index[id(r)] for r in b]),
        "c_direct_S0": lambda a, b: Featurizer(feats, True).fit_transform(a, b),
        "d_oracle_Dfinal": lambda a, b: (Dfin[[index[id(r)] for r in a]], Dfin[[index[id(r)] for r in b]]),
        "e_soft_Dhat_probs": lambda a, b: (soft[[index[id(r)] for r in a]], soft[[index[id(r)] for r in b]]),
    }
    res = {"cohort": len(cohort), "class_counts": {k: suppress(v) for k, v in Counter(y.tolist()).items()},
           "H_Y_bits": entropy_bits(Counter(y.tolist())), "decision_point": "S0 (ED arrival)",
           "dhat_note": "D_hat_0 = cross-fitted model-generated diagnosis (experimental bottleneck)",
           "conditions": {}}
    H_given = sum(cnt / len(y) * entropy_bits(Counter(y[np.array(dhat) == d].tolist()))
                  for d, cnt in Counter(dhat).items())
    res["H_Y_given_Dhat0_bits"] = H_given
    preds = {}
    for name, build in conds.items():
        reps = []
        for i, seed in enumerate(OUTER_SEEDS):
            P, chosen = nested_proba(cohort, y, groups, build, classes, seed)
            ll = logloss_bits(y, P, classes)
            reps.append({"seed": seed, "logloss_bits": float(ll.mean()), "selected_C": chosen,
                         "macro_auroc": float(np.mean([roc_auc_score((y == c).astype(int), P[:, j])
                                                       for j, c in enumerate(classes)]))})
            if i == 0:
                preds[name] = P
        res["conditions"][name] = {"logloss_bits_mean": float(np.mean([r["logloss_bits"] for r in reps])),
                                   "macro_auroc_mean": float(np.mean([r["macro_auroc"] for r in reps])),
                                   "repeats": reps}
    g = res["conditions"]["a_bottleneck_Dhat"]["logloss_bits_mean"] - res["conditions"]["b_Dhat_plus_S0"]["logloss_bits_mean"]
    res["G_hat_0_bits"] = g
    res["G_hat_0_share_of_H_Y_given_Dhat0"] = g / H_given if H_given else None
    la = logloss_bits(y, preds["a_bottleneck_Dhat"], classes)
    lb = logloss_bits(y, preds["b_Dhat_plus_S0"], classes)
    rng = np.random.default_rng(OUTER_SEEDS[0])
    uniq = np.unique(groups)
    idx = defaultdict(list)
    for i, gname in enumerate(groups):
        idx[gname].append(i)
    boots = []
    for _ in range(1000):
        take = np.concatenate([idx[u] for u in rng.choice(uniq, size=len(uniq), replace=True)])
        boots.append(la[take].mean() - lb[take].mean())
    res["G_hat_0_ci95_repeat1"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    write_json(out, "t6b_first_imaging_modality", res)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["vocab", "formation", "t6b"])
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm/early_diagnosis")
    args = ap.parse_args(argv)
    priv = private_dir(args.private_dir)
    table = load_table(priv)
    if "anchor_time" not in table[0]:
        raise SystemExit("Table lacks anchor_time; rebuild it with the current mimic_cdm_table.")
    by_h = {r["hadm_id"]: r for r in table}
    if args.command == "vocab":
        cmd_vocab(schemas.require("mimiciv_hosp", ["poe.csv.gz"]), by_h, args.out)
        return
    ed = schemas.require("mimiciv_ed", ["edstays.csv.gz", "triage.csv.gz"])
    cc = chief_complaints(ed["edstays.csv.gz"].parent, set(by_h))
    with open(priv / "t1_timing_classes.csv", newline="") as f:
        timing = {r["hadm_id"]: r["timing_class_L6"] for r in csv.DictReader(f)}
    rows = ed_cohort(table, cc, timing)
    if args.command == "formation":
        formation(rows, args.out, priv)
    else:
        t6b(rows, schemas.require("mimiciv_hosp", ["poe.csv.gz"]), priv, args.out)


if __name__ == "__main__":
    main()
