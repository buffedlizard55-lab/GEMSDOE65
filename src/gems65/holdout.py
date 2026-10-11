"""Spatially-blocked hide-and-recover holdout, pooled DTI, propensity terciles, leakage canary.

REUSE-NOT-REBUILD: the fold geometry (4 quadrant folds x 2 draws, 15 px collar, 12 px domain
erosion, 20% of whole catalogue components withheld) is the sibling template
``buffedlizard55-lab/GEMSDOE32`` ``src/gems32/holdout.py`` design, kept bit-compatible so the two
lanes' numbers are comparable.  Two changes were made HERE and are reported to the template owner:

1. The protocol for this lane says "score pooled DTI", so ``pooled()`` sums TP/FP/FN over cells
   and takes the ratio once, instead of averaging per-cell DTIs (averaging over-weights the
   small folds).  Both are returned.
2. Tercile reporting by propensity is added, because this lane's gate is "higher blocked-holdout
   DTI overall AND no loss in the highest-propensity tercile".

Hide-and-recover semantics:
* whole catalogue connected components are withheld (never single pixels), so a hidden fault is
  hidden as a segment, not as a Swiss cheese;
* an extra 20% of components in the TRAINING region is also hidden, so the model cannot learn a
  trace that runs into the test quadrant through the collar;
* visible catalogue pixels are removed from the scored domain PIXEL-EXACTLY (``active = domain &
  ~visible``), matching the organizer's known-fault masking rule (community thread 11516);
* nothing in this lane's feature set is catalogue-derived (see covariates.py), so "derive every
  catalogue-based feature only from the visible faults" holds by construction and is asserted in
  ``tests/test_holdout.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt, label

from . import metric as M

FOLD_NAMES = ("NW", "NE", "SW", "SE")
FOLDS = (0, 1, 2, 3)
DRAWS = (20, 21)
COLLAR_PX = 15
DOMAIN_ERODE = 12
HIDE_FRAC = 0.20
KERNEL_PX = M.RADIUS_PX


def quadrant_ids(footprint: np.ndarray) -> np.ndarray:
    foot = np.asarray(footprint, bool)
    yy, xx = np.nonzero(foot)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    H, W = foot.shape
    gy, gx = np.ogrid[:H, :W]
    q = np.full((H, W), -1, np.int8)
    q[(gy < ym) & (gx < xm) & foot] = 0
    q[(gy < ym) & (gx >= xm) & foot] = 1
    q[(gy >= ym) & (gx < xm) & foot] = 2
    q[(gy >= ym) & (gx >= xm) & foot] = 3
    return q


def _pick_components(rng, comp_size, ids, target_px):
    if ids.size == 0:
        return ids
    perm = rng.permutation(ids)
    cum = np.cumsum(comp_size[perm])
    k = int(np.searchsorted(cum, target_px)) + 1
    return perm[: min(k, perm.size)]


@dataclass
class Cell:
    key: str
    fold: int
    seed: int
    bbox: tuple[slice, slice]
    active: np.ndarray           # domain & ~visible, inside bbox
    truth: np.ndarray            # hidden catalogue inside active
    active_full: np.ndarray      # FULL-grid domain & ~visible
    truth_full: np.ndarray       # FULL-grid hidden catalogue inside active_full
    visible_full: np.ndarray     # FULL-grid catalogue pixels the model is allowed to see
    truth_coords: tuple[np.ndarray, np.ndarray]
    k_dtruth: np.ndarray         # kernel(distance to truth) inside bbox
    n_truth: int
    train_region: np.ndarray     # FULL-grid bool: pixels usable for training in this cell


@dataclass
class HoldoutContext:
    foot: np.ndarray
    labels: np.ndarray
    quad: np.ndarray
    cells: list[Cell]


def build_holdout(foot: np.ndarray, labels: np.ndarray, hide_frac: float = HIDE_FRAC,
                  draws=DRAWS) -> HoldoutContext:
    labels = labels & foot
    quad = quadrant_ids(foot)
    comp, n_comp = label(labels, structure=np.ones((3, 3), int))
    comp_size = np.bincount(comp.ravel(), minlength=n_comp + 1)
    all_ids = np.arange(1, n_comp + 1)

    collars, domains = {}, {}
    bboxes = {}
    for fold in FOLDS:
        q = quad == fold
        rows = np.flatnonzero(q.any(axis=1))
        cols = np.flatnonzero(q.any(axis=0))
        bboxes[fold] = (slice(max(0, int(rows[0]) - 6), min(foot.shape[0], int(rows[-1]) + 7)),
                        slice(max(0, int(cols[0]) - 6), min(foot.shape[1], int(cols[-1]) + 7)))
        collars[fold] = binary_dilation(q, structure=np.ones((3, 3), bool), iterations=COLLAR_PX) & foot
        domains[fold] = binary_erosion(q, iterations=DOMAIN_ERODE)

    cells: list[Cell] = []
    for seed in draws:
        for fold in FOLDS:
            rng = np.random.default_rng(10_000 * (seed + 1) + fold)
            q = quad == fold
            collar = collars[fold]
            domain = domains[fold]
            touch_collar = np.isin(all_ids, np.unique(comp[collar & labels]))
            in_test = np.isin(all_ids, np.unique(comp[q & labels]))
            test_ids = all_ids[in_test]
            train_ids = all_ids[~touch_collar]
            hid_test = _pick_components(rng, comp_size, test_ids, hide_frac * float((labels & q).sum()))
            hid_train = _pick_components(rng, comp_size, train_ids, hide_frac * float(comp_size[train_ids].sum()))
            hidden_full = np.isin(comp, hid_test)
            hidden_train = np.isin(comp, hid_train)
            visible = labels & ~hidden_full & ~hidden_train
            # training region: everything in the footprint except the test quadrant and its collar,
            # and except the hidden train-side components (which the model must never see)
            train_region = foot & ~q & ~collar & ~hidden_full
            sl = bboxes[fold]
            active = domain[sl] & ~visible[sl]
            truth = hidden_full[sl] & active
            tc = np.nonzero(truth)
            active_full = domain & ~visible
            truth_full = hidden_full & active_full
            cells.append(Cell(
                key=f"draw{seed}_{FOLD_NAMES[fold]}", fold=fold, seed=seed, bbox=sl,
                active=active, truth=truth, truth_coords=tc,
                active_full=active_full, truth_full=truth_full, visible_full=visible,
                k_dtruth=M.kernel(distance_transform_edt(~truth)),
                n_truth=int(tc[0].size), train_region=train_region,
            ))
    return HoldoutContext(foot=foot, labels=labels, quad=quad, cells=cells)


def score_prediction(pred_sub: np.ndarray, cell: Cell) -> dict:
    """Exact TP/FP/FN of a [0,1] prediction restricted to this cell's active domain."""
    p = np.asarray(pred_sub, dtype=np.float64)
    p = np.where(cell.active & np.isfinite(p), np.clip(p, 0.0, 1.0), 0.0)
    if cell.n_truth == 0 or not p.any():
        return {"tp": 0.0, "fp": float(p.sum()), "fn": float(cell.n_truth), "n_truth": cell.n_truth,
                "mass": float(p.sum()), "dti": 0.0, "coverage": 0.0}
    dp = distance_transform_edt(~(p > 0))
    # soft predictions: TP_w uses max over neighbours of p(x) k(d)
    best = np.zeros(p.shape)
    for dy, dx, k in M._OFFS:
        shifted = np.zeros_like(p)
        h, w = p.shape
        ys0, ys1 = max(0, dy), min(h, h + dy)
        xs0, xs1 = max(0, dx), min(w, w + dx)
        shifted[ys0:ys1, xs0:xs1] = p[max(0, -dy):min(h, h - dy), max(0, -dx):min(w, w - dx)]
        np.maximum(best, shifted * k, out=best)
    tp = float(best[cell.truth].sum())
    fn = float(cell.n_truth) - tp
    fp = float((p * (1.0 - cell.k_dtruth)).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "n_truth": cell.n_truth, "mass": float(p.sum()),
            "dti": M.dti(tp, fp, fn), "coverage": tp / cell.n_truth}


