"""Stage E: diagnosis encoder X_3h -> visit-diagnosis class; cross-fitted soft D_hat_3h.

  python -m src.mcmed.encoder --taxonomy body              # primary (hash split)
  python -m src.mcmed.encoder --taxonomy chapter           # S2 (after the primary result is frozen)
  python -m src.mcmed.encoder --taxonomy body --split chrono   # S4 (after the primary result is frozen)

The encoder never sees the ICU outcome, the disposition, or anything after T. Its only
supervision is the visit diagnosis class, and C is chosen by diagnosis log loss only.

Development: 5-fold patient-grouped cross-fitting. For fold f, C_f is chosen by an inner 4-fold
patient-grouped CV on the other folds, the encoder is fit on the other folds, and fold f is
predicted (out-of-fold D_hat). Locked test: C* is chosen by the mean held-out loss over the same
5 development folds, the encoder is fit on all development patients, and the test set is
predicted once.
"""

import argparse
import math
import warnings
from collections import Counter
import multiprocessing

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold

import src.mcmed  # noqa: F401  (thread limits)
from src.mcmed.common import OUT, config, private, read_cohort, read_split
from src.preflight.reporting import write_json
from src.preflight.simple_incremental_models import fit_transform_x

LN2 = math.log(2)
_S = {}


def masks(cfg, rows, split_mode):
    if split_mode == "primary":
        split = read_split(cfg)
        dev = np.array([split[r["MRN"]] == "dev" for r in rows])
        test = ~dev
    else:  # chronological split of the dataset (S4); visits outside it are not used
        dev = np.array([r["chrono"] in ("train", "val") for r in rows])
        test = np.array([r["chrono"] == "test" for r in rows])
    return dev, test


def _fit(tr, C):
    X, y, K = _S["X"], _S["y"], _S["K"]
    Atr, _ = fit_transform_x(X[tr], X[tr][:1])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ConvergenceWarning)
        m = LogisticRegression(C=C, max_iter=_S["max_iter"], tol=_S["tol"]).fit(Atr, y[tr])
    conv = not any(issubclass(x.category, ConvergenceWarning) for x in w)
    return m, conv


def _predict(m, tr, te):
    X, K = _S["X"], _S["K"]
    _, Ate = fit_transform_x(X[tr], X[te])
    P = np.zeros((len(te), K))
    P[:, m.classes_] = m.predict_proba(Ate)
    return P


def mlogloss(y, P):
    return float(-np.mean(np.log(np.clip(P[np.arange(len(y)), y], 1e-15, 1))))


