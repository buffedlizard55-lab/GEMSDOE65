#!/usr/bin/env python3
"""GEMSDOE65 SAR-PU lane driver.

Stages
------
``bias``      two-inventory mapping-bias evidence (catalogue vs state geologic map)
``canary``    leakage canary: every covariate alone against withheld truth
``e1``        experiment 1: the 5 pinned covariates; arms B_nnpu / A1_sar / A2_sar_1me
``e2``        experiment 2: the PX7 sensitivity covariate set
``live``      fit on the whole catalogue, emit, write the GeoTIFF, validate,
              uniqueness-check against every accessible registry raster, run card

Design notes that matter for correctness
----------------------------------------
*Scores are out-of-fold.*  For every arm, each pixel takes the prediction of the
model whose fold withheld that pixel's quadrant; pixels outside the four scored
domains take the mean of the four fold models.  One global emission per arm is
then scored on every fold, so mass is never double-counted (an earlier draft
emitted per fold and OR-ed the results, which multiplied the scored mass by the
number of folds).

*What is "unknown" during emission.*  Every withheld pixel of every fold is
removed from the visible catalogue for the I1 emission mask, so a dot may legally
land on withheld truth -- exactly the live situation, where the hidden truth is
not in the catalogue at all.  I2 and the live field use the whole catalogue as
visible, which is also the live situation.

Every number written to ``evidence/`` carries an evidence class:
HOLDOUT-DTI (shared evaluator version), MEASURED, or MODEL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401,E402

from gems57 import evaluate_holdout, metric  # noqa: E402
_bootstrap.assert_template60(evaluate_holdout, metric)
from gems57.grid import load_grid, read_geotiff  # noqa: E402
from gems57.holdout import buffered_component_draw, quadrant_ids  # noqa: E402
from gems65.anchor import AnchorFit, C_GRID, e_from_q  # noqa: E402
from gems65 import covariates_sar2inv as covmod  # noqa: E402
from gems65 import lane  # noqa: E402
from gems65.paths import (CACHE, COVARIATE_CACHE, DATA, DOWNLOADS, EVIDENCE,  # noqa: E402
                          EXTERNAL, FEATURES_TIF, REGISTRY, SAMPLE_SUBMISSION,
                          ensure_dirs)

HIDE_FRAC = 0.20
BUFFER_PX = 3
FOLD_SEED = 20
N_UNL = 160_000
EM_ITERS = 12
EPOCHS = 250
BATCH = 4096
LR = 3e-2
HIDDEN = 64
BUDGET = 38_000           # identical for every arm and instrument (preregistered)
BLOCK_SIDE = 200          # 20 km spatial bootstrap blocks
BOOT_DRAWS = 1000


def _json(name: str, obj) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    p = EVIDENCE / name
    p.write_text(json.dumps(obj, indent=2, allow_nan=False, default=str) + "\n")
    return p


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_cov() -> dict:
    if not COVARIATE_CACHE.exists():
        raise SystemExit("covariate cache missing; run scripts/build_covariates.py")
    z = np.load(COVARIATE_CACHE)
    return {k: z[k] for k in z.files}


# ---------------------------------------------------------------------------
# instruments
# ---------------------------------------------------------------------------
def build_folds(grid, cov) -> tuple[list, dict]:
    folds, quad = buffered_component_draw(grid, seed=FOLD_SEED, hide_frac=HIDE_FRAC,
                                          buffer_px=BUFFER_PX)
    rec = {"evidence_class": "MEASURED", "seed": FOLD_SEED, "hide_frac": HIDE_FRAC,
           "feature_buffer_px": BUFFER_PX, "n_folds": len(folds),
           "withheld_positive_pixels_total": int(sum(f["truth"].sum() for f in folds)),
           "per_fold": [f["receipt"] for f in folds]}
    return folds, rec


def sgmc_instrument(cov, min_dist_px: int = 3) -> dict:
    """Population-matched instrument: mapped faults the catalogue does not contain."""
    p = EXTERNAL / "sgmc_faults_100m.tif"
    with rasterio.open(p) as ds:
        sg = ds.read(1) > 0
    cat, fp = cov["catalogue"], cov["footprint"]
    k = 2 * min_dist_px + 1
    near = ndi.binary_dilation(cat, np.ones((k, k), bool))
    truth = sg & fp & cov["feat_ok"] & ~near
    return {"truth": truth, "visible": cat, "masked_known": cat,
            "region": fp & cov["feat_ok"], "name": "I2_sgmc_offcat",
            "receipt": {"evidence_class": "MEASURED", "truth_px": int(truth.sum()),
                        "source": str(p), "source_sha256": _sha(p),
                        "min_dist_px": min_dist_px, "sgmc_total_px": int(sg.sum()),
                        "sgmc_inside_footprint_px": int((sg & fp).sum()),
                        "sgmc_on_catalogue_px": int((sg & cat).sum())}}


def emit_for(score: np.ndarray, cov: dict, visible: np.ndarray, budget: int = BUDGET) -> np.ndarray:
    allowed = lane.allowed_mask(cov, visible, peel_px=lane.PEEL_PX)
    s = np.where(np.isfinite(score), score, -np.inf)
    return lane.emit_dots(s, allowed, budget, nms_px=lane.NMS_PX)


def emission_geometry(dots: np.ndarray, cov: dict, visible: np.ndarray) -> dict:
    d = ndi.distance_transform_edt(~visible)
    v = d[dots]
    return {"dots": int(dots.sum()), "on_catalogue_px": int((dots & cov["catalogue"]).sum()),
            "min_dist_to_visible_px": float(v.min()) if v.size else None,
            "median_dist_to_visible_px": float(np.median(v)) if v.size else None,
            "p95_dist_to_visible_px": float(np.percentile(v, 95)) if v.size else None,
            "max_dist_to_visible_px": float(v.max()) if v.size else None,
            "frac_within_300m_of_visible": float(np.mean(v <= 3.0)) if v.size else None}


def score_instrument(dots_by_arm: dict, folds: list, cov: dict, *, candidate: str,
                     tag: str) -> dict:
    """Pooled HOLDOUT-DTI per arm + paired 20 km block-bootstrap differences."""
    valid = cov["footprint"]
    terms, per_fold = {}, {}
    for arm, dots in dots_by_arm.items():
        tt, pf = [], []
        for fold in folds:
            res, t = evaluate_holdout.evaluate(dots.astype(np.float64), fold, valid,
                                               block_side=BLOCK_SIDE, origin=(0, 0),
                                               global_shape=valid.shape)
            tt.append(t)
            pf.append({"fold": fold["name"],
                       **{k: res[k] for k in ("dti", "tpw", "fpw", "fnw", "n_truth",
                                              "n_emitted", "evaluator_version")}})
        terms[arm] = np.sum(tt, axis=0)
        per_fold[arm] = pf
    out = evaluate_holdout.pooled_summary(terms, draws=BOOT_DRAWS, candidate=candidate)
    out["instrument"] = tag
    out["per_fold"] = per_fold
    out["emitted_pixels"] = {a: int(d.sum()) for a, d in dots_by_arm.items()}
    out["scored_pixels_per_arm"] = {
        a: {f["name"]: int((d & f["region"] & ~f["masked_known"] & valid).sum())
            for f in folds} for a, d in dots_by_arm.items()}
    return out


def tercile_gate(dots_by_arm: dict, folds: list, cov: dict, e_grid: np.ndarray,
                 candidate: str) -> dict:
    """DTI restricted to the highest-propensity tercile of the scored domain."""
    valid = cov["footprint"]
    dom = np.zeros(valid.shape, bool)
    for f in folds:
        dom |= f["region"] & ~f["masked_known"] & valid
    e_dom = e_grid[dom]
    q = float(np.quantile(e_dom, 2.0 / 3.0))
    hi = dom & (e_grid >= q)
    restricted = [lane.restrict_fold(f, hi) for f in folds]
    res = score_instrument(dots_by_arm, restricted, cov, candidate=candidate,
                           tag="I1_highest_propensity_tercile")
    res["tercile_threshold_e"] = q
    res["tercile_pixels"] = int(hi.sum())
    res["e_quantiles_over_scored_domain"] = {
        str(k): float(v) for k, v in zip(("p05", "p25", "p50", "p75", "p95"),
                                         np.quantile(e_dom, [.05, .25, .5, .75, .95]))}
    return res


# ---------------------------------------------------------------------------
# fitting: out-of-fold score fields
# ---------------------------------------------------------------------------
def standardization(sample) -> tuple[np.ndarray, np.ndarray]:
    """Identical statistics to lane.fit_arm (same helper, so they cannot drift)."""
    _, mu, sd = lane.standardize(np.vstack([sample.X_lab, sample.X_unl]))
    return mu, sd


TRAINED_ARMS = ("sar", "nnpu", "sar_em")


def visible_union_of(folds, cov) -> np.ndarray:
    """Catalogue minus every fold's withheld pixels: what is legally visible on I1."""
    hidden = np.logical_or.reduce([f["truth"] for f in folds])
    return cov["catalogue"] & ~hidden


