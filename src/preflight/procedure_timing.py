"""Procedure timing audit for T1 (Q14; docs/procedure_timing_audit.md).

  vocab     : aggregate POE order_type / order_subtype / poe_detail field vocabulary for the
              cohort admissions (counts only), used to map pre-/post-operative markers
              BEFORE classification.
  classify  : per case and landmark, GREEN / YELLOW / RED ordering class for "T1 procedure
              after T". Writes a private CSV (t1_timing_classes.csv) and aggregate counts.

Within-day ordering is never inferred from a date alone.
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import timedelta

from audit.cdm_audit import open_text, parse_time
from src.preflight import schemas
from src.preflight.mimic_cdm_table import PACU_RE, T1_PROCEDURES, code_key, procedure_codes
from src.preflight.reporting import private_dir, suppress, write_json
from src.preflight.targets import _f, companion

csv.field_size_limit(sys.maxsize)

# Marker vocabulary. Fixed after the `vocab` inspection (docs/procedure_timing_audit.md, Part 2)
# and before `classify` was run. Matched case-insensitively against
# "order_type | order_subtype | field_name=field_value ...".
MARKERS = {
    # No order specific to an operation exists in the cohort's POE vocabulary (no pre-op / consent /
    # OR-booking order type or detail), so GREEN rule (d) is unavailable.
    "preop_specific": [],
    # Post-operative: post-op admission/transfer orders, PACU placement, and care orders for drains
    # placed during an operation or procedure.
    "postop": [r"^ADT orders \| Postop", r"Admit category=Place in PACU", r"PACU Boarder",
               r"Tubes & Drains type=Closed suction drain", r"Tubes & Drains type=Wound sump",
               r"Tubes & Drains type=Biliary Tube"],
    # Consistent with a later procedure but not specific to an operation.
    "prep_nonspecific": [r"^Nutrition \| NPO/Diet for Procedure", r"^Consults \| Acute Care Surgery",
                         r"^Consults \| ERCP/Advanced Endoscopy", r"^Consults \| Hepatopancreaticobiliary Surgery",
                         r"Admit to=(General )?Surgery", r"Transfer to=Surgery"],
}
MARKERS_MAPPED = True  # set after the `vocab` inspection (procedure_timing_audit.md, Part 2)
SURGICAL_SERVICES = {"SURG", "TSURG", "VSURG", "CSURG", "NSURG", "PSURG", "TRAUM", "GYN", "ORTHO", "ENT"}


def load_table(path):
    with open(path, newline="") as f:
        return {r["hadm_id"]: r for r in csv.DictReader(f)}


def poe_events(hosp, hadm_ids, with_detail=True):
    """{hadm_id: [(ordertime, descriptor_string)]} for the cohort admissions."""
    detail = defaultdict(list)
    if with_detail:
        with open_text(hosp["poe_detail.csv.gz"]) as f:
            for r in csv.DictReader(f):
                detail[r["poe_id"]].append(f"{r['field_name']}={r['field_value']}")
    out = defaultdict(list)
    with open_text(hosp["poe.csv.gz"]) as f:
        for r in csv.DictReader(f):
            h = r["hadm_id"]
            if h not in hadm_ids:
                continue
            desc = " | ".join([r.get("order_type") or "", r.get("order_subtype") or ""] + detail.get(r["poe_id"], []))
            out[h].append((parse_time(r["ordertime"]), desc))
    return out


def cmd_vocab(table, hosp, out):
    ids = set(table)
    counts_type, counts_detail = Counter(), Counter()
    with open_text(hosp["poe.csv.gz"]) as f:
        poe_ids = {}
        for r in csv.DictReader(f):
            if r["hadm_id"] in ids:
                counts_type[f"{r.get('order_type')} | {r.get('order_subtype')}"] += 1
                poe_ids[r["poe_id"]] = 1
    with open_text(hosp["poe_detail.csv.gz"]) as f:
        for r in csv.DictReader(f):
            if r["poe_id"] in poe_ids:
                counts_detail[f"{r['field_name']}={r['field_value']}"[:120]] += 1
    write_json(out, "poe_vocabulary", {
        "order_type_subtype": {k: suppress(v) for k, v in counts_type.most_common(200)},
        "detail_field_values": {k: suppress(v) for k, v in counts_detail.most_common(300)},
    })


def _any(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_case(row, L, fam_dates, pacu_times, poe, services):
    """Return (class, evidence) for 'T1 procedure after T' at landmark L."""
    sfx = f"_L{L}"
    if _f(row.get(f"cohort{sfx}")) != 1 or _f(row.get(f"T1_excluded_before{sfx}")) == 1:
        return "NOT_IN_COHORT", "outside T1 cohort"
    if _f(row.get(f"Y_T1_procedure{sfx}")) != 1:
        return "GREEN", "no_procedure"
    t0 = parse_time(row["anchor_time"])
    T = t0 + timedelta(hours=L)
    dates = [d for d in fam_dates if d]
    ed_out = parse_time(row.get("ed_outtime"))
    post_before = any(t and t < T and _any(MARKERS["postop"], d) for t, d in poe)
    pacu_before = any(t < T for t in pacu_times)
    if post_before or pacu_before:
        return "RED", "postop_evidence_before_T"
    if dates and min(dates) > T.date():
        return "GREEN", "date_after_T"
    if any(t >= T for t in pacu_times):
        return "GREEN", "pacu_after_T"
    if ed_out and ed_out >= T:
        return "GREEN", "in_ED_at_T"
    if any(t and t >= T and _any(MARKERS["preop_specific"], d) for t, d in poe):
        return "GREEN", "preop_order_after_T"
    partial = []
    if any(t and t >= T and _any(MARKERS["postop"], d) for t, d in poe):
        partial.append("postop_orders_only_after_T")
    if any(t and t >= T and s in SURGICAL_SERVICES for t, s in services):
        partial.append("surgical_service_after_T")
    if any(t and t >= T and _any(MARKERS["prep_nonspecific"], d) for t, d in poe):
        partial.append("nonspecific_prep_after_T")
    if partial:
        return "YELLOW", "+".join(partial)
    return "RED", "no_evidence_beyond_date_or_text"


def cmd_classify(table, hosp, framework_dir, landmarks, priv, out, table_path):
    if not MARKERS_MAPPED:
        raise SystemExit("MARKERS are not mapped yet: run `vocab` and fix the vocabulary first.")
    sys.path.insert(0, str(framework_dir))
    import icd.procedure_mappings as m  # noqa: E402
    families = procedure_codes(m)
    ids = set(table)
    fam_dates = defaultdict(list)
    with open_text(hosp["procedures_icd.csv.gz"]) as f:
        for r in csv.DictReader(f):
            h = r["hadm_id"]
            if h not in ids:
                continue
            key = code_key(r["icd_code"], r["icd_version"].strip())
            fams = T1_PROCEDURES[table[h]["D"]]
            if any(key in families[fam][0] or key in families[fam][1] for fam in fams):
                d = parse_time(r["chartdate"])
                fam_dates[h].append(d.date() if d else None)
    pacu = defaultdict(list)
    with open_text(hosp["transfers.csv.gz"]) as f:
        for r in csv.DictReader(f):
            if r["hadm_id"] in ids and PACU_RE.search(r["careunit"] or ""):
                t = parse_time(r["intime"])
                if t:
                    pacu[r["hadm_id"]].append(t)
    services = defaultdict(list)
    with open_text(hosp["services.csv.gz"]) as f:
        for r in csv.DictReader(f):
            if r["hadm_id"] in ids:
                services[r["hadm_id"]].append((parse_time(r["transfertime"]), r["curr_service"]))
    poe = poe_events(hosp, ids)

    results, rows_out = {}, []
    for h, row in table.items():
        rec = {"hadm_id": h}
        for L in landmarks:
            cls, ev = classify_case(row, L, fam_dates[h], pacu[h], poe.get(h, []), services[h])
            rec[f"timing_class_L{L}"], rec[f"timing_evidence_L{L}"] = cls, ev
        rows_out.append(rec)
    with open(companion(table_path, "t1_timing_classes"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    for L in landmarks:
        pos = [r for r in rows_out if r[f"timing_evidence_L{L}"] not in ("no_procedure", "outside T1 cohort")]
        by_d = defaultdict(Counter)
        for r in pos:
            by_d[table[r["hadm_id"]]["D"]][r[f"timing_class_L{L}"]] += 1
        prior = Counter()
        for r in pos:
            row = table[r["hadm_id"]]
            if _f(row.get(f"T1_same_day_ambiguous_L{L}")) == 1:
                prior["same_day_ambiguous"] += 1
            elif _f(row.get(f"T1_text_only_L{L}")) == 1:
                prior["text_only"] += 1
            else:
                prior["dated_or_pacu_resolved"] += 1
        resolved = Counter((("same_day" if _f(table[r["hadm_id"]].get(f"T1_same_day_ambiguous_L{L}")) == 1
                             else "text_only" if _f(table[r["hadm_id"]].get(f"T1_text_only_L{L}")) == 1
                             else "dated"), r[f"timing_class_L{L}"]) for r in pos)
        results[f"L{L}"] = {
            "t1_positive_cases": len(pos),
            "prior_status": {k: suppress(v) for k, v in prior.items()},
            "class_counts": {k: suppress(v) for k, v in Counter(r[f"timing_class_L{L}"] for r in pos).items()},
            "evidence_counts": {k: suppress(v) for k, v in Counter(r[f"timing_evidence_L{L}"] for r in pos).items()},
            "prior_status_x_class": {f"{a}->{b}": suppress(v) for (a, b), v in sorted(resolved.items())},
            "by_diagnosis": {d: {k: suppress(v) for k, v in c.items()} for d, c in sorted(by_d.items())},
            "cohort_after_exclude_red": sum(1 for r in rows_out if r[f"timing_class_L{L}"] in ("GREEN", "YELLOW")),
            "cohort_green_only": sum(1 for r in rows_out if r[f"timing_class_L{L}"] == "GREEN"),
        }
    results["markers"] = MARKERS
    results["surgical_services"] = sorted(SURGICAL_SERVICES)
    write_json(out, "procedure_timing_classes", results)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["vocab", "classify"])
    ap.add_argument("--framework-dir")
    ap.add_argument("--landmarks", type=int, nargs="+", default=[3, 6])
    ap.add_argument("--private-dir")
    ap.add_argument("--table-name", default="mimic_cdm_landmark_table")
    ap.add_argument("--out", default="results/phase0/sufficiency/mimic_cdm/timing")
    args = ap.parse_args(argv)
    priv = private_dir(args.private_dir)
    table = load_table(priv / f"{args.table_name}.csv")
    if "anchor_time" not in next(iter(table.values())):
        raise SystemExit("Table lacks anchor_time/ed_outtime; rebuild it with the current mimic_cdm_table.")
    names = ["poe.csv.gz", "poe_detail.csv.gz"] + (["procedures_icd.csv.gz", "transfers.csv.gz", "services.csv.gz"]
                                                    if args.command == "classify" else [])
    hosp = schemas.require("mimiciv_hosp", names)
    if args.command == "vocab":
        cmd_vocab(table, hosp, args.out)
    else:
        if not args.framework_dir:
            raise SystemExit("classify requires --framework-dir")
        cmd_classify(table, hosp, args.framework_dir, args.landmarks, priv, args.out,
                     priv / f"{args.table_name}.csv")


if __name__ == "__main__":
    main()
