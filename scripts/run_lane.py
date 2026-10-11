"""GEMSDOE65 lane runner: SAR-propensity PU vs nnPU on identical blocked folds.

Registered before results (see docs/PRE_REGISTRATION.md):

1. Instrument: the shared ``gems57.holdout.build_holdout`` hide-and-recover
   design (whole fault segments withheld per quadrant with a 12 px domain
   erosion and 3 px truth buffer, catalogue features would be derived from
   visible faults only -- this lane uses no catalogue-derived feature at all),
   scored by the shared pooled DTI (alpha 0.2, beta 0.8, 300 m triangular).
2. Arms: ``sar`` = propensity-weighted empirical risk with
   ``clip(1/e(x), 1, 10)``; ``nnpu`` = the same risk with unit weights
   (constant propensity).  Identical features, sampler, optimiser, prior, folds.
3. Gate: pooled holdout DTI(sar) > DTI(nnpu) on the primary ``all`` folds AND
   DTI(sar) >= DTI(nnpu) in the highest-propensity tercile of the scored domain.
4. Budget: one feature build + one arm sweep; no arm is re-tuned after seeing
   a gate value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import evaluate_holdout as EH  # noqa: E402
from gems57 import grid as G  # noqa: E402
from gems57 import holdout as H  # noqa: E402
from gems57 import metric  # noqa: E402
from holdout_biased import build_biased_holdout, withheld_mean_propensity  # noqa: E402
from sar_pu import (CLIP, emit_cell, fit_head, fit_sar_em, fit_sar_em_rbf, phi,  # noqa: E402
                    pooled_from_terms, predict_surface, standardizer, terms_with_mask)

STACK = ROOT / "data" / "derived" / "feature_stack.npy"
META = ROOT / "data" / "derived" / "feature_meta.json"
EVID = ROOT / "registry"
POS_CAP = 6000
UNL_CAP = 40000
STEPS = 800
LR = 0.05
SEED = 20261011
TERCILE_Q = 2.0 / 3.0


def _stack():
    meta = json.loads(META.read_text())
    return np.load(STACK, mmap_mode="r"), meta


def _x_at(stack, rows, cols) -> np.ndarray:
    """Feature rows for (rows, cols) global indices, NaN-safe (sentinel -> NaN -> 0)."""
    out = np.empty((len(rows), stack.shape[0]), np.float32)
    for b in range(stack.shape[0]):
        out[:, b] = stack[b][rows, cols]
    out[~np.isfinite(out)] = 0.0
    return out


def _crop_x(stack, sl) -> np.ndarray:
    return np.asarray(stack[:, sl[0], sl[1]], np.float32)


def _auc(score, truth) -> float:
    from sklearn.metrics import roc_auc_score
    if truth.sum() == 0 or truth.sum() == truth.size:
        return float("nan")
    return float(roc_auc_score(truth, score))


def run_cell(grid, ctx, cell, stack, meta, pi, arms=("sar", "nnpu"), seed=SEED,
             propensity="grid"):
    """One fold cell: fit both arms, emit, return per-arm terms and diagnostics."""
    sl = cell.bbox
    rng = np.random.default_rng(seed + 7919 * cell.fold + (0 if cell.mode == "all" else 1))
    hidden = ctx.hidden_by_cell[cell.key]
    visible = grid.catalogue & ~hidden
    fp = grid.footprint

    # --- training sample (identical for both arms) -------------------------
    vpos = np.flatnonzero(visible.ravel()[fp.ravel()])  # placeholder to keep dtypes honest
    del vpos
    pos_r, pos_c = np.nonzero(visible)
    if pos_r.size > POS_CAP:
        sel = rng.choice(pos_r.size, POS_CAP, replace=False)
        pos_r, pos_c = pos_r[sel], pos_c[sel]
    unl_pool = fp & ~visible
    n_unl_pool = int(unl_pool.sum())
    unl_r, unl_c = np.nonzero(unl_pool)
    if unl_r.size > UNL_CAP:
        sel = rng.choice(unl_r.size, UNL_CAP, replace=False)
        unl_r, unl_c = unl_r[sel], unl_c[sel]
    Xp = _x_at(stack, pos_r, pos_c)
    Xu = _x_at(stack, unl_r, unl_c)
    w_unl = np.full(Xu.shape[0], n_unl_pool / max(Xu.shape[0], 1))
    # both samples are drawn from a finite population: the EM must see pixel-population
    # counts, otherwise the implied hidden-positive mass is smaller than the labelled mass
    # by exactly these ratios and the fixed point collapses to e -> 1 (IR-65-106)
    n_pos_pool = int(visible.sum())
    pool_ratio = n_unl_pool / max(Xu.shape[0], 1)
    labelled_ratio = n_pos_pool / max(Xp.shape[0], 1)

    # --- SAR-EM selection model (fit once, shared by the weighting) --------
    cov_idx = [meta["propensity_covariates"][k] for k in
               ("relief_1km", "slope", "basin_fill_gdd", "lidar_coverage", "dist_range_front_px")]
    fit_prop = fit_sar_em_rbf if propensity == "rbf" else fit_sar_em
    sar = fit_prop(Xp, Xu, cov_idx, pi=pi, pool_ratio=pool_ratio,
                   labelled_ratio=labelled_ratio, labelled_complete=(Xp.shape[0] == n_pos_pool))
    e_pos = sar.predict(Xp)
    e_unl = sar.predict(Xu)
    mean, std = standardizer(np.vstack([Xp, Xu]))

    diag = dict(cell=cell.key, mode=cell.mode, fold=cell.fold, n_pos_fit=int(Xp.shape[0]),
                n_unl_fit=int(Xu.shape[0]), e_pos_mean=float(e_pos.mean()),
                e_pos_min=float(e_pos.min()), e_pos_max=float(e_pos.max()),
                e_unl_mean=float(e_unl.mean()), e_pos_std=float(e_pos.std()),
                e_pos_p10=float(np.quantile(e_pos, 0.10)), e_pos_p90=float(np.quantile(e_pos, 0.90)),
                clip_fraction=float((e_pos < 1 / CLIP).mean()),
                pool_ratio=float(pool_ratio), labelled_ratio=float(labelled_ratio),
                propensity_model=propensity, propensity_fit=sar.to_json())

    results = {}
    for arm in arms:
        w_pos = np.clip(1.0 / np.clip(e_pos, 1e-6, 1.0), 1.0, CLIP) if arm == "sar" else np.ones_like(e_pos)
        feat = lambda X: phi(X, mean, std)  # noqa: E731  fixed basis, both arms
        theta, fit = fit_head(Xp, w_pos, Xu, w_unl, feat, pi, arm,
                              steps=STEPS, lr=LR, seed=seed, log_every=0)
        diag[f"{arm}_fit"] = {k: v for k, v in fit.items() if k != "history"}

        # --- prediction on the cell crop ----------------------------------
        crop = cell.active
        h, w = crop.shape
        p = np.zeros((h, w), np.float32)
        e_surf = np.zeros((h, w), np.float32)
        rows_any = np.flatnonzero(crop.any(axis=1))
        for start in range(0, len(rows_any), 256):
            rr = rows_any[start:start + 256]
            blk = crop[rr]
            yy, xx = np.nonzero(blk)
            if yy.size == 0:
                continue
            gr = rr[yy] + sl[0].start
            gc = xx + sl[1].start
            Xb = _x_at(stack, gr, gc)
            p[rr[yy], xx] = predict_surface(theta, Xb, mean, std)
            e_surf[rr[yy], xx] = sar.predict(Xb)

        emitted = emit_cell(p, crop, pi)
        truth = np.zeros((h, w), bool)
        ty, tx = cell.truth_yx
        truth[ty, tx] = True

        # --- shared evaluator terms (global 20 km blocks) ------------------
        zeros = np.zeros_like(crop)
        fold = dict(region=np.ones_like(crop), truth=truth, masked_known=zeros, visible=zeros)
        res, terms = EH.evaluate(emitted.astype(np.float64), fold, crop,
                                 origin=(sl[0].start, sl[1].start), global_shape=grid.shape)

        # --- highest-propensity tercile of the scored domain ---------------
        ev = e_surf[crop]
        thr = float(np.quantile(ev, TERCILE_Q)) if ev.size else 0.0
        terc = np.zeros_like(crop)
        terc[crop] = e_surf[crop] >= thr
        terc_terms = terms_with_mask(cell, emitted, terc)

        results[arm] = dict(terms=terms, tercile_terms=terc_terms, result=res,
                            emitted_pixels=int(emitted.sum()), p=p, e=e_surf, truth=truth,
                            score_cell=H.score_cell(cell, emitted), tercile_threshold=thr)

    # --- leakage canary: single-feature AUC against the withheld truth -----
    canary = {}
    ay, ax = np.nonzero(crop)
    take = rng.choice(ay.size, min(20000, ay.size), replace=False)
    gr = ay[take] + sl[0].start
    gc = ax[take] + sl[1].start
    Xc = _x_at(stack, gr, gc)
    tc = truth[ay[take], ax[take]]
    for name in meta["channels"]:
        b = meta["channels"].index(name)
        a = _auc(Xc[:, b], tc)
        canary[name] = a if not np.isnan(a) else None
    return results, diag, canary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="20,21")
    ap.add_argument("--modes", default="all,detached")
    ap.add_argument("--sensitivity", action="store_true",
                    help="also run pi x0.5 and pi x2 for the primary mode")
    ap.add_argument("--out", default=str(EVID / "holdout_arms.json"))
    ap.add_argument("--cache", default=str(EVID / "holdout_terms.npz"))
    ap.add_argument("--propensity", choices=("grid", "rbf"), default="grid",
                    help="grid = discretised quantile SAR-EM (E1/E2); "
                         "rbf = continuous soft-binned SAR-EM (E3, non-degenerate e(x))")
    ap.add_argument("--instrument", choices=("registered", "biased"), default="registered",
                    help="registered = shared uniform-withholding design; "
                         "biased = pre-registered covariate-dependent-withholding diagnostic")
    args = ap.parse_args()

    t0 = time.time()
    stack, meta = _stack()
    grid = G.load_grid(ROOT / "data" / "bridge")
    n_cat = int(grid.catalogue.sum())
    n_fp = int(grid.footprint.sum())
    pi = n_cat / n_fp
    seeds = tuple(int(s) for s in args.seeds.split(","))
    modes = tuple(m.strip() for m in args.modes.split(","))
    if args.instrument == "registered":
        ctx = H.build_holdout(grid, seeds=seeds, modes=modes)
        instrument_note = ("shared gems57.holdout.build_holdout; whole segments withheld "
                           "uniformly at random inside each quadrant domain")
    else:
        # label-blind propensity surface for the withholding bias (full catalogue)
        pos_r, pos_c = np.nonzero(grid.catalogue)
        unl = grid.footprint & ~grid.catalogue
        ur, uc = np.nonzero(unl)
        sel = np.random.default_rng(1).choice(ur.size, min(UNL_CAP, ur.size), replace=False)
        ur, uc = ur[sel], uc[sel]
        cov_idx = [meta["propensity_covariates"][k] for k in
                   ("relief_1km", "slope", "basin_fill_gdd", "lidar_coverage", "dist_range_front_px")]
        fit_prop = fit_sar_em_rbf if args.propensity == "rbf" else fit_sar_em
        em = fit_prop(_x_at(stack, pos_r, pos_c), _x_at(stack, ur, uc), cov_idx, pi=pi,
                      pool_ratio=(unl.sum() / max(ur.size, 1)), labelled_ratio=1.0,
                      labelled_complete=True)
        prop = np.zeros(grid.shape, np.float32)
        em_r, em_c = np.nonzero(grid.footprint)
        for i in range(0, em_r.size, 400_000):
            rr, cc = em_r[i:i + 400_000], em_c[i:i + 400_000]
            prop[rr, cc] = em.predict(_x_at(stack, rr, cc))
        ctx = build_biased_holdout(grid, prop, seeds=seeds)
        instrument_note = ("diagnostic instrument: identical geometry/scoring to the shared "
                           "design but segment withholding probability proportional to "
                           "(1 - mean e(x))^2")
        np.save(EVID / "bias_propensity.npy", prop)
    modes = tuple(sorted({c.mode for c in ctx.cells})) or modes

    print(f"catalogue={n_cat} footprint={n_fp} pi={pi:.6g} cells={len(ctx.cells)}")
    all_diag, canaries = [], {}
    terms_by_arm = {"sar": [], "nnpu": []}
    terc_terms_by_arm = {"sar": [], "nnpu": []}
    per_cell = {}
    keys = [c.key for c in ctx.cells]
    cache = Path(args.cache)
    for ci, cell in enumerate(ctx.cells):
        res, diag, canary = run_cell(grid, ctx, cell, stack, meta, pi, propensity=args.propensity)
        if ci == 0:  # reset an earlier sweep's arrays so key order always matches
            np.savez_compressed(cache, **{f"__keys__": np.array(keys)})
        np.savez_compressed(cache, **{f"__keys__": np.array(keys),
                                      **{f"terms_{arm}": np.array([t for t in
                                          [*map(np.asarray, terms_by_arm[arm]), res[arm]["terms"]]])
                                         for arm in ("sar", "nnpu")},
                                      **{f"terc_{arm}": np.array([t for t in
                                          [*map(np.asarray, terc_terms_by_arm[arm]), res[arm]["tercile_terms"]]])
                                         for arm in ("sar", "nnpu")}})
        all_diag.append(diag)
        canaries.setdefault(cell.mode, []).append(canary)
        per_cell[cell.key] = {arm: dict(dti=res[arm]["result"]["dti"],
                                        emitted=res[arm]["emitted_pixels"],
                                        score_cell=res[arm]["score_cell"]) for arm in res}
        for arm in ("sar", "nnpu"):
            terms_by_arm[arm].append(res[arm]["terms"])
            terc_terms_by_arm[arm].append(res[arm]["tercile_terms"])
        print(f"  {cell.key}: sar emit={res['sar']['emitted_pixels']} "
              f"score={res['sar']['result']['dti']:.6f} | "
              f"nnpu emit={res['nnpu']['emitted_pixels']} score={res['nnpu']['result']['dti']:.6f} "
              f"({time.time() - t0:.0f}s)")

    out = dict(
        propensity_model=args.propensity,
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        aoi=dict(catalogue_pixels=n_cat, footprint_pixels=n_fp, pi_visible_density=pi,
                 withheld_pixels_per_cell={c.key: c.n_truth for c in ctx.cells}),
        evaluator=dict(version=EH.VERSION, implementation_sha256=EH.implementation_hashes(),
                       alpha=metric.ALPHA, beta=metric.BETA, radius_m=metric.R_M),
        instrument=args.instrument, instrument_note=instrument_note,
        protocol=dict(seeds=list(seeds), modes=list(modes), pos_cap=POS_CAP, unl_cap=UNL_CAP,
                      steps=STEPS, lr=LR, clip=CLIP, seed=SEED,
                      propensity=("SAR-EM continuous RBF selection model" if args.propensity == "rbf"
                                  else "SAR-EM discretised selection model")
                                 + "; inverse weights clipped at 10",
                      note="identical features, sampler, optimiser, prior and emission for both arms"),
        cells=per_cell, diagnostics=all_diag,
        leakage_canary={m: {k: float(np.nanmax([c[k] for c in cs if c[k] is not None] or [0.0]))
                            for k in cs[0]} for m, cs in canaries.items()},
    )

    pooled = {}
    for mode in modes:
        pool_terms = {"sar": None, "nnpu": None}
        for arm in ("sar", "nnpu"):
            idx = [i for i, c in enumerate(ctx.cells) if c.mode == mode]
            pool_terms[arm] = np.sum([terms_by_arm[arm][i] for i in idx], axis=0)
        summary = EH.pooled_summary(pool_terms, candidate="sar")
        terc = {arm: pooled_from_terms(np.array([terc_terms_by_arm[arm][i] for i in idx]))
                for arm in ("sar", "nnpu")}
        pooled[mode] = dict(summary=summary, tercile_top_third=terc,
                            n_cells=len(idx))
    out["pooled"] = pooled

    # Gate per the registered protocol, primary mode only.
    prim = pooled["all"]
    sar_dti = prim["summary"]["scores"]["sar"]["dti"]
    nnpu_dti = prim["summary"]["scores"]["nnpu"]["dti"]
    sar_terc = prim["tercile_top_third"]["sar"]["dti"]
    nnpu_terc = prim["tercile_top_third"]["nnpu"]["dti"]
    delta = prim["summary"]["paired_differences"]["nnpu"]
    out["gate"] = dict(
        overall=dict(sar=sar_dti, nnpu=nnpu_dti, passed=bool(sar_dti > nnpu_dti),
                     paired_delta=delta["delta"], paired_ci95=delta["ci95"]),
        top_propensity_tercile=dict(sar=sar_terc, nnpu=nnpu_terc,
                                    passed=bool(sar_terc >= nnpu_terc)),
        current_holdout_best="NOT ESTABLISHED — no prior holdout artifact exists in this checkout; "
                             "the matched nnpu arm is the only incumbent available",
        verdict="promote" if (sar_dti > nnpu_dti and sar_terc >= nnpu_terc) else "negative",
    )
    out["runtime_seconds"] = round(time.time() - t0, 1)
    out["environment"] = dict(python=platform.python_version(), numpy=np.__version__,
                              machine=platform.machine())
    Path(args.out).write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps(out["gate"], indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
