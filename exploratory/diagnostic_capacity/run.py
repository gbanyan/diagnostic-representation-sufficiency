"""EXPLORATORY diagnostic-capacity curve (plan.md, fixed before running).

  python -m exploratory.diagnostic_capacity.run [R3 R4 ...]

Reads frozen confirmatory artifacts read-only. Exploratory D_hat files go to a separate private
directory; committed output is aggregate JSON only.
"""

import json
import math
import multiprocessing
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold

import src.mcmed  # noqa: F401  (thread limits)
from exploratory.diagnostic_capacity.ontologies import build
from src.mcmed import downstream as DS
from src.mcmed import encoder as E
from src.mcmed import metrics
from src.mcmed.common import config, private
from src.preflight.reporting import write_json

OUT = Path(__file__).resolve().parent / "results"
PRIV = Path("/mnt/SAM1TB/dev/data/diagnosis-bottleneck-private/mcmed_exploratory")
ENC_GRID = [1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3]
BOOT_REPS, BOOT_SEED = 1000, 20261006
LN2 = math.log(2)
FROZEN = {"R1_icd10_chapter": "dhat_chapter_primary.npz", "R2_ccsr_body_system": "dhat_body_primary.npz"}
HINDSIGHT = {"R2_ccsr_body_system", "R5_ccsr_category_min50", "R7_icd10_3char_min50"}


def encode(cfg, y, groups, dev, test):
    ec = cfg["encoder"]
    D, Te = np.flatnonzero(dev), np.flatnonzero(test)
    K = int(y.max()) + 1
    Z = np.load(private(cfg) / "X.npz", allow_pickle=False)
    E._S.update(X=Z["X"], y=y, K=K, max_iter=ec["max_iter"], tol=ec["tol"])
    outer = list(StratifiedGroupKFold(5, shuffle=True, random_state=ec["crossfit_seed"])
                 .split(np.zeros(len(D)), y[D], groups[D]))
    tasks = []
    for f, (tr, te) in enumerate(outer):
        tr, te = D[tr], D[te]
        tasks += [("outer", f, -1, C, tr, te) for C in ENC_GRID]
        inner = StratifiedGroupKFold(4, shuffle=True, random_state=ec["crossfit_seed"] + 1 + f)
        for j, (itr, ite) in enumerate(inner.split(np.zeros(len(tr)), y[tr], groups[tr])):
            tasks += [("inner", f, j, C, tr[itr], tr[ite]) for C in ENC_GRID]
    with multiprocessing.get_context("fork").Pool(8) as pool:
        res = pool.map(E._task, tasks, chunksize=1)
    bad = {(k, f, C) for k, f, j, C, _, ok, _ in res if not ok}

    def pick(losses, excluded):
        ok = [C for C in ENC_GRID if C not in excluded]
        return min(ok, key=lambda C: (round(losses[C], 12), C))
    C_f = [pick({C: np.mean([l for k, ff, j, CC, l, _, _ in res if k == "inner" and ff == f and CC == C]) for C in ENC_GRID},
                {C for k, ff, C in bad if k == "inner" and ff == f}) for f in range(5)]
    oof = np.zeros((len(y), K))
    for f, (tr, te) in enumerate(outer):
        oof[D[te]] = next(P for k, ff, j, CC, _, _, P in res if k == "outer" and ff == f and CC == C_f[f])
    C_star = pick({C: np.mean([l for k, ff, j, CC, l, _, _ in res if k == "outer" and CC == C]) for C in ENC_GRID},
                  {C for k, ff, C in bad if k == "outer"})
    m, conv = E._fit(D, C_star)
    P = oof.copy()
    P[Te] = E._predict(m, D, Te)
    prior = np.zeros_like(oof)
    for f, (tr, te) in enumerate(outer):
        cnt = np.bincount(y[D[tr]], minlength=K).astype(float)
        prior[D[te]] = cnt / cnt.sum()
    ll, ll0 = E.mlogloss(y[D], oof[D]), E.mlogloss(y[D], prior[D])
    q = {"C_per_fold": C_f, "C_star": C_star, "nonconverged_fits": len(bad), "final_converged": conv,
         "oof_logloss_bits": ll / LN2, "prior_logloss_bits": ll0 / LN2, "diagnostic_info_bits": (ll0 - ll) / LN2,
         "relative_reduction": (ll0 - ll) / ll0, "top1_accuracy": float((oof[D].argmax(1) == y[D]).mean()),
         "macro_f1": float(f1_score(y[D], oof[D].argmax(1), average="macro")),
         "majority_share": Counter(y[D].tolist()).most_common(1)[0][1] / len(D)}
    return P, q


def frozen_encoder(cfg, name):
    Ez = np.load(private(cfg) / FROZEN[name], allow_pickle=False)
    P = np.where(Ez["dev"][:, None], Ez["oof"], np.nan)
    P[Ez["test_mask"]] = Ez["test"]
    return P


_W = {}


