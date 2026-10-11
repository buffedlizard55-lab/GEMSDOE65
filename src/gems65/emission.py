"""Emission: turning a fault-probability surface into the sparse dot raster the metric pays for.

Why dots
--------
The official metric is

    DTI = TPw / (TPw + 0.2*FPw + 0.8*FNw),   k(d) = max(1 - d/300m, 0),  d in pixels

so with ``T = TPw``, ``S = sum p`` and ``M = sum_x p(x) max_g k`` the algebra
(``src/gems65/metric.py``, verified against a brute-force transcription) is

    DTI = T / ( 0.2*(T + S - M) + 0.8*|G| )

Adding one unit of mass whose realised kernel weight is ``k`` raises the denominator
by exactly ``0.2`` regardless of where it lands, so

    adding a dot raises DTI  <=>  k > 0.2 * DTI                                  (bar)

This is the metric's own first-order condition.  A *wide* rasterisation of a good field
is dominated by the 0.2-per-pixel false-positive tax; a sparse emission of the same
field's top pixels is not.  That is why every high-scoring artifact in this competition
is a sparse {0,1} dot raster and not a probability map.

Dispersed credit map
--------------------
The hidden truth is not the surface itself: a real fault that the catalogue missed sits
*near* the detector's response, not exactly on its argmax.  If truth is scattered around
the surface with scale ``sigma``, the expected kernel credit of a dot at ``x`` is

    c(x) = sum_y rho(y) k(|x-y|) ,   rho = surface (*) Gaussian(sigma)

i.e. the surface blurred by ``sigma`` and then by the metric's own triangular kernel.
Emitting on ``c`` instead of on the raw surface is the difference between covering
where the detector is confident and covering where a *real but unlisted* fault is likely
to be.  ``sigma`` is selected on the blocked holdout and reported with its curve.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def dispersed_credit_map(surface: np.ndarray, sigma: float, radius_px: float = 3.0) -> np.ndarray:
    """Expected kernel credit of a unit dot at every pixel.

    ``surface`` is the fault-probability map in [0, 1].  ``sigma`` is the scatter scale
    (pixels) of the hidden truth around the surface.  ``sigma = 0`` reduces to the
    surface convolved with the metric's triangular kernel.
    """
    s = np.asarray(surface, dtype=np.float64)
    if sigma > 0:
        s = ndimage.gaussian_filter(s, sigma, mode="nearest")
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.hypot(yy, xx)
    k = np.maximum(1.0 - d / radius_px, 0.0)
    if k.sum() <= 0:
        return s.copy()
    return ndimage.convolve(s, k, mode="nearest")


def greedy_emission(
    credit: np.ndarray,
    budget: int,
    allowed: np.ndarray,
    exclusion_radius: float = 2.0,
    pool: int = 400_000,
) -> np.ndarray:
    """Greedy maximum-coverage emission on the credit map.

    Pixels are taken in decreasing credit order; a pixel is accepted only if no
    already-accepted dot lies within ``exclusion_radius`` pixels.  This is the standard
    greedy for a submodular coverage objective with a locality constraint (within
    ``1 - 1/e`` of optimal for the unconstrained problem) and it is what the metric's
    own TPw term rewards.

    Only the top ``pool`` credit pixels are considered, which is exact whenever the
    budget is far below ``pool`` (the greedy never reaches deeper than the budget-th
    accepted dot, and every skipped pixel is dominated by an accepted one).
    """
    allowed = np.asarray(allowed, bool)
    c = np.where(allowed, np.asarray(credit, dtype=np.float64), -np.inf).ravel()
    n = c.size
    k = int(min(max(pool, budget * 4), n))
    if k < n:
        cand = np.argpartition(c, n - k)[n - k:]
    else:
        cand = np.arange(n)
    cand = cand[np.isfinite(c[cand]) & (c[cand] > 0)]
    cand = cand[np.argsort(c[cand])[::-1]]
    chosen = np.zeros(n, bool)
    r = int(np.ceil(exclusion_radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    neigh = [(int(a), int(b)) for a, b in zip(yy.ravel(), xx.ravel()) if not (a == 0 and b == 0)]
    H, W = allowed.shape
    taken = 0
    for flat in cand:
        if taken >= budget:
            break
        y, x = divmod(int(flat), W)
        ok = True
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and chosen[ny * W + nx]:
                ok = False
                break
        if not ok:
            continue
        chosen[flat] = True
        taken += 1
    return chosen.reshape(allowed.shape)


def emission_by_bar(credit: np.ndarray, allowed: np.ndarray, bar: float,
                    exclusion_radius: float = 2.0, max_budget: int = 200_000,
                    pool: int = 400_000) -> tuple[np.ndarray, int]:
    """Emit greedily until the marginal expected credit falls below ``bar``.

    ``bar`` is the metric's own break-even condition ``k > 0.2 * DTI``.  The rule needs
    no magic pixel count: it stops when the next dot is no longer expected to pay for
    its own 0.2 false-positive charge.
    """
    allowed = np.asarray(allowed, bool)
    c = np.where(allowed, np.asarray(credit, dtype=np.float64), -np.inf).ravel()
    n = c.size
    k = int(min(max(pool, max_budget * 4), n))
    if k < n:
        cand = np.argpartition(c, n - k)[n - k:]
    else:
        cand = np.arange(n)
    cand = cand[np.isfinite(c[cand]) & (c[cand] > 0)]
    cand = cand[np.argsort(c[cand])[::-1]]
    chosen = np.zeros(n, bool)
    r = int(np.ceil(exclusion_radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    neigh = [(int(a), int(b)) for a, b in zip(yy.ravel(), xx.ravel()) if not (a == 0 and b == 0)]
    H, W = allowed.shape
    taken = 0
    for flat in cand:
        if taken >= max_budget:
            break
        v = c[flat]
        if not np.isfinite(v) or v < bar:
            break
        y, x = divmod(int(flat), W)
        ok = True
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and chosen[ny * W + nx]:
                ok = False
                break
        if not ok:
            continue
        chosen[flat] = True
        taken += 1
    return chosen.reshape(allowed.shape), taken
