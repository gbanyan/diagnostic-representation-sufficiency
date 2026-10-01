"""MIMIC-CDM Phase 0 semantic audit (docs/phase0_preflight_plan.md).

Standard library only. Every subcommand writes aggregate JSON to --out.
Patient-level output (the manual-audit sample) goes only to --private-dir,
which must be outside the repository and is never committed.

Subcommands:
  inventory  Q2   field coverage and length per pathology
  hindsight  Q5   lexicon flag rates per field and pathology
  sample     Q3   stratified manual-audit sample (private output)
  timing     Q3   lab/radiology offsets from ED arrival (needs MIMIC-IV)
  treatment  Q7   prevalence of patient-conditional rubric items
"""

import argparse
import csv
import gzip
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from audit import lexicon

csv.field_size_limit(sys.maxsize)

PATHOLOGIES = ["appendicitis", "cholecystitis", "diverticulitis", "pancreatitis"]

# Columns required by the upstream loader (DS:ConvertPhysionet.py). Loading
# fails loudly if the release differs, rather than silently mis-reading it.
SCHEMA = {
    "history_of_present_illness.csv": {"hadm_id", "hpi"},
    "physical_examination.csv": {"hadm_id", "pe"},
    "laboratory_tests.csv": {"hadm_id", "itemid", "valuestr"},
    "microbiology.csv": {"hadm_id", "test_itemid", "valuestr"},
    "radiology_reports.csv": {"hadm_id", "note_id", "modality", "region", "text"},
    "discharge_diagnosis.csv": {"hadm_id", "discharge_diagnosis"},
    "discharge_procedures.csv": {"hadm_id", "discharge_procedure"},
    "icd_diagnosis.csv": {"hadm_id", "icd_diagnosis"},
    "icd_procedures.csv": {"hadm_id", "icd_code", "icd_version"},
}


def open_text(path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="", encoding="utf-8")
    return open(path, newline="", encoding="utf-8")


def read_rows(path, required=()):
    with open_text(path) as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path}: missing columns {sorted(missing)}; found {reader.fieldnames}")
        yield from reader


def find_file(base, name):
    for candidate in (Path(base) / name, Path(base) / (name + ".gz")):
        if candidate.exists():
            return candidate
    raise SystemExit(f"{name} not found under {base}")


def load_pathology_ids(cdm_dir):
    with open(find_file(cdm_dir, "pathology_ids.json")) as f:
        raw = json.load(f)
    return {p: [int(i) for i in raw[p]] for p in PATHOLOGIES}


def hadm_to_pathology(ids):
    return {h: p for p, hs in ids.items() for h in hs}


def load_cdm(cdm_dir):
    """Load the release into {hadm_id: case dict}, keeping only fields the audit uses."""
    ids = load_pathology_ids(cdm_dir)
    cases = {h: {"pathology": p, "labs": [], "micro": [], "radiology": [],
                 "icd_diagnosis": [], "procedures_discharge": [],
                 "procedures_icd9": [], "procedures_icd10": []}
             for h, p in hadm_to_pathology(ids).items()}
    columns_seen = {}

    def rows(name):
        path = find_file(cdm_dir, name)
        with open_text(path) as f:
            columns_seen[name] = csv.DictReader(f).fieldnames
        for row in read_rows(path, SCHEMA[name]):
            h = int(row["hadm_id"])
            if h in cases:
                yield cases[h], row

    for case, row in rows("history_of_present_illness.csv"):
        case["hpi"] = row["hpi"]
    for case, row in rows("physical_examination.csv"):
        case["pe"] = row["pe"]
    for case, row in rows("discharge_diagnosis.csv"):
        case["discharge_diagnosis"] = row["discharge_diagnosis"]
    for case, row in rows("laboratory_tests.csv"):
        case["labs"].append({"itemid": row["itemid"], "valuestr": row["valuestr"],
                             "charttime": row.get("charttime")})
    for case, row in rows("microbiology.csv"):
        case["micro"].append({"itemid": row["test_itemid"], "charttime": row.get("charttime")})
    for case, row in rows("radiology_reports.csv"):
        case["radiology"].append({"note_id": row["note_id"], "modality": row["modality"],
                                  "region": row["region"], "text": row["text"]})
    for case, row in rows("icd_diagnosis.csv"):
        case["icd_diagnosis"].append(row["icd_diagnosis"])
    for case, row in rows("discharge_procedures.csv"):
        case["procedures_discharge"].append(row["discharge_procedure"])
    for case, row in rows("icd_procedures.csv"):
        code = row["icd_code"].strip()
        if row["icd_version"].strip() == "9":
            # Upstream stores ICD-9 procedure codes as integers.
            case["procedures_icd9"].append(int(code) if code.isdigit() else code)
        else:
            case["procedures_icd10"].append(code)
    return cases, columns_seen