def _inner(args):
    tr, te, C = args
    _, _, pD, pDX, _ = DS.fit_pair(_W["d"], tr, te, C, _W["eps"])
    return C, te, pDX


def downstream(cfg, base, P, y, groups, dev, test, ref_col):
    dc = cfg["downstream"]
    keep = [k for k in range(P.shape[1]) if k != ref_col]
    B = np.column_stack([np.ones(len(y)), P[:, keep], base["season"]])
    d = dict(B=B, X=base["X"], y=y)
    _W.update(d=d, eps=dc["eps_unpenalized_ridge"])
    D, Te = np.flatnonzero(dev), np.flatnonzero(test)
    cv = list(StratifiedGroupKFold(4, shuffle=True, random_state=dc["inner_seed"]).split(np.zeros(len(D)), y[D], groups[D]))
    with multiprocessing.get_context("fork").Pool(8) as pool:
        res = pool.map(_inner, [(D[tr], D[te], C) for tr, te in cv for C in dc["C_grid"]], chunksize=1)
    loss = {C: np.mean([metrics.losses(y[te], p).mean() for CC, te, p in res if CC == C]) for C in dc["C_grid"]}
    C_sel = min(dc["C_grid"], key=lambda C: (round(loss[C], 12), C))
    mD, mDX, pD, pDX, _ = DS.fit_pair(d, D, Te, C_sel, dc["eps_unpenalized_ridge"])
    s = metrics.summary(y[Te], pD, pDX)
    ci = metrics.bootstrap(y[Te], pD, pDX, groups[Te], BOOT_REPS, BOOT_SEED)
    return {"D_columns": len(keep), "C_selected": C_sel, "converged": bool(mD.converged_ and mDX.converged_),
            "L_D_bits": s["L_D_bits"], "L_DX_bits": s["L_DX_bits"], "delta_bits": s["delta_bits"],
            "relative_gain": s["relative_gain"], "auroc_D": s["auroc_D"], "auroc_DX": s["auroc_DX"],
            "ci95": {k: ci[k] for k in ("delta_bits", "relative_gain", "auroc_diff")}}


def main(which):
    cfg = config()
    PRIV.mkdir(parents=True, exist_ok=True)
    rows, onts = build(cfg)
    dhat0 = np.load(private(cfg) / "dhat_body_primary.npz", allow_pickle=False)
    dev, test = dhat0["dev"], dhat0["test_mask"]
    Z = np.load(private(cfg) / "X.npz", allow_pickle=False)
    assert list(Z["csn"]) == [r["CSN"] for r in rows]
    base = {"X": Z["X"], "season": np.array([[1.0 if r["season"] == s else 0.0 for s in DS.SEASONS[1:]] for r in rows])}
    y = np.array([int(r["y_icu"]) for r in rows])
    groups = np.array([r["MRN"] for r in rows])
    out_file = OUT / "capacity.json"
    allres = json.loads(out_file.read_text()) if out_file.exists() else {
        "label": "EXPLORATORY capacity curve (post-confirmatory; test set reused descriptively)", "ontologies": {}}
    for name in [n for n in onts if not which or n.split("_")[0] in which]:
        lab = [onts[name][r["CSN"]] for r in rows]
        classes = sorted(set(lab))
        yd = np.array([classes.index(v) for v in lab])
        ref = max(range(len(classes)), key=lambda k: ((yd[dev] == k).sum(), classes[k]))
        if name in FROZEN:
            tag = "chapter_primary" if name.startswith("R1") else "body_primary"
            o = json.loads((Path(__file__).resolve().parents[2] / "results/mcmed" / f"stageE_encoder_{tag}.json").read_text())["dev_oof"]
            P = frozen_encoder(cfg, name)
            q = {"source": f"frozen {FROZEN[name]}", "oof_logloss_bits": o["logloss_nats"] / LN2,
                 "prior_logloss_bits": o["prior_logloss_nats"] / LN2,
                 "diagnostic_info_bits": (o["prior_logloss_nats"] - o["logloss_nats"]) / LN2,
                 "relative_reduction": o["relative_reduction_vs_prior"], "top1_accuracy": o["top1_accuracy"],
                 "macro_f1": o["macro_f1"], "majority_share": o["majority_class_share"]}
        else:
            P, q = encode(cfg, yd, groups, dev, test)
            np.savez_compressed(PRIV / f"dhat_{name}.npz", P=P, classes=np.array(classes))
        entry = {"n_classes": len(classes), "reference_class": classes[ref], "encoder": q,
                 "soft_dhat": downstream(cfg, base, P, y, groups, dev, test, ref)}
        if name in HINDSIGHT:
            entry["hindsight_label_reference"] = downstream(cfg, base, np.eye(len(classes))[yd], y, groups, dev, test, ref)
        allres["ontologies"][name] = entry
        write_json(OUT, "capacity", allres)
        print(name, len(classes), round(entry["soft_dhat"]["relative_gain"], 4), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