def score_mask(mask: np.ndarray, ctx: HoldoutContext) -> dict:
    """Score a full-grid boolean emission across all cells; returns per-cell + pooled + mean."""
    per_cell = {}
    for c in ctx.cells:
        sl = c.bbox
        per_cell[c.key] = score_prediction((mask[sl] & c.active).astype(np.float64), c)
    cells = list(per_cell.values())
    pooled = M.dti_pooled(cells)
    pooled["per_cell"] = per_cell
    pooled["mean_cell_dti"] = float(np.mean([c["dti"] for c in cells]))
    pooled["per_quadrant"] = {FOLD_NAMES[f]: float(np.mean([per_cell[k]["dti"] for k in per_cell
                                                            if k.endswith(FOLD_NAMES[f])]))
                              for f in FOLDS}
    return pooled


def score_mask_sub(mask_sub: np.ndarray, cells: list[Cell]) -> dict:
    """Score per-cell sub-arrays (used when each fold has its own prediction)."""
    return M.dti_pooled([score_prediction(m.astype(np.float64), c) for m, c in zip(mask_sub, cells)])


def restrict_cell(cell: Cell, mask_full: np.ndarray, key_suffix: str = "") -> Cell:
    """Same cell, but truth and scored domain both restricted to ``mask_full`` (full grid)."""
    sl = cell.bbox
    act = cell.active_full & mask_full
    tru = cell.truth_full & mask_full
    return Cell(key=cell.key + key_suffix, fold=cell.fold, seed=cell.seed, bbox=sl,
                active=act[sl], truth=tru[sl], active_full=act, truth_full=tru,
                visible_full=cell.visible_full,
                truth_coords=np.nonzero(tru[sl]),
                k_dtruth=M.kernel(distance_transform_edt(~tru[sl])),
                n_truth=int(tru.sum()), train_region=cell.train_region)