def _task(args):
    kind, f, j, C, tr, te = args
    m, conv = _fit(tr, C)
    P = _predict(m, tr, te)
    return kind, f, j, C, mlogloss(_S["y"][te], P), conv, (P if kind == "outer" else None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", choices=["body", "chapter"], default="body")
    ap.add_argument("--split", choices=["primary", "chrono"], default="primary")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    cfg = config()
    ec, grid = cfg["encoder"], cfg["downstream"]["C_grid"]
    p = private(cfg)
    tag = f"{a.taxonomy}_{a.split}"
    out_file = p / f"dhat_{tag}.npz"
    if out_file.exists():
        raise SystemExit(f"{out_file} exists: test D_hat is produced exactly once")
    rows = read_cohort(cfg)
    Z = np.load(p / "X.npz", allow_pickle=False)
    assert list(Z["csn"]) == [r["CSN"] for r in rows]
    labels = [r["dx_body" if a.taxonomy == "body" else "dx_chapter"] for r in rows]
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels])
    groups = np.array([r["MRN"] for r in rows])
    dev, test = masks(cfg, rows, a.split)
    D, Te = np.flatnonzero(dev), np.flatnonzero(test)
    _S.update(X=Z["X"], y=y, K=len(classes), max_iter=ec["max_iter"], tol=ec["tol"])

    outer = list(StratifiedGroupKFold(ec["crossfit_folds"], shuffle=True, random_state=ec["crossfit_seed"])
                 .split(np.zeros(len(D)), y[D], groups[D]))
    tasks = []
    for f, (tr, te) in enumerate(outer):
        tr, te = D[tr], D[te]
        for C in grid:
            tasks.append(("outer", f, -1, C, tr, te))
        inner = StratifiedGroupKFold(ec["inner_folds"], shuffle=True, random_state=ec["crossfit_seed"] + 1 + f)
        for j, (itr, ite) in enumerate(inner.split(np.zeros(len(tr)), y[tr], groups[tr])):
            for C in grid:
                tasks.append(("inner", f, j, C, tr[itr], tr[ite]))
    # fork (explicit: Python 3.14 defaults to forkserver on Linux) so workers share the data in _S.
    with multiprocessing.get_context("fork").Pool(a.workers) as pool:
        res = pool.map(_task, tasks, chunksize=1)

    nonconv = [(k, f, j, C) for k, f, j, C, _, conv, _ in res if not conv]
    inner_loss = {(f, C): np.mean([l for k, ff, j, CC, l, _, _ in res if k == "inner" and ff == f and CC == C])
                  for f in range(len(outer)) for C in grid}
    outer_loss = {(f, C): l for k, f, j, C, l, _, _ in res if k == "outer"}
    outer_pred = {(f, C): P for k, f, j, C, _, _, P in res if k == "outer"}
    bad_inner = {(f, C) for k, f, j, C in nonconv if k == "inner"}
    bad_outer = {C for k, f, j, C in nonconv if k == "outer"}

    def pick(d, bad):  # lowest loss among converged C values, ties -> smaller C
        ok = [C for C in grid if C not in bad]
        if not ok:
            raise SystemExit("STOP: no C value converged in every fit")
        return min(ok, key=lambda C: (round(d[C], 12), C))
    C_f = [pick({C: inner_loss[(f, C)] for C in grid}, {C for ff, C in bad_inner if ff == f}) for f in range(len(outer))]
    oof = np.zeros((len(y), len(classes)))
    fold_of = np.full(len(y), -1)
    for f, (tr, te) in enumerate(outer):
        oof[D[te]] = outer_pred[(f, C_f[f])]
        fold_of[D[te]] = f
    C_star = pick({C: np.mean([outer_loss[(f, C)] for f in range(len(outer))]) for C in grid}, bad_outer)
    m, conv_final = _fit(D, C_star)
    P_test = _predict(m, D, Te)

    # Diagnostics (development, out-of-fold); class-prior baseline uses each fold's training prior.
    yD = y[D]
    prior = np.zeros((len(y), len(classes)))
    for f, (tr, te) in enumerate(outer):
        cnt = np.bincount(y[D[tr]], minlength=len(classes)).astype(float)
        prior[D[te]] = cnt / cnt.sum()
    ll, ll0 = mlogloss(yD, oof[D]), mlogloss(yD, prior[D])
    per_fold = [{"fold": f, "C": C_f[f], "logloss": mlogloss(y[D[te]], oof[D[te]]),
                 "prior_logloss": mlogloss(y[D[te]], prior[D[te]])} for f, (tr, te) in enumerate(outer)]
    pred = oof[D].argmax(1)
    maj = Counter(yD.tolist()).most_common(1)[0][1] / len(yD)
    acc = float((pred == yD).mean())
    conf = oof[D].max(1)
    ece_bins = np.clip((conf * 10).astype(int), 0, 9)
    ece = float(sum(abs((pred[ece_bins == b] == yD[ece_bins == b]).mean() - conf[ece_bins == b].mean()) * (ece_bins == b).mean()
                    for b in range(10) if (ece_bins == b).sum() > 0))
    recall = {c: {"n_dev": int((yD == k).sum()), "recall": float((pred[yD == k] == k).mean())}
              for k, c in enumerate(classes)}
    ad = ec["adequacy"]
    rel = (ll0 - ll) / ll0
    adequate = (rel >= ad["min_relative_logloss_reduction_vs_prior"]
                and all(pf["logloss"] < pf["prior_logloss"] for pf in per_fold)
                and acc > maj)
    np.savez_compressed(out_file, oof=oof, test=P_test, dev=dev, test_mask=test, classes=np.array(classes),
                        fold=fold_of, csn=Z["csn"])
    write_json(OUT, f"stageE_encoder_{tag}", {
        "taxonomy": a.taxonomy, "split": a.split, "classes": classes, "n_classes": len(classes),
        "n_features_raw": int(Z["X"].shape[1]), "dev_visits": int(len(D)), "test_visits": int(len(Te)),
        "C_per_fold": C_f, "C_star_final": C_star,
        "nonconverged_fits": [list(map(str, t)) for t in nonconv], "final_converged": conv_final,
        "dev_oof": {"logloss_nats": ll, "logloss_bits": ll / LN2, "prior_logloss_nats": ll0,
                    "relative_reduction_vs_prior": rel, "top1_accuracy": acc, "majority_class_share": maj,
                    "macro_f1": float(f1_score(yD, pred, average="macro")),
                    "top_label_ece": ece, "per_fold": per_fold, "classwise_recall": recall},
        "adequacy_rule": ad, "adequate": bool(adequate),
        "test_dhat": "produced once from the encoder fit on all development patients (no test labels used)",
    })


if __name__ == "__main__":
    main()
