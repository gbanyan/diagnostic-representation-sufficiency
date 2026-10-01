"""Stage B: does contemporaneous X add held-out information about Y beyond D?

Model_D  : D one-hot -> Y   (effectively unpenalized; per-D base rates / means)
Model_DX : D one-hot + X + X*D -> Y   (L2 logistic / ridge)
With --nested (Q13), C is chosen by an inner loop for BOTH models with the same
grid, splits, and rule (docs/model_selection_preflight.md); otherwise C = 1.0.
Imputation (median + missing indicators) and scaling are fit within each
training fold. 5-fold StratifiedGroupKFold grouped by subject_id, seed fixed.
Paired subject-level bootstrap of the out-of-fold predictions gives 95% CIs.

Exploratory target screening only; not the main experiment and not causal.

  python -m src.preflight.simple_incremental_models --dataset mimic_cdm \
      --target T1 --features X0 X1 X2 --landmark 6 [--sensitivity]
"""

import argparse
import math
import warnings
from collections import defaultdict

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from src.preflight import targets
from src.preflight.reporting import private_dir, suppress, write_json
from src.preflight.target_heterogeneity import stage_a

SEED = 20260929
N_BOOT = 1000
LN2 = math.log(2)


def design(rows, feats, d_levels):
    D = np.array([[1.0 if r["D"] == d else 0.0 for d in d_levels] for r in rows])
    X = np.array([[targets._f(r.get(f)) for f in feats] for r in rows]) if feats else np.zeros((len(rows), 0))
    return D, X


# Deviation 2026-09-29 (decision_log.md), applied to every target before any X1/X2
# result: log1p for right-skewed features, and standardized values clipped to +-5,
# so that single extreme values cannot dominate a linear model.
LOG_FEATURES = ("prior_admissions", "lab_wbc", "lab_crp", "lab_lactate", "lab_lipase", "lab_tbili", "lab_alt",
                "lab_ast", "lab_alp", "lab_creat", "lab_bun", "lab_glucose", "lab_inr")
CLIP_Z = 5.0


def log_columns(feats):
    return [j for j, f in enumerate(feats) if f.startswith(LOG_FEATURES)]


def fit_transform_x(Xtr, Xte, log_cols=()):
    Xtr, Xte = Xtr.copy(), Xte.copy()
    for j in log_cols:
        Xtr[:, j] = np.log1p(np.clip(Xtr[:, j], 0, None))
        Xte[:, j] = np.log1p(np.clip(Xte[:, j], 0, None))
    imp = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    sc = StandardScaler()
    Atr = np.clip(sc.fit_transform(imp.fit_transform(Xtr)), -CLIP_Z, CLIP_Z)
    Ate = np.clip(sc.transform(imp.transform(Xte)), -CLIP_Z, CLIP_Z)
    return Atr, Ate


def with_interactions(D, A):
    return np.hstack([D, A] + [A * D[:, [k]] for k in range(D.shape[1])])


def oof_predict(rows, y, ytype, feats, d_levels, classes):
    groups = np.array([r["subject_id"] for r in rows])
    strat = y if ytype != "continuous" else np.array([r["D"] for r in rows])
    if ytype == "categorical":
        strat = np.array([f"{r['D']}|{v}" for r, v in zip(rows, y)])
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    D, X = design(rows, feats, d_levels)
    n = len(rows)
    shape = (n,) if ytype != "categorical" else (n, len(classes))
    pred_d, pred_dx = np.zeros(shape), np.zeros(shape)
    for tr, te in cv.split(np.zeros(n), strat, groups):
        if ytype == "continuous":
            m_d = LinearRegression().fit(D[tr], y[tr])
            pred_d[te] = m_d.predict(D[te])
            Atr, Ate = fit_transform_x(X[tr], X[te], log_columns(feats))
            m_dx = Ridge(alpha=1.0).fit(with_interactions(D[tr], Atr), y[tr])
            pred_dx[te] = m_dx.predict(with_interactions(D[te], Ate))
            continue
        m_d = LogisticRegression(C=1e6, max_iter=5000).fit(D[tr], y[tr])
        Atr, Ate = fit_transform_x(X[tr], X[te], log_columns(feats))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m_dx = LogisticRegression(C=1.0, max_iter=5000).fit(with_interactions(D[tr], Atr), y[tr])
        for model, Z, store in ((m_d, D[te], pred_d), (m_dx, with_interactions(D[te], Ate), pred_dx)):
            p = model.predict_proba(Z)
            full = np.full((len(te), len(classes)), 1e-12)
            for j, c in enumerate(model.classes_):
                full[:, classes.index(c)] = p[:, j]
            full /= full.sum(axis=1, keepdims=True)
            store[te] = full[:, 1] if ytype == "binary" else full
    return pred_d, pred_dx, groups


