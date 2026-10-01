"""Shared helpers: frozen config, timestamps, private paths, hashing."""

import csv
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import yaml

from src.preflight.reporting import REPO

csv.field_size_limit(sys.maxsize)
CONFIG = REPO / "config" / "mcmed_confirmatory_v1.yaml"
OUT = REPO / "results" / "mcmed"


def config():
    return yaml.safe_load(CONFIG.read_text())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ts(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def private(cfg):
    p = Path(cfg["data"]["private_dir"])
    if p == REPO or REPO in p.resolve().parents:
        raise SystemExit("private_dir must be outside the repository")
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_path(cfg, name):
    return Path(cfg["data"]["root"]) / "data" / name


def season(t):
    return {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
            6: "JJA", 7: "JJA", 8: "JJA"}.get(t.month, "SON")


def read_cohort(cfg):
    with open(private(cfg) / "cohort.csv", newline="") as f:
        return list(csv.DictReader(f))


def read_split(cfg):
    with open(private(cfg) / "split_manifest.csv", newline="") as f:
        return {r["MRN"]: r["set"] for r in csv.DictReader(f)}
