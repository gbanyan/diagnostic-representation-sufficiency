"""MC-MED semantics / eligibility / taxonomy / 3h-feature / leakage audit (no modeling).

Aggregates only (counts < 10 suppressed). ICU prevalence is reported at the cohort level only,
never by diagnosis class, so the taxonomy cannot be chosen against the ICU endpoint.

  python -m src.t3_followup.mcmed_audit cohort|taxonomy|features|leakage --root <mc-med dir>
"""

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from src.preflight.reporting import count_share, suppress, write_json

csv.field_size_limit(sys.maxsize)
ADMITTED = {"Inpatient", "Observation", "ICU"}
LANDMARK = timedelta(hours=3)
CCSR = Path("/mnt/SAM1TB/dev/data/reference/ccsr/DXCCSR_v2024-1.csv")


def ts(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def q(vals):
    if len(vals) < 20:
        return None
    s = statistics.quantiles(vals, n=20)
    return {"p5": s[0], "p25": s[4], "median": s[9], "p75": s[14], "p95": s[18], "n": len(vals)}


def visits(root):
    with open(root / "data" / "visits.csv", newline="") as f:
        return list(csv.DictReader(f))


def cohort_rows(root):
    """Admitted adult visits with valid arrival and disposition times, flagged for 3h eligibility."""
    out = []
    for r in visits(root):
        if r["ED_dispo"] not in ADMITTED:
            continue
        a, d = ts(r["Arrival_time"]), ts(r["Dispo_time"])
        r["_a"], r["_d"], r["_adm"] = a, d, ts(r["Admit_time"])
        r["_eligible"] = bool(a and d and d > a + LANDMARK)
        out.append(r)
    return out


def cmd_cohort(root, out):
    rows = cohort_rows(root)
    elig = [r for r in rows if r["_eligible"]]
    excl = [r for r in rows if r["_a"] and r["_d"] and not r["_eligible"]]
    icu = lambda rs: count_share(sum(r["ED_dispo"] == "ICU" for r in rs), len(rs))
    adm_rel = Counter()
    for r in elig:
        if r["_adm"] is None:
            adm_rel["admit_time_missing"] += 1
        elif r["_adm"] <= r["_a"] + LANDMARK:
            adm_rel["admit_time_at_or_before_T"] += 1
        elif r["_adm"] < r["_d"]:
            adm_rel["admit_time_after_T_before_dispo"] += 1
        else:
            adm_rel["admit_time_at_or_after_dispo"] += 1
    write_json(out, "cohort", {
        "admitted_visits": len(rows), "admitted_missing_times": suppress(sum(1 for r in rows if not (r["_a"] and r["_d"]))),
        "eligible_visits_dispo_after_3h": len(elig), "eligible_patients": len({r["MRN"] for r in elig}),
        "excluded_dispo_at_or_before_3h": len(excl),
        "icu_prevalence": {"eligible": icu(elig), "excluded_dispo_before_3h": icu(excl), "all_admitted": icu(rows)},
        "eligible_hours_arrival_to_dispo": q([(r["_d"] - r["_a"]).total_seconds() / 3600 for r in elig]),
        "eligible_admit_time_relative": {k: suppress(v) for k, v in adm_rel.items()},
        "eligible_by_chrono_split_note": "see counts.json from mcmed_counts",
    })


def load_ccsr():
    m = {}
    with open(CCSR, newline="", encoding="latin-1") as f:
        # Codes are single-quoted (no commas); descriptions with commas are double-quoted.
        r = csv.reader(f, quotechar='"')
        head = [h.strip("'\"") for h in next(r)]
        ic, io = head.index("ICD-10-CM CODE"), head.index("Default CCSR CATEGORY OP")
        for row in r:
            m[row[ic].strip("'\" ")] = row[io].strip("'\" ")
    return m


def taxonomies(rows, ccsr):
    """Candidate fixed ontologies (rules fixed by semantics and sample adequacy, not by outcome)."""
    code = lambda r: (r["Dx_ICD10"] or "").replace(".", "").strip().upper()
    chap = lambda r: code(r)[:1] or "MISSING"
    c3 = Counter(code(r)[:3] for r in rows)
    cc = Counter(ccsr.get(code(r), "UNMAPPED") for r in rows)
    return {
        "A_icd10_chapter": lambda r: chap(r),
        "B_ccsr_body_system": lambda r: (ccsr.get(code(r), "UNMAPPED") or "UNMAPPED")[:3],
        "C_ccsr_category_min300": lambda r: (lambda k: k if cc[k] >= 300 else "OTHER_" + k[:3])(ccsr.get(code(r), "UNMAPPED")),
        "D_icd10_3char_min200": lambda r: (lambda k: k if c3[k] >= 200 else "OTHER_" + k[:1])(code(r)[:3]),
    }


def cmd_taxonomy(root, out):
    rows = [r for r in cohort_rows(root) if r["_eligible"]]
    ccsr = load_ccsr()
    res = {"cohort_n": len(rows), "note": "counts only; no ICU information by class", "candidates": {}}
    unm = sum(1 for r in rows if ccsr.get((r["Dx_ICD10"] or "").replace(".", "").strip().upper()) is None)
    res["ccsr_unmapped_codes"] = count_share(unm, len(rows))
    for name, fn in taxonomies(rows, ccsr).items():
        c = Counter(fn(r) for r in rows)
        sizes = sorted(c.values())
        other = sum(v for k, v in c.items() if k.startswith("OTHER") or k in ("MISSING", "UNMAPPED"))
        symptom = sum(v for k, v in c.items() if k in ("R", "SYM") or k.startswith("SYM") or k.startswith("OTHER_R"))
        res["candidates"][name] = {
            "n_classes": len(c), "min_class": suppress(sizes[0]), "median_class": statistics.median(sizes), "max_class": sizes[-1],
            "classes_lt_50": sum(1 for v in sizes if v < 50), "classes_lt_100": sum(1 for v in sizes if v < 100),
            "share_other_or_unmapped": count_share(other, len(rows)),
            "share_symptom_classes": count_share(symptom, len(rows)),
            "top15": {k: suppress(v) for k, v in c.most_common(15)},
        }
    write_json(out, "taxonomy", res)


def read_csv_by_csn(path, csns, cols):
    out = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r["CSN"] in csns:
                out[r["CSN"]].append({c: r.get(c) for c in cols})
    return out


def cmd_features(root, out):
    rows = [r for r in cohort_rows(root) if r["_eligible"]]
    by = {r["CSN"]: r for r in rows}
    n = len(rows)
    res = {"cohort_n": n}
    labs = read_csv_by_csn(root / "data" / "labs.csv", set(by), ["Order_time", "Result_time", "Component_name"])
    resulted, ordered_only, comp = 0, 0, Counter()
    lag = []
    for csn, ls in labs.items():
        T = by[csn]["_a"] + LANDMARK
        got = [l for l in ls if ts(l["Result_time"]) and ts(l["Result_time"]) <= T]
        if got:
            resulted += 1
            for l in {l["Component_name"] for l in got}:
                comp[l] += 1
        elif any(ts(l["Order_time"]) and ts(l["Order_time"]) <= T for l in ls):
            ordered_only += 1
        for l in ls:
            o, rt = ts(l["Order_time"]), ts(l["Result_time"])
            if o and rt:
                lag.append((rt - o).total_seconds() / 60)
    res["labs"] = {"visits_with_any_result_by_T": count_share(resulted, n),
                   "visits_with_order_by_T_but_no_result_by_T": count_share(ordered_only, n),
                   "order_to_result_minutes": q(lag),
                   "top_components_resulted_by_T": {k: suppress(v) for k, v in comp.most_common(40)}}
    rads = read_csv_by_csn(root / "data" / "rads.csv", set(by), ["Order_time", "Result_time", "Study"])
    rres = sum(1 for csn, ls in rads.items() if any(ts(l["Result_time"]) and ts(l["Result_time"]) <= by[csn]["_a"] + LANDMARK for l in ls))
    res["rads"] = {"visits_with_imaging_result_by_T": count_share(rres, n)}
    orders = read_csv_by_csn(root / "data" / "orders.csv", set(by), ["Order_time", "Order_type", "Procedure_name", "First_admin_time"])
    types_before, types_all = Counter(), Counter()
    for csn, ls in orders.items():
        T = by[csn]["_a"] + LANDMARK
        for l in ls:
            types_all[l["Order_type"]] += 1
            if ts(l["Order_time"]) and ts(l["Order_time"]) <= T:
                types_before[l["Order_type"]] += 1
    res["orders"] = {"order_types_all": {k: suppress(v) for k, v in types_all.most_common()},
                     "order_types_placed_by_T": {k: suppress(v) for k, v in types_before.most_common()}}
    pmh_before = pmh_same = pmh_after = 0
    mrn_first = {}
    for r in rows:
        mrn_first.setdefault(r["MRN"], []).append(r["_a"].date())
    with open(root / "data" / "pmh.csv", newline="") as f:
        per_visit = Counter()
        for p in csv.DictReader(f):
            d = ts(p["Noted_date"])
            if not d or p["MRN"] not in mrn_first:
                continue
            for ad in mrn_first[p["MRN"]]:
                if d.date() < ad:
                    pmh_before += 1
                elif d.date() == ad:
                    pmh_same += 1
                else:
                    pmh_after += 1
    res["pmh_rows_relative_to_visit_date"] = {"noted_before_visit_date": pmh_before, "noted_same_day": pmh_same,
                                              "noted_after_visit_date": pmh_after}
    write_json(out, "features", res)


def cmd_leakage(root, out):
    rows = [r for r in cohort_rows(root) if r["_eligible"]]
    by = {r["CSN"]: r for r in rows}
    orders = read_csv_by_csn(root / "data" / "orders.csv", set(by), ["Order_time", "Order_type", "Procedure_name"])
    kw = ("icu", "intensive", "critical care", "admit", "admission", "bed request", "transfer", "consult")
    hits, visits_hit = Counter(), Counter()
    for csn, ls in orders.items():
        T = by[csn]["_a"] + LANDMARK
        seen = set()
        for l in ls:
            name = (l["Procedure_name"] or "").lower() + " | " + (l["Order_type"] or "").lower()
            if ts(l["Order_time"]) and ts(l["Order_time"]) <= T:
                for k in kw:
                    if k in name:
                        hits[f"{k} :: {(l['Order_type'] or '')}"] += 1
                        seen.add(k)
        for k in seen:
            visits_hit[k] += 1
    write_json(out, "leakage", {
        "cohort_n": len(rows),
        "escalation_related_orders_placed_by_T_rows": {k: suppress(v) for k, v in hits.most_common(40)},
        "visits_with_such_orders_by_T": {k: count_share(v, len(rows)) for k, v in visits_hit.items()},
        "note": "keyword screen only; order vocabulary reviewed before any exclusion rule is fixed"})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["cohort", "taxonomy", "features", "leakage"])
    ap.add_argument("--root", default="/mnt/SAM1TB/dev/data/mc-med/1.0.1")
    ap.add_argument("--out", default="results/t3_followup/mcmed_audit")
    a = ap.parse_args(argv)
    {"cohort": cmd_cohort, "taxonomy": cmd_taxonomy, "features": cmd_features, "leakage": cmd_leakage}[a.command](Path(a.root), a.out)


if __name__ == "__main__":
    main()
