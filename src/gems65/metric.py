"""Official Distance-Weighted Tversky Index (DTI) for the DOE GEMS Prize Challenge.

REUSE-NOT-REBUILD: ported verbatim in mathematics from the sibling template
``buffedlizard55-lab/GEMSDOE32`` ``src/gems32/metric.py`` (Apache-style in-repo code written by
the same owner), which is itself verified two ways:
  * against a literal brute-force transcription of the published formulas
    (``tests/test_metric.py::test_bruteforce_equivalence_random``, abs tol 1e-9), and
  * against the organizers' own worked example.

Official source of the formulas (read 2026-10-11):
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric
  TP_w = sum_{g in G} max_{x : d(x,g) <= R} p(x) k(d(x,g))
  FP_w = sum_{x : p(x) > 0} p(x) [1 - max_{g in G} k(d(x,g))]
  FN_w = sum_{g in G} [1 - max_{x : d(x,g) <= R} p(x) k(d(x,g))] = |G| - TP_w
  k(d) = (1 - d/R)_+ ,  R = 300 m = 3 px at 100 m
  DTI  = TP_w / (TP_w + alpha FP_w + beta FN_w + eps),  alpha = 0.2, beta = 0.8

Organizer clarification used for the ``known`` mask (DrivenData staff ``chrisk-dd``,
community thread 11516, 16 Sep 2026):
  https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516
  "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation,
   so they do not count towards penalty terms."
=> prediction mass on catalogue pixels earns neither TP nor FP.  It is pure budget waste, so
   this repo's emitter refuses to place any dot there.

Algebraic reductions used for speed (both re-derived and brute-force checked in tests):
  FN_w = |G| - TP_w                                   (exact)
  DTI  = T / (alpha (T + S - M) + beta K)             with S = sum p, M = sum p*k(d(x,G)), K = |G|
  dDTI > 0 when adding a unit of mass with realised kernel weight k  <=>  k > alpha * DTI
      because the denominator rises by exactly alpha: d(alpha(T+F)) = alpha(k + 1 - k) = alpha.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_PX: float = 3.0
EPS: float = 1e-12


def kernel(d, radius: float = RADIUS_PX) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0); d and R in pixels (1 px = 100 m)."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def _offsets(radius: float = RADIUS_PX):
    r = int(np.ceil(radius))
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k > 0.0:
                out.append((dy, dx, k))
    return out


_OFFS = _offsets()


def _prepare(pred, truth, valid, known):
    pred = np.asarray(pred)
    truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("prediction and truth must be equal-shaped 2-D grids")
    valid = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    if valid.shape != pred.shape or known.shape != pred.shape:
        raise ValueError("mask grid mismatch")
    active = valid & ~known
    vals = pred[active]
    if not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any():
        raise ValueError("predictions inside the scored domain must be finite and in [0, 1]")
    p = np.where(active & np.isfinite(pred), pred, 0.0).astype(np.float64)
    g = active & (np.asarray(truth) > 0)
    return p, g, active


def dti_exact(pred, truth, valid=None, known=None, alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Exact DTI for arbitrary soft or binary predictions in [0, 1]."""
    p, g, _ = _prepare(pred, truth, valid, known)
    H, W = p.shape
    yy, xx = np.nonzero(g)
    n = int(yy.size)
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    credit = np.zeros(n, dtype=np.float64)
    for dy, dx, k in _OFFS:
        ny, nx = yy + dy, xx + dx
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * k)
    tp = float(credit.sum())
    fn = float(n) - tp
    d = distance_transform_edt(~g)
    fp = float((p * (1.0 - kernel(d))).sum())
    dti = tp / (tp + alpha * fp + beta * fn + EPS)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, dti=float(dti), coverage=tp / n)


def dti_binary(pred_bool, truth, valid=None, known=None, alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Fast exact DTI when predictions are binary {0, 1}, via Euclidean distance transforms."""
    pred_bool = np.asarray(pred_bool, bool)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(pred_bool.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred_bool.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_ & ~known_
    p = pred_bool & active
    g = truth & active
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    if not p.any():
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n, dti=0.0, coverage=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g]).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p])).sum())
    dti = tp / (tp + alpha * fp + beta * fn + EPS)
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, dti=float(dti), coverage=tp / n)


def dti_bruteforce(pred, truth, alpha: float = ALPHA, beta: float = BETA, radius: float = RADIUS_PX) -> dict:
    """Literal O(|G|*|P|) transcription of the published equations, for verification only."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    tp = fn = 0.0
    for g in gs:
        best = 0.0
        for x in xs:
            d = float(np.hypot(*(x - g)))
            if d <= radius:
                best = max(best, pred[tuple(x)] * max(1.0 - d / radius, 0.0))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += pred[tuple(x)] * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, dti=tp / (tp + alpha * fp + beta * fn + EPS))


def _shift(arr, dy: int, dx: int):
    out = np.zeros_like(arr)
    h, w = arr.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    out[ys0:ys1, xs0:xs1] = arr[max(0, -dy):min(h, h - dy), max(0, -dx):min(w, w - dx)]
    return out


def components(pred, truth, valid=None, known=None) -> dict:
    """Exact TP_w / FP_w / FN_w plus the algebra terms K, S, M and the marginal credit bar."""
    p, g, _ = _prepare(pred, truth, valid, known)
    best = np.zeros(p.shape)
    for dy, dx, kk in _OFFS:
        np.maximum(best, _shift(p, -int(dy), -int(dx)) * kk, out=best)
    best = np.clip(best, 0.0, 1.0)
    tp = float(best[g].sum())
    if g.any():
        k_near = kernel(distance_transform_edt(~g))
    else:
        k_near = np.zeros(p.shape)
    fp = float((p * (1.0 - k_near)).sum())
    fn = float(g.sum()) - tp
    c = {"TP_w": tp, "FP_w": fp, "FN_w": fn, "K": float(g.sum()), "S": float(p.sum()),
         "M": float((p * k_near).sum())}
    c["credit_per_unit_mass"] = (tp / c["S"]) if c["S"] else 0.0
    c["dti"] = dti(tp, fp, fn)
    c["marginal_bar"] = ALPHA * c["dti"]
    return c


def dti(tp: float, fp: float, fn: float, alpha: float = ALPHA, beta: float = BETA) -> float:
    return float(tp / (tp + alpha * fp + beta * fn + EPS))


def dti_pooled(cell_dicts, alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Pooled DTI: sum TP/FP/FN over cells, then take the ratio once (protocol requirement)."""
    tp = sum(float(c["tp"]) for c in cell_dicts)
    fp = sum(float(c["fp"]) for c in cell_dicts)
    fn = sum(float(c["fn"]) for c in cell_dicts)
    n_truth = sum(int(c["n_truth"]) for c in cell_dicts)
    return {"tp": tp, "fp": fp, "fn": fn, "n_truth": n_truth, "dti": dti(tp, fp, fn, alpha, beta),
            "coverage": (tp / n_truth) if n_truth else 0.0, "n_cells": len(cell_dicts)}


def marginal_inclusion_threshold(current_dti: float, alpha: float = ALPHA) -> float:
    """Minimum realised kernel credit k for an added unit of mass to raise DTI: k > alpha*DTI."""
    return alpha * current_dti


def bootstrap_ci(values, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI over per-cell components (cells are the resampling unit)."""
    rng = np.random.default_rng(seed)
    vals = np.asarray(values, dtype=float)
    if vals.size == 0:
        return (0.0, 0.0)
    idx = rng.integers(0, vals.size, size=(n_boot, vals.size))
    boots = vals[idx].mean(axis=1)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
