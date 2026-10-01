"""Binary probabilistic metrics and the patient-cluster bootstrap (locked test set)."""

import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import average_precision_score, roc_auc_score

LN2 = math.log(2)
P_EPS = 1e-15


def losses(y, p):
    p = np.clip(p, P_EPS, 1 - P_EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calibration(y, p):
    """Calibration intercept (calibration-in-the-large, slope fixed at 1) and slope (logistic recalibration)."""
    p = np.clip(p, P_EPS, 1 - P_EPS)
    lp = np.log(p / (1 - p))

    def nll(w, fix_slope):
        z = w[0] + (lp if fix_slope else w[1] * lp)
        return np.sum(np.logaddexp(0, z) - y * z)
    a = minimize(lambda w: nll(w, True), [0.0], method="BFGS").x[0]
    b = minimize(lambda w: nll(w, False), [0.0, 1.0], method="BFGS").x
    return {"intercept_citl": float(a), "slope": float(b[1]), "recal_intercept": float(b[0])}


def deciles(y, p, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    out = []
    for k in range(bins):
        m = idx == k
        ev = int(y[m].sum())
        if m.sum() < 10:
            continue
        small = 0 < ev < 10  # small-cell rule: event counts 1-9 are not disclosed, even implicitly
        out.append({"bin": int(k), "n": int(m.sum()), "mean_pred": float(p[m].mean()),
                    "observed": None if small else float(y[m].mean()), "events": "<10" if small else ev})
    return out


def summary(y, pD, pDX):
    lD, lDX = losses(y, pD).mean(), losses(y, pDX).mean()
    out = {"n": int(len(y)), "events": int(y.sum()),
           "L_D_nats": float(lD), "L_DX_nats": float(lDX), "delta_L_nats": float(lD - lDX),
           "delta_bits": float((lD - lDX) / LN2), "L_D_bits": float(lD / LN2), "L_DX_bits": float(lDX / LN2),
           "relative_gain": float((lD - lDX) / lD)}
    for tag, p in (("D", pD), ("DX", pDX)):
        out[f"auroc_{tag}"] = float(roc_auc_score(y, p))
        out[f"auprc_{tag}"] = float(average_precision_score(y, p))
        out[f"brier_{tag}"] = float(np.mean((p - y) ** 2))
        out[f"calibration_{tag}"] = calibration(y, p)
        out[f"deciles_{tag}"] = deciles(y, p)
    out["auroc_diff"] = out["auroc_DX"] - out["auroc_D"]
    out["auprc_diff"] = out["auprc_DX"] - out["auprc_D"]
    out["brier_diff"] = out["brier_D"] - out["brier_DX"]
    return out


def bootstrap(y, pD, pDX, groups, reps, seed):
    """Patient-cluster bootstrap: resample patients with replacement, carrying all their visits."""
    rng = np.random.default_rng(seed)
    uniq, inv = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(inv == g) for g in range(len(uniq))]
    lD, lDX = losses(y, pD), losses(y, pDX)
    keys = ["delta_L_nats", "delta_bits", "relative_gain", "auroc_diff", "auprc_diff", "brier_diff", "auroc_D", "auroc_DX"]
    draws = {k: [] for k in keys}
    for _ in range(reps):
        idx = np.concatenate([members[g] for g in rng.integers(0, len(uniq), len(uniq))])
        yy = y[idx]
        a, b = lD[idx].mean(), lDX[idx].mean()
        draws["delta_L_nats"].append(a - b)
        draws["delta_bits"].append((a - b) / LN2)
        draws["relative_gain"].append((a - b) / a)
        if 0 < yy.sum() < len(yy):
            aD, aDX = roc_auc_score(yy, pD[idx]), roc_auc_score(yy, pDX[idx])
            draws["auroc_D"].append(aD)
            draws["auroc_DX"].append(aDX)
            draws["auroc_diff"].append(aDX - aD)
            draws["auprc_diff"].append(average_precision_score(yy, pDX[idx]) - average_precision_score(yy, pD[idx]))
        draws["brier_diff"].append(np.mean((pD[idx] - yy) ** 2) - np.mean((pDX[idx] - yy) ** 2))
    return {k: {"lo": float(np.percentile(v, 2.5)), "hi": float(np.percentile(v, 97.5)), "reps": len(v)}
            for k, v in draws.items()}