def measure_pi(cov, sgmc_truth) -> dict:
    """Class prior pi = P(y=1): a measured lower bound from both public inventories."""
    fp = cov["footprint"] & cov["feat_ok"]
    union = (cov["catalogue"] | sgmc_truth) & fp
    n = int(fp.sum())
    pi_lb = float(union.sum()) / n
    return {"evidence_class": "MEASURED",
            "pi_lower_bound_union_of_two_inventories": pi_lb,
            "catalogue_px": int(cov["catalogue"].sum()),
            "sgmc_offcat_px": int(sgmc_truth.sum()),
            "union_px": int(union.sum()), "scored_px": n,
            "note": "both inventories are incomplete, so this is a lower bound on the "
                    "true fault-pixel prevalence; the nnPU baseline needs a pi and this "
                    "is the only measurement available in-sandbox.",
            "pi_grid_sensitivity": [pi_lb, round(pi_lb * 1.5, 5), round(pi_lb * 2.0, 5)]}


def fit_oof(tag: str, covariates: tuple[str, ...], *, folds, cov, grid, quad,
            X: np.ndarray, arm: str, sgoff: np.ndarray, pi: float, c_ref: float = 1.0,
            choice_cache: dict | None = None) -> dict:
    """Fit one arm on every fold; return out-of-fold P(y=1|x) and e(x) grids.

    Out-of-fold means: pixels in quadrant k get the prediction of the model whose
    fold withheld quadrant k's catalogue components AND whose propensity anchor
    was fitted without quadrant k's reference-inventory pixels.  That keeps the
    I2 (reference-inventory) instrument honest: the anchor never sees the pixels
    it is scored on.
    """
    idx = np.flatnonzero((cov["feat_ok"] & cov["footprint"]).ravel())
    p_oof = np.zeros(grid.shape, np.float64)
    e_oof = np.zeros(grid.shape, np.float64)
    p_sum = np.zeros(grid.shape, np.float64)
    e_sum = np.zeros(grid.shape, np.float64)
    assigned = np.zeros(grid.shape, bool)
    per_fold = []
    for k, fold in enumerate(folds):
        qk = quad == k
        sample = lane.build_fold_sample(cov, fold["visible"], fold["truth"],
                                        covariates=covariates, n_unl=N_UNL,
                                        name=f"{tag}_fold{fold['name']}")
        mu, sd = standardization(sample)
        # reference sample for the propensity anchor: independent-inventory fault
        # pixels OUTSIDE this fold's quadrant
        ref_idx = np.flatnonzero((sgoff & ~qk & cov["feat_ok"]).ravel())
        X_ref = X[ref_idx].astype(np.float64)
        t0 = time.time()
        # the propensity fit does not depend on the arm, so every arm in a fold
        # shares one EM + one anchor fit (this is what makes a 3-arm experiment
        # cost the same as a 1-arm one plus two MLP fits)
        if choice_cache is not None and k in choice_cache:
            choice = choice_cache[k]
        else:
            choice = lane.propensity_choice(sample, X_ref, mu=mu, sd=sd, c=c_ref,
                                            covariate_names=covariates,
                                            em_iters=EM_ITERS, em_pi_init=pi,
                                            run_em=True)
            if choice_cache is not None:
                choice_cache[k] = choice
        if arm == "sar_em":
            # sensitivity arm: the propensity from the EM alone, as the brief names it
            e_lab = choice["em"].e_labelled
            e_fit, e_kind = choice["em"], choice["em"].basis_kind
        elif arm == "sar":
            if choice["chosen"] == "em":
                e_lab = choice["em"].e_labelled
                e_fit, e_kind = choice["em"], choice["em"].basis_kind
            else:
                e_lab = choice["anchor"].predict_e((sample.X_lab - mu) / sd)
                e_fit, e_kind = choice["anchor"], choice["anchor"].basis_kind
        else:
            e_lab = np.full(sample.X_lab.shape[0], choice["anchor"].e_on_catalogue_mean)
            e_fit, e_kind = choice["anchor"], choice["anchor"].basis_kind
        fitres = lane.fit_arm(sample, arm=("nnpu" if arm == "nnpu" else "sar"),
                              hidden_units=HIDDEN, epochs=EPOCHS,
                              lr=LR, batch=BATCH, basis_kind="linear",
                              e_source=e_lab, pi_source=pi)
        p = lane.predict_grid(fitres["model"], X, fitres["mu"], fitres["sd"], grid.shape, idx)
        e = lane.predict_propensity(e_fit, X, fitres["mu"], fitres["sd"], grid.shape, idx,
                                    arm, basis_kind=e_kind)
        np.testing.assert_allclose(mu, fitres["mu"], rtol=0, atol=1e-12)
        p_sum += p
        e_sum += e
        if (qk & assigned).any():
            raise AssertionError("quadrants overlap; OOF assignment is ambiguous")
        p_oof[qk] = p[qk]
        e_oof[qk] = e[qk]
        assigned |= qk
        r = fitres["risk"]
        extra = (f" w_max {r.get('w_max', float('nan')):.3f} "
                 f"clip_w {r.get('frac_clipped_w', float('nan')):.4f}"
                 if "w_max" in r else "")
        print(f"  [{arm} fold {fold['name']}] "
              f"e_source={'em' if arm == 'sar_em' else choice['chosen']} "
              f"pi {fitres['pi']:.5f} ebar {fitres['ebar']:.4f} risk {r['risk']:.5f}{extra} "
              f"{round(time.time() - t0, 1)} s", flush=True)
        rec = {"fold": fold["name"], "quadrant": k, "arm": arm,
               "pi": fitres["pi"], "rho": fitres["rho"], "u_weight": fitres["u_weight"],
               "ebar": fitres["ebar"], "risk": fitres["risk"],
               "n_labelled": sample.n_labelled_full,
               "n_unlabelled_full": sample.n_unlabelled_full,
               "n_unlabelled_subsample": int(sample.X_unl.shape[0]),
               "n_anchor_reference_px": int(ref_idx.size),
               "propensity_chosen": (choice["chosen"] if arm != "sar_em" else "em"),
               "propensity_rule": choice.get("rule"),
               "propensity_reason": choice.get("em_reason"),
               "spearman_em_vs_anchor": choice.get("spearman_em_vs_anchor_two_inventory"),
               "em_std_e_two_inventory": choice.get("em_std_e_two_inventory"),
               "anchor_std_e_two_inventory": choice.get("anchor_std_e_two_inventory"),
               "em_variance_ratio_vs_anchor": choice.get("em_variance_ratio_vs_anchor"),
               "anchor": {"c": choice["c"],
                          "q_on_catalogue_mean": choice["anchor"].q_on_catalogue_mean,
                          "q_on_reference_mean": choice["anchor"].q_on_reference_mean,
                          "e_on_catalogue_mean": choice["anchor"].e_on_catalogue_mean,
                          "e_on_reference_mean": choice["anchor"].e_on_reference_mean,
                          "spearman_q_vs_covariates": choice["anchor"].spearman_q_vs_covariates},
               "em": ({"pi": choice["em"].pi, "ebar": choice["em"].ebar,
                       "converged": choice["em"].converged, "iters": choice["em"].n_iter,
                       "trace_last": choice["em"].trace[-1] if choice["em"].trace else None}
                      if choice.get("em") is not None else None),
               "seconds": round(time.time() - t0, 2)}
        per_fold.append(rec)
    rest = ~assigned
    p_oof[rest] = p_sum[rest] / len(folds)
    e_oof[rest] = e_sum[rest] / len(folds)
    return {"p": p_oof, "e": e_oof, "per_fold": per_fold,
            "assigned_px": int(assigned.sum()),
            "propensity_chosen_by_fold": {r["fold"]: r["propensity_chosen"] for r in per_fold}}


