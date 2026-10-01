"""EXPLORATORY T1 decomposition and residual-signal heterogeneity (docs/t1_exploratory_plan.md).

Not confirmatory: one outer repeat, descriptive bootstrap intervals, no p-values.

  python -m src.exploratory.t1_heterogeneity subtypes          # private ICD complication subtype file
  python -m src.exploratory.t1_heterogeneity run --config <name> [--table-name ...] [--t1-timing ...]
"""

import argparse
import csv
import re
import warnings
from collections import defaultdict

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

import src.confirmatory  # noqa: F401  (thread limits)
from audit.cdm_audit import open_text
from src.confirmatory import target_sufficiency as ts
from src.confirmatory.partial_logistic import PartialLogistic
from src.preflight import schemas, simple_incremental_models as sim, targets
from src.preflight.reporting import private_dir, suppress, write_json

SEED = ts.OUTER_SEEDS[0]
N_BOOT = 1000
COMPLICATED = re.compile(r"\bwith\b[^,;]*?(perforation|abscess|peritonitis|gangren|necrosis|obstruction|cholangitis)",
                         re.IGNORECASE)
GROUPS = {
    "demo_history": ["age", "female", "prior_admissions", "arrival_ambulance"],
    "triage": targets.TRIAGE,
    "labs_inflammatory": ["wbc", "neut_pct", "crp", "lactate"],
    "labs_hepatobiliary_pancreatic": ["tbili", "alt", "ast", "alp", "lipase"],
    "labs_renal_metabolic": ["creat", "bun", "glucose", "sodium", "potassium", "bicarb", "calcium"],
    "labs_hematologic_other": ["hgb", "plt", "inr", "albumin"],
}


def group_features(name, L):
    """Feature column names for a group (lab groups hold short lab names)."""
    return [f"lab_{f}_L{L}" if name.startswith("labs") else f for f in GROUPS[name]]


# --- configurations ---------------------------------------------------------------------

def configs():
    c = {}
    for inter in (False, True):
        for ctx in ("none", "era_main", "full"):
            for pen in ("partial", "shared"):
                c[f"fx_I{int(inter)}_{ctx}_{pen}"] = {"interactions": inter, "context": ctx, "penalty": pen}
    c["conf"] = {"interactions": False, "context": "full", "penalty": "partial"}
    for g in GROUPS:
        c[f"only_{g}"] = {**c["conf"], "only_group": g}
        c[f"minus_{g}"] = {**c["conf"], "minus_group": g}
    c["values_only"] = {**c["conf"], "xmode": "values"}
    c["missing_only"] = {**c["conf"], "xmode": "missing"}
    c["subtype"] = {**c["conf"], "subtype": True}
    return c


# --- design -----------------------------------------------------------------------------

def base(rows, d_levels, context, subtypes=None):
    if context == "none":
        B = np.column_stack([np.ones(len(rows))] + [[1.0 if r["D"] == d else 0.0 for r in rows] for d in d_levels[1:]])
    else:
        B, _ = ts.base_matrix(rows, d_levels, context)
    if subtypes is not None:
        cols = [[1.0 if (r["D"] == d and subtypes.get(r["hadm_id"]) == "complicated") else 0.0 for r in rows]
                for d in d_levels]
        B = np.column_stack([B] + cols)
    return B


def xblock(Xr, tr, te, feats, xmode):
    if xmode == "full":
        return sim.fit_transform_x(Xr[tr], Xr[te], sim.log_columns(feats))
    if xmode == "missing":
        Mtr, Mte = np.isnan(Xr[tr]).astype(float), np.isnan(Xr[te]).astype(float)
        keep = Mtr.std(axis=0) > 0
        if not keep.any():                      # no missingness varies -> no X information
            return np.zeros((len(tr), 0)), np.zeros((len(te), 0))
        sc = StandardScaler()
        return sc.fit_transform(Mtr[:, keep]), sc.transform(Mte[:, keep])
    Xtr, Xte = Xr[tr].copy(), Xr[te].copy()       # values only: no missing indicators
    for j in sim.log_columns(feats):
        Xtr[:, j] = np.log1p(np.clip(Xtr[:, j], 0, None)); Xte[:, j] = np.log1p(np.clip(Xte[:, j], 0, None))
    imp, sc = SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler()
    return (np.clip(sc.fit_transform(imp.fit_transform(Xtr)), -sim.CLIP_Z, sim.CLIP_Z),
            np.clip(sc.transform(imp.transform(Xte)), -sim.CLIP_Z, sim.CLIP_Z))


