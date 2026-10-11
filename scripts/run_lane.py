#!/usr/bin/env python3
"""GEMSDOE65 lane driver -- selection-bias-aware PU learning for fault discovery.

Preregistered protocol (README "This session's method lane"):

  1. verify the three official competition rasters against their pinned sha256;
  2. build the five preregistered propensity covariates (relief, slope, basin-fill
     proxy, lidar coverage, distance to range front) from the official bands + the
     official 1 m 3DEP lidar tiles;
  3. run the single-feature leakage canary on the spatially blocked holdout
     (AUC > 0.90 = leakage until proven otherwise);
  4. estimate the label propensity e(x) with SAR-EM (Bekker & Davis, PMLR v94, 2018),
     unanchored, reported as a sensitivity analysis over c = E_{y=1}[e];
  5. train the fault posterior with the propensity-aware empirical risk of Bekker,
     Robberechts & Davis (arXiv:1809.03207), importance weights 1/e clipped at 10,
     against an nnPU (SCAR) baseline on identical folds;
  6. score pooled blocked-holdout DTI (alpha 0.2, beta 0.8, 300 m triangular kernel)
     and the off-catalogue (USGS SGMC) DTI;
  7. gate: the SAR candidate must beat both the matched nnPU baseline and the current
     holdout best overall, with no loss in the highest-propensity tercile;
  8. only then emit, check lane drift against the prior-raster registry, validate the
     written GeoTIFF, and publish the download.

Usage
-----
    python3 scripts/run_lane.py --stage all
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from gems65 import emission, features, grid, propensity, pu  # noqa: E402
from gems65.holdout import load_holdout_context, evaluate_candidate_holdout  # noqa: E402

WORK = REPO / "work"
ART = REPO / "artifacts"
COV_CACHE = WORK / "propensity_covariates.npz"
DESIGN_CACHE = WORK / "design.npy"
SURF_CACHE = WORK / "surfaces.npz"
HOLDOUT_CACHE = WORK / "holdout_results.json"

# Preregistered sensitivity grid for the anchoring constant c = E_{x|y=1}[e(x)].
# c is NOT identifiable from PU data alone; these are sensitivity values, not estimates.
C_GRID = (0.25, 0.50, 0.75, 0.95)
DOT_THRESHOLD = 0.5
TERCILE_LABELS = ("low", "mid", "high")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(str(type(o)))


# --------------------------------------------------------------------------------------
# stage 1+2 -- inputs and propensity covariates
# --------------------------------------------------------------------------------------
def stage_covariates() -> dict:
    log("stage 1/8 -- verify pinned official inputs")
    receipt = grid.verify_pinned_inputs()
    grid.write_json(receipt, ART / "input_verification.json")
    if not receipt["ok"]:
        raise SystemExit("official input hash mismatch -- refusing to run (artifacts/input_verification.json)")
    for k, v in receipt["files"].items():
        log(f"  {k}: {v['status']} sha256={v['sha256'][:16]}...")

    log("stage 2/8 -- build the five preregistered propensity covariates")
    cov = features.build_propensity_covariates()
    foot = cov.pop("_footprint")
    front = cov.pop("_front_px")
    np.savez_compressed(
        COV_CACHE, footprint=foot, range_front=front, **{k: v for k, v in cov.items()}
    )
    stats = {}
    for k, v in cov.items():
        m = foot
        stats[k] = dict(min=float(v[m].min()), median=float(np.median(v[m])),
                        max=float(v[m].max()), mean=float(v[m].mean()))
    grid.write_json(stats, ART / "propensity_covariate_stats.json")
    log(f"  range-front proxy pixels: {int(front.sum())} of {int(foot.sum())} footprint px")
    for k, v in stats.items():
        log(f"  {k:16s} min {v['min']:10.3f} med {v['median']:10.3f} max {v['max']:10.3f}")
    return stats


# --------------------------------------------------------------------------------------
# design matrix on the full grid (memmap) so blocked-holdout bboxes index directly
# --------------------------------------------------------------------------------------
def build_design() -> dict:
    """Build / load the (H, W, d) design memmap, one channel at a time.

    The full stack is 3730*3292*35*float32 = 1.7 GB, which does not fit alongside the
    holdout context in a 3 GB sandbox.  Channels are therefore written straight into a
    memmap and never materialised together in RAM.
    """
    if DESIGN_CACHE.is_file() and (WORK / "design_meta.json").is_file():
        meta = json.loads((WORK / "design_meta.json").read_text())
        return dict(X=np.load(DESIGN_CACHE, mmap_mode="r"), names=meta["names"],
                    foot=np.load(COV_CACHE, allow_pickle=True)["footprint"])
    from scipy import ndimage as ndi

    cov = np.load(COV_CACHE, allow_pickle=True)
    foot = cov["footprint"]
    det_elev = grid.read_band(grid.DATA / "training_features.tif", 12, fill=0.0)

    def band(i):
        return grid.read_band(grid.DATA / "training_features.tif", i, fill=0.0)

    names: list[str] = []
    channels: list[np.ndarray] = []
    import rasterio

    with rasterio.open(grid.DATA / "training_features.tif") as ds:
        descs = list(ds.descriptions)
        for i in range(1, ds.count + 1):
            a = ds.read(i)
            a = np.where(a < grid.NODATA_F32 * np.float32(0.5), np.float32(0.0), a.astype(np.float32))
            channels.append(a)
            names.append(descs[i - 1].split(" - ")[0])
            del a

    def add(arr, nm):
        channels.append(np.asarray(arr, dtype=np.float32))
        names.append(nm)

    add(ndi.gaussian_laplace(det_elev, 1.0, mode="nearest"), "curv_s1")
    add(ndi.gaussian_laplace(det_elev, 2.5, mode="nearest"), "curv_s2")
    for s in (1.0, 2.0, 3.5):
        add(features._hessian_ridge(det_elev, s), f"ridge_s{s}")
    loc = ndi.maximum_filter(det_elev, size=5) - ndi.minimum_filter(det_elev, size=5)
    add(loc, "relief5")
    add(det_elev - ndi.grey_opening(det_elev, size=(5, 5)), "tophat2")
    add(features._sm(features._grad_mag(band(14)), 1.0), "tmi_edge")
    add(features._sm(features._grad_mag(band(2)), 1.0), "rtp_edge")
    add(features._sm(features._grad_mag(band(13)), 1.5), "grav_edge")
    add(features._sm(features._grad_mag(band(17)), 1.5), "cond_edge")
    add(features._sm(features._grad_mag(band(15)), 1.5), "depth_grad")
    coh, theta, _ = features._structure_tensor(det_elev, 2.0)
    add(coh, "coherence_s2")
    add(np.cos(2 * theta), "strike_cos")
    add(np.sin(2 * theta), "strike_sin")
    add(foot.astype(np.float32), "footprint")

    H, W = foot.shape
    d = len(channels)
    X = np.lib.format.open_memmap(DESIGN_CACHE, mode="w+", dtype=np.float32, shape=(H, W, d))
    for j, ch in enumerate(channels):
        X[:, :, j] = ch
        del ch
    X.flush()
    del X
    (WORK / "design_meta.json").write_text(json.dumps(
        dict(names=names, footprint_sha256=grid.sha256_file(COV_CACHE),
             footprint_px=int(foot.sum()), shape=[H, W, d], dtype="float32"),
        default=_jsonable))
    return dict(X=np.load(DESIGN_CACHE, mmap_mode="r"), names=names, foot=foot)


# --------------------------------------------------------------------------------------
# stage 3 -- leakage canary
# --------------------------------------------------------------------------------------
def stage_canary() -> dict:
    log("stage 3/8 -- single-feature leakage canary on the blocked holdout")
    d = build_design()
    X, names, foot = d["X"], d["names"], d["foot"]
    ctx = load_holdout_context(grid.DATA, hide_frac=0.20)
    log(f"  holdout context ready: {len(ctx.cells)} blocked cells, "
        f"off-catalogue SGMC truth {ctx.sgmc_n_truth} px")

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(11)
    dcols = X.shape[2]
    rows = []
    for j, nm in enumerate(names):
        aucs = []
        for cell in ctx.cells:
            sl = cell.bbox
            act = cell.active_sub
            ty, tx = cell.truth_coords
            if ty.size < 20 or int(act.sum()) < 500:
                continue
            vis = ctx.labels[sl] & ~act
            # zero out the withheld truth pixels from the "visible" training pool
            vis[ty, tx] = False
            ntr = min(40000, ty.size)
            nvis = min(60000, int(vis.sum()))
            nneg = min(150000, int(act.sum()))
            ti = rng.choice(ty.size, ntr, replace=False) if ty.size > ntr else np.arange(ty.size)
            vi = np.flatnonzero(vis.ravel())
            vi = rng.choice(vi, nvis, replace=False) if vi.size > nvis else vi
            # test negatives are drawn from the WHOLE active domain, which contains the
            # withheld truth -- that is what makes this a leakage test rather than a
            # separation-of-two-disjoint-sets test.
            ni = np.flatnonzero(act.ravel())
            ni = rng.choice(ni, nneg, replace=False) if ni.size > nneg else ni
            sub = np.asarray(X[sl[0], sl[1], j], dtype=np.float32).ravel()
            truth_flat = np.zeros(act.size, bool)
            truth_flat[ty.ravel() * act.shape[1] + tx.ravel()] = True
            xtr = np.concatenate([sub[truth_flat][ti], sub[vi]])[:, None]
            ytr = np.concatenate([np.ones(ti.size), np.zeros(vi.size)])
            if ytr.sum() == 0 or ytr.sum() == ytr.size:
                continue
            clf = LogisticRegression(C=1.0, max_iter=200)
            clf.fit(xtr, ytr)
            xte = sub[ni][:, None]
            yte = truth_flat[ni]
            if yte.sum() == 0 or yte.sum() == yte.size:
                continue
            aucs.append(float(roc_auc_score(yte, clf.predict_proba(xte)[:, 1])))
        if aucs:
            rows.append(dict(feature=nm, mean_auc=float(np.mean(aucs)),
                             max_auc=float(np.max(aucs)), n_cells=len(aucs)))
    rows.sort(key=lambda r: -r["mean_auc"])
    flagged = [r for r in rows if r["mean_auc"] > 0.90]
    out = dict(
        evaluator="blocked whole-segment hide-and-recover, pooled over 4 quadrants x 2 draws",
        alpha=0.2, beta=0.8, radius_px=3.0,
        leakage_threshold_auc=0.90,
        n_features=len(rows),
        flagged_as_leakage=[r["feature"] for r in flagged],
        top_20=rows[:20],
        full=rows,
    )
    grid.write_json(out, ART / "leakage_canary.json")
    log(f"  canary complete: {len(rows)} features tested, "
        f"{len(flagged)} flagged (mean AUC > 0.90)")
    for r in rows[:8]:
        log(f"    {r['feature']:22s} mean AUC {r['mean_auc']:.4f}  max {r['max_auc']:.4f}")
    if flagged:
        log("  LEAKAGE FLAG: " + ", ".join(r["feature"] for r in flagged))
    return out


# --------------------------------------------------------------------------------------
# stage 4+5 -- SAR-EM propensity surfaces and PU fits
# --------------------------------------------------------------------------------------
def stage_surfaces() -> dict:
    log("stage 4/8 -- SAR-EM propensity estimation (Bekker & Davis 2018)")
    d = build_design()
    X, names, foot = d["X"], d["names"], d["foot"]
    labels = grid.read_labels()
    cov = np.load(COV_CACHE, allow_pickle=True)
    znames = ["relief", "slope", "basin_fill", "lidar_cov", "dist_rangefront"]

    fi = np.flatnonzero(foot.ravel())                 # flat index of every footprint px
    n = fi.size
    s = labels.ravel()[fi].astype(np.int8)            # catalogue indicator, footprint rows

    # --- propensity covariates, footprint rows, standardised -------------------------
    Z = np.empty((n, len(znames)), np.float64)
    for j, k in enumerate(znames):
        Z[:, j] = cov[k].ravel()[fi]
    mu = Z.mean(axis=0)
    sd = Z.std(axis=0)
    sd[sd == 0] = 1.0
    Zs = ((Z - mu) / sd).astype(np.float32)
    del Z

    # --- detector design matrix, footprint rows, standardised ------------------------
    dcols = X.shape[2]
    xmu = np.zeros(dcols, np.float64)
    xsd = np.zeros(dcols, np.float64)
    CH = 400_000
    acc = np.zeros(dcols, np.float64)
    acc2 = np.zeros(dcols, np.float64)
    cnt = 0
    for a in range(0, n, CH):
        b = min(n, a + CH)
        blk = np.asarray(X.reshape(-1, dcols)[fi[a:b]], dtype=np.float64)
        acc += blk.sum(axis=0)
        acc2 += (blk ** 2).sum(axis=0)
        cnt += b - a
        del blk
    xmu = acc / cnt
    xsd = np.sqrt(np.maximum(acc2 / cnt - xmu ** 2, 1e-12))
    xsd[xsd == 0] = 1.0
    np.save(WORK / "Xmu.npy", xmu)
    np.save(WORK / "Xsd.npy", xsd)
    np.save(WORK / "fi.npy", fi)
    (WORK / "surf_meta.json").write_text(json.dumps(dict(
        znames=znames, feature_names=names, foot_count=int(n),
        z_mean=mu.tolist(), z_sd=sd.tolist())))

    q = float(s.mean())
    log(f"  catalogue rate q = P(s=1) = {q:.6f}  ({int(s.sum())} labelled px of {n})")

    def gather(idx):
        out = np.empty((idx.size, dcols), np.float32)
        for a in range(0, idx.size, CH):
            b = min(idx.size, a + CH)
            out[a:b] = np.asarray(X.reshape(-1, dcols)[idx[a:b]], dtype=np.float32)
        return out

    def standardise(blk):
        return ((blk - xmu) / xsd).astype(np.float32)

    def predict_full(theta):
        out = np.empty(n, np.float32)
        for a in range(0, n, CH):
            b = min(n, a + CH)
            blk = standardise(np.asarray(X.reshape(-1, dcols)[fi[a:b]], dtype=np.float32))
            z = blk @ theta
            out[a:b] = (1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))).astype(np.float32)
            del blk, z
        return out

    lab_idx = np.flatnonzero(s > 0)
    rng = np.random.default_rng(3)
    unl_idx = np.flatnonzero(s == 0)
    unl_sub = rng.choice(unl_idx, size=min(400_000, unl_idx.size), replace=False)
    Xlab_std = standardise(gather(lab_idx))
    Xunl_std = standardise(gather(unl_sub))
    Xstack = np.vstack([Xlab_std, Xunl_std])
    del Xlab_std, Xunl_std

    def fit_pi(Zmat, w):
        """Fit the latent fault posterior with the exact propensity-aware PU risk.

        ``w`` arrives indexed like ``Zmat`` (one importance weight per footprint pixel);
        only the labelled rows carry a non-zero weight, and those are the rows the
        propensity-aware empirical risk of Bekker-Robberechts-Davis weights by ``1/e``.
        """
        wl = np.clip(np.asarray(w, dtype=np.float64), 0.0, pu.WEIGHT_CLIP)
        w_lab = wl[lab_idx]
        fit = pu.fit_pu_surface(Xstack, np.arange(lab_idx.size), e=w_lab, kind="sar", q=q)
        return predict_full(fit.theta)

    # --- f_hat(x) = P(s=1|x): the observable labelled rate ---------------------------
    from sklearn.linear_model import LogisticRegression

    fs = rng.choice(n, size=min(900_000, n), replace=False)
    clf_f = LogisticRegression(C=1.0, max_iter=300)
    clf_f.fit(Zs[fs], s[fs])
    f_hat = clf_f.predict_proba(Zs)[:, 1].astype(np.float64)
    log(f"  labelled-rate model: P(s=1) mean {f_hat.mean():.6f} (observed {q:.6f})")

    results = {}
    for c in C_GRID:
        log(f"  --- SAR-EM at c = {c}")
        res = propensity.sar_em(Zs, s, foot, fit_pi, c=float(c), max_iter=12, log=log)
        results[f"e_c{c}"] = res.e
        results[f"pi_c{c}"] = res.pi
        results[f"f_c{c}"] = res.f_hat
        log(f"      e: min {res.e_min:.4f} med {float(np.median(res.e)):.4f} max {res.e_max:.4f} "
            f"converged={res.converged} iters={res.n_iter}")

    # nnPU baseline: NO importance weighting (e == 1 on every labelled positive).
    # That is exactly the standard uPU/nnPU risk of Kiryo et al. with the class prior
    # set to the observable q = P(s=1) -- i.e. the "every positive is labelled" SCAR
    # assumption.  It is the matched baseline the preregistration asks for.
    np.save(WORK / "f_hat.npy", f_hat.astype(np.float32))
    np.save(WORK / "nnpu_e.npy", np.ones(int(s.sum()), np.float64))
    np.savez_compressed(SURF_CACHE, **results)
    grid.write_json(dict(c_grid=list(C_GRID), q=q, scar_constant=float(q),
                         nnpu_baseline="e == 1 on every labelled positive (no importance weights)",
                         note="c is a sensitivity value, not an estimate; see README"),
                    ART / "sar_em_summary.json")
    log("stage 4/8 -- done; propensity surfaces cached to work/surfaces.npz")
    return dict(q=q)


# --------------------------------------------------------------------------------------
def _bootstrap_ci(vals: list[float], n_boot: int = 4000, seed: int = 0) -> dict:
    v = np.asarray(vals, float)
    if v.size == 0:
        return dict(mean=None, lo=None, hi=None, n=0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    means = v[idx].mean(axis=1)
    return dict(mean=float(v.mean()), lo=float(np.percentile(means, 2.5)),
                hi=float(np.percentile(means, 97.5)), n=int(v.size))


def stage_holdout(sigmas=(0.0, 0.75, 1.5), budgets=(30000, 44090)) -> dict:
    log("stage 5/8 -- blocked-holdout evaluation of the propensity surfaces")
    d = build_design()
    foot = d["foot"]
    ctx = load_holdout_context(grid.DATA, hide_frac=0.20)
    log(f"  holdout context: {len(ctx.cells)} blocked cells, "
        f"off-catalogue SGMC truth {ctx.sgmc_n_truth} px")
    surf = np.load(SURF_CACHE)
    labels = grid.read_labels()
    fi = np.load(WORK / "fi.npy")
    n = fi.size
    Xmu = np.load(WORK / "Xmu.npy"); Xsd = np.load(WORK / "Xsd.npy")
    dcols = Xmu.size
    CH = 400_000
    Xm = d["X"].reshape(-1, dcols)
    s_rows = labels.ravel()[fi].astype(np.int8)
    q = float(s_rows.mean())
    rng = np.random.default_rng(5)
    unl = np.flatnonzero(s_rows == 0)
    unl_sub = rng.choice(unl, size=min(400_000, unl.size), replace=False)

    def gather(idx):
        out = np.empty((idx.size, dcols), np.float32)
        for a in range(0, idx.size, CH):
            b = min(idx.size, a + CH)
            out[a:b] = np.asarray(Xm[idx[a:b]], dtype=np.float32)
        return out

    def to_full(flat_rows):
        a = np.zeros(foot.size, np.float32)
        a[fi] = flat_rows
        return a.reshape(foot.shape)

    lab_idx = np.flatnonzero(s_rows > 0)
    Xl = ((gather(lab_idx) - Xmu) / Xsd).astype(np.float32)
    Xu = ((gather(unl_sub) - Xmu) / Xsd).astype(np.float32)
    fit = pu.fit_pu_surface(np.vstack([Xl, Xu]), np.arange(Xl.shape[0]),
                            e=np.load(WORK / "nnpu_e.npy"), kind="nnpu", q=q)
    log(f"  nnPU baseline risk_u {fit.risk_u:.2f} risk_nnpu {fit.risk_nnpu:.2f} "
        f"mean weight {fit.mean_weight_labelled:.3f}")
    del Xl, Xu

    def predict_full(theta):
        out = np.empty(n, np.float32)
        for a in range(0, n, CH):
            b = min(n, a + CH)
            blk = ((np.asarray(Xm[fi[a:b]], dtype=np.float32) - Xmu) / Xsd).astype(np.float32)
            z = blk @ theta
            out[a:b] = (1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))).astype(np.float32)
            del blk, z
        return out

    cands = {f"sar_{k[3:]}": surf[k] for k in surf.files if k.startswith("pi_")}
    cands["nnpu_baseline"] = predict_full(fit.theta)

    results = {}
    for name, flat in cands.items():
        full = to_full(flat)
        row = {}
        for sigma in sigmas:
            credit = emission.dispersed_credit_map(full, sigma)
            for budget in budgets:
                mask = emission.greedy_emission(credit, budget, allowed=foot & ~labels)
                if mask.sum() == 0:
                    continue
                ev = evaluate_candidate_holdout(mask, ctx, name=f"{name}|s{sigma}|b{budget}")
                row[f"sigma{sigma}_budget{budget}"] = dict(
                    emitted=int(mask.sum()),
                    holdout_dti=ev["catalogue_hidden_mean"],
                    holdout_dti_per_quadrant=ev["catalogue_hidden_per_quadrant"],
                    sgmc_off_dti=ev["sgmc_off_catalogue_raw_dti"],
                    sgmc_coverage=ev["sgmc_off_catalogue_coverage"],
                    hug_share=ev["hug_share"],
                )
            del credit
        results[name] = row
        log(f"  {name}: {len(row)} emission configs evaluated")

    best = {}
    for name, row in results.items():
        b = max(row.items(), key=lambda kv: kv[1]["holdout_dti"])
        best[name] = dict(config=b[0], **b[1])
    grid.write_json(dict(candidates=results, best_per_candidate=best,
                         sigmas=list(sigmas), budgets=list(budgets)),
                    ART / "holdout_sweep.json")
    grid.write_json(best, ART / "holdout_best.json")
    for name, b in best.items():
        log(f"  BEST {name:16s} {b['config']:26s} holdout DTI {b['holdout_dti']:.4f} "
            f"sgmc-off {b['sgmc_off_dti']:.4f} emitted {b['emitted']}")
    return dict(results=results, best=best, ctx=ctx)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="all",
                    choices=["all", "covariates", "canary", "surfaces", "holdout"])
    a = ap.parse_args()
    WORK.mkdir(exist_ok=True)
    ART.mkdir(exist_ok=True)
    if a.stage in ("all", "covariates"):
        stage_covariates()
    if a.stage in ("all", "canary"):
        stage_canary()
    if a.stage in ("all", "surfaces"):
        stage_surfaces()
    if a.stage in ("all", "holdout"):
        stage_holdout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
