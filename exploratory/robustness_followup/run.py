"""EXPLORATORY MC-MED robustness follow-up (plan.md, fixed before running).

  python -m exploratory.robustness_followup.run

Variants: 1a aggregated 127->20, 1b PCA-19 of the 127 posterior, 1c 20-class encoder at C=0.01,
2a additive log-ratio D, 2b spline-expanded D with tuned penalty, 5 comparator matched to MIMIC X1.
Reads frozen artifacts read-only; aggregates only.
"""

import json
import math
import multiprocessing
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import SplineTransformer

import src.mcmed  # noqa: F401  (thread limits)
import exploratory.diagnostic_capacity.run as CR
from exploratory.diagnostic_capacity.ontologies import build
from src.mcmed import downstream as DS
from src.mcmed import metrics
from src.mcmed.common import config, private
from src.mcmed.newton_logistic import NewtonPartialLogistic
from src.preflight.reporting import write_json
from src.preflight.simple_incremental_models import fit_transform_x

OUT = Path(__file__).resolve().parent / "results"
CAP = Path(__file__).resolve().parents[1] / "diagnostic_capacity" / "results" / "capacity.json"
REPS, SEED, TOL = 1000, 20261006, 1e-4
LN2 = math.log(2)
TRIAGE = [f"triage_{m}" for m in ("Temp", "HR", "RR", "SpO2", "SBP", "DBP", "ESI")]
MATCH_LABS = ["WHITE BLOOD CELLS (WBC)", "NEUTROPHIL % (AUTO DIFF)", "HEMOGLOBIN (HGB)", "PLATELET COUNT (PLT)",
              "POC:LACTATE, ISTAT", "LIPASE", "BILIRUBIN, TOTAL", "ALT (SGPT)", "AST (SGOT)", "ALKALINE PHOSPHATASE",
              "CREATININE", "BLOOD UREA NITROGEN (BUN)", "GLUCOSE", "SODIUM", "POTASSIUM", "CO2", "ALBUMIN", "INR", "CALCIUM"]

_W = {}


def _fit_pair_generic(args):
    tr, te, C = args
    _, _, pD, pDX, _ = _W["fitter"](tr, te, C)
    return C, te, pDX


def pair_standard(B, X, y, eps):
    d = dict(B=B, X=X, y=y)
    return lambda tr, te, C: DS.fit_pair(d, tr, te, C, eps)


def tune_and_fit(fitter, y, groups, dev, test, grid, seed):
    D, Te = np.flatnonzero(dev), np.flatnonzero(test)
    cv = list(StratifiedGroupKFold(4, shuffle=True, random_state=seed).split(np.zeros(len(D)), y[D], groups[D]))
    _W["fitter"] = fitter
    with multiprocessing.get_context("fork").Pool(8) as pool:
        res = pool.map(_fit_pair_generic, [(D[tr], D[te], C) for tr, te in cv for C in grid], chunksize=1)
    loss = {C: np.mean([metrics.losses(y[te], p).mean() for CC, te, p in res if CC == C]) for C in grid}
    C_sel = min(grid, key=lambda C: (round(loss[C], 12), C))
    mD, mDX, pD, pDX, _ = fitter(D, Te, C_sel)
    return C_sel, pD, pDX, bool(mD.converged_ and mDX.converged_)


def spline_fitter(A, season, X, y, eps, grid, groups, dev, seed):
    """2b: Model D = intercept + season + spline(A) with tuned C_D; Model D+X keeps the spline block at C_D."""
    def basis(tr, te):
        st = SplineTransformer(n_knots=4, degree=3, extrapolation="linear").fit(A[tr])
        return st.transform(A[tr]), st.transform(A[te])

    def fitD(tr, te, CD):
        Str, Ste = basis(tr, te)
        Ztr = np.column_stack([np.ones(len(tr)), season[tr], Str])
        Zte = np.column_stack([np.ones(len(te)), season[te], Ste])
        pen = np.array([False] * (1 + season.shape[1]) + [True] * Str.shape[1])
        m = NewtonPartialLogistic(C=CD, eps=eps).fit(Ztr, y[tr], pen, classes=[0, 1])
        return m, m.predict_proba(Zte)[:, 1]

    D = np.flatnonzero(dev)
    cv = list(StratifiedGroupKFold(4, shuffle=True, random_state=seed).split(np.zeros(len(D)), y[D], groups[D]))
    lossD = {CD: np.mean([metrics.losses(y[D[te]], fitD(D[tr], D[te], CD)[1]).mean() for tr, te in cv]) for CD in grid}
    CD = min(grid, key=lambda C: (round(lossD[C], 12), C))

    def fitter(tr, te, CX):
        mD, pD = fitD(tr, te, CD)
        Str, Ste = basis(tr, te)
        s = math.sqrt(CD / CX)
        Atr, Ate = fit_transform_x(X[tr], X[te])
        Ztr = np.column_stack([np.ones(len(tr)), season[tr], s * Str, Atr])
        Zte = np.column_stack([np.ones(len(te)), season[te], s * Ste, Ate])
        pen = np.array([False] * (1 + season.shape[1]) + [True] * (Str.shape[1] + Atr.shape[1]))
        mDX = NewtonPartialLogistic(C=CX, eps=eps).fit(Ztr, y[tr], pen, classes=[0, 1])
        return mD, mDX, pD, mDX.predict_proba(Zte)[:, 1], Atr.shape[1]
    return fitter, CD


