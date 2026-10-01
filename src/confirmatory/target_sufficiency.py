"""Confirmatory target-sufficiency analysis (preregistration sections H-T; binding commit 600f368).

Model_D : intercept + diagnosis + common context C            (all unpenalized; no tuning)
Model_DX: Model_D + patient state X (L2 on X only, C by inner CV)

  python -m src.confirmatory.target_sufficiency --endpoint T1 --t1-timing green_only   # primary
  ... --endpoint T3 | M5 | M3 | T5 ; --context era_main ; --landmark 3 ; --temporal ; --features X2

Aggregate JSON only (counts < 10 suppressed). Success criteria are evaluated as registered
but do not change what is reported.
"""

import argparse
import math
import warnings
from collections import defaultdict
from datetime import datetime

import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold

import src.confirmatory  # noqa: F401  (thread limits)
from src.confirmatory.partial_logistic import PartialLogistic
from src.preflight import simple_incremental_models as sim
from src.preflight import targets
from src.preflight.reporting import private_dir, suppress, write_json

PRIMARY_TABLE = "mimic_iv_expanded_dxproc_landmark_table"
C_GRID = [1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0]
OUTER_SEEDS = [20260929, 20260930, 20260931]
ERAS = ["2008 - 2010", "2011 - 2013", "2014 - 2016", "2017 - 2019"]
EARLY, LATE = set(ERAS[:3]), {ERAS[3]}
N_BOOT = 2000
LN2 = math.log(2)


# --- design -------------------------------------------------------------------------

def tod_block(t):
    h = t.hour
    return "night" if h < 8 else ("day" if h < 16 else "evening")


def context_matrix(rows, d_levels, mode):
    """Unpenalized common context (section N). mode: full | era_main | no_era."""
    cols, names = [], []
    eras = [r["anchor_year_group"] for r in rows]
    times = [datetime.fromisoformat(r["anchor_time"]) for r in rows]
    if mode in ("full", "era_main"):
        for e in ERAS[1:]:
            cols.append([1.0 if x == e else 0.0 for x in eras]); names.append(f"era={e}")
    if mode == "full":
        for d in d_levels[1:]:
            for e in ERAS[1:]:
                cols.append([1.0 if (r["D"] == d and x == e) else 0.0 for r, x in zip(rows, eras)])
                names.append(f"D={d}*era={e}")
    for b in ("night", "evening"):
        cols.append([1.0 if tod_block(t) == b else 0.0 for t in times]); names.append(f"tod={b}")
    cols.append([1.0 if t.weekday() >= 5 else 0.0 for t in times]); names.append("weekend")
    return np.array(cols).T, names


def base_matrix(rows, d_levels, mode):
    D = np.array([[1.0 if r["D"] == d else 0.0 for d in d_levels[1:]] for r in rows])
    Cm, cnames = context_matrix(rows, d_levels, mode)
    return np.column_stack([np.ones(len(rows)), D, Cm]), ["intercept"] + [f"D={d}" for d in d_levels[1:]] + cnames


def x_raw(rows, feats):
    return np.array([[targets._f(r.get(f)) for f in feats] for r in rows])


def designs(B, Xr, tr, te, feats):
    """Model_D and Model_DX design matrices; X preprocessing fit on tr only."""
    Atr, Ate = sim.fit_transform_x(Xr[tr], Xr[te], sim.log_columns(feats))
    Ztr = np.column_stack([B[tr], Atr]); Zte = np.column_stack([B[te], Ate])
    pen = np.array([False] * B.shape[1] + [True] * Atr.shape[1])
    return (B[tr], B[te]), (Ztr, Zte, pen)


# --- metrics ------------------------------------------------------------------------

def proba(model, Z, ytype):
    P = model.predict_proba(Z)
    return P[:, 1] if ytype == "binary" else P


def loss_bits(y, P, ytype, classes):
    return sim.losses(y, P, ytype, classes)


def auroc(y, P, ytype, classes):
    if ytype == "binary":
        return sim.auroc(y, P)
    return float(np.mean([roc_auc_score((y == c).astype(int), P[:, j]) for j, c in enumerate(classes)]))


