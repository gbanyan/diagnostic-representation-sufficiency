"""Aggregate-only output helpers.

Counts below SMALL_CELL are suppressed in anything written to --out, so
committed results never expose small groups. Patient-level tables go only
to the private directory, which must lie outside the repository.
"""

import json
import math
import os
from pathlib import Path

SMALL_CELL = 10
REPO = Path(__file__).resolve().parents[2]


def private_dir(explicit=None):
    p = Path(explicit or os.environ.get("PREFLIGHT_PRIVATE_DIR", ""))
    if not str(p) or str(p) == ".":
        raise SystemExit("Set --private-dir or PREFLIGHT_PRIVATE_DIR (outside the repository)")
    p = p.resolve()
    if p == REPO or REPO in p.parents:
        raise SystemExit(f"Private directory must be outside the repository ({REPO})")
    p.mkdir(parents=True, exist_ok=True)
    return p


def suppress(n):
    """Return a count, or '<10' when it is a small nonzero cell."""
    return f"<{SMALL_CELL}" if 0 < n < SMALL_CELL else n


def pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def count_share(n, d):
    return {"n": suppress(n), "of": d, "pct": pct(n, d) if not (0 < n < SMALL_CELL) else None}


def _clean(obj):
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else round(obj, 4)
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return _clean(obj.item())
    return obj


def write_json(out_dir, name, payload):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{name}.json"
    target.write_text(json.dumps(_clean(payload), indent=2, sort_keys=False))
    print(f"wrote {target}")
    return target
