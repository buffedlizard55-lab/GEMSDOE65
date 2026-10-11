#!/usr/bin/env python3
"""GEMSDOE65 experiment 3 -- propensity-weight shrinkage sensitivity.

Experiment 1 (single-feature leakage canary) and experiment 2 (SAR-EM vs nnPU at four
anchoring constants c) are recorded in ``artifacts/``.  Experiment 2's gate FAILED on the
highest-propensity tercile: full propensity correction pushed the emission out of the
well-mapped, high-observability terrain where the withheld catalogue segments live, so
the tercile DTI fell to 0.000 against the nnPU baseline's 0.056.

This experiment asks the natural follow-up inside the same lane: is there a *partial*
correction that keeps the overall gain without the tercile loss?  Shrinking the
importance weights toward 1,

    w_lambda = 1 / e(x)^lambda ,   lambda in [0, 1],

interpolates between the nnPU baseline (lambda = 0, no correction) and the full
propensity-aware risk (lambda = 1).  lambda is a single scalar reported as a sensitivity
curve; the preregistered clip at 10 is retained.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from gems65 import emission, grid, pu  # noqa: E402
from gems65.holdout import load_holdout_context, evaluate_candidate_holdout  # noqa: E402
from gems65.metric import ALPHA, BETA, dti_binary  # noqa: E402

WORK = REPO / "work"
ART = REPO / "artifacts"
LAMBDAS = (0.0, 0.5, 1.0)
SIGMA = 0.0
BUDGET = 44090
NGRID = 3730 * 3292


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def tercile_dti(mask, ctx, e_full, foot_full):
    out = {}
    thr = np.quantile(e_full[foot_full], [1 / 3, 2 / 3])
    for name, lo, hi in (("low", -np.inf, thr[0]), ("mid", thr[0], thr[1]),
                         ("high", thr[1], np.inf)):
        in_t = foot_full & (e_full >= lo) & (e_full < hi)
        vals = []
        for cell in ctx.cells:
            sl = cell.bbox
            act = cell.active_sub
            if int(act.sum()) < 100:
                continue
            t = np.zeros(act.shape, bool)
            ty, tx = cell.truth_coords
            t[ty, tx] = True
            sub_truth = act & t & in_t[sl]
            if sub_truth.sum() == 0:
                continue
            vals.append(float(dti_binary(mask[sl] & act & in_t[sl], sub_truth,
                                         alpha=ALPHA, beta=BETA)["dti"]))
        if vals:
            out[name] = float(np.mean(vals))
    return out


def main() -> int:
    fi = np.load(WORK / "fi.npy")
    foot_full = np.zeros(NGRID, bool)
    foot_full[fi] = True
    foot_full = foot_full.reshape(3730, 3292)
    labels = grid.read_labels()
    surf = np.load(WORK / "surfaces.npz")
    e_rows = np.asarray(surf["e_c0.5"], dtype=np.float64)      # full correction surface
    Xmu = np.load(WORK / "Xmu.npy"); Xsd = np.load(WORK / "Xsd.npy")
    dcols = Xmu.size
    Xm = np.load(WORK / "design.npy", mmap_mode="r").reshape(-1, dcols)
    s_rows = labels.ravel()[fi].astype(np.int8)
    q = float(s_rows.mean())
    lab_idx = np.flatnonzero(s_rows > 0)
    rng = np.random.default_rng(5)
    unl = np.flatnonzero(s_rows == 0)
    unl_sub = rng.choice(unl, size=min(250_000, unl.size), replace=False)

    def gather(idx):
        out = np.empty((idx.size, dcols), np.float32)
        for a in range(0, idx.size, 200_000):
            b = min(idx.size, a + 200_000)
            out[a:b] = np.asarray(Xm[idx[a:b]], dtype=np.float32)
        return out

    Xstack = np.vstack([((gather(lab_idx) - Xmu) / Xsd).astype(np.float32),
                        ((gather(unl_sub) - Xmu) / Xsd).astype(np.float32)])

    ctx = load_holdout_context(grid.DATA, hide_frac=0.20)
    e_full = np.zeros(NGRID, np.float32)
    e_full[fi] = e_rows
    e_full = e_full.reshape(foot_full.shape)

    rows = {}
    for lam in LAMBDAS:
        if lam == 0.0:
            e_use = np.ones(lab_idx.size, np.float64)
        else:
            e_use = np.power(np.clip(e_rows[lab_idx], 1e-6, 1.0), lam)
        t0 = time.time()
        fit = pu.fit_pu_surface(Xstack, np.arange(lab_idx.size), e=e_use, kind="sar",
                                q=q, maxiter=150, subsample_unlabelled=10 ** 9)
        pi_rows = np.empty(fi.size, np.float32)
        for a in range(0, fi.size, 400_000):
            b = min(fi.size, a + 400_000)
            blk = ((np.asarray(Xm[fi[a:b]], dtype=np.float32) - Xmu) / Xsd).astype(np.float32)
            z = blk @ fit.theta
            pi_rows[a:b] = (1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))).astype(np.float32)
            del blk, z
        pi_full = np.zeros(NGRID, np.float32)
        pi_full[fi] = pi_rows
        pi_full = pi_full.reshape(foot_full.shape)
        np.save(WORK / f"pi_lam{lam}.npy", pi_full)
        credit = emission.dispersed_credit_map(pi_full, SIGMA)
        mask = emission.greedy_emission(credit, BUDGET, allowed=foot_full & ~labels)
        ev = evaluate_candidate_holdout(mask, ctx, name=f"lam{lam}")
        terc = tercile_dti(mask, ctx, e_full, foot_full)
        rows[str(lam)] = dict(
            lambda_=lam,
            mean_weight=float(fit.mean_weight_labelled),
            risk_nnpu=float(fit.risk_nnpu),
            emitted=int(mask.sum()),
            holdout_dti=float(ev["catalogue_hidden_mean"]),
            holdout_per_quadrant=ev["catalogue_hidden_per_quadrant"],
            sgmc_off_dti=float(ev["sgmc_off_catalogue_raw_dti"]),
            hug_share=float(ev["hug_share"]),
            tercile_dti=terc,
            seconds=round(time.time() - t0, 1),
        )
        log(f"lambda={lam:<5} w={fit.mean_weight_labelled:6.3f} dots={int(mask.sum()):6d} "
            f"holdout={ev['catalogue_hidden_mean']:.4f} sgmc-off={ev['sgmc_off_catalogue_raw_dti']:.4f} "
            f"terciles={ {k: round(v,4) for k,v in terc.items()} } ({rows[str(lam)]['seconds']}s)")
        del credit, mask, pi_full, pi_rows

    grid.write_json(dict(
        experiment=3, description="propensity-weight shrinkage sensitivity",
        lambdas=list(LAMBDAS), sigma_px=SIGMA, budget=BUDGET,
        results=rows), ART / "shrinkage_sensitivity.json")
    base = rows["0.0"]
    full = rows["1.0"]
    log(f"summary: nnPU(lambda=0) holdout {base['holdout_dti']:.4f} tercile-high "
        f"{base['tercile_dti'].get('high', float('nan')):.4f} | "
        f"full(lambda=1) holdout {full['holdout_dti']:.4f} tercile-high "
        f"{full['tercile_dti'].get('high', float('nan')):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
