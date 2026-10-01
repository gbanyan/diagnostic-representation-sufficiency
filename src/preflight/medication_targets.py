"""Medication targets M1-M6 (Q17; docs/prescription_target_audit.md).

  audit : timing semantics of prescriptions / POE / eMAR for the cohort (aggregates only)
  build : private table mimic_cdm_med_targets.csv with Y_M*_L{L} and flags

Decision time of an order = poe.ordertime (via poe_id) when linked; otherwise
prescriptions.starttime (flagged as proxy). No medication is used as a predictor.
"""

import argparse
import csv
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import timedelta

from audit.cdm_audit import open_text, parse_time
from src.preflight import schemas
from src.preflight.reporting import count_share, pct, private_dir, suppress, write_json
from src.preflight.targets import _f, companion

csv.field_size_limit(sys.maxsize)

# Non-systemic routes, matched against the whole route string (MIMIC-IV route codes; the list is
# checked against the observed route vocabulary in the prescription timing audit).
EXCLUDED_ROUTES = re.compile(
    r"^(TP|TOPICAL|IH|INHALATION|NEB|NU|NAS|NASAL|BOTH EYES|RIGHT EYE|LEFT EYE|OU|OD|OS|OPHTHALMIC|"
    r"BOTH EARS|RIGHT EAR|LEFT EAR|AU|AS|AD|VG|VAGINAL|IRR|IRRIGATION|DWELL|DIALYS|ID|IP|BU|BUCCAL|"
    r"MUCOUS MEMBRANE|MM|LOCK|TRANSPLANT|INTRAPERITONEAL|"
    # added after inspecting the prescriptions route vocabulary (before any target was built):
    # ED = epidural (bupivacaine / epidural opioid bags), IT intrathecal, regional/local and device routes
    r"ED|IT|PERIPHNERVE|PL|INTRAPLEURAL|IMPELLA|FLUSH|IN|IJ|IVT|INTRAVITREAL|IR|NS|LUMBAR PLEXUS|IA|"
    r"INTRA-ARTERIALLY|INTERSPACE|TT|REPLACE)$", re.I)

ANTIBIOTIC = re.compile(
    r"cef|ceph|penem|piperacillin|ampicillin|amoxicillin|nafcillin|penicillin|vancomycin|levofloxacin|"
    r"ciprofloxacin|moxifloxacin|azithromycin|doxycycline|metronidazole|clindamycin|linezolid|daptomycin|"
    r"gentamicin|tobramycin|aztreonam|sulfamethoxazole|trimethoprim|bactrim|nitrofurantoin|tigecycline", re.I)
BROAD = re.compile(r"piperacillin|cefepime|ceftazidime|meropenem|imipenem|ertapenem|vancomycin", re.I)
ANAEROBIC = re.compile(r"metronidazole|piperacillin|penem|ampicillin.*sulbactam|unasyn", re.I)
OPIOID = re.compile(r"morphine|hydromorphone|dilaudid|oxycodone|fentanyl|tramadol|hydrocodone", re.I)
INSULIN = re.compile(r"insulin", re.I)
ENOX = re.compile(r"enoxaparin|lovenox", re.I)
HEPARIN = re.compile(r"^heparin(?! flush| lock| dwell)|heparin sodium(?! flush| lock)", re.I)


IV_ROUTES = re.compile(r"^(IV|IV DRIP|IV BOLUS|IV INFUSION|IVCI|PB)$", re.I)  # PB = IV piggyback
ENTERAL_ROUTES = re.compile(r"^(PO|ORAL|NG|PO/NG|NG/OG|G TUBE|J TUBE|PO/PR)$", re.I)


def systemic(route):
    route = (route or "").strip()
    return bool(route) and not EXCLUDED_ROUTES.match(route)


