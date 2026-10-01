"""Temporal semantics checks.

mimic_cdm: landmark attrition, from the table build (table_build.json).
eicu     : does the problem-list diagnosis time approximate diagnosis
           availability, and can actions be aligned after a frozen landmark?
  - distinct diagnosis save offsets per stay (batch saving);
  - share of treatment rows sharing an offset with a diagnosis row in the stay;
  - first-diagnosis offset relative to unit admission;
  - for landmark T (default 6 h after unit admission): coverage of a primary
    diagnosis entered by T, and Stage A for candidate targets
      E1 = vasopressor infusion start in (T, T+24h], among stays without one by T
      E2 = new systemic antibiotic order in (T, T+24h]
  - hospitals contributing after filtering.

  python -m src.preflight.temporal_checks --dataset eicu [--data-root DIR] [--landmark-min 360]
"""

import argparse
import csv
import gzip
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from src.preflight import schemas
from src.preflight.reporting import count_share, pct, suppress, write_json
from src.preflight.target_heterogeneity import stage_a

VASOPRESSOR = re.compile(r"norepinephrine|levophed|vasopressin|phenylephrine|neosynephrine|\bepinephrine|dopamine",
                         re.IGNORECASE)
ANTIBIOTIC = re.compile(
    r"cef|ceph|penem|piperacillin|tazobactam|zosyn|vancomycin|ampicillin|amoxicillin|nafcillin|oxacillin|"
    r"penicillin|levofloxacin|ciprofloxacin|moxifloxacin|azithromycin|doxycycline|metronidazole|flagyl|"
    r"clindamycin|linezolid|daptomycin|gentamicin|tobramycin|amikacin|aztreonam|sulfamethoxazole|bactrim|"
    r"tigecycline|colistin", re.IGNORECASE)


def rows(p):
    with gzip.open(p, "rt", newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def intish(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def diagnosis_group(s, depth=3):
    return "|".join((s or "").split("|")[:depth])


def eicu_checks(files, landmark_min, top_k=15):
    stay_hosp, stay_pid, stay_disch = {}, {}, {}
    for r in rows(files["patient.csv.gz"]):
        s = r["patientunitstayid"]
        stay_hosp[s], stay_pid[s] = r["hospitalid"], r["uniquepid"]
        stay_disch[s] = intish(r["unitdischargeoffset"])

    diag_offsets = defaultdict(set)
    primary_by_T = {}
    first_diag = {}
    for r in rows(files["diagnosis.csv.gz"]):
        s, o = r["patientunitstayid"], intish(r["diagnosisoffset"])
        if o is None:
            continue
        diag_offsets[s].add(o)
        first_diag[s] = min(o, first_diag.get(s, o))
        if r["diagnosispriority"] == "Primary" and o <= landmark_min:
            prev = primary_by_T.get(s)
            if prev is None or o >= prev[0]:  # latest primary entry at or before T
                primary_by_T[s] = (o, diagnosis_group(r["diagnosisstring"]))

    same_offset = total_tx = 0
    for r in rows(files["treatment.csv.gz"]):
        o = intish(r["treatmentoffset"])
        if o is None:
            continue
        total_tx += 1
        same_offset += o in diag_offsets.get(r["patientunitstayid"], ())

    vaso_first = {}
    vaso_hosp = set()
    for r in rows(files["infusionDrug.csv.gz"]):
        if VASOPRESSOR.search(r["drugname"] or ""):
            s, o = r["patientunitstayid"], intish(r["infusionoffset"])
            if o is not None:
                vaso_first[s] = min(o, vaso_first.get(s, o))
                vaso_hosp.add(stay_hosp.get(s))
    abx = defaultdict(list)
    med_hosp = set()
    for r in rows(files["medication.csv.gz"]):
        s = r["patientunitstayid"]
        med_hosp.add(stay_hosp.get(s))
        if (r.get("drugordercancelled") or "").lower() == "yes":
            continue
        if ANTIBIOTIC.search(r["drugname"] or ""):
            o = intish(r["drugstartoffset"]) if r["drugstartoffset"] else intish(r["drugorderoffset"])
            if o is not None:
                abx[s].append(o)

    saves = [len(v) for v in diag_offsets.values()]
    firsts = [v for v in first_diag.values()]
    T, W = landmark_min, landmark_min + 24 * 60
    alive_at_T = {s for s, d in stay_disch.items() if d is not None and d > T}
    with_primary = alive_at_T & set(primary_by_T)
    top = Counter(primary_by_T[s][1] for s in with_primary).most_common(top_k)
    top_set = {d for d, _ in top}

    def pairs(target):
        out = []
        for s in with_primary:
            d = primary_by_T[s][1]
            d = d if d in top_set else "other"
            row = {"D": d, "subject_id": stay_pid[s]}
            if target == "E1":
                if s in vaso_first and vaso_first[s] <= T:
                    continue
                out.append((row, int(s in vaso_first and T < vaso_first[s] <= W)))
            else:
                if any(o <= T for o in abx.get(s, [])):
                    continue  # "new" antibiotic: none started by T
                out.append((row, int(any(T < o <= W for o in abx.get(s, [])))))
        return out

    hospitals = set(stay_hosp.values())
    return {
        "stays": len(stay_hosp),
        "hospitals": len(hospitals),
        "diagnosis_saves_per_stay": {"median": statistics.median(saves) if saves else None,
                                     "p90": statistics.quantiles(saves, n=10)[-1] if len(saves) > 1 else None},
        "first_diagnosis_offset_min": {"median": statistics.median(firsts) if firsts else None,
                                       "share_after_landmark": pct(sum(f > T for f in firsts), len(firsts))},
        "treatment_rows_sharing_offset_with_diagnosis": count_share(same_offset, total_tx),
        "landmark_min": T,
        "stays_alive_in_unit_at_T": len(alive_at_T),
        "with_primary_diagnosis_entered_by_T": count_share(len(with_primary), len(alive_at_T)),
        "hospitals_with_any_vasopressor_infusion_rows": suppress(len(vaso_hosp - {None})),
        "hospitals_with_any_medication_rows": suppress(len(med_hosp - {None})),
        "top_primary_groups": {d: suppress(n) for d, n in top},
        "stage_a": {"E1_vasopressor_start_next_24h": stage_a(pairs("E1"), "binary"),
                    "E2_new_antibiotic_next_24h": stage_a(pairs("E2"), "binary")},
        "stage_b": "Cannot evaluate: contemporaneous X (lab, vitalPeriodic) not downloaded.",
        "diagnosis_object": "D_t-like: latest primary problem-list entry saved by T (entry-time semantics, "
                            "not formation time)",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["eicu"], required=True)
    ap.add_argument("--data-root", help="eICU directory (default: registry path)")
    ap.add_argument("--landmark-min", type=int, default=360)
    ap.add_argument("--out", default="results/phase0/sufficiency/eicu")
    ap.add_argument("--tag", default="temporal_checks")
    args = ap.parse_args(argv)
    names = ["patient.csv.gz", "diagnosis.csv.gz", "treatment.csv.gz", "medication.csv.gz", "infusionDrug.csv.gz"]
    if args.data_root:
        root = Path(args.data_root)
        files = {}
        for n in names:  # the demo uses lower-case infusiondrug
            cand = [root / n, root / n.lower()]
            hit = next((c for c in cand if c.exists()), None)
            if not hit:
                raise schemas.MissingData(f"missing {n} under {root}")
            files[n] = hit
    else:
        files = schemas.require("eicu", names)
    write_json(args.out, args.tag, eicu_checks(files, args.landmark_min))


if __name__ == "__main__":
    main()