def by_pathology(cases):
    groups = defaultdict(list)
    for case in cases.values():
        groups[case["pathology"]].append(case)
    return groups


def quantiles(values):
    if not values:
        return None
    values = sorted(values)
    q = statistics.quantiles(values, n=20, method="inclusive") if len(values) > 1 else [values[0]] * 19
    return {"n": len(values), "min": values[0], "p5": q[0], "p25": q[4], "median": q[9],
            "p75": q[14], "p95": q[18], "max": values[-1]}


def share(numerator, denominator):
    return {"n": numerator, "of": denominator,
            "pct": round(100 * numerator / denominator, 1) if denominator else None}


SMALL_CELL = 10


def suppress_small(obj):
    """Applied only when writing output: share dicts with 0 < n < 10 become '<10' without a percentage."""
    if isinstance(obj, dict):
        if set(obj) == {"n", "of", "pct"} and isinstance(obj["n"], int) and 0 < obj["n"] < SMALL_CELL:
            return {"n": f"<{SMALL_CELL}", "of": obj["of"], "pct": None}
        return {k: suppress_small(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [suppress_small(v) for v in obj]
    return obj


# --- inventory (Q2) ---------------------------------------------------------

def cmd_inventory(cases, columns_seen):
    out = {"columns_seen": columns_seen, "by_pathology": {}}
    for p, group in sorted(by_pathology(cases).items()):
        n = len(group)
        out["by_pathology"][p] = {
            "cases": n,
            "hpi_present": share(sum(bool(c.get("hpi")) for c in group), n),
            "pe_present": share(sum(bool(c.get("pe")) for c in group), n),
            "hpi_chars": quantiles([len(c.get("hpi") or "") for c in group]),
            "pe_chars": quantiles([len(c.get("pe") or "") for c in group]),
            "labs_per_case": quantiles([len(c["labs"]) for c in group]),
            "lab_charttime_present": share(
                sum(1 for c in group for l in c["labs"] if l["charttime"]),
                sum(len(c["labs"]) for c in group)),
            "micro_per_case": quantiles([len(c["micro"]) for c in group]),
            "radiology_per_case": quantiles([len(c["radiology"]) for c in group]),
            "radiology_modalities": Counter(r["modality"] for c in group for r in c["radiology"]),
        }
    return out


# --- hindsight (Q5) ---------------------------------------------------------

def cmd_hindsight(cases):
    out = {"lexicon": lexicon.CATEGORIES, "by_pathology": {}}
    for p, group in sorted(by_pathology(cases).items()):
        stats = {}
        for field in ("hpi", "pe", "radiology"):
            texts_per_case = [
                [r["text"] for r in c["radiology"]] if field == "radiology" else [c.get(field) or ""]
                for c in group
            ]
            case_flags = [set().union(*(lexicon.flags(t) for t in texts)) if texts else set()
                          for texts in texts_per_case]
            stats[field] = {cat: share(sum(cat in f for f in case_flags), len(group))
                            for cat in lexicon.ALL_CATEGORIES}
            stats[field]["any"] = share(sum(bool(f) for f in case_flags), len(group))
        out["by_pathology"][p] = stats
    return out


# --- sample (Q3/Q5 manual audit) --------------------------------------------

def cmd_sample(cases, per_pathology, seed):
    rng = random.Random(seed)
    sample = {}
    for p, group in sorted(by_pathology(cases).items()):
        hadm_ids = sorted(h for h, c in cases.items() if c["pathology"] == p)
        sample[p] = sorted(rng.sample(hadm_ids, min(per_pathology, len(hadm_ids))))
    return {"seed": seed, "per_pathology": per_pathology, "hadm_ids": sample}


# --- timing (Q3) ------------------------------------------------------------

def parse_time(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def load_anchors(mimic_dir, hadm_ids):
    """Earliest ED arrival per admission; fall back to edregtime, then admittime."""
    anchors, source = {}, {}
    ed = Path(mimic_dir) / "ed" / "edstays.csv.gz"
    if ed.exists():
        for row in read_rows(ed, {"hadm_id", "intime"}):
            if row["hadm_id"] and int(float(row["hadm_id"])) in hadm_ids:
                h, t = int(float(row["hadm_id"])), parse_time(row["intime"])
                if t and (h not in anchors or t < anchors[h]):
                    anchors[h], source[h] = t, "ed_intime"
    for row in read_rows(find_file(Path(mimic_dir) / "hosp", "admissions.csv"),
                         {"hadm_id", "admittime"}):
        h = int(row["hadm_id"])
        if h in hadm_ids and h not in anchors:
            t = parse_time(row.get("edregtime")) or parse_time(row["admittime"])
            if t:
                anchors[h] = t
                source[h] = "edregtime" if parse_time(row.get("edregtime")) else "admittime"
    return anchors, source


def load_admissions(mimic_dir, hadm_ids):
    info = {}
    for row in read_rows(find_file(Path(mimic_dir) / "hosp", "admissions.csv"),
                         {"hadm_id", "subject_id", "dischtime"}):
        h = int(row["hadm_id"])
        if h in hadm_ids:
            info[h] = {"subject_id": int(row["subject_id"]), "dischtime": parse_time(row["dischtime"])}
    return info


def lab_row_usable(row):
    """Upstream drops lab rows whose value string would be empty or '___'."""
    value = (row.get("value") or "").strip()
    return value != "___" and any((row.get(k) or "").strip() for k in ("valuenum", "value", "flag", "comments"))


def value_matches(cdm_valuestr, row):
    head = (cdm_valuestr or "").split(" ")[0]
    try:
        return abs(float(head) - float(row["valuenum"])) < 1e-6
    except (TypeError, ValueError):
        return head == (row.get("value") or "").strip().split(" ")[0]


def load_lab_times(mimic_dir, cases, anchors, admissions):
    """Recover charttime for each CDM lab item, which the release omits.

    Mirrors upstream selection (DS:dataset/labs.py:15-26, dataset/dataset.py:341-387):
    the earliest usable row per (admission, itemid), where rows without hadm_id
    are attributed to the admission if charted within [anchor - 1 day, dischtime].
    Upstream uses transfer times for that window; this is an approximation.
    Returns {(hadm_id, itemid): (charttime, value_matches_release)}.
    """
    wanted = {(h, l["itemid"]): l["valuestr"] for h, c in cases.items() for l in c["labs"]}
    by_subject = defaultdict(list)
    for h, a in admissions.items():
        by_subject[a["subject_id"]].append(h)
    best = {}
    path = find_file(Path(mimic_dir) / "hosp", "labevents.csv")
    for row in read_rows(path, {"subject_id", "hadm_id", "itemid", "charttime", "value", "valuenum"}):
        if not lab_row_usable(row):
            continue
        itemid = row["itemid"]
        if row["hadm_id"]:
            candidates = [int(float(row["hadm_id"]))]
        else:
            candidates = by_subject.get(int(row["subject_id"]), [])
        for h in candidates:
            key = (h, itemid)
            if key not in wanted:
                continue
            t = parse_time(row["charttime"])
            if not t:
                continue
            if not row["hadm_id"]:
                t0, end = anchors.get(h), admissions[h]["dischtime"]
                if not (t0 and end and t0 - timedelta(days=1) <= t <= end):
                    continue
            if key not in best or t < best[key][0]:
                best[key] = (t, value_matches(wanted[key], row))
    return best


def load_radiology_times(mimic_dir, note_ids):
    times = {}
    path = find_file(Path(mimic_dir) / "note", "radiology.csv")
    for row in read_rows(path, {"note_id", "charttime"}):
        if row["note_id"] in note_ids:
            times[row["note_id"]] = parse_time(row["charttime"])
    return times


def load_procedure_dates(mimic_dir, hadm_ids):
    dates = defaultdict(list)
    path = find_file(Path(mimic_dir) / "hosp", "procedures_icd.csv")
    for row in read_rows(path, {"hadm_id", "chartdate"}):
        h = int(row["hadm_id"])
        if h in hadm_ids:
            d = parse_time(row["chartdate"])
            if d:
                dates[h].append(d.date())
    return dates


def offset_summary(offsets_by_case):
    flat = [o for offs in offsets_by_case for o in offs]
    n_cases = len(offsets_by_case)
    return {
        "items": len(flat),
        "offset_hours": quantiles([round(o, 2) for o in flat]),
        "items_before_anchor_gt_1h": share(sum(o < -1 for o in flat), len(flat)),
        "items_gt_6h": share(sum(o > 6 for o in flat), len(flat)),
        "items_gt_24h": share(sum(o > 24 for o in flat), len(flat)),
        "items_gt_72h": share(sum(o > 72 for o in flat), len(flat)),
        "cases_with_any_item_gt_24h": share(sum(any(o > 24 for o in offs) for offs in offsets_by_case), n_cases),
    }


def cmd_timing(cases, mimic_dir, skip_lab_times=False):
    hadm_ids = set(cases)
    anchors, source = load_anchors(mimic_dir, hadm_ids)
    note_ids = {r["note_id"] for c in cases.values() for r in c["radiology"]}
    rad_times = load_radiology_times(mimic_dir, note_ids)
    proc_dates = load_procedure_dates(mimic_dir, hadm_ids)
    admissions = load_admissions(mimic_dir, hadm_ids)
    release_has_lab_times = any(l["charttime"] for c in cases.values() for l in c["labs"])
    lab_times_mimic = ({} if release_has_lab_times or skip_lab_times
                       else load_lab_times(mimic_dir, cases, anchors, admissions))

    out = {"anchor_source": Counter(source.values()),
           "cases_without_anchor": len(hadm_ids - set(anchors)),
           "radiology_notes_without_time": len(note_ids - {k for k, v in rad_times.items() if v}),
           "lab_time_source": ("release" if release_has_lab_times else
                               "skipped" if skip_lab_times else "mimic-iv labevents (reconstructed)"),
           "lab_items_total": sum(len(c["labs"]) for c in cases.values()),
           "lab_items_timed": len(lab_times_mimic) if not release_has_lab_times else None,
           "lab_items_value_match": (sum(m for _, m in lab_times_mimic.values())
                                     if not release_has_lab_times else None),
           "by_pathology": {}}
    for p, group in sorted(by_pathology(cases).items()):
        lab_offsets, rad_offsets = [], []
        after_first_procedure = Counter()
        for h, c in ((h, c) for h, c in cases.items() if c["pathology"] == p):
            t0 = anchors.get(h)
            if not t0:
                continue
            lab_times = [parse_time(l["charttime"]) if release_has_lab_times
                         else lab_times_mimic.get((h, l["itemid"]), (None, None))[0]
                         for l in c["labs"]]
            r_times = [rad_times.get(r["note_id"]) for r in c["radiology"]]
            lab_offsets.append([(t - t0).total_seconds() / 3600 for t in lab_times if t])
            rad_offsets.append([(t - t0).total_seconds() / 3600 for t in r_times if t])
            # Procedure dates have day resolution: same-day items are ambiguous.
            if proc_dates.get(h):
                first = min(proc_dates[h])
                for kind, times in (("labs", lab_times), ("radiology", r_times)):
                    for t in times:
                        if t:
                            after_first_procedure[f"{kind}_total"] += 1
                            if t.date() > first:
                                after_first_procedure[f"{kind}_after_procedure_day"] += 1
                            elif t.date() == first:
                                after_first_procedure[f"{kind}_on_procedure_day"] += 1
        out["by_pathology"][p] = {
            "labs": offset_summary(lab_offsets),
            "radiology": offset_summary(rad_offsets),
            "relative_to_first_icd_procedure_date": dict(after_first_procedure),
        }
    return out


# --- treatment (Q7) ---------------------------------------------------------

NEGATION = re.compile(r"\b(?:no|not|without|denies|negative for|deferred|declined)\b[^.]{0,40}$", re.IGNORECASE)


def keyword_positive(text, keyword):
    """Approximation of upstream keyword_positive (spaCy + negex): substring
    match without a negation cue in the preceding 40 characters of the sentence."""
    for sentence in (text or "").split("."):
        low = sentence.lower()
        i = low.find(keyword.lower())
        if i >= 0 and not NEGATION.search(low[max(0, i - 60):i]):
            return True
    return False


def codes_done(valid, done):
    return any(v in done for v in valid)


def keywords_done(valid, done):
    return any(keyword_positive(d, v) for v in valid for d in done if isinstance(d, str))


def conditional_items(case, m):
    """Mirror of the upstream score_treatment 'Treatment Required' conditions
    (FW:evaluators/*_evaluator.py). Returns the triggered conditional items."""
    i9, i10, disc = case["procedures_icd9"], case["procedures_icd10"], case["procedures_discharge"]
    p, hits = case["pathology"], []
    if p == "appendicitis" and (codes_done(m.APPENDECTOMY_PROCEDURES_ICD9, i9)
                                or codes_done(m.APPENDECTOMY_PROCEDURES_ICD10, i10)
                                or keywords_done(m.APPENDECTOMY_PROCEDURES_KEYWORDS, disc)):
        hits.append("appendectomy")
    if p == "cholecystitis" and (codes_done(m.CHOLECYSTECTOMY_PROCEDURES_ICD9, i9)
                                 or codes_done(m.CHOLECYSTECTOMY_PROCEDURES_ICD10, i10)
                                 or keywords_done(m.CHOLECYSTECTOMY_PROCEDURES_KEYWORDS, disc)):
        hits.append("cholecystectomy")
    if p == "diverticulitis":
        if (codes_done(m.DRAINAGE_PROCEDURES_ICD9, i9)
                or codes_done(m.DRAINAGE_PROCEDURES_ALL_ICD10, i10)
                or (keywords_done(m.DRAINAGE_PROCEDURES_KEYWORDS, disc)
                    and keywords_done(m.DRAINAGE_LOCATIONS_DIVERTICULITIS, disc))):
            hits.append("drainage")
        if (codes_done(m.COLECTOMY_PROCEDURES_ICD9, i9)
                or codes_done(m.COLECTOMY_PROCEDURES_ICD10, i10)
                or keywords_done(m.COLECTOMY_PROCEDURES_KEYWORDS, disc)):
            hits.append("colectomy")
    if p == "pancreatitis":
        if (codes_done(m.DRAINAGE_PROCEDURES_ICD9, i9)
                or codes_done(m.DRAINAGE_PROCEDURES_ALL_ICD10, i10)
                or codes_done(m.DRAINAGE_PROCEDURES_PANCREATITIS_ICD10, i10)
                or (keywords_done(m.DRAINAGE_PROCEDURES_KEYWORDS, disc)
                    and keywords_done(m.DRAINAGE_LOCATIONS_PANCREATITIS, disc))):
            hits.append("drainage")
        if (codes_done(m.ERCP_PROCEDURES_ICD9, i9)
                or codes_done(m.ERCP_PROCEDURES_ICD10, i10)
                or keywords_done(m.ERCP_PROCEDURES_KEYWORDS, disc)):
            hits.append("ercp")
        dx = case["icd_diagnosis"] + [case.get("discharge_diagnosis") or ""]
        if any(keyword_positive(d, "biliary") for d in dx):
            hits.append("cholecystectomy_biliary")
    return hits


def load_upstream_mappings(framework_dir):
    sys.path.insert(0, str(framework_dir))
    import icd.procedure_mappings as m  # noqa: E402  (upstream, pinned by commit)
    return m


def cmd_treatment(cases, framework_dir):
    m = load_upstream_mappings(framework_dir)
    out = {"by_pathology": {}}
    for p, group in sorted(by_pathology(cases).items()):
        triggered = [conditional_items(c, m) for c in group]
        out["by_pathology"][p] = {
            "cases": len(group),
            "any_conditional_item": share(sum(bool(t) for t in triggered), len(group)),
            "per_item": {k: share(v, len(group)) for k, v in
                         sorted(Counter(i for t in triggered for i in t).items())},
        }
    total = sum(len(g) for g in by_pathology(cases).values())
    out["overall_any_conditional_item"] = share(
        sum(v["any_conditional_item"]["n"] for v in out["by_pathology"].values()), total)
    return out


# --- CLI --------------------------------------------------------------------

def assert_outside_repo(path):
    repo = Path(__file__).resolve().parent.parent
    resolved = Path(path).resolve()
    if resolved == repo or repo in resolved.parents:
        raise SystemExit(f"--private-dir must be outside the repository ({repo})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["inventory", "hindsight", "sample", "timing", "treatment", "all"])
    ap.add_argument("--cdm-dir", required=True, help="MIMIC-IV-Ext-CDM release directory")
    ap.add_argument("--mimic-dir", help="MIMIC-IV root with hosp/, ed/, note/ (timing only)")
    ap.add_argument("--framework-dir", help="Upstream framework checkout (treatment only)")
    ap.add_argument("--out", required=True, help="Directory for aggregate JSON")
    ap.add_argument("--private-dir", help="Directory outside the repo for patient-level output (sample)")
    ap.add_argument("--per-pathology", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260929)
    ap.add_argument("--skip-lab-times", action="store_true",
                    help="timing: do not reconstruct lab times from labevents (radiology only)")
    args = ap.parse_args(argv)

    cases, columns_seen = load_cdm(args.cdm_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    commands = ["inventory", "hindsight", "sample", "timing", "treatment"] if args.command == "all" else [args.command]

    for command in commands:
        if command == "inventory":
            result = cmd_inventory(cases, columns_seen)
        elif command == "hindsight":
            result = cmd_hindsight(cases)
        elif command == "sample":
            if not args.private_dir:
                raise SystemExit("sample requires --private-dir")
            assert_outside_repo(args.private_dir)
            private = Path(args.private_dir)
            private.mkdir(parents=True, exist_ok=True)
            sample = cmd_sample(cases, args.per_pathology, args.seed)
            (private / "audit_sample.json").write_text(json.dumps(sample, indent=2))
            result = {"seed": args.seed, "per_pathology": args.per_pathology,
                      "sizes": {p: len(v) for p, v in sample["hadm_ids"].items()},
                      "written_to": "private dir (not recorded)"}
        elif command == "timing":
            if not args.mimic_dir:
                raise SystemExit("timing requires --mimic-dir")
            result = cmd_timing(cases, args.mimic_dir, args.skip_lab_times)
        else:
            if not args.framework_dir:
                raise SystemExit("treatment requires --framework-dir")
            result = cmd_treatment(cases, args.framework_dir)
        (out / f"{command}.json").write_text(json.dumps(suppress_small(result), indent=2, default=str))
        print(f"wrote {out / (command + '.json')}")


if __name__ == "__main__":
    main()
