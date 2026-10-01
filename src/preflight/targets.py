"""Registry of pre-specified targets and feature sets (docs/target_suitability.md).

A target names its column, type, cohort filter, and whether Stage B with
D_final is valid. Examination targets (T6, T7) are stratified by D_final only:
modelling them against D_final would reward reconstructing the final
diagnosis (gate G9), so Stage B refuses them.
"""

import csv
import math

TRIAGE = ["triage_temperature", "triage_heartrate", "triage_resprate", "triage_o2sat",
          "triage_sbp", "triage_dbp", "triage_pain", "triage_acuity"]
X0 = ["age", "female", "prior_admissions", "arrival_ambulance"] + TRIAGE

LAB_NAMES = ["wbc", "neut_pct", "hgb", "plt", "crp", "lactate", "lipase", "tbili", "alt", "ast", "alp",
             "creat", "bun", "glucose", "sodium", "potassium", "bicarb", "albumin", "inr", "calcium"]
IMG_NAMES = ["done_ct", "done_ultrasound", "done_mri", "perforation", "abscess_collection", "free_air",
             "gangrene_necrosis", "free_fluid", "gallstones", "cbd_dilation", "wall_thickening",
             "fat_stranding", "phlegmon", "obstruction"]


def feature_sets(landmark):
    sfx = f"_L{landmark}"
    x1 = X0 + [f"lab_{n}{sfx}" for n in LAB_NAMES]
    x2 = x1 + [f"img_{n}{sfx}" for n in IMG_NAMES]
    return {"X0": X0, "X1": x1, "X2": x2}


DEFAULT_TABLE = "mimic_cdm_landmark_table"


def companion(table_path, name):
    """Path of a private companion file (timing classes, medication targets) for a table.
    The CDM table keeps its original names; other tables get '<table>__<name>.csv'."""
    from pathlib import Path
    table_path = Path(table_path)
    stem = table_path.stem
    return table_path.parent / (f"{name}.csv" if stem == DEFAULT_TABLE else f"{stem}__{name}.csv")


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return math.nan
    return x


def cohort_flags(row, landmark, extra=()):
    sfx = f"_L{landmark}"
    ok = _f(row.get(f"cohort{sfx}")) == 1
    for flag in extra:
        ok = ok and _f(row.get(f"{flag}{sfx}")) == 0
    return ok


TARGETS = {
    "T1": {"column": "Y_T1_procedure_L{L}", "type": "binary", "stage_b": True,
           "exclude": ["T1_excluded_before"],
           "sensitivity_exclude": ["T1_excluded_before", "T1_same_day_ambiguous", "T1_text_only"],
           "label": "Pathology-specific definitive procedure after T"},
    "T2": {"column": "Y_T2_pacu_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "label": "Any OR/PACU transfer after T"},
    "T3": {"column": "Y_T3_icu_L{L}", "type": "binary", "stage_b": True, "exclude": ["icu_before"],
           "label": "ICU admission after T"},
    "T4": {"column": "Y_T4_log_los_days_L{L}", "type": "continuous", "stage_b": True, "exclude": [],
           "label": "Remaining length of stay after T (log1p days)"},
    "T5": {"column": "Y_T5_organ", "type": "categorical", "stage_b": True, "exclude": [],
           "label": "Organ operated (negative-control candidate)"},
    "T6": {"column": "Y_T6_first_modality", "type": "categorical", "stage_b": False, "exclude": [],
           "label": "First abdominal imaging modality (examination; D_final as stratifier only)"},
    "T7": {"column": "Y_T7_n_abd_imaging", "type": "continuous", "stage_b": False, "exclude": [],
           "label": "Number of abdominal imaging studies (examination burden; D_final as stratifier only)"},
    "T8": {"column": "Y_T8_death", "type": "binary", "stage_b": True, "exclude": [],
           "label": "In-hospital death after T"},
    # Medication targets (Q17; docs/prescription_target_audit.md). Values come from the private
    # table mimic_cdm_med_targets.csv, merged on hadm_id.
    "M1": {"column": "Y_M1_antibiotic_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets", "label": "Any systemic antibiotic order placed in (T, T+24h]"},
    "M2": {"column": "Y_M2_broad_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets", "label": "Broad-spectrum antibiotic order placed in (T, T+48h]"},
    "M3": {"column": "Y_M3_enoxaparin_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets",
           "label": "Enoxaparin (vs SC heparin) among VTE prophylaxis orders in (T, T+48h]"},
    "M4": {"column": "Y_M4_opioid_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets", "label": "Any opioid order placed in (T, T+24h]"},
    "M5": {"column": "Y_M5_anaerobic_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets",
           "label": "Anaerobic coverage among antibiotic orders in (T, T+24h]"},
    "M6": {"column": "Y_M6_insulin_L{L}", "type": "binary", "stage_b": True, "exclude": [],
           "extra_table": "mimic_cdm_med_targets", "label": "Any insulin order placed in (T, T+24h]"},
    "T9": {"column": "Y_T9_hours_to_pacu_L{L}", "type": "continuous", "stage_b": True, "exclude": [],
           "label": "Hours from arrival to first PACU, among operated after T (timing)"},
}


def load_rows(table_path, target_id, landmark, sensitivity=False):
    """Return (rows, y) for the target's cohort; rows keep all columns."""
    spec = TARGETS[target_id]
    col = spec["column"].format(L=landmark)
    extra = spec.get("sensitivity_exclude", spec["exclude"]) if sensitivity else spec["exclude"]
    out = []
    extra_rows = {}
    if spec.get("extra_table"):
        from pathlib import Path
        p = companion(table_path, spec["extra_table"])
        if not p.exists():
            raise SystemExit(f"{p} not found; build it first (src.preflight.medication_targets build)")
        with open(p, newline="") as f:
            extra_rows = {r["hadm_id"]: r for r in csv.DictReader(f)}
    with open(table_path, newline="") as f:
        for row in csv.DictReader(f):
            if extra_rows:
                row = {**row, **extra_rows.get(row["hadm_id"], {})}
            if col not in row:
                raise SystemExit(f"Column {col} not in table; rebuild the table with landmark {landmark}")
            if not cohort_flags(row, landmark, extra):
                continue
            y = row[col]
            if spec["type"] in ("binary", "continuous"):
                y = _f(y)
                if math.isnan(y):
                    continue
            elif not y:
                continue
            out.append((row, y))
    return out, col