def summary(y, PD, PDX, ytype, classes, rows, d_levels):
    lD, lDX = loss_bits(y, PD, ytype, classes), loss_bits(y, PDX, ytype, classes)
    out = {"n": len(y), "logloss_D": lD.mean(), "logloss_DX": lDX.mean(), "delta": lD.mean() - lDX.mean(),
           "rel_delta": (lD.mean() - lDX.mean()) / lD.mean(),
           "auroc_D": auroc(y, PD, ytype, classes), "auroc_DX": auroc(y, PDX, ytype, classes)}
    out["delta_auroc"] = out["auroc_DX"] - out["auroc_D"]
    if ytype == "binary":
        out.update({"events": suppress(int(y.sum())), "brier_D": float(((PD - y) ** 2).mean()),
                    "brier_DX": float(((PDX - y) ** 2).mean()),
                    "calibration_D": sim.calibration(y, PD), "calibration_DX": sim.calibration(y, PDX)})
    within = {}
    for d in d_levels:
        m = np.array([r["D"] == d for r in rows])
        w = {"n": int(m.sum()), "delta": float(lD[m].mean() - lDX[m].mean())}
        if ytype == "binary":
            w["events"] = suppress(int(y[m].sum()))
            w["auroc_DX"] = sim.auroc(y[m], PDX[m])
        within[d] = w
    out["within_diagnosis"] = within
    return out


def bootstrap(y, PD, PDX, groups, ytype, classes, seed):
    rng = np.random.default_rng(seed)
    idx = defaultdict(list)
    for i, g in enumerate(groups):
        idx[g].append(i)
    uniq = np.array(sorted(idx))
    lD, lDX = loss_bits(y, PD, ytype, classes), loss_bits(y, PDX, ytype, classes)
    d, dauc, rel = [], [], []
    for _ in range(N_BOOT):
        take = np.concatenate([idx[g] for g in rng.choice(uniq, size=len(uniq), replace=True)])
        d.append(lD[take].mean() - lDX[take].mean())
        rel.append(d[-1] / lD[take].mean())
        if ytype == "binary" and len(set(y[take].tolist())) == 2:
            dauc.append(sim.auroc(y[take], PDX[take]) - sim.auroc(y[take], PD[take]))
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return {"delta": ci(d), "rel_delta": ci(rel), "delta_auroc": ci(dauc), "resamples": N_BOOT}


# --- nested CV ------------------------------------------------------------------------

def select_C(B, Xr, idx, y, strat, groups, feats, ytype, classes, seed):
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(inner.split(np.zeros(len(idx)), strat[idx], groups[idx]))
    tot = np.zeros(len(C_GRID))
    for a, b in splits:
        tr, te = idx[a], idx[b]
        _, (Ztr, Zte, pen) = designs(B, Xr, tr, te, feats)
        for k, C in enumerate(C_GRID):
            m = PartialLogistic(C=C).fit(Ztr, y[tr], pen, classes)
            tot[k] += loss_bits(y[te], proba(m, Zte, ytype), ytype, classes).mean()
    best, best_loss = C_GRID[0], tot[0]
    for C, t in zip(C_GRID[1:], tot[1:]):
        if t < best_loss - 1e-12:          # strict improvement -> ties go to the smaller C
            best, best_loss = C, t
    return best


def nested(rows, y, ytype, classes, B, Xr, feats, seed):
    groups = np.array([r["subject_id"] for r in rows])
    strat = np.array([f"{v}|{r['anchor_year_group']}" for r, v in zip(rows, y)])
    n = len(rows)
    shape = (n,) if ytype == "binary" else (n, len(classes))
    PD, PDX = np.zeros(shape), np.zeros(shape)
    chosen, converged = [], True
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(outer.split(np.zeros(n), strat, groups))
    for k, (tr, te) in enumerate(splits):
        (Btr, Bte), (Ztr, Zte, pen) = designs(B, Xr, tr, te, feats)
        mD = PartialLogistic(C=1.0).fit(Btr, y[tr], np.zeros(Btr.shape[1], bool), classes)
        PD[te] = proba(mD, Bte, ytype)
        C = select_C(B, Xr, tr, y, strat, groups, feats, ytype, classes, seed + k)
        chosen.append(C)
        mDX = PartialLogistic(C=C).fit(Ztr, y[tr], pen, classes)
        PDX[te] = proba(mDX, Zte, ytype)
        converged &= mD.converged_ and mDX.converged_
    return PD, PDX, groups, chosen, converged