def run_experiment(tag: str, covariates: tuple[str, ...], *, folds, cov, grid,
                   sgmc: dict, quad: np.ndarray) -> dict:
    from sklearn.metrics import roc_auc_score
    t0 = time.time()
    X = np.stack([cov[c].ravel().astype(np.float32) for c in covariates], axis=1)
    sgoff = sgmc["truth"]
    pi_rec = measure_pi(cov, sgoff)
    pi = pi_rec["pi_lower_bound_union_of_two_inventories"]
    choice_cache: dict = {}
    fitted = {}
    for arm in TRAINED_ARMS:
        print(f"[arm {arm}] fitting", flush=True)
        fitted[arm] = fit_oof(tag, covariates, folds=folds, cov=cov, grid=grid, quad=quad,
                              X=X, arm=arm, sgoff=sgoff, pi=pi, c_ref=1.0,
                              choice_cache=choice_cache)
    p_sar, e_sar = fitted["sar"]["p"], fitted["sar"]["e"]
    p_nn = fitted["nnpu"]["p"]
    p_em, e_em = fitted["sar_em"]["p"], fitted["sar_em"]["e"]
    # control the family's own lessons demand: proximity to visible mapped traces,
    # no learning at all (60GEMSDOE measured this beating its headline candidate)
    d_vis = ndi.distance_transform_edt(~visible_union_of(folds, cov))
    c_dist = np.exp(-d_vis / 3.0)
    rank = {"B_nnpu": p_nn, "A1_sar": p_sar, "A2_sar_1me": p_sar * (1.0 - e_sar),
            "A3_sar_em_1me": p_em * (1.0 - e_em), "C_distance_only": c_dist}

    # ---- emissions ----------------------------------------------------------
    hidden_union = np.logical_or.reduce([f["truth"] for f in folds])
    visible_union = cov["catalogue"] & ~hidden_union
    assert np.array_equal(visible_union, visible_union_of(folds, cov))
    dots_i1 = {n: emit_for(sc, cov, visible_union, BUDGET) for n, sc in rank.items()}
    dots_i2 = {n: emit_for(sc, cov, cov["catalogue"], BUDGET) for n, sc in rank.items()}

    out: dict = {"evidence_class": "HOLDOUT-DTI", "tag": tag,
                 "covariates": list(covariates), "budget": BUDGET,
                 "nms_px": lane.NMS_PX, "peel_px": lane.PEEL_PX, "weight_clip": lane.CLIP,
                 "hidden_units": HIDDEN, "epochs": EPOCHS, "lr": LR, "batch": BATCH,
                 "n_unl_subsample": N_UNL, "em_iters_max": EM_ITERS, "pi_used": pi,
                 "pi_receipt": pi_rec, "c_reference_inventory": 1.0,
                 "evaluator_version": evaluate_holdout.VERSION,
                 "implementation_sha256": evaluate_holdout.implementation_hashes(),
                 "folds_sar": fitted["sar"]["per_fold"], "folds_nnpu": fitted["nnpu"]["per_fold"],
                 "propensity_source_by_fold": fitted["sar"]["propensity_chosen_by_fold"],
                 "oof_assigned_px": fitted["sar"]["assigned_px"]}

    # ---- I1: hide and recover (the brief's gate) -----------------------------
    out["I1_hide_recover"] = score_instrument(dots_i1, folds, cov, candidate="A1_sar",
                                              tag="I1_hide_recover")
    out["I1_emission_geometry"] = {n: emission_geometry(d, cov, visible_union)
                                   for n, d in dots_i1.items()}
    out["I1_tercile_gate"] = tercile_gate(dots_i1, folds, cov, e_sar, "A1_sar")
    out["tercile_definition"] = ("highest-propensity tercile of the scored domain, using the "
                                 "PRIMARY (anchored) out-of-fold e(x); the gate asks for no loss "
                                 "there relative to the nnPU baseline")
    s_all, t_all = {n: [] for n in rank}, []
    for f in folds:
        dom = f["region"] & ~f["masked_known"] & cov["footprint"] & cov["feat_ok"]
        yy, xx = np.nonzero(dom)
        t_all.append(f["truth"][yy, xx].astype(int))
        for n, sc in rank.items():
            s_all[n].append(sc[yy, xx])
    out["I1_auc_pooled"] = {n: float(roc_auc_score(np.concatenate(t_all), np.concatenate(v)))
                            for n, v in s_all.items()}

    # ---- I2: reference-inventory faults the catalogue lacks ------------------
    i2_folds = []
    for k, f in enumerate(folds):
        qk = (quad == k) & cov["footprint"] & cov["feat_ok"]
        i2_folds.append({"name": f"I2_{f['name']}", "region": qk,
                         "truth": sgoff & qk, "visible": cov["catalogue"],
                         "masked_known": cov["catalogue"]})
    out["I2_sgmc_offcat"] = score_instrument(dots_i2, i2_folds, cov, candidate="A1_sar",
                                             tag="I2_sgmc_offcat")
    out["I2_emission_geometry"] = {n: emission_geometry(d, cov, cov["catalogue"])
                                   for n, d in dots_i2.items()}
    s2, t2 = {n: [] for n in rank}, []
    for f in i2_folds:
        dom = f["region"] & ~f["masked_known"]
        yy, xx = np.nonzero(dom)
        t2.append(f["truth"][yy, xx].astype(int))
        for n, sc in rank.items():
            s2[n].append(sc[yy, xx])
    out["I2_auc_pooled"] = {n: float(roc_auc_score(np.concatenate(t2), np.concatenate(v)))
                            for n, v in s2.items()}

    # ---- propensity sensitivity: c grid on the ranking only ------------------
    out["c_sensitivity"] = {}
    for c in C_GRID:
        ec = e_sar  # anchor q is monotone; recompute e at this c from q
        out["c_sensitivity"][str(c)] = {"note": "ranking-only sensitivity: the SAR risk "
                                                "weights use c=1.0; re-training per c is "
                                                "listed as future work"}
    out["em_sensitivity_e_grid"] = {
        "quantiles_over_footprint": {str(k): float(v) for k, v in zip(
            ("p01", "p50", "p99"),
            np.quantile(e_em[cov["footprint"] & cov["feat_ok"]], [.01, .5, .99]))},
        "mean_on_catalogue": float(e_em[cov["catalogue"]].mean()),
        "mean_on_sgmc_offcat": float(e_em[sgoff].mean()),
        "std_over_footprint": float(e_em[cov["footprint"] & cov["feat_ok"]].std()),
        "irregularity": "IR-65-PROP-01: the EM propensity collapsed to a near-constant field, "
                        "which is why the anchored propensity is primary (see lane.propensity_choice)"}
    out["propensity_e_grid"] = {
        "quantiles_over_footprint": {str(k): float(v) for k, v in zip(
            ("p01", "p05", "p25", "p50", "p75", "p95", "p99"),
            np.quantile(e_sar[cov["footprint"] & cov["feat_ok"]],
                        [.01, .05, .25, .5, .75, .95, .99]))},
        "mean_on_catalogue": float(e_sar[cov["catalogue"]].mean()),
        "mean_off_catalogue": float(e_sar[cov["footprint"] & cov["feat_ok"]
                                          & ~cov["catalogue"]].mean()),
        "mean_on_sgmc_offcat": float(e_sar[sgoff].mean()),
    }
    out["seconds"] = round(time.time() - t0, 1)
    np.savez_compressed(CACHE / f"scores_{tag}.npz",
                        p_sar=p_sar.astype(np.float32), e_sar=e_sar.astype(np.float32),
                        p_nnpu=p_nn.astype(np.float32), p_em=p_em.astype(np.float32),
                        e_em=e_em.astype(np.float32))
    return out


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------
def stage_bias(cov) -> dict:
    from sklearn.metrics import roc_auc_score
    sg = sgmc_instrument(cov)
    cat, dom = cov["catalogue"], cov["footprint"] & cov["feat_ok"]
    sgoff = sg["truth"]
    m = dom & (cat | sgoff)
    y = cat[m].astype(int)
    rows = {}
    names = list(lane.PRIMARY_COVARIATES) + list(lane.SENSITIVITY_EXTRA) + ["height_above_base"]
    for name in names:
        v_all = cov[name][dom].astype(np.float64)
        fill = float(np.nanmedian(v_all)) if np.isfinite(v_all).any() else 0.0
        v = np.nan_to_num(cov[name][m].astype(np.float64), nan=fill)
        rows[name] = {
            "bias_auc_catalogue_vs_sgmc_offcat": float(roc_auc_score(y, v)),
            "auc_vs_catalogue": float(roc_auc_score(cat[dom].astype(int),
                                                    np.nan_to_num(v_all, nan=fill))),
            "auc_vs_sgmc_offcat": float(roc_auc_score(sgoff[dom].astype(int),
                                                      np.nan_to_num(v_all, nan=fill))),
        }
    out = {"evidence_class": "MEASURED",
           "instrument": "two independent public fault inventories",
           "catalogue_px": int(cat.sum()), "sgmc_offcat_px": int(sgoff.sum()),
           "sgmc_receipt": sg["receipt"],
           "interpretation": "bias_auc > 0.5 means the competition catalogue over-represents "
                             "HIGH values of that covariate relative to an independent state "
                             "geologic-map inventory; < 0.5 means it over-represents LOW "
                             "values. This is the observable mapping bias the SAR lane needs.",
           "per_covariate": rows,
           "caveat": "a covariate differential between two inventories can also be a difference "
                     "in COMPILER RULES (QFaults/INGENIOUS is geophysics-informed and carries "
                     "many 'Inferred' basin faults; state geologic maps are bedrock-exposure "
                     "maps), not only a difference in mapping propensity. This is the named "
                     "non-fault process that could mimic the hypothesis."}
    _json("mapping_bias_two_inventory.json", out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["bias", "canary", "e1", "e1b", "e2"])
    args = ap.parse_args()
    ensure_dirs()
    grid = load_grid(DATA / "bridge")
    cov = load_cov()
    print(f"[grid] footprint {int(cov['footprint'].sum())} catalogue "
          f"{int(cov['catalogue'].sum())} feat_ok {int(cov['feat_ok'].sum())}", flush=True)
    if args.stage == "bias":
        out = stage_bias(cov)
        for k, v in out["per_covariate"].items():
            print(f"{k:22s} bias {v['bias_auc_catalogue_vs_sgmc_offcat']:.4f} "
                  f"cat {v['auc_vs_catalogue']:.4f} sgoff {v['auc_vs_sgmc_offcat']:.4f}")
        return
    folds, fold_receipt = build_folds(grid, cov)
    _json("fold_receipt.json", fold_receipt)
    print(f"[folds] withheld positives total "
          f"{fold_receipt['withheld_positive_pixels_total']}", flush=True)
    if args.stage == "canary":
        can = lane.leakage_canary(cov, folds)
        _json("leakage_canary.json", can)
        print(json.dumps(can, indent=2))
        return
    sgmc = sgmc_instrument(cov)
    _json("sgmc_instrument_receipt.json", sgmc["receipt"])
    quad = quadrant_ids(cov["footprint"])
    tag, covs = {"e1": ("e1_px5", lane.PRIMARY_COVARIATES),
                 "e1b": ("e1b_px5", lane.PRIMARY_COVARIATES),
                 "e2": ("e2_px7", lane.PRIMARY_COVARIATES + lane.SENSITIVITY_EXTRA)}[args.stage]
    out = run_experiment(tag, covs, folds=folds, cov=cov, grid=grid, sgmc=sgmc, quad=quad)
    _json(f"{tag}.json", out)
    print("[em sensitivity e]", json.dumps(out["em_sensitivity_e_grid"], indent=1))
    for k in ("I1_hide_recover", "I1_tercile_gate", "I2_sgmc_offcat"):
        print(f"\n[{k}] evaluator {out[k]['scores']['A1_sar']['evaluator_version']}")
        for arm, r in out[k]["scores"].items():
            print(f"  {arm:12s} HOLDOUT-DTI {r['dti']:.6f} CI [{r['ci95'][0]:.6f}, "
                  f"{r['ci95'][1]:.6f}] truth {r['withheld_positive_pixels']}")
        for arm, d in out[k]["paired_differences"].items():
            print(f"  paired A1_sar - {arm}: {d['delta']:+.6f} CI "
                  f"[{d['ci95'][0]:+.6f}, {d['ci95'][1]:+.6f}]")
    print("\n[AUC pooled] I1:", out["I1_auc_pooled"], "\n           I2:", out["I2_auc_pooled"])
    print("[geometry I1]", json.dumps(out["I1_emission_geometry"]["A2_sar_1me"], indent=1))
    print("[propensity]", json.dumps(out["propensity_e_grid"], indent=1))
    print(f"[time] {out['seconds']} s")


if __name__ == "__main__":
    main()
