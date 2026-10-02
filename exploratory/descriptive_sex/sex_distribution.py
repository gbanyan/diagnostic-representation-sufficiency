"""Descriptive sex distribution of the analysis cohorts (SAGER). See plan.md.

Run on gbminipc from the repo root:  python -m exploratory.descriptive_sex.sex_distribution
Reads private patient-level files; writes aggregates only (cells < 10 shown as "<10").
"""
import csv
import json
from collections import Counter
from pathlib import Path

from src.preflight import simple_incremental_models as sim
from src.mcmed.common import config, data_path, read_cohort, read_split

PRIVATE = Path("/mnt/SAM1TB/dev/data/diagnosis-bottleneck-private")
OUT = Path(__file__).resolve().parent / "results" / "sex_distribution.json"


def cell(k, n):
    return {"n": k if k >= 10 else "<10", "pct": round(100 * k / n, 1) if k >= 10 and n else None}


def levels(counter, n):
    """Complementary suppression: a level below 10 is merged with the largest other
    non-female level so that it cannot be recovered by subtraction from n."""
    c = dict(counter)
    small = [k for k, v in c.items() if v < 10]
    if small:
        rest = sorted((k for k in c if k not in small and k != "F"), key=lambda k: -c[k])
        if rest:
            merged = "+".join([rest[0]] + sorted(small))
            c[merged] = c.pop(rest[0]) + sum(c.pop(k) for k in small)
    return {lvl: cell(k, n) for lvl, k in sorted(c.items())}


def mimic():
    table = PRIVATE / "mimic_iv_expanded_dxproc_landmark_table.csv"
    _, _, _, rows, y, *_ = sim.prepare(str(table), "T1", 6, False, "green_only")
    fem = [int(float(r["female"])) for r in rows]
    ev = [f for f, yy in zip(fem, y) if yy == 1]
    return {"cohort": "MIMIC-IV T1 primary (green_only, L6)", "n": len(rows), "female": cell(sum(fem), len(rows)),
            "events": len(ev), "female_among_events": cell(sum(ev), len(ev)),
            "source_field": "hosp/patients.gender (F/M) -> female"}


def mcmed():
    cfg = config()
    cohort, split = read_cohort(cfg), read_split(cfg)
    with open(data_path(cfg, "visits.csv"), newline="") as f:
        g = {r["CSN"]: (r["Gender"] or "MISSING") for r in csv.DictReader(f)}
    out = {"source_field": "visits.csv Gender"}
    for name, sel in (("all", lambda r: True), ("development", lambda r: split[r["MRN"]] == "dev"),
                      ("test", lambda r: split[r["MRN"]] != "dev")):
        rs = [r for r in cohort if sel(r)]
        icu = [r for r in rs if r["y_icu"] == "1"]
        out[name] = {"n": len(rs), "levels": levels(Counter(g[r["CSN"]] for r in rs), len(rs)),
                     "icu": len(icu), "levels_among_icu": levels(Counter(g[r["CSN"]] for r in icu), len(icu))}
    return out


if __name__ == "__main__":
    res = {"mimic_iv": mimic(), "mc_med": mcmed()}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))