# --- temporal holdout (sensitivity 4) ----------------------------------------------------

def offset_fit(y, P):
    """Additive logit offset minimizing NLL on a calibration subset (binary)."""
    from scipy.optimize import minimize_scalar
    z = np.log(np.clip(P, 1e-9, 1 - 1e-9) / (1 - np.clip(P, 1e-9, 1 - 1e-9)))
    nll = lambda b: np.sum(np.logaddexp(0, z + b) - y * (z + b))
    return float(minimize_scalar(nll, bounds=(-10, 10), method="bounded").x)


def shift(P, b):
    z = np.log(np.clip(P, 1e-9, 1 - 1e-9) / (1 - np.clip(P, 1e-9, 1 - 1e-9)))
    return 1 / (1 + np.exp(-(z + b)))


def temporal(rows, y, ytype, classes, feats, d_levels):
    B, _ = base_matrix(rows, d_levels, "no_era")
    Xr = x_raw(rows, feats)
    groups = np.array([r["subject_id"] for r in rows])
    strat = np.array([f"{v}|{r['anchor_year_group']}" for r, v in zip(rows, y)])
    tr = np.flatnonzero([r["anchor_year_group"] in EARLY for r in rows])
    te = np.flatnonzero([r["anchor_year_group"] in LATE for r in rows])
    C = select_C(B, Xr, tr, y, strat, groups, feats, ytype, classes, OUTER_SEEDS[0])
    (Btr, Bte), (Ztr, Zte, pen) = designs(B, Xr, tr, te, feats)
    PD = proba(PartialLogistic(C=1.0).fit(Btr, y[tr], np.zeros(Btr.shape[1], bool), classes), Bte, ytype)
    PDX = proba(PartialLogistic(C=C).fit(Ztr, y[tr], pen, classes), Zte, ytype)
    test_rows = [rows[i] for i in te]
    out = {"train_eras": sorted(EARLY), "test_eras": sorted(LATE), "train_n": len(tr), "test_n": len(te),
           "selected_C": C, "context": "no_era (diagnosis + operational)",
           "raw": summary(y[te], PD, PDX, ytype, classes, test_rows, d_levels),
           "raw_ci": bootstrap(y[te], PD, PDX, groups[te], ytype, classes, OUTER_SEEDS[0])}
    if ytype == "binary":
        rng = np.random.default_rng(OUTER_SEEDS[0])
        subj = sorted(set(groups[te].tolist()))
        cal_subj = set(rng.choice(subj, size=len(subj) // 4, replace=False).tolist())
        cal = np.array([g in cal_subj for g in groups[te]])
        bD, bDX = offset_fit(y[te][cal], PD[cal]), offset_fit(y[te][cal], PDX[cal])
        ev = ~cal
        ev_rows = [r for r, e in zip(test_rows, ev) if e]
        out["recalibrated"] = {"calibration_subset_n": int(cal.sum()), "evaluation_n": int(ev.sum()),
                               "offset_D": bD, "offset_DX": bDX,
                               "raw_on_eval_subset": summary(y[te][ev], PD[ev], PDX[ev], ytype, classes, ev_rows, d_levels),
                               "recalibrated_on_eval_subset": summary(y[te][ev], shift(PD[ev], bD), shift(PDX[ev], bDX),
                                                                      ytype, classes, ev_rows, d_levels),
                               "ci": bootstrap(y[te][ev], shift(PD[ev], bD), shift(PDX[ev], bDX), groups[te][ev],
                                               ytype, classes, OUTER_SEEDS[0])}
    return out


# --- driver -------------------------------------------------------------------------------

def run(table, endpoint, landmark, t1_timing, context, feature_set, do_temporal):
    spec, pairs, col, rows, y, ytype, classes, timing = sim.prepare(table, endpoint, landmark, False,
                                                                    t1_timing if endpoint == "T1" else "none")
    keep = np.array([r.get("anchor_year_group") in ERAS and bool(r.get("anchor_time")) for r in rows])
    excluded_missing_context = int((~keep).sum())
    rows = [r for r, k in zip(rows, keep) if k]
    y = y[keep]
    d_levels = sorted({r["D"] for r in rows})
    feats = targets.feature_sets(landmark)[feature_set]
    res = {"endpoint": endpoint, "label": spec["label"], "column": col, "landmark_h": landmark,
           "t1_timing": timing, "context": context, "features": feature_set, "n_features": len(feats),
           "excluded_missing_context": excluded_missing_context,
           "preregistration": "docs/main_experiment_preregistration.md @ 600f368",
           "data_reuse_disclosure": "cohort previously analyzed in the preflight; no blind holdout exists",
           "diagnosis_object": "D_icd / D_final-type (not D_t)"}
    if do_temporal:
        res["temporal_holdout"] = temporal(rows, y, ytype, classes, feats, d_levels)
        return res
    B, bnames = base_matrix(rows, d_levels, context)
    Xr = x_raw(rows, feats)
    res["model_D_columns"] = bnames
    reps = []
    for i, seed in enumerate(OUTER_SEEDS):
        PD, PDX, groups, chosen, conv = nested(rows, y, ytype, classes, B, Xr, feats, seed)
        rep = {"seed": seed, "selected_C_DX": chosen, "converged": conv,
               "metrics": summary(y, PD, PDX, ytype, classes, rows, d_levels)}
        if i == 0:
            rep["bootstrap_ci"] = bootstrap(y, PD, PDX, groups, ytype, classes, seed)
        reps.append(rep)
    res["repeats"] = reps
    vals = lambda k: [r["metrics"][k] for r in reps]
    res["across_repeats"] = {k: {"mean": float(np.mean(vals(k))), "sd": float(np.std(vals(k), ddof=1))}
                             for k in ("delta", "rel_delta", "logloss_D", "logloss_DX", "auroc_D", "auroc_DX")}
    ci = reps[0]["bootstrap_ci"]["delta"]
    res["registered_success_criteria"] = {
        "ci_lower_gt_0": ci[0] > 0,
        "rel_delta_ge_0.10": res["across_repeats"]["rel_delta"]["mean"] >= 0.10,
        "success": ci[0] > 0 and res["across_repeats"]["rel_delta"]["mean"] >= 0.10,
        "note": "evaluated as preregistered; T3 is confirmatory only if T1 succeeds; controls are descriptive"}
    if ytype == "binary":
        slope = reps[0]["metrics"]["calibration_D"]["slope"]
        res["flags"] = {"model_D_calibration_slope_outside_0.8_1.25": not (0.8 <= slope <= 1.25)}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", required=True, choices=["T1", "T3", "T5", "M3", "M5"])
    ap.add_argument("--table-name", default=PRIMARY_TABLE)
    ap.add_argument("--landmark", type=int, default=6)
    ap.add_argument("--t1-timing", default="green_only", choices=["green_only", "exclude_red"])
    ap.add_argument("--context", default="full", choices=["full", "era_main"])
    ap.add_argument("--features", default="X1", choices=["X1", "X2"])
    ap.add_argument("--temporal", action="store_true")
    ap.add_argument("--tag", required=True, help="analysis name, e.g. primary_T1")
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/main/target_sufficiency")
    args = ap.parse_args(argv)
    table = private_dir(args.private_dir) / f"{args.table_name}.csv"
    res = run(table, args.endpoint, args.landmark, args.t1_timing, args.context, args.features, args.temporal)
    res["table"] = args.table_name
    write_json(args.out, args.tag, res)


if __name__ == "__main__":
    main()