def classify_drug(drug, route):
    """Return the set of pre-specified categories a prescription row belongs to."""
    cats = set()
    d = drug or ""
    if not systemic(route):
        return cats
    vanco = bool(re.search(r"vancomycin", d, re.I))
    route_s = (route or "").strip()
    # Oral/enteral vancomycin treats C. difficile, not systemic infection: excluded.
    if ANTIBIOTIC.search(d) and not (vanco and ENTERAL_ROUTES.match(route_s)):
        cats.add("antibiotic")
        if BROAD.search(d) and not (vanco and not IV_ROUTES.match(route_s)):
            cats.add("broad")
        if ANAEROBIC.search(d):
            cats.add("anaerobic")
    if OPIOID.search(d):
        cats.add("opioid")
    if INSULIN.search(d):
        cats.add("insulin")
    if re.match(r"SC|SUBCUT|SQ", route or "", re.I):
        if ENOX.search(d):
            cats.add("enoxaparin")
        elif HEPARIN.search(d):
            cats.add("heparin_sc")
    return cats


def load_table(path):
    with open(path, newline="") as f:
        return {r["hadm_id"]: r for r in csv.DictReader(f)}


def read_orders(hosp, ids):
    """Prescription rows for cohort admissions with decision time (POE ordertime if linked)."""
    poe_time = {}
    with open_text(hosp["poe.csv.gz"]) as f:
        for r in csv.DictReader(f):
            if r["hadm_id"] in ids:
                poe_time[r["poe_id"]] = parse_time(r["ordertime"])
    orders = defaultdict(list)
    with open_text(hosp["prescriptions.csv.gz"]) as f:
        for r in csv.DictReader(f):
            h = r["hadm_id"]
            if h not in ids:
                continue
            start = parse_time(r["starttime"])
            ot = poe_time.get(r["poe_id"]) if r.get("poe_id") else None
            orders[h].append({"drug": r["drug"], "route": r["route"], "drug_type": r["drug_type"],
                              "starttime": start, "stoptime": parse_time(r["stoptime"]),
                              "ordertime": ot, "decision": ot or start, "proxy": ot is None,
                              "cats": classify_drug(r["drug"], r["route"])})
    return orders, poe_time


def cmd_audit(table, hosp, out):
    ids = set(table)
    orders, poe_time = read_orders(hosp, ids)
    lag, linked, total, before_anchor, drug_types, routes = [], 0, 0, 0, Counter(), Counter()
    per_adm = []
    for h, os_ in orders.items():
        t0 = parse_time(table[h]["anchor_time"])
        per_adm.append(len(os_))
        for o in os_:
            total += 1
            drug_types[o["drug_type"]] += 1
            routes[o["route"]] += 1
            if o["ordertime"]:
                linked += 1
                if o["starttime"]:
                    lag.append((o["starttime"] - o["ordertime"]).total_seconds() / 60)
            if o["decision"] and t0 and o["decision"] < t0:
                before_anchor += 1
    emar_rows, emar_adm, events = 0, set(), Counter()
    admin_lag, admin_before_order = [], 0
    with open_text(hosp["emar.csv.gz"]) as f:
        for r in csv.DictReader(f):
            h = r["hadm_id"]
            if h not in ids:
                continue
            emar_rows += 1
            emar_adm.add(h)
            events[r["event_txt"]] += 1
            ot, ct = poe_time.get(r.get("poe_id") or ""), parse_time(r["charttime"])
            if ot and ct and (r["event_txt"] or "").lower().startswith("administered"):
                d = (ct - ot).total_seconds() / 60
                admin_lag.append(d)
                admin_before_order += d < 0
    q = statistics.quantiles(lag, n=20) if len(lag) > 20 else None
    write_json(out, "prescription_timing_audit", {
        "cohort_admissions": len(ids),
        "admissions_with_prescriptions": count_share(len(orders), len(ids)),
        "prescription_rows": total,
        "rows_per_admission_median": statistics.median(per_adm) if per_adm else None,
        "rows_linked_to_poe_ordertime": count_share(linked, total),
        "starttime_minus_ordertime_min": ({"p5": q[0], "p25": q[4], "median": q[9], "p75": q[14], "p95": q[18]}
                                          if q else None),
        "rows_with_decision_before_anchor": count_share(before_anchor, total),
        "drug_type": {k: suppress(v) for k, v in drug_types.most_common()},
        "routes_top": {k: suppress(v) for k, v in routes.most_common(30)},
        "emar_rows": emar_rows,
        "admissions_with_emar": count_share(len(emar_adm), len(ids)),
        "emar_event_txt_top": {k: suppress(v) for k, v in events.most_common(25)},
        "administered_minus_ordertime_min": (dict(zip(("p5", "p25", "median", "p75", "p95"),
                                                      [statistics.quantiles(admin_lag, n=20)[i] for i in (0, 4, 9, 14, 18)]))
                                             if len(admin_lag) > 20 else None),
        "administered_before_ordertime": count_share(admin_before_order, len(admin_lag)),
        "category_rows": {c: suppress(sum(c in o["cats"] for os_ in orders.values() for o in os_))
                          for c in ("antibiotic", "broad", "anaerobic", "opioid", "insulin", "enoxaparin", "heparin_sc")},
    })