def main():
    cfg = config()
    dc = cfg["downstream"]
    grid, eps, seed = dc["C_grid"], dc["eps_unpenalized_ridge"], dc["inner_seed"]
    cap = json.loads(CAP.read_text())["ontologies"]
    rows, onts = build(cfg)
    dh = np.load(private(cfg) / "dhat_body_primary.npz", allow_pickle=False)
    dev, test = dh["dev"], dh["test_mask"]
    Z = np.load(private(cfg) / "X.npz", allow_pickle=False)
    assert list(Z["csn"]) == [r["CSN"] for r in rows]
    X, xnames = Z["X"], list(Z["names"])
    season = np.array([[1.0 if r["season"] == s else 0.0 for s in DS.SEASONS[1:]] for r in rows])
    y = np.array([int(r["y_icu"]) for r in rows])
    groups = np.array([r["MRN"] for r in rows])
    Te = np.flatnonzero(test)

    # primary 20-class labels / posterior
    body = [onts["R2_ccsr_body_system"][r["CSN"]] for r in rows]
    bcls = sorted(set(body))
    yb = np.array([bcls.index(v) for v in body])
    ref = max(range(len(bcls)), key=lambda k: ((yb[dev] == k).sum(), bcls[k]))
    assert bcls[ref] == cap["R2_ccsr_body_system"]["reference_class"]
    P20 = CR.frozen_encoder(cfg, "R2_ccsr_body_system")
    keep = [k for k in range(len(bcls)) if k != ref]
    Bmat = lambda Dcols: np.column_stack([np.ones(len(y)), Dcols, season])

    variants, notes = {}, {}
    # REF
    variants["REF_primary20"] = pair_standard(Bmat(P20[:, keep]), X, y, eps)
    # 1a aggregated 127 -> 20
    r5 = [onts["R5_ccsr_category_min50"][r["CSN"]] for r in rows]
    R5 = np.load(CR.PRIV / "dhat_R5_ccsr_category_min50.npz", allow_pickle=False)
    P127, c127 = R5["P"], list(R5["classes"])
    assert c127 == sorted(set(r5))
    to_body, mixed = [], {}
    for c in c127:
        cnt = Counter(b for b, rr, d in zip(body, r5, dev) if rr == c and d)
        top, n = cnt.most_common(1)[0]
        to_body.append(bcls.index(top))
        if len(cnt) > 1:
            mixed[c] = {"dev_members": int(sum(cnt.values())), "share_not_majority": round(1 - n / sum(cnt.values()), 4)}
    Agg = np.zeros((len(y), len(bcls)))
    for j, b in enumerate(to_body):
        Agg[:, b] += P127[:, j]
    notes["1a_mixed_classes"] = mixed
    variants["1a_agg127to20"] = pair_standard(Bmat(Agg[:, keep]), X, y, eps)
    # 1b PCA-19 of the 127 posterior (fitted on development rows)
    pca = PCA(n_components=len(keep), random_state=0).fit(P127[dev])
    notes["1b_explained_variance"] = round(float(pca.explained_variance_ratio_.sum()), 4)
    variants["1b_pca127_19"] = pair_standard(Bmat(pca.transform(P127)), X, y, eps)
    # 1c 20-class encoder refitted at C = 0.01
    CR.ENC_GRID = [0.01]
    P20c, q = CR.encode(cfg, yb, groups, dev, test)
    np.savez_compressed(CR.PRIV / "dhat_R2_body_C001.npz", P=P20c)
    notes["1c_encoder"] = {k: q[k] for k in ("C_star", "relative_reduction", "top1_accuracy", "nonconverged_fits")}
    variants["1c_enc20_C001"] = pair_standard(Bmat(P20c[:, keep]), X, y, eps)
    # 2a additive log-ratio
    L = np.log(np.clip(P20, 1e-6, None))
    ALR = L[:, keep] - L[:, [ref]]
    variants["2a_alr20"] = pair_standard(Bmat(ALR), X, y, eps)
    # 2b spline-expanded ALR with tuned penalty
    f2b, CD = spline_fitter(ALR, season, X, y, eps, grid, groups, dev, seed)
    notes["2b_C_D"] = CD
    variants["2b_spline_alr20"] = f2b
    # 5 comparator matched to MIMIC X1
    want = ["age"] + [n for n in xnames if n.startswith(("sex=", "arrival_mode="))] + TRIAGE + [f"lab={l}" for l in MATCH_LABS]
    cols = [xnames.index(n) for n in want if n in xnames]
    notes["5_matched_columns"] = {"n": len(cols), "missing_from_X": [n for n in want if n not in xnames]}
    variants["5_xmatch_mimic"] = pair_standard(Bmat(P20[:, keep]), X[:, cols], y, eps)

    res, lD, lDX = {}, {}, {}
    for name, fitter in variants.items():
        C, pD, pDX, conv = tune_and_fit(fitter, y, groups, dev, test, grid, seed)
        s = metrics.summary(y[Te], pD, pDX)
        lD[name], lDX[name] = metrics.losses(y[Te], pD), metrics.losses(y[Te], pDX)
        res[name] = {"C_selected": C, "converged": conv, "L_D_bits": s["L_D_bits"], "L_DX_bits": s["L_DX_bits"],
                     "delta_bits": s["delta_bits"], "relative_gain": s["relative_gain"], "auroc_D": s["auroc_D"], "auroc_DX": s["auroc_DX"]}
        print(name, C, round(s["relative_gain"], 4), flush=True)
        if name == "REF_primary20":
            r = cap["R2_ccsr_body_system"]["soft_dhat"]
            ci = metrics.bootstrap(y[Te], pD, pDX, groups[Te], REPS, SEED)
            dev_ = max(abs(s["L_D_bits"] - r["L_D_bits"]), abs(s["L_DX_bits"] - r["L_DX_bits"]),
                       abs(ci["delta_bits"]["lo"] - r["ci95"]["delta_bits"]["lo"]), abs(ci["delta_bits"]["hi"] - r["ci95"]["delta_bits"]["hi"]))
            gate = {"max_abs_dev_bits": dev_, "passed": dev_ <= TOL}
            if not gate["passed"]:
                write_json(OUT, "robustness", {"status": "STOPPED: reproduction gate failed", "gate": gate})
                return
    uniq, inv = np.unique(groups[Te], return_inverse=True)
    members = [np.flatnonzero(inv == k) for k in range(len(uniq))]
    rng = np.random.default_rng(SEED)
    draws = {n: [] for n in variants}
    for _ in range(REPS):
        idx = np.concatenate([members[k] for k in rng.integers(0, len(uniq), len(uniq))])
        for n in variants:
            a, b = lD[n][idx].mean(), lDX[n][idx].mean()
            draws[n].append(((a - b) / a, (a - b) / LN2))
    for n in variants:
        dr = np.array(draws[n]); ref_d = np.array(draws["REF_primary20"])
        res[n]["ci95"] = {"relative_gain": [float(np.percentile(dr[:, 0], 2.5)), float(np.percentile(dr[:, 0], 97.5))],
                          "delta_bits": [float(np.percentile(dr[:, 1], 2.5)), float(np.percentile(dr[:, 1], 97.5))]}
        if n != "REF_primary20":
            dd = dr[:, 0] - ref_d[:, 0]
            res[n]["paired_diff_relative_gain_vs_REF"] = {"point": res[n]["relative_gain"] - res["REF_primary20"]["relative_gain"],
                                                          "lo": float(np.percentile(dd, 2.5)), "hi": float(np.percentile(dd, 97.5))}
    write_json(OUT, "robustness", {"label": "EXPLORATORY post-confirmatory robustness follow-up; opened test set reused descriptively; no margin applied",
                                   "plan": "exploratory/robustness_followup/plan.md", "reps": REPS, "seed": SEED,
                                   "reproduction_gate": gate, "notes": notes, "variants": res,
                                   "reference_127_class": cap["R5_ccsr_category_min50"]["soft_dhat"]["relative_gain"]})


if __name__ == "__main__":
    main()
