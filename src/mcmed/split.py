"""Stage C: deterministic patient-level development / locked-test split (hash of MRN + frozen salt).

  python -m src.mcmed.split

One split, generated once. The private manifest (MRN -> set) stays outside git; only its SHA-256
and aggregate counts are committed.
"""

import csv
import hashlib
from collections import Counter

from src.mcmed.common import OUT, config, private, read_cohort, sha256_file
from src.preflight.reporting import count_share, suppress, write_json


def assign(mrn, salt, test_fraction):
    h = hashlib.sha256(f"{salt}:{mrn}".encode()).hexdigest()
    return "test" if int(h[:15], 16) / 16 ** 15 < test_fraction else "dev"


def main():
    cfg = config()
    s = cfg["split"]
    p = private(cfg)
    manifest = p / "split_manifest.csv"
    if manifest.exists():
        raise SystemExit(f"{manifest} exists: the split is generated once and never regenerated")
    rows = read_cohort(cfg)
    mrns = sorted({r["MRN"] for r in rows})
    sets = {m: assign(m, s["salt"], s["test_fraction"]) for m in mrns}
    with open(manifest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["MRN", "set"])
        for m in mrns:
            w.writerow([m, sets[m]])
    out = {"rule": s["rule"], "salt": s["salt"], "test_fraction": s["test_fraction"],
           "manifest_sha256": sha256_file(manifest), "by_set": {}}
    for part in ("dev", "test"):
        rs = [r for r in rows if sets[r["MRN"]] == part]
        out["by_set"][part] = {
            "visits": len(rs), "patients": len({r["MRN"] for r in rs}),
            "icu": count_share(sum(int(r["y_icu"]) for r in rs), len(rs)),
            "dx_body_counts": {k: suppress(v) for k, v in Counter(r["dx_body"] for r in rs).most_common()},
        }
    out["patient_overlap"] = 0 if not ({r["MRN"] for r in rows if sets[r["MRN"]] == "dev"}
                                       & {r["MRN"] for r in rows if sets[r["MRN"]] == "test"}) else "OVERLAP"
    write_json(OUT, "stageC_split", out)


if __name__ == "__main__":
    main()
