"""Diagnostic (second) instrument: covariate-biased segment withholding.

Why this instrument exists
--------------------------
The shared ``gems57.holdout.build_holdout`` instrument withholds whole segments
chosen **uniformly at random** inside each quadrant domain.  That is SCAR
withholding: the withheld positives are exchangeable with the visible ones, so a
selection-bias correction has no bias left to remove and can only add variance.
Experiment 1 therefore measured a tie (registry/holdout_arms.json) and that tie
is a property of the instrument, not evidence that selection bias is absent from
the real catalogue.

The live task is not SCAR: the organizer's hidden faults are, by construction,
the ones the published compilations missed, and the brief's premise (Giddens &
Faulds 2025; mapping effort concentrated where terrain is easy to see) is that
misses cluster in specific terrain.  This module builds the matching instrument:
whole-segment withholding in which each eligible segment's selection probability
increases as its mean inclusion propensity ``e(x)`` decreases:

    P(select segment s)  proportional to  (1 - mean_s e)^kappa

Everything else is held fixed: same quadrant domains, same 12 px domain erosion,
same 3 px visible-context buffer semantics, same ``hide_frac`` pixel mass, same
per-cell bookkeeping objects (``gems57.holdout.Cell``), and the *same shared*
scorer (``gems57.evaluate_holdout`` / ``gems57.metric``).  Only the *draw* of
which segments are withheld changes.  This is a pre-registered diagnostic
variant, not a replacement for the shared instrument, and no shared tool is
modified: nothing here is imported by the shared template.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from gems57 import grid as G
from gems57.holdout import (DOMAIN_ERODE, FOLD_NAMES, MAX_SEG_PX, Cell,
                            HoldoutContext, quadrant_ids)
from gems57.metric import kernel
from gems57.network import segments


def _weighted_pick(rng, seg_ids, sizes, weights, target_px):
    """Draw whole segments without replacement, probability proportional to weight."""
    order = np.argsort(-weights)  # deterministic tie-break; positions reused below
    remaining = seg_ids[order]
    w = weights[order].astype(np.float64)
    chosen, total = [], 0.0
    while remaining.size and total < target_px:
        p = w / w.sum()
        i = int(rng.choice(remaining.size, p=p))
        chosen.append(int(remaining[i]))
        total += float(sizes[remaining[i]])
        remaining = np.delete(remaining, i)
        w = np.delete(w, i)
    return np.array(chosen, np.int64)


def build_biased_holdout(grid: G.Grid, propensity: np.ndarray, *, seeds=(20, 21),
                         hide_frac: float = 0.20, kappa: float = 2.0,
                         boundary_px: int = DOMAIN_ERODE) -> HoldoutContext:
    """Holdout cells whose withheld segments are enriched in low-propensity areas.

    ``propensity`` is the full-grid estimated ``e(x)`` in (0, 1].
    """
    cat = np.asarray(grid.catalogue, bool)
    fp = np.asarray(grid.footprint, bool)
    seg, n_seg = segments(cat, max_len_px=MAX_SEG_PX)[:2]
    sizes = np.bincount(seg.ravel(), minlength=n_seg + 1)
    all_ids = np.arange(1, n_seg + 1)
    quad = quadrant_ids(fp)
    hidden_by_cell, cells = {}, []
    e = np.clip(np.asarray(propensity, np.float64), 1e-3, 1.0)
    mean_e = np.bincount(seg.ravel(), weights=e.ravel(), minlength=n_seg + 1) / np.maximum(sizes, 1)

    for seed in seeds:
        for fold, qname in enumerate(FOLD_NAMES):
            q = quad == fold
            rows = np.flatnonzero(q.any(axis=1))
            cols = np.flatnonzero(q.any(axis=0))
            sl = (slice(max(0, rows[0] - 6), min(grid.height, rows[-1] + 7)),
                  slice(max(0, cols[0] - 6), min(grid.width, cols[-1] + 7)))
            domain = ndi.binary_erosion(q, iterations=boundary_px) & fp
            clipped = np.isin(all_ids, np.unique(seg[~domain & cat]))
            eligible = all_ids[~clipped]
            if eligible.size == 0:
                continue
            # bias weight: low mean inclusion propensity -> higher chance withheld
            w = (1.0 - mean_e[eligible]) ** kappa
            if not np.isfinite(w).all() or w.sum() <= 0:
                raise ValueError("degenerate bias weights")
            rng = np.random.default_rng(10_000 * (seed + 1) + 7 * fold + 2)
            target = hide_frac * float((cat & q & domain).sum())
            hidden_ids = _weighted_pick(rng, eligible, sizes, w, target)
            hidden = np.isin(seg, hidden_ids) & fp
            visible = cat & ~hidden

            key = f"bdraw{seed}_fold{qname}_all"
            hidden_by_cell[key] = hidden
            active = domain & ~visible
            truth = hidden & domain & active
            tyx_full = np.nonzero(truth)
            k_full = kernel(ndi.distance_transform_edt(~truth))
            a_sub = active[sl].copy()
            k_sub = k_full[sl].astype(np.float32)
            t_sub = truth[sl]
            tyx = np.nonzero(t_sub)
            cells.append(Cell(key=key, fold=fold, seed=seed, mode="all", bbox=sl,
                              active=a_sub, truth_yx=tyx, k_dg=k_sub, n_truth=int(tyx[0].size)))
            del hidden, visible, active, truth, a_sub, k_sub, t_sub
    return HoldoutContext(grid=grid, quad=quad, cells=cells, hidden_by_cell=hidden_by_cell)


def withheld_mean_propensity(ctx: HoldoutContext, propensity: np.ndarray) -> dict:
    """Diagnostic: mean e of withheld vs visible catalogue pixels, per cell."""
    e = np.asarray(propensity, np.float64)
    out = {}
    for key, hidden in ctx.hidden_by_cell.items():
        vis = ctx.grid.catalogue & ~hidden
        out[key] = dict(hidden_mean_e=float(e[hidden].mean()) if hidden.any() else None,
                        visible_mean_e=float(e[vis].mean()) if vis.any() else None)
    return out