def cmd_build(table, hosp, landmarks, priv, out, table_path):
    ids = set(table)
    orders, _ = read_orders(hosp, ids)
    rows_out, summary = [], {}
    for h, row in table.items():
        rec = {"hadm_id": h}
        t0 = parse_time(row["anchor_time"])
        os_ = orders.get(h, [])
        for L in landmarks:
            T = t0 + timedelta(hours=L)
            sfx = f"_L{L}"

            def placed(cat, hours):
                return any(cat in o["cats"] and o["decision"] and T < o["decision"] <= T + timedelta(hours=hours)
                           for o in os_)

            def before(cat):
                return any(cat in o["cats"] and o["decision"] and o["decision"] <= T for o in os_)

            rec[f"Y_M1_antibiotic{sfx}"] = int(placed("antibiotic", 24))
            rec[f"Y_M2_broad{sfx}"] = int(placed("broad", 48))
            enox, hep = placed("enoxaparin", 48), placed("heparin_sc", 48)
            rec[f"Y_M3_enoxaparin{sfx}"] = int(enox) if (enox or hep) else ""
            rec[f"Y_M4_opioid{sfx}"] = int(placed("opioid", 24))
            abx = placed("antibiotic", 24)
            rec[f"Y_M5_anaerobic{sfx}"] = int(placed("anaerobic", 24)) if abx else ""
            rec[f"Y_M6_insulin{sfx}"] = int(placed("insulin", 24))
            for cat in ("antibiotic", "broad", "opioid", "insulin"):
                rec[f"{cat}_ordered_before{sfx}"] = int(before(cat))
            rec[f"any_prescription{sfx}"] = int(bool(os_))
        rows_out.append(rec)
    with open(companion(table_path, "mimic_cdm_med_targets"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    for L in landmarks:
        sfx = f"_L{L}"
        coh = [r for r in rows_out if _f(table[r["hadm_id"]].get(f"cohort{sfx}")) == 1]
        summary[f"L{L}"] = {"cohort": len(coh),
                            "with_any_prescription": count_share(sum(r[f"any_prescription{sfx}"] for r in coh), len(coh))}
    write_json(out, "medication_targets_build", summary)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["audit", "build"])
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--private-dir")
    ap.add_argument("--table-name", default="mimic_cdm_landmark_table")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm/medications")
    args = ap.parse_args(argv)
    priv = private_dir(args.private_dir)
    table = load_table(priv / f"{args.table_name}.csv")
    if "anchor_time" not in next(iter(table.values())):
        raise SystemExit("Table lacks anchor_time; rebuild it with the current mimic_cdm_table.")
    names = ["poe.csv.gz", "prescriptions.csv.gz"] + (["emar.csv.gz"] if args.command == "audit" else [])
    hosp = schemas.require("mimiciv_hosp", names)
    if args.command == "audit":
        cmd_audit(table, hosp, args.out)
    else:
        cmd_build(table, hosp, args.landmarks, priv, args.out, priv / f"{args.table_name}.csv")


if __name__ == "__main__":
    main()
