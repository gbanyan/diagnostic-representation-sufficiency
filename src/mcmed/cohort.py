"""Stage A: exact 3-hour cohort, attrition, outcome, frozen diagnosis mapping (no modeling).

  python -m src.mcmed.cohort

Writes private cohort.csv and results/mcmed/stageA_cohort.json (aggregates only).
"""

import csv
from collections import Counter
from datetime import timedelta

from src.mcmed.common import OUT, config, data_path, private, season, sha256_file, ts, CONFIG
from src.preflight.reporting import count_share, suppress, write_json


def load_ccsr(path, column):
    m = {}
    with open(path, newline="", encoding="latin-1") as f:
        # Codes are single-quoted (no commas); descriptions with commas are double-quoted.
        r = csv.reader(f, quotechar='"')
        head = [h.strip("'\"") for h in next(r)]
        ic, io = head.index("ICD-10-CM CODE"), head.index(column)
        idesc = head.index(column + " DESCRIPTION") if column + " DESCRIPTION" in head else None
        desc = {}
        for row in r:
            cat = row[io].strip("'\" ")
            m[row[ic].strip("'\" ")] = cat
            if idesc is not None and cat:
                desc[cat] = row[idesc].strip("'\" ")
    return m, desc


def icd_code(r):
    return (r["Dx_ICD10"] or "").replace(".", "").strip().upper()


def body_system(code, ccsr):
    cat = ccsr.get(code, "")
    return cat[:3] if cat else None


def early_orders(cfg, csns, T):
    """Earliest ADT order time per CSN, and CSNs with an ICU/critical-care consult at or before T."""
    c = cfg["cohort"]
    adt_types, subs = set(c["adt_order_types"]), [s.upper() for s in c["early_consult_name_substrings"]]
    first_adt, consult = {}, set()
    with open(data_path(cfg, "orders.csv"), newline="") as f:
        for o in csv.DictReader(f):
            csn = o["CSN"]
            if csn not in csns:
                continue
            t = ts(o["Order_time"])
            if t is None:
                continue
            if o["Order_type"] in adt_types:
                first_adt[csn] = min(t, first_adt.get(csn, t))
            name = (o["Procedure_name"] or "").upper()
            if o["Order_type"] == c["early_consult_order_type"] and any(s in name for s in subs) and t <= T[csn]:
                consult.add(csn)
    return first_adt, consult