# --- nested cross-validation (Q13; docs/model_selection_preflight.md) ---------

C_GRID = [1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0]
OUTER_SEEDS = [20260929, 20260930, 20260931]


def strat_labels(rows, y, ytype):
    if ytype == "continuous":
        return np.array([r["D"] for r in rows])
    if ytype == "categorical":
        return np.array([f"{r['D']}|{v}" for r, v in zip(rows, y)])
    return y


# Q19 sensitivity (model_selection_preflight.md addendum): scale the D main-effect columns of
# Model_DX by D_SCALE so their effective L2 penalty is divided by D_SCALE**2. 1.0 = registered spec.
D_SCALE = 1.0


def _design_for(D, X, tr, te, feats, use_x):
    if not use_x:
        return D[tr], D[te]
    Atr, Ate = fit_transform_x(X[tr], X[te], log_columns(feats))
    Ztr, Zte = with_interactions(D[tr], Atr), with_interactions(D[te], Ate)
    if D_SCALE != 1.0:
        k = D.shape[1]
        Ztr[:, :k] *= D_SCALE
        Zte[:, :k] *= D_SCALE
    return Ztr, Zte


def _fit_predict(ytype, Ztr, ytr, Zte, C, classes):
    if ytype == "continuous":
        return Ridge(alpha=1.0 / C).fit(Ztr, ytr).predict(Zte)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = LogisticRegression(C=C, max_iter=5000).fit(Ztr, ytr)
    p = model.predict_proba(Zte)
    full = np.full((len(Zte), len(classes)), 1e-12)
    for j, c in enumerate(model.classes_):
        full[:, classes.index(c)] = p[:, j]
    full /= full.sum(axis=1, keepdims=True)
    return full[:, 1] if ytype == "binary" else full


def select_c(D, X, idx, y, ytype, strat, groups, feats, use_x, classes, seed):
    """Inner loop on training indices idx: return the C with the lowest mean held-out
    loss; ties go to the smaller C (grid is ascending, strict improvement required)."""
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    totals = np.zeros(len(C_GRID))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(inner.split(np.zeros(len(idx)), strat[idx], groups[idx]))
    for itr, ite in splits:
        tr, te = idx[itr], idx[ite]
        Ztr, Zte = _design_for(D, X, tr, te, feats, use_x)
        for k, C in enumerate(C_GRID):
            totals[k] += losses(y[te], _fit_predict(ytype, Ztr, y[tr], Zte, C, classes), ytype, classes).mean()
    best, best_loss = C_GRID[0], totals[0]
    for C, tot in zip(C_GRID[1:], totals[1:]):
        if tot < best_loss - 1e-12:
            best, best_loss = C, tot
    return best


def nested_oof(rows, y, ytype, feats, d_levels, classes, seed):
    groups = np.array([r["subject_id"] for r in rows])
    strat = strat_labels(rows, y, ytype)
    D, X = design(rows, feats, d_levels)
    n = len(rows)
    shape = (n,) if ytype != "categorical" else (n, len(classes))
    pred = {"D": np.zeros(shape), "DX": np.zeros(shape)}
    chosen = {"D": [], "DX": []}
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(outer.split(np.zeros(n), strat, groups))
    for k, (tr, te) in enumerate(splits):
        for name, use_x in (("D", False), ("DX", True)):
            C = select_c(D, X, tr, y, ytype, strat, groups, feats, use_x, classes, seed + k)
            chosen[name].append(C)
            Ztr, Zte = _design_for(D, X, tr, te, feats, use_x)
            pred[name][te] = _fit_predict(ytype, Ztr, y[tr], Zte, C, classes)
    return pred["D"], pred["DX"], groups, chosen


