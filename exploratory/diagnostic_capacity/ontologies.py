"""EXPLORATORY: candidate diagnosis ontologies for the capacity analysis (counts only, never the outcome).

  python -m exploratory.diagnostic_capacity.ontologies audit

Each ontology maps the visit Dx_ICD10 of the frozen MC-MED cohort to a class. Rare classes are
pooled hierarchically (into OTHER_<parent>), and pooled groups still below the minimum go to OTHER.
Writes aggregate counts only.
"""

import csv
import math
import sys
from collections import Counter
from pathlib import Path

from src.mcmed.cohort import icd_code, load_ccsr
from src.mcmed.common import config, data_path, read_cohort, read_split
from src.preflight.reporting import write_json

OUT = Path(__file__).resolve().parent / "results"
MIN_POOLED = 50  # pooled groups below this go to the global OTHER (same rule as the frozen primary)


def raw_labels(cfg):
    rows = read_cohort(cfg)
    want = {r["CSN"] for r in rows}
    code = {}
    with open(data_path(cfg, "visits.csv"), newline="") as f:
        for v in csv.DictReader(f):
            if v["CSN"] in want:
                code[v["CSN"]] = icd_code(v)
    ccsr, _ = load_ccsr(cfg["data"]["ccsr_file"], cfg["data"]["ccsr_column"])
    return rows, {r["CSN"]: (code[r["CSN"]], ccsr[code[r["CSN"]]]) for r in rows}


def hierarchical(fine, parent, min_n):
    """fine, parent: dict csn -> label. Fine classes < min_n pool into OTHER_<parent>; small pools -> OTHER."""
    n = Counter(fine.values())
    step = {c: (f if n[f] >= min_n else f"OTHER_{parent[c]}") for c, f in fine.items()}
    m = Counter(step.values())
    return {c: (s if (not s.startswith("OTHER_") or m[s] >= MIN_POOLED) else "OTHER") for c, s in step.items()}


def build(cfg):
    rows, lab = raw_labels(cfg)
    body = {c: cat[:3] for c, (code, cat) in lab.items()}
    chap = {c: code[:1] for c, (code, cat) in lab.items()}
    cat = {c: cat for c, (code, cat) in lab.items()}
    icd3 = {c: code[:3] for c, (code, cat) in lab.items()}
    frozen_body = {r["CSN"]: r["dx_body"] for r in rows}
    frozen_chap = {r["CSN"]: r["dx_chapter"] for r in rows}
    return rows, {
        "R1_icd10_chapter": frozen_chap,
        "R2_ccsr_body_system": frozen_body,
        "R3_ccsr_category_min300": hierarchical(cat, body, 300),
        "R4_ccsr_category_min100": hierarchical(cat, body, 100),
        "R5_ccsr_category_min50": hierarchical(cat, body, 50),
        "R6_icd10_3char_min100": hierarchical(icd3, chap, 100),
        "R7_icd10_3char_min50": hierarchical(icd3, chap, 50),
    }


def audit(cfg):
    rows, onts = build(cfg)
    split = read_split(cfg)
    dev = [r["CSN"] for r in rows if split[r["MRN"]] == "dev"]
    n = len(rows)
    out = {"label": "EXPLORATORY ontology audit; counts only; no outcome used", "cohort_visits": n, "ontologies": {}}
    for name, m in onts.items():
        c = Counter(m.values())
        sizes = sorted(c.values())
        dc = Counter(m[x] for x in dev)
        H = -sum(v / n * math.log2(v / n) for v in c.values())
        pooled = sum(v for k, v in c.items() if k.startswith("OTHER"))
        out["ontologies"][name] = {
            "n_classes": len(c), "median_class": sizes[len(sizes) // 2], "min_class": sizes[0] if sizes[0] >= 10 else "<10",
            "max_class": sizes[-1], "share_pooled_other": round(pooled / n, 3), "n_pooled_classes": sum(k.startswith("OTHER") for k in c),
            "entropy_bits": round(H, 3), "normalized_entropy": round(H / math.log2(len(c)), 3),
            "classes_lt_30_dev": sum(1 for k in c if dc[k] < 30), "min_dev_class": min(dc[k] for k in c) if min(dc[k] for k in c) >= 10 else "<10",
            "encoder_parameters_approx": len(c) * 606,
        }
    write_json(OUT, "ontology_audit", out)


if __name__ == "__main__":
    if sys.argv[1:] == ["audit"]:
        audit(config())