def tercile_masks(propensity_full: np.ndarray, ctx: HoldoutContext) -> list[np.ndarray]:
    """Full-grid boolean masks for the low/mid/high propensity terciles of the FOOTPRINT."""
    v = propensity_full[ctx.foot]
    q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
    lo = ctx.foot & (propensity_full <= q1)
    mid = ctx.foot & (propensity_full > q1) & (propensity_full <= q2)
    hi = ctx.foot & (propensity_full > q2)
    return [lo, mid, hi]


def score_by_tercile(pred_full: np.ndarray, ctx: HoldoutContext, terciles: list[np.ndarray]) -> dict:
    """Pooled DTI restricted to each propensity tercile (truth and prediction both restricted)."""
    out = {}
    for name, tm in zip(("low", "mid", "high"), terciles):
        cells = []
        for c in ctx.cells:
            sl = c.bbox
            sub = tm[sl]
            p = np.where(sub, np.asarray(pred_full[sl], dtype=np.float64), 0.0)
            cc = Cell(key=c.key, fold=c.fold, seed=c.seed, bbox=sl,
                      active=c.active & sub, truth=c.truth & sub,
                      truth_coords=np.nonzero(c.truth & sub),
                      k_dtruth=M.kernel(distance_transform_edt(~(c.truth & sub))),
                      n_truth=int((c.truth & sub).sum()), train_region=c.train_region)
            cells.append(score_prediction(p, cc))
        r = M.dti_pooled(cells)
        out[name] = {"dti": r["dti"], "tp": r["tp"], "fp": r["fp"], "fn": r["fn"],
                     "n_truth": r["n_truth"], "coverage": r["coverage"]}
    return out


def single_feature_auc(values: np.ndarray, truth: np.ndarray, active: np.ndarray) -> float:
    """Rank AUC of one feature against hidden truth inside the active domain (leakage canary)."""
    v = np.asarray(values, dtype=np.float64)[active]
    t = np.asarray(truth, bool)[active]
    if not np.isfinite(v).all():
        v = np.nan_to_num(v, nan=float(np.nanmedian(v)))
    n_pos, n_neg = int(t.sum()), int((~t).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    r = np.argsort(np.argsort(v)).astype(np.float64) + 1.0
    # tie-corrected ranks
    order = np.argsort(v, kind="mergesort")
    sv = v[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = np.mean(r[order[i:j + 1]])
        i = j + 1
    auc = (r[t].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(max(auc, 1.0 - auc))
