"""EXPLORATORY paired bootstrap differences along the CCSR curve (plan_addendum_paired_diff.md, fixed before running).

  python -m exploratory.diagnostic_capacity.paired_diff

Refits each CCSR level with its recorded C_selected (no re-tuning), checks reproduction against capacity.json,
then evaluates all levels on one shared patient-cluster bootstrap. Committed output is aggregate JSON only.
"""

import json
import math
from pathlib import Path

import numpy as np

import src.mcmed  # noqa: F401  (thread limits)
from exploratory.diagnostic_capacity.ontologies import build
from exploratory.diagnostic_capacity.run import FROZEN, PRIV, frozen_encoder
from src.mcmed import downstream as DS
from src.mcmed import metrics
from src.mcmed.common import config, private
from src.preflight.reporting import write_json

OUT = Path(__file__).resolve().parent / "results"
LEVELS = ["R2_ccsr_body_system", "R3_ccsr_category_min300", "R4_ccsr_category_min100", "R5_ccsr_category_min50"]
REPS, SEED, TOL = 1000, 20261006, 1e-4
LN2 = math.log(2)


def main():
    cfg = config()
    cap = json.loads((OUT / "capacity.json").read_text())["ontologies"]
    rows, onts = build(cfg)
    dhat0 = np.load(private(cfg) / "dhat_body_primary.npz", allow_pickle=False)
    dev, test = dhat0["dev"], dhat0["test_mask"]
    Z = np.load(private(cfg) / "X.npz", allow_pickle=False)
    assert list(Z["csn"]) == [r["CSN"] for r in rows]
    season = np.array([[1.0 if r["season"] == s else 0.0 for s in DS.SEASONS[1:]] for r in rows])
    y = np.array([int(r["y_icu"]) for r in rows])
    groups = np.array([r["MRN"] for r in rows])
    D, Te = np.flatnonzero(dev), np.flatnonzero(test)
    eps = cfg["downstream"]["eps_unpenalized_ridge"]

    lD, lDX, repro = {}, {}, {}
    for name in LEVELS:
        lab = [onts[name][r["CSN"]] for r in rows]
        classes = sorted(set(lab))
        yd = np.array([classes.index(v) for v in lab])
        ref = max(range(len(classes)), key=lambda k: ((yd[dev] == k).sum(), classes[k]))
        assert classes[ref] == cap[name]["reference_class"], name
        P = frozen_encoder(cfg, name) if name in FROZEN else np.load(PRIV / f"dhat_{name}.npz", allow_pickle=False)["P"]
        keep = [k for k in range(P.shape[1]) if k != ref]
        B = np.column_stack([np.ones(len(y)), P[:, keep], season])
        C = cap[name]["soft_dhat"]["C_selected"]
        _, _, pD, pDX, _ = DS.fit_pair(dict(B=B, X=Z["X"], y=y), D, Te, C, eps)
        lD[name], lDX[name] = metrics.losses(y[Te], pD), metrics.losses(y[Te], pDX)
        s, ci = metrics.summary(y[Te], pD, pDX), metrics.bootstrap(y[Te], pD, pDX, groups[Te], REPS, SEED)
        ref_s = cap[name]["soft_dhat"]
        dev_ = {"L_D_bits": abs(s["L_D_bits"] - ref_s["L_D_bits"]), "L_DX_bits": abs(s["L_DX_bits"] - ref_s["L_DX_bits"]),
                "ci_lo": abs(ci["delta_bits"]["lo"] - ref_s["ci95"]["delta_bits"]["lo"]),
                "ci_hi": abs(ci["delta_bits"]["hi"] - ref_s["ci95"]["delta_bits"]["hi"])}
        repro[name] = {"max_abs_dev_bits": max(dev_.values()), "passed": max(dev_.values()) <= TOL}
        print(name, repro[name], flush=True)
    out = {"label": "EXPLORATORY paired bootstrap differences, CCSR curve (post-confirmatory; opened test set reused descriptively)",
           "plan": "exploratory/diagnostic_capacity/plan_addendum_paired_diff.md", "reps": REPS, "seed": SEED,
           "reproduction_gate": repro}
    if not all(v["passed"] for v in repro.values()):
        out["status"] = "STOPPED: reproduction gate failed; no differences reported"
        write_json(OUT, "capacity_paired_diff", out)
        return

    g = groups[Te]
    rng = np.random.default_rng(SEED)
    uniq, inv = np.unique(g, return_inverse=True)
    members = [np.flatnonzero(inv == k) for k in range(len(uniq))]
    stats = {n: {"rel": [], "dbits": [], "LD": [], "LDX": []} for n in LEVELS}
    for _ in range(REPS):
        idx = np.concatenate([members[k] for k in rng.integers(0, len(uniq), len(uniq))])
        for n in LEVELS:
            a, b = lD[n][idx].mean(), lDX[n][idx].mean()
            stats[n]["rel"].append((a - b) / a)
            stats[n]["dbits"].append((a - b) / LN2)
            stats[n]["LD"].append(a / LN2)
            stats[n]["LDX"].append(b / LN2)
    pt = {n: {"rel": (lD[n].mean() - lDX[n].mean()) / lD[n].mean(), "dbits": (lD[n].mean() - lDX[n].mean()) / LN2,
              "LD": lD[n].mean() / LN2, "LDX": lDX[n].mean() / LN2} for n in LEVELS}
    base = LEVELS[0]
    diffs = {}
    for n in LEVELS[1:]:
        diffs[f"{n}_minus_{base}"] = {
            m: {"point": float(pt[n][m] - pt[base][m]),
                "lo": float(np.percentile(np.subtract(stats[n][m], stats[base][m]), 2.5)),
                "hi": float(np.percentile(np.subtract(stats[n][m], stats[base][m]), 97.5))}
            for m in ("rel", "dbits", "LD", "LDX")}
    out.update(status="complete", units={"rel": "relative gain (fraction)", "dbits": "bits/visit", "LD": "bits/visit", "LDX": "bits/visit"},
               points={n: {m: float(v) for m, v in pt[n].items()} for n in LEVELS}, differences=diffs,
               not_done="no trend test, no p-values, no cutoff search, no margin applied to finer levels")
    write_json(OUT, "capacity_paired_diff", out)
    print(json.dumps(diffs, indent=1))


if __name__ == "__main__":
    main()
