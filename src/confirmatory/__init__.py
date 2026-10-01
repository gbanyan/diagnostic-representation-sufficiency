"""Confirmatory target-sufficiency analysis (docs/main_experiment_preregistration.md, binding 600f368).

Reuses the preflight data pipeline. One BLAS thread per process (see src.preflight).
"""

import src.preflight  # noqa: F401  (sets thread limits before numpy loads)
