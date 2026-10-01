"""MC-MED external confirmatory study (docs/mcmed_confirmatory_preregistration.md).

Frozen choices live in config/mcmed_confirmatory_v1.yaml. Patient-level artifacts go only to the
private directory named there (outside git); committed outputs are aggregates with counts < 10
suppressed. One BLAS thread per process (set by src.preflight before numpy loads).
"""

import src.preflight  # noqa: F401  (thread limits before numpy)
