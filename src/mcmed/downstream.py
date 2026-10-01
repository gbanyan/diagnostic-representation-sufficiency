"""Stages F, G, I: Model D vs Model D+X for observed ED-to-ICU disposition.

  python -m src.mcmed.downstream develop                # Stage F: development only (no test outcomes)
  python -m src.mcmed.downstream test                   # Stage G: one-shot locked-test evaluation
  python -m src.mcmed.downstream develop --analysis S1  # Stage I (only after the primary freeze)
  python -m src.mcmed.downstream test --analysis S1

Model_D : intercept + D block + season context     (unpenalized; eps ridge 1e-4)
Model_DX: Model_D + X_3h                           (L2 on X only; C by inner patient-grouped CV)

D block (primary): soft D_hat, K-1 probability columns (reference = largest development class).
S1: hard top-1 D_hat (one-hot of argmax, same reference). S2: ICD-10-chapter soft D_hat.
S3: primary + race/ethnicity in X. S4: chronological split (dataset split_chrono_*), full refit.
"""

import argparse
import hashlib
import pickle
from collections import Counter

import numpy as np
from scipy.special import expit
from sklearn.model_selection import StratifiedGroupKFold

import src.mcmed  # noqa: F401  (thread limits)
import multiprocessing

from src.mcmed.newton_logistic import NewtonPartialLogistic
from src.mcmed import metrics
from src.mcmed.common import OUT, config, private, read_cohort
from src.preflight.reporting import REPO, write_json
from src.preflight.simple_incremental_models import fit_transform_x

SEASONS = ["DJF", "JJA", "MAM", "SON"]  # reference DJF
ANALYSES = {"primary": ("body_primary", "soft", False), "S1": ("body_primary", "hard", False),
            "S2": ("chapter_primary", "soft", False), "S3": ("body_primary", "soft", True),
            "S4": ("body_chrono", "soft", False)}


def load(cfg, analysis):
    p = private(cfg)
    rows = read_cohort(cfg)
    Z = np.load(p / "X.npz", allow_pickle=False)
    enc_tag, rep, add_s3 = ANALYSES[analysis]
    E = np.load(p / f"dhat_{enc_tag}.npz", allow_pickle=False)
    assert list(Z["csn"]) == list(E["csn"]) == [r["CSN"] for r in rows]
    dev, test = E["dev"], E["test_mask"]
    classes = list(E["classes"])
    P = np.where(dev[:, None], E["oof"], np.nan)
    P[test] = E["test"]
    lab = [r["dx_body" if enc_tag.startswith("body") else "dx_chapter"] for r in rows]
    dev_counts = Counter(l for l, d in zip(lab, dev) if d)
    ref = max(classes, key=lambda c: (dev_counts[c], c))  # largest development class (diagnosis counts only)
    keep = [k for k, c in enumerate(classes) if c != ref]
    if rep == "soft":
        Dm = P[:, keep]
        dnames = [f"p_hat={classes[k]}" for k in keep]
    else:
        H = np.eye(len(classes))[P.argmax(1)]
        present = [k for k in keep if H[dev, k].sum() > 0]  # a class never predicted in development has no column
        Dm = H[:, present]
        dnames = [f"top1={classes[k]}" for k in present]
    season = np.array([[1.0 if r["season"] == s else 0.0 for s in SEASONS[1:]] for r in rows])
    X = Z["X"]
    xnames = list(Z["names"])
    if add_s3:
        X = np.column_stack([X, Z["S3"]])
        xnames += list(Z["s3_names"])
    y = np.array([int(r["y_icu"]) for r in rows])
    groups = np.array([r["MRN"] for r in rows])
    B = np.column_stack([np.ones(len(rows)), Dm, season])
    bnames = ["intercept"] + dnames + [f"season={s}" for s in SEASONS[1:]]
    return dict(rows=rows, B=B, bnames=bnames, X=X, xnames=xnames, y=y, groups=groups, dev=dev, test=test,
                ref=ref, rep=rep, enc_tag=enc_tag, csn=Z["csn"])


