"""Stage 02 -- the lane's experiment: propensity-aware ERM vs nnPU on identical blocked folds.

Run:  python scripts/02_run_holdout.py [--cells 8] [--dots 40000]
Out:  evidence/holdout_pu.json   (HOLDOUT-DTI numbers + leakage canary + gate)

Protocol compliance:
  * Holdout = hide-and-recover: whole catalogue connected components are withheld with a 15 px
    collar, an extra 20% of train-side components is hidden, every catalogue-derived quantity in
    this lane is derived ONLY from visible faults (this lane has none: covariates.py is
    catalogue-free by construction), visible faults are masked pixel-exactly, and the score is
    POOLED DTI (alpha 0.2, beta 0.8, 300 m triangular kernel).
  * Both arms see identical folds, identical sampled rows, identical population weights and
    identical RFF basis; they differ ONLY in the risk (Definition 2 with c=min(1/e,10) vs nnPU).
  * The emission rule and the dot budget are also identical, so any difference in pooled DTI is
    attributable to the risk, not to the placement heuristic.
  * Leakage canary: every single feature is scored alone on the holdout; AUC > 0.90 is reported
    as LEAKAGE-SUSPECT.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import covariates as CV  # noqa: E402
from gems65 import emission as EM  # noqa: E402
from gems65 import features as FT  # noqa: E402
from gems65 import grid as G  # noqa: E402
from gems65 import holdout as HO  # noqa: E402
from gems65 import metric as M  # noqa: E402
from gems65 import pu  # noqa: E402
from scipy.ndimage import distance_transform_edt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts_lib import covariate_rows, propensity_design  # noqa: E402  (single source of truth)

A_BAR_PRIMARY = 0.25          # brief: "only about 25% of the region has detailed (~1:24,000) mapping"
A_BAR_GRID = (0.15, 0.25, 0.32, 0.50)
N_RFF = 48
N_RFF_E = 0                   # 0 => linear-in-covariates propensity model (+ squares), interpretable
N_UNLABELED = 120_000
EM_ITERS = 6
W_CLIP = 10.0
DOTS_TOTAL = 40_000
MIN_DIST_PX = 2.8
CAT_BUFFER_PX = 3
CHUNK = 250_000
SEED = 20261011


def fit_propensity_model(e_target: np.ndarray, s: np.ndarray, w: np.ndarray, De: np.ndarray,
                         l2: float = 1e-2) -> np.ndarray:
    return pu.fit_soft_target_logistic(De, s, w * np.clip(e_target, 1e-3, 1.0), l2=l2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=int, default=8)
    ap.add_argument("--dots", type=int, default=DOTS_TOTAL)
    ap.add_argument("--unlabeled", type=int, default=N_UNLABELED)
    ap.add_argument("--em-iters", type=int, default=EM_ITERS)
    args = ap.parse_args()

    t0 = time.time()
    work = G.work_dir()
    repo = G.repo_root()
    z = np.load(work / "masks.npz")
    foot, labels = z["foot"], z["labels"]
    store = FT.FeatureStore(work)
    lookup = store.lookup()
    cvz = np.load(work / "covariates.npz")
    cov_full = {k: cvz[k] for k in cvz.files}
    cov_stats = json.loads((repo / "evidence" / "covariates.json").read_text())["covariate_stats"]

    def cov_rows(flat: np.ndarray) -> np.ndarray:
        return covariate_rows(cov_full, flat)

    ctx = HO.build_holdout(foot, labels)
    print(f"[holdout] {len(ctx.cells)} cells; hidden truth px per cell: "
          f"{[c.n_truth for c in ctx.cells]}")

    rng_global = np.random.default_rng(SEED)
    per_cell = []
    canary_num = {}
    canary_den = 0
    arms_out = {"sar_erm": [], "nnpU_scar": [], "sar_em_only": []}
    tercile_out = {"sar_erm": [], "nnpU_scar": []}
    a_bar_out = {str(a): [] for a in A_BAR_GRID}

    for ci, cell in enumerate(ctx.cells[: args.cells]):
        tc0 = time.time()
        # ---------- training population for this cell
        vis = labels & cell.train_region
        unl = cell.train_region & ~labels
        n_unl_pop = int(unl.sum())
        pos_flat = np.flatnonzero(vis.ravel())
        rng = np.random.default_rng(SEED + 17 * ci)
        take = min(args.unlabeled, n_unl_pop)
        unl_flat = rng.choice(np.flatnonzero(unl.ravel()), size=take, replace=False)
        tr_flat = np.concatenate([pos_flat, unl_flat])
        s = np.concatenate([np.ones(len(pos_flat)), np.zeros(len(unl_flat))])
        w = np.concatenate([np.ones(len(pos_flat)), np.full(len(unl_flat), n_unl_pop / max(take, 1))])
        Xtr = store.rows_for_flat(tr_flat)
        Xcov_tr = cov_rows(tr_flat)
        rff = pu.RFF.fit(Xtr, n_features=N_RFF, seed=SEED)
        Df_tr = rff.design(Xtr)
        cmed = np.median(Xcov_tr, axis=0)
        ciqr = np.maximum(np.percentile(Xcov_tr, 75, axis=0) - np.percentile(Xcov_tr, 25, axis=0), 1e-6)
        De_tr = propensity_design(Xcov_tr, cmed, ciqr)

        # ---------- EM for (f, e)  [SOURCE B sec. 5.2]
        em = pu.fit_sar_em(Df_tr, De_tr, s, w, max_iter=args.em_iters, seed=SEED, verbose=False)
        e_raw = em.e_raw
        b_shift = {a: pu.anchor_shift(e_raw, s, a) for a in A_BAR_GRID}
        pi_ht = {}
        # ---------- arms
        # Arm A: propensity-aware ERM (Definition 2), weights clipped at 10
        thetaA = {}
        for a_bar in A_BAR_GRID:
            e_a = pu.apply_shift(e_raw, b_shift[a_bar])
            c_a = np.minimum(1.0 / np.clip(e_a, 1e-3, 1.0), W_CLIP)
            pi_ht[a_bar] = pu.horvitz_thompson_prior(e_a, s, w)
            thetaA[a_bar] = pu.fit_risk(
                Df_tr, float(np.mean(s)), s, w,
                lambda p, ss, ww, c=c_a: pu.propensity_weighted_risk(p, ss, c, ww), l2=1e-3)
        # Arm B: nnPU (SCAR) baseline, prior = the SAME Horvitz-Thompson prevalence at the primary
        # anchor, so the two arms differ only in whether the propensity is instance-dependent.
        a0 = A_BAR_PRIMARY
        e0 = pu.apply_shift(e_raw, b_shift[a0])
        c0 = np.minimum(1.0 / np.clip(e0, 1e-3, 1.0), W_CLIP)
        pi0 = pi_ht[a0]
        thetaB = pu.fit_risk(Df_tr, pi0, s, w,
                             lambda p, ss, ww: pu.nnpu_risk_pn(p, ss, pi0, ww), l2=1e-3)

        # ---------- test domain prediction, chunked (full-grid active mask -> flat indices)
        sl = cell.bbox
        H, W = foot.shape
        act_sub_flat = np.flatnonzero(cell.active_full.ravel())

        # Shared-chunk prediction: one RFF design per chunk feeds every arm (EM f, nnPU f, and the
        # propensity-aware ERM f at each anchor).  This is 6x cheaper than one pass per model.
        NP = H * W
        belA = np.zeros(NP, np.float32)
        belB = np.zeros(NP, np.float32)
        belEM = np.zeros(NP, np.float32)
        e_test = np.zeros(NP, np.float32)
        belA_bar = {a: np.zeros(NP, np.float32) for a in A_BAR_GRID if a != a0}
        for a in range(0, act_sub_flat.size, CHUNK):
            bnd = min(act_sub_flat.size, a + CHUNK)
            fl = act_sub_flat[a:bnd]
            Db = rff.design(store.rows_for_flat(fl))
            Deb = propensity_design(cov_rows(fl), cmed, ciqr)
            eb = pu.apply_shift(np.clip(pu.sigmoid(Deb @ em.theta_e), pu.E_MIN, pu.E_MAX), b_shift[a0])
            fA = pu.sigmoid(Db @ thetaA[a0])
            fB = pu.sigmoid(Db @ thetaB)
            fEM = pu.sigmoid(Db @ em.theta_f)
            belA[fl] = pu.posterior_from_models(fA, eb).astype(np.float32)
            belB[fl] = fB.astype(np.float32)
            belEM[fl] = fEM.astype(np.float32)
            e_test[fl] = eb.astype(np.float32)
            for a_bar in belA_bar:
                eb2 = pu.apply_shift(np.clip(pu.sigmoid(Deb @ em.theta_e), pu.E_MIN, pu.E_MAX), b_shift[a_bar])
                belA_bar[a_bar][fl] = pu.posterior_from_models(pu.sigmoid(Db @ thetaA[a_bar]), eb2).astype(np.float32)
        belA = belA.reshape(H, W)
        belB = belB.reshape(H, W)
        belEM = belEM.reshape(H, W)
        e_test = e_test.reshape(H, W)
        belA_bar = {k: v.reshape(H, W) for k, v in belA_bar.items()}

        # ---------- emission: identical rule and budget for both arms
        n_active = int(cell.active_full.sum())
        budget = int(round(args.dots * n_active / float(foot.sum())))
        # PROTOCOL: every catalogue-derived quantity must come from VISIBLE faults only.  The
        # off-catalogue buffer is therefore built from cell.visible_full, NOT from the full label
        # raster -- otherwise the emitter is structurally forbidden from ever reaching the withheld
        # truth and the holdout measures nothing (found and fixed 2026-10-11, IR-65-002).
        elig_full = EM.eligible_offcatalogue(foot, cell.visible_full, buffer_px=CAT_BUFFER_PX) & cell.active_full
        cells_res = {}
        for arm, bel in (("sar_erm", belA), ("nnpU_scar", belB), ("sar_em_only", belEM)):
            dots = EM.poisson_disk_dots(bel, elig_full, budget, MIN_DIST_PX)
            r = HO.score_prediction(dots[sl].astype(np.float64), cell)
            cells_res[arm] = {"score": r, "dots": dots}
            arms_out[arm].append(r)

        # ---------- propensity terciles (gate: no loss in the highest-propensity tercile)
        v = e_test[cell.active_full]
        q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
        hi = cell.active_full & (e_test > q2)
        for arm in ("sar_erm", "nnpU_scar"):
            dots = cells_res[arm]["dots"]
            sub_hi = (dots & hi)[sl].astype(np.float64)
            cell_hi = HO.restrict_cell(cell, hi, "_hiE")
            tercile_out[arm].append(HO.score_prediction(sub_hi, cell_hi))
        for a_bar in A_BAR_GRID:
            if a_bar == a0:
                continue
            dots = EM.poisson_disk_dots(belA_bar[a_bar], elig_full, budget, MIN_DIST_PX)
            a_bar_out[str(a_bar)].append(HO.score_prediction(dots[sl].astype(np.float64), cell))

        # ---------- leakage canary accumulators (single feature vs hidden truth, pooled)
        Xall = store.rows_for_flat(act_sub_flat)
        covall = cov_rows(act_sub_flat)
        truth_flat = cell.truth_full.ravel()[act_sub_flat]
        act_flat_1 = np.ones(act_sub_flat.size, bool)
        for j, nm in enumerate(FT.FEATURE_NAMES):
            auc = HO.single_feature_auc(Xall[:, j], truth_flat, act_flat_1)
            if np.isfinite(auc):
                canary_num[nm] = canary_num.get(nm, 0.0) + auc * cell.n_truth
        for j, nm in enumerate(CV.COVARIATE_NAMES):
            auc = HO.single_feature_auc(covall[:, j], truth_flat, act_flat_1)
            if np.isfinite(auc):
                canary_num[f"cov_{nm}"] = canary_num.get(f"cov_{nm}", 0.0) + auc * cell.n_truth
        canary_den += cell.n_truth

        per_cell.append({
            "cell": cell.key, "n_truth": cell.n_truth, "n_active": n_active,
            "budget_dots": budget, "n_pos_train": int(len(pos_flat)), "n_unl_sampled": int(take),
            "n_unl_population": n_unl_pop,
            "em_history": em.history, "em_converged": bool(em.converged), "em_iters": em.n_iter,
            "mean_e_labelled_raw": float(np.mean(e_raw[s > 0.5])),
            "pi_horvitz_thompson_by_anchor": {str(k): float(v) for k, v in pi_ht.items()},
            "seconds": round(time.time() - tc0, 1),
            "arms": {arm: {"dti": cells_res[arm]["score"]["dti"], "tp": cells_res[arm]["score"]["tp"],
                           "fp": cells_res[arm]["score"]["fp"], "fn": cells_res[arm]["score"]["fn"],
                           "coverage": cells_res[arm]["score"]["coverage"],
                           "dots": int(cells_res[arm]["score"]["mass"])} for arm in cells_res},
        })
        print(f"[cell {cell.key}] truth={cell.n_truth} budget={budget} "
              f"SAR={cells_res['sar_erm']['score']['dti']:.5f} "
              f"nnPU={cells_res['nnpU_scar']['score']['dti']:.5f} "
              f"EMonly={cells_res['sar_em_only']['score']['dti']:.5f} "
              f"pi_HT={pi0:.4f} ({time.time()-tc0:.0f}s)")
        del Xall, covall, belA, belB, belEM, e_test, belA_bar

    # ---------------- pooled results
    pooled = {arm: M.dti_pooled(v) for arm, v in arms_out.items()}
    pooled_tercile = {arm: M.dti_pooled(v) for arm, v in tercile_out.items()}
    pooled_abar = {k: M.dti_pooled(v) for k, v in a_bar_out.items() if v}
    # bootstrap CI over cells of the per-cell DTI difference (paired)
    d_sar = np.array([c["dti"] for c in arms_out["sar_erm"]])
    d_npu = np.array([c["dti"] for c in arms_out["nnpU_scar"]])
    diff = d_sar - d_npu
    ci = M.bootstrap_ci(diff, n_boot=4000, seed=SEED)
    canary = {k: v / max(canary_den, 1) for k, v in canary_num.items()}

    gate = {
        "rule": "higher blocked-holdout pooled DTI overall AND no loss in the highest-propensity tercile",
        "primary_anchor_a_bar": A_BAR_PRIMARY,
        "pooled_dti_sar_erm": pooled["sar_erm"]["dti"],
        "pooled_dti_nnpu_scar": pooled["nnpU_scar"]["dti"],
        "overall_delta": pooled["sar_erm"]["dti"] - pooled["nnpU_scar"]["dti"],
        "overall_delta_mean_cell_ci95": [ci[0], ci[1]],
        "overall_wins": int((diff > 0).sum()), "overall_cells": int(diff.size),
        "top_tercile_dti_sar_erm": pooled_tercile["sar_erm"]["dti"],
        "top_tercile_dti_nnpu_scar": pooled_tercile["nnpU_scar"]["dti"],
        "top_tercile_delta": pooled_tercile["sar_erm"]["dti"] - pooled_tercile["nnpU_scar"]["dti"],
        "leakage_canary_max_auc": max(canary.values()) if canary else None,
        "leakage_canary_suspects": sorted([k for k, v in canary.items() if v > 0.90], key=lambda k: -canary[k]),
    }
    gate["GATE_PASSED"] = bool(gate["overall_delta"] > 0 and gate["top_tercile_delta"] >= 0
                               and not gate["leakage_canary_suspects"])

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": "HOLDOUT-DTI (proxy: truth = withheld catalogue segments; cannot reward a fault in no catalogue)",
        "seconds_total": round(time.time() - t0, 1),
        "config": {
            "folds": "4 quadrant blocks x 2 draws, collar 15 px, domain erosion 12 px, hide_frac 0.20",
            "metric": "pooled DTI alpha=0.2 beta=0.8 triangular kernel R=300 m (3 px)",
            "n_rff": N_RFF, "n_unlabeled_sample": args.unlabeled, "em_iters": args.em_iters,
            "weight_clip": W_CLIP, "dots_total": args.dots, "min_dist_px": MIN_DIST_PX,
            "catalogue_buffer_px": CAT_BUFFER_PX, "seed": SEED,
            "a_bar_primary": A_BAR_PRIMARY, "a_bar_grid": list(A_BAR_GRID),
            "anchor_justification": ("mean propensity over labelled positives set to the brief's cited "
                                     "detailed-mapping share (~25%, Giddens & Faulds 2025 SGP-TR-229); "
                                     "propensity scale is NOT identified from PU data alone "
                                     "(arXiv:1809.03207 sec. 2/5.1) so the full grid is reported"),
        },
        "per_cell": per_cell,
        "pooled": pooled,
        "pooled_top_propensity_tercile": pooled_tercile,
        "pooled_by_anchor_a_bar": pooled_abar,
        "leakage_canary_auc": dict(sorted(canary.items(), key=lambda kv: -kv[1])),
        "gate": gate,
        "covariate_provenance": cov_stats,
    }
    (repo / "evidence").mkdir(exist_ok=True)
    (repo / "evidence" / "holdout_pu.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(gate, indent=2))
    print(f"[done] {time.time()-t0:.1f}s -> evidence/holdout_pu.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