def build(B, Dfull, Xr, tr, te, feats, cfg):
    Atr, Ate = xblock(Xr, tr, te, feats, cfg.get("xmode", "full"))
    if cfg["interactions"]:
        Atr = np.hstack([Atr] + [Atr * Dfull[tr][:, [k]] for k in range(Dfull.shape[1])])
        Ate = np.hstack([Ate] + [Ate * Dfull[te][:, [k]] for k in range(Dfull.shape[1])])
    shared = cfg["penalty"] == "shared"
    base_pen = np.array([False] + [shared] * (B.shape[1] - 1))
    pen = np.concatenate([base_pen, np.ones(Atr.shape[1], bool)])
    return (B[tr], B[te], base_pen), (np.hstack([B[tr], Atr]), np.hstack([B[te], Ate]), pen)


def pick_C(Ztr_fn, y, idx, strat, groups, seed, classes):
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(inner.split(np.zeros(len(idx)), strat[idx], groups[idx]))
    tot = np.zeros(len(ts.C_GRID))
    for a, b in splits:
        Za, Zb, pen = Ztr_fn(idx[a], idx[b])
        for k, C in enumerate(ts.C_GRID):
            m = PartialLogistic(C=C).fit(Za, y[idx[a]], pen, classes)
            tot[k] += sim.losses(y[idx[b]], m.predict_proba(Zb)[:, 1], "binary", classes).mean()
    best, bl = ts.C_GRID[0], tot[0]
    for C, t in zip(ts.C_GRID[1:], tot[1:]):
        if t < bl - 1e-12:
            best, bl = C, t
    return best


def run_config(rows, y, cfg, feats, d_levels, subtypes):
    classes = [0, 1]
    B = base(rows, d_levels, cfg["context"], subtypes if cfg.get("subtype") else None)
    Dfull = np.array([[1.0 if r["D"] == d else 0.0 for d in d_levels] for r in rows])
    Xr = ts.x_raw(rows, feats)
    groups = np.array([r["subject_id"] for r in rows])
    strat = np.array([f"{v}|{r['anchor_year_group']}" for r, v in zip(rows, y)])
    n = len(rows)
    PD, PDX = np.zeros(n), np.zeros(n)
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splits = list(outer.split(np.zeros(n), strat, groups))
    for k, (tr, te) in enumerate(splits):
        (Btr, Bte, bpen), (Ztr, Zte, pen) = build(B, Dfull, Xr, tr, te, feats, cfg)
        if cfg["penalty"] == "shared":
            fnD = lambda a, b: (B[a], B[b], bpen)
            CD = pick_C(fnD, y, tr, strat, groups, SEED + k, classes)
        else:
            CD = 1.0
        PD[te] = PartialLogistic(C=CD).fit(Btr, y[tr], bpen, classes).predict_proba(Bte)[:, 1]
        fnDX = lambda a, b: (lambda d: (d[1][0], d[1][1], d[1][2]))(build(B, Dfull, Xr, a, b, feats, cfg))
        CX = pick_C(fnDX, y, tr, strat, groups, SEED + k, classes)
        PDX[te] = PartialLogistic(C=CX).fit(Ztr, y[tr], pen, classes).predict_proba(Zte)[:, 1]
    return PD, PDX, groups


def entropy_given_d(rows, y):
    out, n = 0.0, len(y)
    for d in {r["D"] for r in rows}:
        m = np.array([r["D"] == d for r in rows]); p = y[m].mean()
        if 0 < p < 1:
            out += m.sum() / n * -(p * np.log2(p) + (1 - p) * np.log2(1 - p))
    return out


def describe(rows, y, PD, PDX, groups):
    lD, lDX = sim.losses(y, PD, "binary", [0, 1]), sim.losses(y, PDX, "binary", [0, 1])
    rng = np.random.default_rng(SEED)
    idx = defaultdict(list)
    for i, g in enumerate(groups):
        idx[g].append(i)
    uniq = np.array(sorted(idx))
    boots = []
    for _ in range(N_BOOT):
        take = np.concatenate([idx[g] for g in rng.choice(uniq, size=len(uniq), replace=True)])
        boots.append(lD[take].mean() - lDX[take].mean())
    delta = lD.mean() - lDX.mean()
    out = {"n": len(y), "events": suppress(int(y.sum())), "logloss_D": lD.mean(), "logloss_DX": lDX.mean(),
           "delta": delta, "delta_ci95_descriptive": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
           "rel_delta_vs_LL_D": delta / lD.mean(), "H_Y_given_D_empirical": entropy_given_d(rows, y),
           "rel_delta_vs_H_Y_given_D": delta / entropy_given_d(rows, y),
           "auroc_D": sim.auroc(y, PD), "auroc_DX": sim.auroc(y, PDX)}
    for key, keyfn in (("by_diagnosis", lambda r: r["D"]), ("by_era", lambda r: r["anchor_year_group"])):
        res = {}
        for v in sorted({keyfn(r) for r in rows}):
            m = np.array([keyfn(r) == v for r in rows])
            res[v] = {"n": int(m.sum()), "events": suppress(int(y[m].sum())),
                      "delta": float(lD[m].mean() - lDX[m].mean()), "auroc_DX": sim.auroc(y[m], PDX[m])}
        out[key] = res
    return out


