"""Target sufficiency + dataset semantic preflight (docs/target_sufficiency_framework.md).

Lightweight, CPU-only. No foundation models, no LLMs, no hyperparameter tuning outside the
registered nested CV. Patient-level tables are written only to a private directory outside the
repository (PREFLIGHT_PRIVATE_DIR); committed outputs are aggregates only.
"""

import os

# gbminipc is shared (16 cores). Small L2/lbfgs fits do not benefit from multithreaded BLAS, and
# several parallel runs with default threading oversubscribe the machine (load ~56 observed).
# One BLAS/OpenMP thread per process unless PREFLIGHT_THREADS overrides. Set before numpy loads.
_threads = os.environ.get("PREFLIGHT_THREADS", "1")
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, _threads)
