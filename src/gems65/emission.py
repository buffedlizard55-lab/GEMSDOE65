"""Emitters: how a belief field becomes a legal [0,1] prediction raster.

The decision rule is analytic (see metric.py docstring): adding one unit of prediction mass
raises the DTI denominator by exactly alpha = 0.2 wherever it lands, so a unit pays for itself
iff its realised kernel credit k > 0.2 * DTI.  Two structural consequences drive the design:

* mass that is not the best-covering pixel of some truth pixel is pure cost, so dots must be
  separated by roughly the kernel radius (3 px) -- overlapping dots saturate TP_w (a max) while
  adding FP_w linearly;
* prediction mass on catalogue pixels earns neither TP nor FP (organizer masking rule, community
  thread 11516), so it is excluded outright rather than merely de-prioritised.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt

from . import metric as M


def poisson_disk_dots(field: np.ndarray, eligible: np.ndarray, n_dots: int, min_dist_px: float,
                      candidate_pool_factor: int = 40) -> np.ndarray:
    """Greedy highest-field-first Poisson-disk selection of exactly ``n_dots`` eligible pixels.

    Walks candidates in DESCENDING field order (unlike a raster-order thin, so the layout is
    driven by the belief field) and rejects any candidate within ``min_dist_px`` of an already
    accepted dot.  Deterministic: ties are broken by flat raster index.
    """
    f = np.where(eligible & np.isfinite(field), field, -np.inf).astype(np.float64)
    flat = f.ravel()
    pool = min(int(eligible.sum()), max(n_dots * candidate_pool_factor, n_dots))
    if pool <= 0:
        return np.zeros(f.shape, bool)
    pool = min(pool, flat.size)
    idx = np.argpartition(flat, -pool)[-pool:]
    idx = idx[np.argsort(-flat[idx], kind="stable")]
    H, W = f.shape
    out = np.zeros(flat.size, bool)
    blocked = np.zeros((H, W), bool)
    r = int(np.ceil(min_dist_px))
    ys, xs = np.meshgrid(np.arange(-r, r + 1), np.arange(-r, r + 1), indexing="ij")
    d2 = (ys ** 2 + xs ** 2)
    oy, ox = ys[d2 <= min_dist_px ** 2], xs[d2 <= min_dist_px ** 2]
    taken = 0
    for i in idx:
        y, x = divmod(int(i), W)
        if blocked[y, x]:
            continue
        out[i] = True
        ny, nx = y + oy, x + ox
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        blocked[ny[ok], nx[ok]] = True
        taken += 1
        if taken >= n_dots:
            break
    return out.reshape(f.shape)


def eligible_offcatalogue(foot: np.ndarray, labels: np.ndarray, buffer_px: int = 3,
                          extra_exclude: np.ndarray | None = None) -> np.ndarray:
    """Pixels that can earn credit: inside the footprint and >= buffer_px from any catalogue pixel."""
    if buffer_px <= 0:
        ex = labels & foot
    else:
        ex = binary_dilation(labels & foot, iterations=buffer_px)
    ok = foot & ~ex
    if extra_exclude is not None:
        ok &= ~extra_exclude
    return ok


def grade_dots(mask: np.ndarray, field: np.ndarray) -> np.ndarray:
    """Two-tier graded emission: 1.0 for the top 75% of the ranked dots, 0.6 for the tail.

    Rationale (metric-level, not aesthetic): a dot whose expected credit sits near the marginal
    bar alpha*DTI is roughly score-neutral at full mass, so paying only part of the 0.2 FP tax on
    the least-confident tier is weakly better than either dropping it (loses any credit) or
    emitting it at full mass (pays the whole tax).  Returned array stays inside [0, 1].
    """
    if not mask.any():
        return np.zeros(mask.shape, np.float32)
    vals = field[mask]
    thr = np.quantile(vals, 0.25)
    out = np.where(mask, 1.0, 0.0)
    tail = mask & (field <= thr)
    out[tail] = 0.6
    return out.astype(np.float32)


def emission_budget_from_bar(field: np.ndarray, eligible: np.ndarray, dti_target: float,
                             min_dist_px: float, max_dots: int = 200_000) -> int:
    """Largest Poisson-disk budget whose marginal dot still clears the credit bar alpha*DTI.

    The realised credit of a dot is unknown without truth, so the bar is applied to the field's
    own calibrated posterior: a dot is kept while field >= alpha * dti_target.  This is the
    metric's own first-order condition (see metric.marginal_inclusion_threshold).
    """
    bar = M.marginal_inclusion_threshold(dti_target)
    n = int(((field >= bar) & eligible).sum())
    return int(min(n, max_dots))