# --- commands -------------------------------------------------------------------------------

def cmd_subtypes(priv, table_name):
    table_path = priv / f"{table_name}.csv"
    with open(table_path, newline="") as f:
        ids = {r["hadm_id"] for r in csv.DictReader(f)}
    hosp = schemas.require("mimiciv_hosp", ["diagnoses_icd.csv.gz", "d_icd_diagnoses.csv.gz"])
    titles = {(r["icd_code"].strip(), r["icd_version"].strip()): r["long_title"]
              for r in csv.DictReader(open_text(hosp["d_icd_diagnoses.csv.gz"]))}
    rows = []
    for r in csv.DictReader(open_text(hosp["diagnoses_icd.csv.gz"])):
        if r["seq_num"].strip() == "1" and r["hadm_id"] in ids:
            t = titles.get((r["icd_code"].strip(), r["icd_version"].strip()), "")
            rows.append({"hadm_id": r["hadm_id"], "icd_version": r["icd_version"].strip(),
                         "subtype": "complicated" if COMPLICATED.search(t) else "uncomplicated"})
    path = targets.companion(table_path, "t1_icd_subtypes")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hadm_id", "icd_version", "subtype"]); w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} subtype rows to private dir")


def cmd_run(priv, table_name, name, t1_timing, feature_set, out):
    cfg = configs()[name]
    table = priv / f"{table_name}.csv"
    spec, pairs, col, rows, y, ytype, classes, timing = sim.prepare(table, "T1", 6, False, t1_timing)
    keep = np.array([r.get("anchor_year_group") in ts.ERAS for r in rows])
    rows, y = [r for r, k in zip(rows, keep) if k], y[keep]
    d_levels = sorted({r["D"] for r in rows})
    feats = targets.feature_sets(6)[feature_set]
    if "only_group" in cfg:
        feats = group_features(cfg["only_group"], 6)
    if "minus_group" in cfg:
        drop = set(group_features(cfg["minus_group"], 6))
        feats = [f for f in feats if f not in drop]
    subtypes = None
    if cfg.get("subtype"):
        with open(targets.companion(table, "t1_icd_subtypes"), newline="") as f:
            subtypes = {r["hadm_id"]: r["subtype"] for r in csv.DictReader(f)}
    PD, PDX, groups = run_config(rows, y, cfg, feats, d_levels, subtypes)
    res = {"EXPLORATORY": "not confirmatory; one outer repeat; descriptive intervals; no p-values",
           "config": name, "spec": cfg, "t1_timing": t1_timing, "table": table_name, "features": feature_set,
           "n_features": len(feats), **describe(rows, y, PD, PDX, groups)}
    if subtypes is not None:
        res["subtype_counts"] = {f"{d}|{s}": suppress(sum(1 for r in rows if r["D"] == d and subtypes.get(r["hadm_id"]) == s))
                                 for d in d_levels for s in ("complicated", "uncomplicated")}
    write_json(out, f"{name}__{t1_timing}__{feature_set}__{table_name}", res)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["subtypes", "run", "list"])
    ap.add_argument("--config")
    ap.add_argument("--table-name", default=ts.PRIMARY_TABLE)
    ap.add_argument("--t1-timing", default="green_only", choices=["green_only", "exclude_red"])
    ap.add_argument("--features", default="X1", choices=["X1", "X2"])
    ap.add_argument("--private-dir")
    ap.add_argument("--out", default="results/exploratory/t1")
    args = ap.parse_args(argv)
    if args.command == "list":
        print("\n".join(configs()))
        return
    priv = private_dir(args.private_dir)
    if args.command == "subtypes":
        cmd_subtypes(priv, args.table_name)
    else:
        cmd_run(priv, args.table_name, args.config, args.t1_timing, args.features, args.out)


if __name__ == "__main__":
    main()
