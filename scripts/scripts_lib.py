"""Shared helpers for the stage scripts.

Single source of truth: anything used by more than one stage lives here so the holdout run and the
submission build cannot drift apart (parallel-run protocol rule 2: "never keep a private fork").
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

COVARIATE_ORDER = ("relief", "slope", "basin_fill", "lidar_cov", "dist_range_front")


def propensity_design(Xcov: np.ndarray, med: np.ndarray, iqr: np.ndarray) -> np.ndarray:
    """Interpretable low-dimensional propensity design: [1, z(x_e), z(x_e)^2 for the continuous 4].

    The propensity model MUST be lower-dimensional than the classifier (arXiv:1809.03207 sec. 5.1:
    "the propensity score needs to depend on fewer attributes than the final classifier"), otherwise
    e(x) is not identifiable even in principle.  ``lidar_cov`` is binary so it gets no squared term.
    Keeping the design explicit also makes the fitted propensity auditable as a named coefficient
    vector rather than an opaque kernel expansion.
    """
    Z = np.clip((np.asarray(Xcov, dtype=np.float64) - med) / iqr, -5.0, 5.0)
    sq = Z[:, [0, 1, 2, 4]] ** 2          # relief, slope, basin_fill, dist_range_front
    return np.column_stack([np.ones(len(Z)), Z, sq])


def covariate_rows(cov_full: dict, flat: np.ndarray) -> np.ndarray:
    """(n, 5) covariate matrix for absolute flat pixel indices, in COVARIATE_ORDER."""
    return np.column_stack([np.asarray(cov_full[name]).ravel()[flat] for name in COVARIATE_ORDER]).astype(np.float64)
