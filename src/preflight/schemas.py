"""Dataset file registry and fail-safe availability checks.

Each dataset lists the files (relative to its root) and the columns a
preflight step needs. `require()` raises MissingData naming every absent
file or column; nothing is substituted silently.
"""

import csv
import gzip
import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("PREFLIGHT_DATA_ROOT", "/mnt/SAM1TB/dev/data"))

DATASETS = {
    "mimic_cdm": {
        "root": "mimic-iv-ext-cdm/1.1",
        "files": {
            "pathology_ids.json": None,
            "history_of_present_illness.csv": {"hadm_id", "hpi"},
            "physical_examination.csv": {"hadm_id", "pe"},
            "laboratory_tests.csv": {"hadm_id", "itemid", "valuestr"},
            "radiology_reports.csv": {"hadm_id", "note_id", "modality", "region", "text"},
            "discharge_diagnosis.csv": {"hadm_id", "discharge_diagnosis"},
            "discharge_procedures.csv": {"hadm_id", "discharge_procedure"},
            "icd_diagnosis.csv": {"hadm_id", "icd_diagnosis"},
            "icd_procedures.csv": {"hadm_id", "icd_code", "icd_version"},
        },
    },
    "mimiciv_hosp": {
        "root": "mimiciv/3.1/hosp",
        "files": {
            "admissions.csv.gz": {"subject_id", "hadm_id", "admittime", "dischtime", "deathtime",
                                  "edregtime", "hospital_expire_flag"},
            "patients.csv.gz": {"subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group"},
            "diagnoses_icd.csv.gz": {"hadm_id", "seq_num", "icd_code", "icd_version"},
            "d_icd_diagnoses.csv.gz": {"icd_code", "icd_version", "long_title"},
            "transfers.csv.gz": {"subject_id", "hadm_id", "eventtype", "careunit", "intime", "outtime"},
            "procedures_icd.csv.gz": {"hadm_id", "chartdate", "icd_code", "icd_version"},
            "d_labitems.csv.gz": {"itemid", "label", "fluid"},
            "labevents.csv.gz": {"subject_id", "hadm_id", "itemid", "charttime", "value", "valuenum"},
            # Q14 procedure timing
            "poe.csv.gz": {"poe_id", "hadm_id", "ordertime", "order_type", "order_subtype"},
            "poe_detail.csv.gz": {"poe_id", "field_name", "field_value"},
            "services.csv.gz": {"hadm_id", "transfertime", "curr_service"},
            # Q17 medications
            "prescriptions.csv.gz": {"hadm_id", "poe_id", "starttime", "stoptime", "drug_type", "drug", "route"},
            "emar.csv.gz": {"hadm_id", "poe_id", "charttime", "medication", "event_txt", "scheduletime", "storetime"},
        },
    },
    "mimiciv_ed": {
        "root": "mimic-iv-ed/2.2/ed",
        "files": {
            "edstays.csv.gz": {"subject_id", "hadm_id", "stay_id", "intime", "outtime", "arrival_transport"},
            "triage.csv.gz": {"stay_id", "temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp",
                              "pain", "acuity"},
        },
    },
    "mimiciv_note": {
        "root": "mimic-iv-note/2.2/note",
        "files": {"radiology.csv.gz": {"note_id", "charttime", "storetime"},
                  "discharge.csv.gz": {"hadm_id", "text"}},
    },
    "eicu": {
        "root": "eicu-crd/2.0",
        "files": {
            "patient.csv.gz": {"patientunitstayid", "uniquepid", "hospitalid", "unitdischargeoffset",
                               "hospitaladmitoffset", "unitdischargestatus"},
            "diagnosis.csv.gz": {"patientunitstayid", "diagnosisoffset", "diagnosisstring",
                                 "activeupondischarge", "diagnosispriority"},
            "treatment.csv.gz": {"patientunitstayid", "treatmentoffset", "treatmentstring",
                                 "activeupondischarge"},
            "medication.csv.gz": {"patientunitstayid", "drugstartoffset", "drugorderoffset", "drugname",
                                  "drugordercancelled"},
            "infusionDrug.csv.gz": {"patientunitstayid", "infusionoffset", "drugname"},
            "admissionDx.csv.gz": {"patientunitstayid", "admitdxenteredoffset", "admitdxpath"},
            "hospital.csv.gz": {"hospitalid"},
        },
    },
}


class MissingData(SystemExit):
    """Raised when required files or columns are absent. Exits non-zero with a clear message."""


def path(dataset, name, root=None):
    base = Path(root) if root else DATA_ROOT / DATASETS[dataset]["root"]
    return base / name


def header(p):
    opener = gzip.open if str(p).endswith(".gz") else open
    with opener(p, "rt", newline="", encoding="utf-8") as f:
        return next(csv.reader(f), [])


def check(dataset, names=None, root=None):
    """Return (present, problems) for the dataset's files (or a subset)."""
    spec = DATASETS[dataset]["files"]
    problems, present = [], []
    for name in names or spec:
        if name not in spec:
            raise KeyError(f"{name} is not registered for {dataset}")
        p = path(dataset, name, root)
        if not p.exists():
            problems.append(f"{dataset}: missing file {p}")
            continue
        if (p.parent / (p.name + ".parts")).exists():
            problems.append(f"{dataset}: {p} is still downloading")
            continue
        cols = spec[name]
        if cols:
            missing = cols - set(header(p))
            if missing:
                problems.append(f"{dataset}: {p} lacks columns {sorted(missing)}")
                continue
        present.append(name)
    return present, problems


def require(dataset, names=None, root=None):
    _, problems = check(dataset, names, root)
    if problems:
        raise MissingData("Required data unavailable; nothing was computed.\n  " + "\n  ".join(problems))
    return {n: path(dataset, n, root) for n in (names or DATASETS[dataset]["files"])}
