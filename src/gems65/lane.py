"""Lane: selection-bias-aware PU learning for off-catalogue fault placement.

The lane paragraph, implemented end to end
------------------------------------------
1. Treat the catalogue as **positives selected at random given covariates (SAR)**,
   not completely at random.
2. Estimate the propensity ``e(x) = P(labeled | fault, x)`` with the EM method of
   Bekker & Davis (PMLR v94, 2018) -- :mod:`gems65.propensity`.
3. Small covariate set: local relief, slope, a gravity-derived basin-fill proxy,
   lidar coverage, distance to range front -- :data:`gems65.features.PROPENSITY_ATTRIBUTES`.
4. Train with the **propensity-aware empirical risk** of Bekker, Robberechts &
   Davis (arXiv:1809.03207), weights clipped at 10, against an **nnPU** baseline
   on identical folds -- :mod:`gems65.pu`.
5. Emit dots with the exact marginal DTI bar -- `template.emit.allocate_by_marginal_bar`.
6. Gate: higher blocked-holdout DTI overall and no loss in the highest-propensity
   tercile.

Why the propensity is used twice, and why that is the point
----------------------------------------------------------
``e(x)`` enters the risk estimator as an inverse-probability weight: it is what
stops the model from reading "nothing mapped here" as "no fault here".  It also
enters the *emission* as a prior on where the organiser's hidden truth can be:
the private truth is a set of faults an expert panel actually identified, and an
expert can only identify what the available data show.  Under the DTI a dot is
worth placing only if it is within 300 m of a hidden truth pixel, so the
emission must be conditioned on where truth can be observed, not merely on where
faults are likely.  Both uses are reported separately and neither is hidden
inside the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from . import features as F
from .grid import MISSING_BELOW, SHAPE, GridMismatch, read_band
from .pu import nnpu_fit, propensity_weighted_fit, scar_fit
from .propensity import sar_em

TRAIN_UNLABELLED_N: int = 200_000
SCORE_CHUNK_ROWS: int = 256
CACHE_VERSION: int = 2

# Predeclared emission constants (frozen before the holdout was read).
K_TRUTH_PUBLIC: int = 14_143     # |G| for the public subset, see docs/method.html
K_GLOBAL: int = 60_988           # catalogue size, used as the holdout's K
EMIT_FLOOR: float = 1e-4
MAX_DOTS: int = 120_000


# --------------------------------------------------------------------------
# cells and features
# --------------------------------------------------------------------------
def sample_cells(footprint: np.ndarray, catalogue: np.ndarray, *,
                 n_unlabelled: int = TRAIN_UNLABELLED_N, seed: int = 6565) -> dict:
    """One global sample: all catalogue pixels plus a random unlabelled sample.

    Sampled once so that every fold and every arm sees the *same* rows, which is
    what "identical folds" means operationally.
    """
    rng = np.random.default_rng(seed)
    ys_c, xs_c = np.nonzero(catalogue)
    unl = footprint & ~catalogue
    ys_u_all, xs_u_all = np.nonzero(unl)
    take = min(n_unlabelled, ys_u_all.size)
    pick = rng.choice(ys_u_all.size, size=take, replace=False)
    pick.sort()
    ys = np.concatenate([ys_c, ys_u_all[pick]]).astype(np.int32)
    xs = np.concatenate([xs_c, xs_u_all[pick]]).astype(np.int32)
    is_cat = np.concatenate([np.ones(ys_c.size, bool), np.zeros(take, bool)])
    return {"y": ys, "x": xs, "is_catalogue": is_cat, "seed": seed,
            "n_catalogue": int(ys_c.size), "n_unlabelled": int(take)}


def extract(rows: np.ndarray, cols: np.ndarray, *, features_path: str,
            lidar_cov: np.ndarray | None, visible_catalogue: np.ndarray | None,
            ) -> dict:
    """Extract the 19 official bands plus the 5 propensity covariates at cells.

    Missing cells stay NaN and are dropped by the caller, never silently zeroed.
    ``visible_catalogue`` is required whenever any catalogue-derived covariate is
    requested; the fold's *visible* mask is what must be passed, so a withheld
    segment can never inform its own features.
    """
    n = rows.size
    X = np.full((19, n), np.nan, np.float32)
    order = sorted(F.BAND.items(), key=lambda kv: kv[1])
    for name, b in order:
        full = read_band(features_path, b)
        X[b - 1] = full[rows, cols]
        del full
    cov: dict[str, np.ndarray] = {}
    cov["slope"] = X[F.BAND["det_elev_slope"] - 1].copy()

    # local relief needs the neighbourhood, so it is computed on the full grid
    det = read_band(features_path, F.BAND["det_elev"])
    relief = F.local_relief(det)
    cov["local_relief"] = relief[rows, cols]
    del det, relief
    basin = read_band(features_path, F.BAND["depth_to_base_surf"])
    cov["basin_fill_proxy"] = basin[rows, cols]
    del basin

    if lidar_cov is None:
        cov["lidar_coverage"] = np.full(n, np.nan, np.float32)
    else:
        cov["lidar_coverage"] = lidar_cov[rows, cols].astype(np.float32)

    if visible_catalogue is None:
        cov["dist_range_front"] = np.full(n, np.nan, np.float32)
    else:
        rf = F.range_front_mask(visible_catalogue)
        d = F.distance_to_line(rf)
        cov["dist_range_front"] = d[rows, cols]
        del rf, d
    return {"X": X, "cov": cov, "rows": rows, "cols": cols}


def save_cache(path, payload: dict) -> None:
    out = {k: v for k, v in payload.items() if isinstance(v, np.ndarray)}
    out["__meta__"] = np.array([CACHE_VERSION])
    np.savez_compressed(path, **out)


# --------------------------------------------------------------------------
# fit + score
# --------------------------------------------------------------------------
def fit_arms(X: np.ndarray, s: np.ndarray, cov_z: np.ndarray, *,
             kappa: float = 1.0, C: float = 1.0, w_clip: float = 10.0,
             max_iter: int = 12, verbose: bool = False) -> dict:
    """Fit every arm on the same rows.  Returns models, scores and diagnostics."""
    out: dict = {}
    em = sar_em(X, s, cov_z, d=0.10, kappa=kappa, max_iter=max_iter, C=C,
                w_clip=w_clip, verbose=verbose)
    out["sar_em"] = em
    m_sar, f_sar = propensity_weighted_fit(X, s, em.e, C=C, w_clip=w_clip)
    out["sar"] = {"model": m_sar, "f_train": f_sar,
                  "e_train": em.e, "summary": em.summary()}
    c = em.c_scar
    m_scar, f_scar = scar_fit(X, s, c=c, C=C, w_clip=w_clip)
    out["scar"] = {"model": m_scar, "f_train": f_scar, "c": c}
    m_nn, f_nn, tr = nnpu_fit(X, s, pi=c, C=C)
    out["nnpu"] = {"model": m_nn, "f_train": f_nn, "pi": c, "trace": tr}
    return out


@dataclass
class ArmModel:
    """A fitted arm plus everything needed to score the whole grid."""

    name: str
    beta: np.ndarray            # 20 coefficients + intercept, in the design order
    cov_stats: list[dict]
    f_train: np.ndarray | None = None
    e_train: np.ndarray | None = None
    summary: dict | None = None


def build_design_names() -> list[str]:
    """Column order of the design matrix: 19 official bands then 5 covariates."""
    return list(F.CLASSIFIER_FEATURES) + list(F.PROPENSITY_ATTRIBUTES)


def score_full_multi(arms: list[ArmModel], *, features_path: str,
                     cov_stats: list[dict],
                     lidar_cov: np.ndarray | None,
                     visible_catalogue: np.ndarray | None) -> dict[str, np.ndarray]:
    """Apply every arm's coefficients to the whole grid in ONE pass over the file.

    All arms share the *same* covariate statistics (they are fitted on the same
    rows), so the standardisation happens once per block and is then reused --
    which is both faster and removes any chance of two arms seeing differently
    scaled covariates.

    Each band is read once per row-block and shared by all arms: one 419 MB pass
    instead of three.  Peak memory is one 19-band block (~64 MB at the default
    chunk) plus the output fields.
    """
    H, W = SHAPE
    out = {a.name: np.full(SHAPE, np.nan, np.float32) for a in arms}
    det = read_band(features_path, F.BAND["det_elev"])
    relief = F.local_relief(det)
    del det
    slope = read_band(features_path, F.BAND["det_elev_slope"])
    basin = read_band(features_path, F.BAND["depth_to_base_surf"])
    rf_d = None
    if visible_catalogue is not None:
        rf_d = F.distance_to_line(F.range_front_mask(visible_catalogue))
    import rasterio
    from rasterio.windows import Window

    with rasterio.open(features_path) as ds:
        if (ds.height, ds.width) != SHAPE:
            raise GridMismatch(f"{features_path}: {ds.height}x{ds.width} != {SHAPE}")
        for y0 in range(0, H, SCORE_CHUNK_ROWS):
            y1 = min(y0 + SCORE_CHUNK_ROWS, H)
            rows = y1 - y0
            blk = np.empty((19, rows, W), np.float32)
            for b in range(1, 20):
                w = ds.read(b, window=Window(0, y0, W, rows))
                if np.issubdtype(ds.dtypes[b - 1], np.floating):
                    w = np.where(w < MISSING_BELOW, np.float32(np.nan), w)
                blk[b - 1] = w
            zc = np.empty((len(F.PROPENSITY_ATTRIBUTES), rows, W), np.float32)
            raw = [relief[y0:y1], slope[y0:y1], basin[y0:y1],
                   None if lidar_cov is None else lidar_cov[y0:y1].astype(np.float32),
                   None if rf_d is None else rf_d[y0:y1]]
            for i in range(len(F.PROPENSITY_ATTRIBUTES)):
                st = cov_stats[i]
                v = raw[i]
                if v is None:
                    v = np.full((rows, W), st["median"], np.float32)
                else:
                    v = np.where(np.isfinite(v), v, st["median"])
                zc[i] = np.clip((v - st["mean"]) / st["sd"],
                                -st["clip_z"], st["clip_z"])
            del raw
            ncol = len(F.CLASSIFIER_FEATURES) + len(F.PROPENSITY_ATTRIBUTES)
            Zm = np.concatenate([blk, zc], axis=0).reshape(ncol, -1).T.astype(np.float64)
            del blk, zc
            for a in arms:
                if a.beta.size != ncol + 1:
                    raise GridMismatch(
                        f"arm {a.name}: beta has {a.beta.size} coefficients for a "
                        f"{ncol}-column design (expected {ncol + 1}).")
                z = Zm @ a.beta[:ncol] + a.beta[ncol]
                p1 = np.empty(z.size, np.float64)
                pos = z >= 0
                p1[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
                ez = np.exp(z[~pos])
                p1[~pos] = ez / (1.0 + ez)
                out[a.name][y0:y1] = p1.reshape(rows, W).astype(np.float32)
            del Zm
    del relief, slope, basin, rf_d
    return out


def propensity_field_full(coef_e: np.ndarray, cov_stats: list[dict], *,
                          features_path: str, lidar_cov: np.ndarray | None,
                          visible_catalogue: np.ndarray | None,
                          kappa: float = 1.0) -> np.ndarray:
    """The fitted SAR-EM propensity e(x) over the whole grid.

    ``coef_e`` is the final propensity model's ``[w, b]`` for the five
    propensity attributes in :data:`gems65.features.PROPENSITY_ATTRIBUTES` order.
    Only those five covariates are needed, so this never touches the 19-band
    stack: one pass over five fields instead of one over the 419 MB file.
    Used to define the *propensity terciles* the gate is stated on.
    """
    H, W = SHAPE
    det = read_band(features_path, F.BAND["det_elev"])
    relief = F.local_relief(det)
    del det
    slope = read_band(features_path, F.BAND["det_elev_slope"])
    basin = read_band(features_path, F.BAND["depth_to_base_surf"])
    rf = None
    if visible_catalogue is not None:
        rf = F.distance_to_line(F.range_front_mask(visible_catalogue))
    Z = np.empty((5, H, W), np.float32)
    raw = [relief, slope, basin, lidar_cov, rf]
    for i in range(5):
        st = cov_stats[i]
        v = raw[i]
        if v is None:
            v = np.full((H, W), st["median"], np.float32)
        else:
            v = np.where(np.isfinite(v), v, st["median"])
        Z[i] = np.clip((v - st["mean"]) / st["sd"], -st["clip_z"], st["clip_z"])
    del raw, relief, slope, basin, rf
    z = (Z.reshape(5, -1).T @ coef_e[:5] + coef_e[5]) * 1.0
    e = 1.0 / (1.0 + np.exp(-z))
    e = np.clip(e * kappa, 1e-3, 1.0)
    del z, Z
    return e.reshape(H, W).astype(np.float32)


def allocate_topb(p: np.ndarray, allowed: np.ndarray, k_truth: float, *,
                  b_grid: tuple[int, ...] = (500, 1000, 2000, 4000, 8000, 16000,
                                             32000, 64000, 100000),
                  candidate_cap: int = 600_000) -> dict:
    """Pick the dot budget that maximises the *model's own* surrogate DTI.

    Why this is needed rather than just running the bar
    ---------------------------------------------------
    ``allocate_by_marginal_bar`` stops when the marginal test fails.  On a field
    whose discrimination is weak but positive, the smoothed credit ``E[k]`` is
    nearly flat, so almost every candidate passes the bar and the allocation
    walks deep into the noise.  Measured 2026-10-11 on this lane's first gate
    run: 19,688 dots from the SAR arm, 0 of them within 300 m of any withheld
    truth cell, i.e. worse than 1,219 expected from a uniform draw.

    The bar alone therefore does not set a budget; it only tells you when to
    stop *given* a trustworthy ``p``.  Here the budget is chosen explicitly by
    the predeclared rule

        B* = argmax_B  T_B / (alpha * (T_B + B - M_B) + beta * K)

    over a FIXED grid ``b_grid`` frozen before any holdout number was read, with
    ``(T_B, M_B)`` accumulated in descending ``E[k]`` order.  ``b_grid`` is
    predeclared and identical for every arm and every population, so the
    comparison between arms stays fair.

    Returns ``{"emitted", "budget", "curve": [...], "surrogate_dti"}``.
    """
    from .template.emit import expected_credit

    p = np.asarray(p, np.float32)
    H, W = p.shape
    ek = expected_credit(p)
    cand = allowed & (ek > 0)
    ys, xs = np.nonzero(cand)
    if ys.size == 0:
        return {"emitted": np.zeros(p.shape, bool), "budget": 0, "curve": [],
                "surrogate_dti": 0.0}
    order = np.argsort(-ek[ys, xs], kind="stable")
    if order.size > candidate_cap:
        order = order[:candidate_cap]
    ys, xs = ys[order], xs[order]
    k_self = np.minimum(ek[ys, xs].astype(np.float64), 1.0)

    from .template.metric import ALPHA, BETA, OFF_DX, OFF_DY, OFF_K, EPS
    cover = np.zeros(p.shape, np.float32)
    T = M = 0.0
    n = 0
    curve: list[dict] = []
    best = {"budget": 0, "dti": 0.0, "T": 0.0, "M": 0.0}
    bset = set(int(b) for b in b_grid)
    max_b = max(bset)
    taken: list[tuple[int, int]] = []
    for i in range(ys.size):
        if n >= max_b:
            break
        y, x = int(ys[i]), int(xs[i])
        ny, nx = y + OFF_DY, x + OFF_DX
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        nyv, nxv, kw = ny[ok], nx[ok], OFF_K[ok]
        cv = cover[nyv, nxv].astype(np.float64)
        dT = float((p[nyv, nxv].astype(np.float64) * np.maximum(kw - cv, 0.0)).sum())
        taken.append((y, x))
        n += 1
        T += dT
        M += float(k_self[i])
        np.maximum.at(cover, (nyv, nxv), kw.astype(np.float32))
        if n in bset:
            D = ALPHA * (T + n - M) + BETA * k_truth + EPS
            dti = T / D
            curve.append({"budget": n, "T": T, "M": M, "surrogate_dti": dti})
            if dti > best["dti"]:
                best = {"budget": n, "dti": dti, "T": T, "M": M}
    emitted = np.zeros(p.shape, bool)
    if best["budget"] > 0:
        idx = np.array(taken[: best["budget"]], dtype=np.int64)
        emitted[idx[:, 0], idx[:, 1]] = True
    return {"emitted": emitted, "budget": int(best["budget"]),
            "surrogate_dti": float(best["dti"]), "curve": curve,
            "n_placed": int(n)}


def allocate_nms(p: np.ndarray, allowed: np.ndarray, k_truth: float, *,
                radius_px: int = 3,
                b_grid: tuple[int, ...] = (500, 1000, 2000, 4000, 8000, 16000,
                                           32000, 64000, 100000, 160000),
                candidate_cap: int = 900_000) -> dict:
    """Greedy max-coverage allocation with non-maximum suppression.

    Why NMS is required by the metric's own definition
    -------------------------------------------------
    ``TP_w = sum_{g in G} max_{x in P} p(x) k(d(x,g))`` -- a **max over
    predictions, per truth pixel**.  Two dots on the same truth pixel therefore
    earn the credit of ONE.  A plain descending-``E[k]`` sweep keeps draining
    candidates from whichever cluster has the highest intensity, and every dot
    after the first in that cluster has marginal credit ``dT ~ 0`` while still
    paying ``alpha`` of false-positive cost.

    Measured on this lane's first emission (2026-10-11, SAR arm, 100,000 dots):
    1,195 of the dots sat within 300 m of a withheld truth pixel -- a 92x
    enrichment over a uniform draw -- yet the pooled holdout DTI was only
    0.006183, because those dots covered very few *distinct* truth pixels.

    Fix: accept a candidate only if no already-accepted dot lies within
    ``radius_px`` (the kernel radius), so each accepted dot works on fresh
    territory.  This is the standard non-maximum-suppression post-process and is
    the same device earlier lanes describe as "the highest-intensity cells at
    >= 3 px separation".  The budget is then taken from the predeclared price
    curve, exactly as in :func:`allocate_topb`.
    """
    from .template.emit import expected_credit
    from .template.metric import ALPHA, BETA, OFF_DX, OFF_DY, OFF_K, EPS

    p = np.asarray(p, np.float32)
    H, W = p.shape
    ek = expected_credit(p)
    cand = allowed & (ek > 0)
    ys, xs = np.nonzero(cand)
    if ys.size == 0:
        return {"emitted": np.zeros(p.shape, bool), "budget": 0, "curve": [],
                "surrogate_dti": 0.0, "n_scanned": 0, "n_dots": 0,
                "scan_order": np.zeros((0, 2), np.int32)}
    order = np.argsort(-ek[ys, xs], kind="stable")
    if order.size > candidate_cap:
        order = order[:candidate_cap]
    ys, xs = ys[order], xs[order]
    k_self = np.minimum(ek[ys, xs].astype(np.float64), 1.0)

    r = int(radius_px)
    disk = [(j, i) for j in range(-r, r + 1) for i in range(-r, r + 1)
            if j * j + i * i <= r * r]
    blocked = np.zeros((H, W), bool)
    cover = np.zeros((H, W), np.float32)
    T = M = 0.0
    taken: list[tuple[int, int]] = []
    curve: list[dict] = []
    best = {"budget": 0, "dti": 0.0}
    bset = set(int(b) for b in b_grid)
    max_b = max(bset)
    for i in range(ys.size):
        if len(taken) >= max_b:
            break
        y, x = int(ys[i]), int(xs[i])
        if blocked[y, x]:
            continue
        ny, nx = y + OFF_DY, x + OFF_DX
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        nyv, nxv, kw = ny[ok], nx[ok], OFF_K[ok]
        cv = cover[nyv, nxv].astype(np.float64)
        dT = float((p[nyv, nxv].astype(np.float64) * np.maximum(kw - cv, 0.0)).sum())
        taken.append((y, x))
        T += dT
        M += float(k_self[i])
        n = len(taken)
        np.maximum.at(cover, (nyv, nxv), kw.astype(np.float32))
        for j, ii in disk:
            yy, xx = y + j, x + ii
            if 0 <= yy < H and 0 <= xx < W:
                blocked[yy, xx] = True
        if n in bset:
            D = ALPHA * (T + n - M) + BETA * k_truth + EPS
            curve.append({"budget": n, "T": T, "M": M, "surrogate_dti": T / D})
            if T / D > best["dti"]:
                best = {"budget": n, "dti": T / D}
    emitted = np.zeros((H, W), bool)
    if best["budget"] > 0:
        idx = np.array(taken[: best["budget"]], dtype=np.int64)
        emitted[idx[:, 0], idx[:, 1]] = True
    taken_arr = np.asarray(taken, dtype=np.int32) if taken else np.zeros((0, 2), np.int32)
    return {"emitted": emitted, "budget": int(best["budget"]),
            "surrogate_dti": float(best["dti"]), "curve": curve,
            "scan_order": taken_arr,
            "n_scanned": int(min(ys.size, candidate_cap))}


def prune_band(emitted: np.ndarray, dist_to_catalogue: np.ndarray, radius_px: float):
    """Drop emitted dots that sit within ``radius_px`` of a mapped fault.

    Justified by two independent measurements, both in evidence/:

    * ``prune.json`` -> ``score_02778``: the highest-scoring file this project
      has a receipt for (0.2778) is, by exact set identity, an earlier 0.2708
      file with every dot inside 2.0 px of the catalogue deleted (2,545 dots;
      1,201 at sqrt(2) and 1,344 at exactly 2.0).  The +0.0070 that bought is
      exactly 0.2 * 2545 = 509.0 units of false-positive mass at a constant
      true-positive mass.
    * ``prune.json`` -> ``prune_only``: on this lane's own blocked holdout, the
      same edit on a frozen saturated allocation raises HOLDOUT-DTI from
      0.073242 to 0.073348, while pruning at 2.828 px or 3.0 px lowers it.

    So the rule is not "stay away from the catalogue" (see emission_halo.json,
    which rejects that) but "never spend a dot where the nearest truth is
    masked", which is precisely the <= 2 px band.
    """
    keep = ~((emitted) & (dist_to_catalogue <= radius_px))
    return emitted & keep


def rescale_to_prior(score: np.ndarray, allowed: np.ndarray, k_truth: float) -> np.ndarray:
    """Rescale a score field so its mass over ``allowed`` equals ``k_truth``.

    The bar in :func:`allocate_by_marginal_bar` compares an expected credit,
    computed from ``p``, against ``alpha * DTI``, computed from ``|G|``.  Those
    two only balance if ``p`` is on the scale of "probability that this cell is
    hidden truth".  A raw classifier output is not: its training base rate is the
    *visible catalogue* rate, which is a different population from the hidden
    truth.  Mass-matching to the declared ``|G|`` is therefore a required step,
    stated here rather than buried in the emission.
    """
    s = np.asarray(score, np.float64)
    m = np.isfinite(s) & allowed
    tot = float(s[m].sum())
    if tot <= 0:
        return np.zeros_like(s, np.float32)
    out = np.where(m, s * (float(k_truth) / tot), 0.0)
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def canary(feature_values: np.ndarray, truth: np.ndarray, valid: np.ndarray,
           *, names: list[str], n_sample: int = 60_000, seed: int = 11) -> list[dict]:
    """Leakage canary: discriminative AUC of each feature alone on the holdout.

    AUC > 0.90 (either direction, so ``max(auc, 1-auc)``) means leakage until
    proven otherwise -- parallel-run protocol rule 4.
    """
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(seed)
    pos = np.nonzero(truth & valid)[0]
    neg_all = np.nonzero(valid & ~truth)[0]
    if pos.size < 32 or neg_all.size < 32:
        return []
    n_pos = min(pos.size, n_sample // 2)
    n_neg = min(neg_all.size, n_sample - n_pos)
    idx = np.concatenate([rng.choice(pos, n_pos, replace=False),
                          rng.choice(neg_all, n_neg, replace=False)])
    y = np.zeros(idx.size, int)
    y[:n_pos] = 1
    rows = []
    for i, nm in enumerate(names):
        v = feature_values[i][idx].astype(float)
        ok = np.isfinite(v)
        if ok.sum() < 64 or y[ok].min() == y[ok].max():
            continue
        auc = float(roc_auc_score(y[ok], v[ok]))
        rows.append({"feature": nm, "auc": auc, "discriminative_auc": max(auc, 1 - auc),
                     "n_used": int(ok.sum())})
    rows.sort(key=lambda r: -r["discriminative_auc"])
    return rows