def fit_pair(d, tr, te, C, eps):
    B, X, y = d["B"], d["X"], d["y"]
    # Amendment 1: exact Newton on the preregistered objective (L-BFGS did not converge on this design).
    mD = NewtonPartialLogistic(C=1.0, eps=eps).fit(B[tr], y[tr], np.zeros(B.shape[1], bool), classes=[0, 1])
    Atr, Ate = fit_transform_x(X[tr], X[te])
    pen = np.array([False] * B.shape[1] + [True] * Atr.shape[1])
    mDX = NewtonPartialLogistic(C=C, eps=eps).fit(np.column_stack([B[tr], Atr]), y[tr], pen, classes=[0, 1])
    pD = mD.predict_proba(B[te])[:, 1]
    pDX = mDX.predict_proba(np.column_stack([B[te], Ate]))[:, 1]
    return mD, mDX, pD, pDX, Atr.shape[1]


def digest(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype=float).tobytes())
    return h.hexdigest()


_W = {}


def _inner(args):
    tr, te, C = args
    mD, mDX, pD, pDX, _ = fit_pair(_W["d"], tr, te, C, _W["eps"])
    return C, te, pD, pDX, mD.converged_ and mDX.converged_


def develop(cfg, analysis):
    if (private(cfg) / f"test_opened_{analysis}.flag").exists():
        raise SystemExit(f"CONFIRMATORY ANALYSIS FROZEN: {analysis} test already opened; models cannot be refit")
    dc = cfg["downstream"]
    grid, eps = dc["C_grid"], dc["eps_unpenalized_ridge"]
    d = load(cfg, analysis)
    D = np.flatnonzero(d["dev"])
    y, groups = d["y"], d["groups"]
    cv = list(StratifiedGroupKFold(dc["inner_folds"], shuffle=True, random_state=dc["inner_seed"])
              .split(np.zeros(len(D)), y[D], groups[D]))
    loss = {C: [] for C in grid}
    conv = True
    oofD, oofDX = {C: np.zeros(len(y)) for C in grid}, {C: np.zeros(len(y)) for C in grid}
    _W.update(d=d, eps=eps)
    tasks = [(D[tr], D[te], C) for tr, te in cv for C in grid]
    with multiprocessing.get_context("fork").Pool(8) as pool:
        for C, te, pD, pDX, ok in pool.map(_inner, tasks, chunksize=1):
            conv &= ok
            loss[C].append(metrics.losses(y[te], pDX).mean())
            oofD[C][te], oofDX[C][te] = pD, pDX
    mean_loss = {C: float(np.mean(v)) for C, v in loss.items()}
    C_sel = min(grid, key=lambda C: (round(mean_loss[C], 12), C))
    mD, mDX, _, _, n_x_cols = fit_pair(d, D, D[:1], C_sel, eps)
    # Numerical check that penalty-zero blocks are unpenalized: with C -> 0 the D+context coefficients
    # of Model_DX must equal Model_D's (X shrunk to 0), on the development data.
    _, mTiny, pD0, pTiny, _ = fit_pair(d, D, D, 1e-8, eps)
    Xpart = mTiny.coef_[d["B"].shape[1]:]
    check = {"max_abs_X_coef_at_C_1e-8": float(np.abs(Xpart).max()),
             "max_abs_pred_diff_vs_Model_D": float(np.abs(pD0 - pTiny).max())}
    check["abs_logloss_diff_vs_Model_D"] = float(abs(metrics.losses(y[D], pD0).mean() - metrics.losses(y[D], pTiny).mean()))
    check["passed"] = (check["max_abs_X_coef_at_C_1e-8"] < 1e-4 and check["max_abs_pred_diff_vs_Model_D"] < 1e-4
                       and check["abs_logloss_diff_vs_Model_D"] < 1e-6)
    models = {"analysis": analysis, "C": C_sel, "coef_D": mD.coef_, "coef_DX": mDX.coef_,
              "bnames": d["bnames"], "xnames": d["xnames"], "ref": d["ref"], "rep": d["rep"]}
    p = private(cfg)
    with open(p / f"models_{analysis}.pkl", "wb") as f:
        pickle.dump(models, f)
    dev_cv = metrics.summary(y[D], oofD[C_sel][D], oofDX[C_sel][D])
    for k in [k for k in dev_cv if k.startswith("deciles")]:
        dev_cv.pop(k)
    rep = {
        "analysis": analysis, "encoder": d["enc_tag"], "representation": d["rep"], "reference_class": d["ref"],
        "dev_visits": int(len(D)), "dev_patients": int(len(set(groups[D]))), "dev_events": int(y[D].sum()),
        "D_block_columns": len([n for n in d["bnames"] if n.startswith(("p_hat", "top1"))]),
        "context_columns": [n for n in d["bnames"] if n.startswith("season")],
        "X_raw_columns": int(d["X"].shape[1]), "X_model_columns_after_indicators": int(n_x_cols),
        "inner_cv_mean_logloss_DX_by_C": mean_loss, "C_selected": C_sel,
        "all_inner_fits_converged": bool(conv), "final_D_converged": mD.converged_, "final_DX_converged": mDX.converged_,
        "solver": "exact Newton (amendment 1)", "final_max_abs_gradient": {"D": mD.max_grad_, "DX": mDX.max_grad_},
        "final_newton_iterations": {"D": mD.n_iter_, "DX": mDX.n_iter_},
        "penalty_zero_check": check,
        "coef_sha256": {"D": digest(mD.coef_), "DX": digest(mDX.coef_)},
        "dev_inner_cv_at_selected_C": dev_cv,
    }
    write_json(OUT, f"stageF_develop_{analysis}", rep)