def main():
    cfg = config()
    c = cfg["cohort"]
    L = timedelta(hours=c["landmark_hours"])
    ccsr, ccsr_desc = load_ccsr(cfg["data"]["ccsr_file"], cfg["data"]["ccsr_column"])
    chrono = {}
    for part in ("train", "val", "test"):
        with open(data_path(cfg, f"split_chrono_{part}.csv")) as f:
            for line in f:
                chrono[line.strip()] = part

    with open(data_path(cfg, "visits.csv"), newline="") as f:
        visits = list(csv.DictReader(f))
    steps, icu = [], lambda rs: sum(r["ED_dispo"] == c["outcome"]["positive"] for r in rs)

    def step(name, rs, excluded=None):
        e = {"step": name, "visits": len(rs), "patients": len({r["MRN"] for r in rs}), "icu": count_share(icu(rs), len(rs))}
        if excluded is not None:
            e["excluded"] = {"visits": len(excluded), "icu": count_share(icu(excluded), len(excluded))}
        steps.append(e)

    step("all_visits", visits)
    adm = [r for r in visits if r["ED_dispo"] in set(c["admitted_dispositions"])]
    step("admitted (Inpatient/Observation/ICU)", adm)
    for r in adm:
        r["_a"], r["_d"] = ts(r["Arrival_time"]), ts(r["Dispo_time"])
    ok = [r for r in adm if r["_a"] and r["_d"]]
    step("valid Arrival_time and Dispo_time", ok, [r for r in adm if not (r["_a"] and r["_d"])])
    adult = [r for r in ok if float(r["Age"] or 0) >= c["min_age"]]
    step("age >= 18", adult, [r for r in ok if r not in adult] if len(adult) != len(ok) else [])
    T = {r["CSN"]: r["_a"] + L for r in adult}
    first_adt, consult = early_orders(cfg, set(T), T)
    a1 = [r for r in adult if r["_d"] > T[r["CSN"]]]
    step("Dispo_time > T", a1, [r for r in adult if r["_d"] <= T[r["CSN"]]])
    dec = lambda r: min(r["_d"], first_adt.get(r["CSN"], r["_d"]))
    a2 = [r for r in a1 if dec(r) > T[r["CSN"]]]
    step("decision_time = min(Dispo_time, first ADT order) > T", a2, [r for r in a1 if dec(r) <= T[r["CSN"]]])
    a3 = [r for r in a2 if r["CSN"] not in consult]
    step("no ICU / critical-care consult at or before T", a3, [r for r in a2 if r["CSN"] in consult])
    for r in a3:
        r["_code"] = icd_code(r)
        r["_body"] = body_system(r["_code"], ccsr)
    unmapped_detail = Counter("missing Dx_ICD10" if not r["_code"] else "code not in CCSR" if r["_code"] not in ccsr
                              else "blank default category" for r in a3 if r["_body"] is None)
    final = [r for r in a3 if r["_body"] is not None]
    step("primary CCSR mapping available (unmapped excluded)", final, [r for r in a3 if r["_body"] is None])

    # Frozen rare-class rule, counts on the final cohort only (no outcome information).
    m = cfg["taxonomy"]["rare_class_min_visits"]
    other = cfg["taxonomy"]["rare_class_label"]
    raw_body, raw_chap = Counter(r["_body"] for r in final), Counter(r["_code"][:1] for r in final)
    body_map = {k: (k if v >= m else other) for k, v in raw_body.items()}
    chap_map = {k: (k if v >= m else other) for k, v in raw_chap.items()}
    for r in final:
        r["_dx"], r["_chap"] = body_map[r["_body"]], chap_map[r["_code"][:1]]

    p = private(cfg)
    if (p / "split_manifest.csv").exists():
        raise SystemExit("CONFIRMATORY ANALYSIS FROZEN: cohort.csv is fixed once the split exists")
    cols = ["CSN", "MRN", "Arrival_time", "T", "season", "dx_body", "dx_chapter", "y_icu", "chrono", "Race", "Ethnicity"]
    with open(p / "cohort.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in final:
            w.writerow([r["CSN"], r["MRN"], r["_a"].isoformat(), T[r["CSN"]].isoformat(), season(r["_a"]), r["_dx"],
                        r["_chap"], int(r["ED_dispo"] == c["outcome"]["positive"]), chrono.get(r["CSN"], "none"),
                        r["Race"], r["Ethnicity"]])
    body_counts = Counter(r["_dx"] for r in final)
    write_json(OUT, "stageA_cohort", {
        "config_sha256": sha256_file(CONFIG),
        "ccsr": {"file": cfg["data"]["ccsr_file"].split("/")[-1], "version": cfg["data"]["ccsr_version"],
                 "column": cfg["data"]["ccsr_column"], "sha256": sha256_file(cfg["data"]["ccsr_file"]),
                 "rule": "body system = first 3 letters of the default OP CCSR category of Dx_ICD10 (dots removed)"},
        "attrition": steps,
        "unmapped_breakdown": {k: suppress(v) for k, v in unmapped_detail.items()},
        "final": {"visits": len(final), "patients": len({r["MRN"] for r in final}),
                  "icu": count_share(icu(final), len(final))},
        "primary_taxonomy_ccsr_body_system": {
            "rare_rule": f"< {m} visits in the final cohort -> {other}",
            "classes_before_rule": len(raw_body), "merged_into_other": sorted(k for k, v in body_map.items() if v == other),
            "n_classes_final": len(body_counts),
            "class_counts": {k: {"n": suppress(v), "pct": round(100 * v / len(final), 2) if v >= 10 else None}
                             for k, v in sorted(body_counts.items(), key=lambda kv: -kv[1])},
            "note": "counts only; no ICU information by class"},
        "sensitivity_taxonomy_icd10_chapter": {
            "n_classes_final": len(set(chap_map.values())),
            "merged_into_other": sorted(k for k, v in chap_map.items() if v == other),
            "class_counts": {k: suppress(v) for k, v in Counter(r["_chap"] for r in final).most_common()}},
        "chrono_split_membership": dict(Counter(chrono.get(r["CSN"], "none") for r in final)),
        "season": dict(Counter(season(r["_a"]) for r in final)),
    })


if __name__ == "__main__":
    main()