def calibration(y, p, bins=10):
    """Logistic recalibration (intercept, slope of the logit) and expected calibration error."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p)).reshape(-1, 1)
    if len(set(y.tolist())) < 2:
        return {"intercept": math.nan, "slope": math.nan, "ece": math.nan}
    m = LogisticRegression(C=1e6, max_iter=5000).fit(logit, y)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    ece = sum(abs(p[idx == b].mean() - y[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any())
    return {"intercept": float(m.intercept_[0]), "slope": float(m.coef_[0][0]), "ece": float(ece)}


def clipping_share(rows, feats, d_levels):
    """Share of standardized cells at the +-5 SD clip, over the full cohort (descriptive)."""
    _, X = design(rows, feats, d_levels)
    A, _ = fit_transform_x(X, X[:1], log_columns(feats))
    base = A[:, :len(feats)]
    return {"share_cells_clipped": float((np.abs(base) >= CLIP_Z - 1e-9).mean()),
            "features_with_any_clipping": int((np.abs(base) >= CLIP_Z - 1e-9).any(axis=0).sum())}


def losses(y, p, ytype, classes):
    """Per-case loss: log loss in bits (binary/categorical) or squared error (continuous)."""
    if ytype == "binary":
        p = np.clip(p, 1e-12, 1 - 1e-12)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)) / LN2
    if ytype == "categorical":
        idx = np.array([classes.index(v) for v in y])
        return -np.log(np.clip(p[np.arange(len(y)), idx], 1e-12, 1)) / LN2
    return (y - p) ** 2


def auroc(y, p):
    return roc_auc_score(y, p) if len(set(y.tolist())) == 2 else math.nan


def summarize(y, pd_, pdx, ytype, classes, mask=None):
    if mask is not None:
        y, pd_, pdx = y[mask], pd_[mask], pdx[mask]
    ld, ldx = losses(y, pd_, ytype, classes), losses(y, pdx, ytype, classes)
    out = {"n": len(y), "loss_D": ld.mean(), "loss_DX": ldx.mean(), "delta_loss": ld.mean() - ldx.mean()}
    if ytype == "binary":
        out.update({"events": suppress(int(y.sum())), "auroc_D": auroc(y, pd_), "auroc_DX": auroc(y, pdx),
                    "brier_D": ((pd_ - y) ** 2).mean(), "brier_DX": ((pdx - y) ** 2).mean()})
        out["delta_auroc"] = out["auroc_DX"] - out["auroc_D"]
    if ytype == "continuous":
        var = y.var()
        out.update({"r2_D": 1 - ld.mean() / var if var else math.nan,
                    "r2_DX": 1 - ldx.mean() / var if var else math.nan})
        out["delta_r2"] = out["r2_DX"] - out["r2_D"]
    return out


def bootstrap(y, pd_, pdx, groups, ytype, classes, masks):
    rng = np.random.default_rng(SEED)
    uniq = np.unique(groups)
    index = defaultdict(list)
    for i, g in enumerate(groups):
        index[g].append(i)
    ld, ldx = losses(y, pd_, ytype, classes), losses(y, pdx, ytype, classes)
    stats = defaultdict(list)
    for _ in range(N_BOOT):
        take = np.concatenate([index[g] for g in rng.choice(uniq, size=len(uniq), replace=True)])
        for name, m in masks.items():
            sel = take[m[take]] if m is not None else take
            if len(sel) == 0:
                continue
            stats[f"{name}.delta_loss"].append(ld[sel].mean() - ldx[sel].mean())
            if ytype == "binary" and len(set(y[sel].tolist())) == 2:
                stats[f"{name}.delta_auroc"].append(auroc(y[sel], pdx[sel]) - auroc(y[sel], pd_[sel]))
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in stats.items()}


TIMING_FILTERS = {"none": None, "exclude_red": {"GREEN", "YELLOW"}, "green_only": {"GREEN"}}


def apply_timing_filter(pairs, table, landmark, timing_filter):
    """T1 only: keep cohort rows whose procedure-timing class is allowed (procedure_timing_audit.md)."""
    allowed = TIMING_FILTERS[timing_filter]
    if allowed is None:
        return pairs, None
    path = targets.companion(table, "t1_timing_classes")
    if not path.exists():
        raise SystemExit(f"{path} not found; run src.preflight.procedure_timing first")
    import csv
    with open(path, newline="") as f:
        cls = {r["hadm_id"]: r[f"timing_class_L{landmark}"] for r in csv.DictReader(f)}
    kept = [(r, y) for r, y in pairs if cls.get(str(r["hadm_id"])) in allowed]
    counts = defaultdict(int)
    for r, _ in pairs:
        counts[cls.get(str(r["hadm_id"]), "UNCLASSIFIED")] += 1
    return kept, {"filter": timing_filter, "before": len(pairs), "after": len(kept),
                  "classes_before_filter": {k: suppress(v) for k, v in sorted(counts.items())}}


def prepare(table, target_id, landmark, sensitivity, timing_filter):
    spec = targets.TARGETS[target_id]
    if not spec["stage_b"]:
        raise SystemExit(f"{target_id} is an examination target: Stage B against D_final would reward "
                         "reconstructing the final diagnosis (G9). It needs D_hat_t; refused.")
    pairs, col = targets.load_rows(table, target_id, landmark, sensitivity)
    timing = None
    if timing_filter != "none":
        if target_id != "T1":
            raise SystemExit("--t1-timing applies to T1 only")
        pairs, timing = apply_timing_filter(pairs, table, landmark, timing_filter)
    rows = [r for r, _ in pairs]
    ytype = spec["type"]
    if ytype == "continuous":
        y = np.array([v for _, v in pairs], dtype=float)
        if target_id == "T9":
            y = np.log1p(y)
    elif ytype == "binary":
        y = np.array([int(v) for _, v in pairs])
    else:
        y = np.array([v for _, v in pairs])
    classes = [0, 1] if ytype == "binary" else (sorted(set(y.tolist())) if ytype == "categorical" else None)
    return spec, pairs, col, rows, y, ytype, classes, timing


def evaluate(rows, y, ytype, classes, d_levels, pd_, pdx, groups, bootstrap_ci=True):
    masks = {"overall": None}
    masks.update({f"D={d}": np.array([r["D"] == d for r in rows]) for d in d_levels})
    res = {"overall": summarize(y, pd_, pdx, ytype, classes)}
    for d in d_levels:
        res[f"D={d}"] = summarize(y, pd_, pdx, ytype, classes, masks[f"D={d}"])
    if ytype == "binary":
        res["calibration_DX"] = calibration(y, pdx)
        res["calibration_D"] = calibration(y, pd_)
    if bootstrap_ci:
        res["ci95"] = bootstrap(y, pd_, pdx, groups, ytype, classes, masks)
    return res


EARLY_PERIODS = {"2008 - 2010", "2011 - 2013", "2014 - 2016"}
LATE_PERIODS = {"2017 - 2019", "2020 - 2022"}


def temporal_validate(rows, y, ytype, classes, feats, d_levels):
    """Train on anchor_year_group <= 2014-2016, test on 2017-2022; C by inner CV on train only."""
    tr = np.array([r.get("anchor_year_group") in EARLY_PERIODS for r in rows])
    te = np.array([r.get("anchor_year_group") in LATE_PERIODS for r in rows])
    groups = np.array([r["subject_id"] for r in rows])
    strat = strat_labels(rows, y, ytype)
    D, X = design(rows, feats, d_levels)
    tr_idx, te_idx = np.flatnonzero(tr), np.flatnonzero(te)
    out = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "selected_C": {}}
    preds = {}
    for name, use_x in (("D", False), ("DX", True)):
        C = select_c(D, X, tr_idx, y, ytype, strat, groups, feats, use_x, classes, OUTER_SEEDS[0])
        out["selected_C"][name] = C
        Ztr, Zte = _design_for(D, X, tr_idx, te_idx, feats, use_x)
        preds[name] = _fit_predict(ytype, Ztr, y[tr_idx], Zte, C, classes)
    test_rows = [rows[i] for i in te_idx]
    res = evaluate(test_rows, y[te_idx], ytype, classes, d_levels, preds["D"], preds["DX"], groups[te_idx])
    res.update(out)
    return res


def run(table, target_id, landmark, feature_set_names, sensitivity=False, nested=False, timing_filter="none",
        exclude_cdm=False, temporal=False):
    spec, pairs, col, rows, y, ytype, classes, timing = prepare(table, target_id, landmark, sensitivity,
                                                                timing_filter)
    if exclude_cdm:
        keep = np.array([r.get("in_cdm") != "1" for r in rows])
        pairs = [p for p, k in zip(pairs, keep) if k]
        rows, y = [r for r, k in zip(rows, keep) if k], y[keep]
    d_levels = sorted({r["D"] for r in rows})
    result = {"target": target_id, "label": spec["label"], "column": col, "landmark_h": landmark,
              "sensitivity_cohort": sensitivity, "timing_filter": timing,
              "diagnosis_object": "D_final (post-diagnostic)",
              "model_selection": ("nested CV: outer 5-fold x 3 repeats, inner 4-fold, C grid "
                                  f"{C_GRID}, min inner loss, ties to smaller C" if nested
                                  else "fixed C = 1.0 (superseded by nested CV for classification)"),
              "stage_a": stage_a(pairs, ytype), "feature_sets": {}}
    result["exclude_cdm"] = exclude_cdm
    fsets = targets.feature_sets(landmark)
    for name in feature_set_names:
        feats = fsets[name]
        if temporal:
            result["feature_sets"][name] = {"n_features": len(feats),
                                            "temporal": temporal_validate(rows, y, ytype, classes, feats, d_levels)}
            continue
        if not nested:
            pd_, pdx, groups = oof_predict(rows, y, ytype, feats, d_levels, classes)
            res = {"n_features": len(feats)}
            res.update(evaluate(rows, y, ytype, classes, d_levels, pd_, pdx, groups))
            result["feature_sets"][name] = res
            continue
        repeats = []
        for i, seed in enumerate(OUTER_SEEDS):
            pd_, pdx, groups, chosen = nested_oof(rows, y, ytype, feats, d_levels, classes, seed)
            rep = evaluate(rows, y, ytype, classes, d_levels, pd_, pdx, groups, bootstrap_ci=(i == 0))
            rep["selected_C"] = chosen
            rep["seed"] = seed
            repeats.append(rep)
        keys = ["delta_loss", "auroc_D", "auroc_DX", "delta_auroc", "r2_D", "r2_DX", "delta_r2"]
        across = {}
        for k in keys:
            vals = [r["overall"][k] for r in repeats if k in r["overall"]]
            if vals:
                across[k] = {"mean": float(np.mean(vals)), "sd": float(np.std(vals, ddof=1)), "values": vals}
        within = {}
        for d in d_levels:
            vals = [r[f"D={d}"].get("auroc_DX") for r in repeats]
            if all(v is not None and not math.isnan(v) for v in vals):
                within[f"D={d}"] = {"auroc_DX_mean": float(np.mean(vals)), "auroc_DX_minus_0.5": float(np.mean(vals)) - 0.5}
            dl = [r[f"D={d}"]["delta_loss"] for r in repeats]
            within.setdefault(f"D={d}", {})["delta_loss_mean"] = float(np.mean(dl))
        result["feature_sets"][name] = {"n_features": len(feats), "clipping": clipping_share(rows, feats, d_levels),
                                        "across_repeats": across, "within_D_across_repeats": within,
                                        "repeats": repeats}
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["mimic_cdm"], required=True)
    ap.add_argument("--target", choices=sorted(targets.TARGETS), nargs="+", required=True)
    ap.add_argument("--diagnosis", default="D")
    ap.add_argument("--features", nargs="+", default=["X0", "X1", "X2"], choices=["X0", "X1", "X2"])
    ap.add_argument("--landmark", type=int, default=6)
    ap.add_argument("--sensitivity", action="store_true", help="use the target's sensitivity cohort")
    ap.add_argument("--nested", action="store_true", help="nested CV over C (docs/model_selection_preflight.md)")
    ap.add_argument("--unpenalized-d", action="store_true",
                    help="Q19 sensitivity: D main effects in Model_DX effectively unpenalized (scale 100)")
    ap.add_argument("--exclude-cdm", action="store_true", help="drop admissions that are in MIMIC-CDM")
    ap.add_argument("--temporal", action="store_true",
                    help="temporal validation: train <= 2014-2016, test 2017-2022 (anchor_year_group)")
    ap.add_argument("--t1-timing", choices=sorted(TIMING_FILTERS), default="none",
                    help="T1 procedure-timing filter (docs/procedure_timing_audit.md)")
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
    for t in args.target:
        global D_SCALE
        D_SCALE = 100.0 if args.unpenalized_d else 1.0
        res = run(table, t, args.landmark, args.features, args.sensitivity, args.nested, args.t1_timing,
                  args.exclude_cdm, args.temporal)
        res["d_main_effect_scale"] = D_SCALE
        tag = (f"stage_b_{t}_L{args.landmark}" + ("_sens" if args.sensitivity else "")
               + (f"_{args.t1_timing}" if args.t1_timing != "none" else "") + ("_nested" if args.nested else "")
               + ("_nocdm" if args.exclude_cdm else "") + ("_temporal" if args.temporal else ""))
        write_json(args.out, tag, res)


if __name__ == "__main__":
    main()