def test(cfg, analysis):
    p = private(cfg)
    guard = p / f"test_opened_{analysis}.flag"
    if guard.exists():
        raise SystemExit(f"{guard} exists: the locked test for {analysis} is evaluated once only")
    if analysis != "primary" and not (REPO / "results" / "mcmed_primary_frozen.md").exists():
        raise SystemExit("sensitivities run only after results/mcmed_primary_frozen.md is committed")
    with open(p / f"models_{analysis}.pkl", "rb") as f:  # written by develop() above; private, never external
        m = pickle.load(f)
    ec = cfg["evaluation"]
    d = load(cfg, analysis)
    assert d["bnames"] == m["bnames"] and d["xnames"] == m["xnames"]
    D, Te = np.flatnonzero(d["dev"]), np.flatnonzero(d["test"])
    guard.write_text("opened\n")
    # Rebuild the frozen X preprocessing from development data (deterministic), then apply frozen coefficients.
    _, Ate = fit_transform_x(d["X"][D], d["X"][Te])
    pD = expit(d["B"][Te] @ m["coef_D"])
    pDX = expit(np.column_stack([d["B"][Te], Ate]) @ m["coef_DX"])
    y, groups = d["y"][Te], d["groups"][Te]
    pred_file = p / f"test_predictions_{analysis}.csv"
    with open(pred_file, "w") as f:
        f.write("CSN,y_true,p_D,p_DX\n")
        for c, a, b, cc in zip(d["csn"][Te], y, pD, pDX):
            f.write(f"{c},{a},{b:.17g},{cc:.17g}\n")
    pred_file.chmod(0o400)
    s = metrics.summary(y, pD, pDX)
    ci = metrics.bootstrap(y, pD, pDX, groups, ec["bootstrap_replicates"], ec["bootstrap_seed"])
    succ = ec["success"]
    supported = ci["delta_L_nats"]["lo"] > succ["delta_ci_lower_gt"] and s["relative_gain"] >= succ["relative_gain_min"]
    write_json(OUT, f"stageG_test_{analysis}", {
        "analysis": analysis, "C_selected": m["C"], "test_visits": int(len(Te)), "test_patients": int(len(set(groups))),
        "predictions_sha256": hashlib.sha256(pred_file.read_bytes()).hexdigest(),
        "coef_sha256": {"D": digest(m["coef_D"]), "DX": digest(m["coef_DX"])},
        "summary": s, "bootstrap_95ci": ci,
        "criterion": {"delta_ci_lower_gt_0": ci["delta_L_nats"]["lo"] > 0,
                      "relative_gain_ge_10pct": s["relative_gain"] >= succ["relative_gain_min"],
                      "result": ("SUPPORTED" if supported else "NOT SUPPORTED") if analysis == "primary" else "sensitivity (no confirmatory role)"},
    })


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["develop", "test"])
    ap.add_argument("--analysis", choices=list(ANALYSES), default="primary")
    a = ap.parse_args(argv)
    cfg = config()
    (develop if a.command == "develop" else test)(cfg, a.analysis)


if __name__ == "__main__":
    main()
