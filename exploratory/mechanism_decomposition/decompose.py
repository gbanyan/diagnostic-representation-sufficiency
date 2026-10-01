"""EXPLORATORY mechanism decomposition of the MC-MED incremental signal (plan.md, fixed before running).

  .venv/bin/python -m exploratory.mechanism_decomposition.decompose

Reads the frozen confirmatory artifacts (read-only) and writes only to
exploratory/mechanism_decomposition/results/. Aggregates only.
"""

import multiprocessing
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

import src.mcmed  # noqa: F401  (thread limits)
from src.mcmed import downstream as DS
from src.mcmed import metrics
from src.mcmed.common import config
from src.mcmed.newton_logistic import NewtonPartialLogistic
from src.preflight.reporting import write_json

OUT = Path(__file__).resolve().parent / "results"
CLIP = 5.0
BOOT_REPS, BOOT_SEED = 1000, 20261005
TRIAGE_VITALS = [f"triage_{m}" for m in ("Temp", "HR", "RR", "SpO2", "SBP", "DBP")]


def families(names):
    idx = lambda pred: [j for j, n in enumerate(names) if pred(n)]
    A1 = idx(lambda n: n in TRIAGE_VITALS)
    A2 = idx(lambda n: n.startswith("num_") and not n.endswith("_count"))
    B = idx(lambda n: n.startswith(("lab=", "lab_abnormal=")))
    C = idx(lambda n: n.startswith("pmh_"))
    Dp = idx(lambda n: n == "age" or n.startswith(("sex=", "arrival_mode=", "cc_")) or n == "triage_ESI")
    counts = idx(lambda n: n.startswith("num_") and n.endswith("_count"))
    A = A1 + A2
    assert len(set(A + B + C + Dp + counts)) == len(names) == len(A + B + C + Dp + counts)
    F = A + B + C + Dp
    ALL = F + counts
    # spec: (value columns, measurement-process block included?)
    return {
        "A_physiology": (A, False), "A1_triage_vitals": (A1, False), "A2_numerics_values": (A2, False),
        "B_labs": (B, False), "C_history": (C, False), "D_presenting": (Dp, False),
        "E_measurement_process": ([], True), "F_state_without_process": (F, False),
        "ALL_minus_A": ([j for j in ALL if j not in A], True), "ALL_minus_B": ([j for j in ALL if j not in B], True),
        "ALL_minus_C": ([j for j in ALL if j not in C], True), "ALL_minus_D": ([j for j in ALL if j not in Dp], True),
        "ALL": (ALL, True),
    }, counts


def design(X, tr, te, cols, process, counts):
    """Values (median-imputed, no indicators) + optional measurement-process block; scaled/clipped on tr."""
    blocks_tr, blocks_te = [], []
    if cols:
        imp = SimpleImputer(strategy="median", keep_empty_features=True).fit(X[tr][:, cols])
        blocks_tr.append(imp.transform(X[tr][:, cols]))
        blocks_te.append(imp.transform(X[te][:, cols]))
    if process:
        miss = [j for j in range(X.shape[1]) if np.isnan(X[tr, j]).any()]
        cnt = [j for j in counts if j not in cols]
        blocks_tr.append(np.column_stack([np.isnan(X[tr][:, miss]).astype(float), X[tr][:, cnt]]))
        blocks_te.append(np.column_stack([np.isnan(X[te][:, miss]).astype(float), X[te][:, cnt]]))
    Atr, Ate = np.column_stack(blocks_tr), np.column_stack(blocks_te)
    sc = StandardScaler().fit(Atr)
    return np.clip(sc.transform(Atr), -CLIP, CLIP), np.clip(sc.transform(Ate), -CLIP, CLIP)


_W = {}


def fit(tr, te, fam, C):
    d, spec, counts = _W["d"], _W["spec"], _W["counts"]
    cols, process = spec[fam]
    B, y = d["B"], d["y"]
    Atr, Ate = design(d["X"], tr, te, cols, process, counts)
    pen = np.array([False] * B.shape[1] + [True] * Atr.shape[1])
    m = NewtonPartialLogistic(C=C, eps=_W["eps"]).fit(np.column_stack([B[tr], Atr]), y[tr], pen)
    return m, m.predict_proba(np.column_stack([B[te], Ate]))[:, 1], Atr.shape[1]


def _task(args):
    fam, tr, te, C = args
    m, p, _ = fit(tr, te, fam, C)
    return fam, C, float(metrics.losses(_W["d"]["y"][te], p).mean()), m.converged_


def main():
    cfg = config()
    dc = cfg["downstream"]
    grid, eps = dc["C_grid"], dc["eps_unpenalized_ridge"]
    d = DS.load(cfg, "primary")
    spec, counts = families(list(d["xnames"]))
    _W.update(d=d, spec=spec, counts=counts, eps=eps)
    D, Te = np.flatnonzero(d["dev"]), np.flatnonzero(d["test"])
    y, groups = d["y"], d["groups"]
    cv = list(StratifiedGroupKFold(dc["inner_folds"], shuffle=True, random_state=dc["inner_seed"])
              .split(np.zeros(len(D)), y[D], groups[D]))
    tasks = [(fam, D[tr], D[te], C) for fam in spec for tr, te in cv for C in grid]
    with multiprocessing.get_context("fork").Pool(8) as pool:
        res = pool.map(_task, tasks, chunksize=1)
    mD = NewtonPartialLogistic(C=1.0, eps=eps).fit(d["B"][D], y[D], np.zeros(d["B"].shape[1], bool))
    pD = mD.predict_proba(d["B"][Te])[:, 1]
    out = {"label": "EXPLORATORY (after the confirmatory result was seen); not confirmatory",
           "test_visits": int(len(Te)), "test_events": int(y[Te].sum()), "model_D_converged": mD.converged_,
           "bootstrap": {"reps": BOOT_REPS, "seed": BOOT_SEED}, "families": {}}
    for fam in spec:
        loss = {C: np.mean([l for f, CC, l, _ in res if f == fam and CC == C]) for C in grid}
        conv = all(ok for f, _, _, ok in res if f == fam)
        C_sel = min(grid, key=lambda C: (round(loss[C], 12), C))
        m, pF, ncols = fit(D, Te, fam, C_sel)
        s = metrics.summary(y[Te], pD, pF)
        ci = metrics.bootstrap(y[Te], pD, pF, groups[Te], BOOT_REPS, BOOT_SEED)
        out["families"][fam] = {
            "value_columns": len(spec[fam][0]), "process_block": spec[fam][1], "model_columns": ncols,
            "C_selected": C_sel, "all_fits_converged": bool(conv and m.converged_),
            "L_D": s["L_D_nats"], "L_DF": s["L_DX_nats"], "delta_L_nats": s["delta_L_nats"], "delta_bits": s["delta_bits"],
            "relative_gain": s["relative_gain"], "auroc_D": s["auroc_D"], "auroc_DF": s["auroc_DX"],
            "ci95": {k: ci[k] for k in ("delta_L_nats", "delta_bits", "relative_gain", "auroc_diff")},
        }
        print(fam, C_sel, round(s["relative_gain"], 4), flush=True)
    write_json(OUT, "mechanism_decomposition", out)


if __name__ == "__main__":
    main()
