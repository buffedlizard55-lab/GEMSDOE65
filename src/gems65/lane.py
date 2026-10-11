"""Lane orchestration: folds, propensity-aware PU training, emission, scoring.

Instruments
-----------
``I1_hide_recover`` (the brief's instrument)
    ``gems57.holdout.buffered_component_draw``: whole 8-connected catalogue
    components are withheld, a ``buffer_px`` collar is removed from the *feature*
    context, every remaining catalogue pixel is masked pixel-exactly out of
    scoring, and the score is pooled DTI (alpha=0.2, beta=0.8, 300 m triangular
    kernel) via ``gems57.evaluate_holdout`` (evaluator version
    ``gems57-pooled-hide-v2``).  Nothing in this module re-implements the metric.

``I2_sgmc_offcat`` (population-matched control instrument)
    Truth = pixels of the mirrored state-geologic-map fault raster that lie more
    than 300 m (3 px) from the competition catalogue, i.e. real mapped faults
    that the catalogue does *not* contain.  This is the population the live board
    scores; I1 rewards proximity to visible traces, which the live board does
    not (the family's own ladder measured that removing dots 1-2 px from the
    catalogue *raised* the live score twice).  Both are reported; neither is
    presented as a leaderboard projection.

Arms (identical folds, covariates, architecture, seed, budget, NMS and peel)
--------------------------------------------------------------------------
``B_nnpu``      SCAR baseline: nnPU risk (Kiryo 2017), rank by ``P(y=1|x)``.
``A1_sar``      propensity-aware SAR risk (arXiv:1809.03207), rank by ``P(y=1|x)``.
``A2_sar_1me``  same risk, rank by ``P(y=1|x) * (1 - e(x))`` -- the probability
                that ``x`` is an *unmapped* fault, which is what the competition
                truth actually is.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

from gems57 import evaluate_holdout, metric
from gems57.grid import Grid, load_grid
from gems57.holdout import buffered_component_draw
from . import propensity_sar2inv as prop
from .anchor import AnchorFit, fit_anchor
from .risks import MLP, W_CLIP, sar_risk, nnpu_risk, sigmoid, train

PRIMARY_COVARIATES = ("relief_local", "slope", "grav_basin_fill", "lidar_cover",
                      "dist_range_front")
SENSITIVITY_EXTRA = ("depth_to_base_surf", "iso_grav_anom_slope")

NMS_PX = 3.0            # min separation between emitted dots (300 m), champion geometry
PEEL_PX = 3             # no mass within 300 m of a *visible* catalogue pixel
LIVE_BUDGET = 38_000    # dots for the live field (see docs/research/mass-budget.md)
EM_SEED = 65
CLIP = W_CLIP


# ---------------------------------------------------------------------------
# sampling helpers
# ---------------------------------------------------------------------------
def standardize(X: np.ndarray, ref: np.ndarray | None = None):
    """Return ``(X_std, mean, std)``; statistics come from ``ref`` if given."""
    R = X if ref is None else ref
    mu = R.mean(axis=0)
    sd = R.std(axis=0)
    sd[sd < 1e-9] = 1.0
    return (X - mu) / sd, mu, sd


def draw_unlabelled(rng, n_unl: int, k: int) -> np.ndarray:
    if k >= n_unl:
        return np.arange(n_unl)
    return np.sort(rng.choice(n_unl, size=k, replace=False))


@dataclass
class FoldSample:
    """Training sample for one fold: labelled pixels + unlabelled pixels."""
    name: str
    X_lab: np.ndarray
    X_unl: np.ndarray
    idx_lab: np.ndarray
    idx_unl: np.ndarray
    n_labelled_full: int
    n_unlabelled_full: int


def build_fold_sample(cov: dict, visible: np.ndarray, hidden: np.ndarray, *,
                      covariates=PRIMARY_COVARIATES, n_unl: int = 200_000,
                      seed: int = EM_SEED, name: str = "fold") -> FoldSample:
    """Positives = visible catalogue; unlabelled = footprint minus visible catalogue.

    The withheld (hidden) pixels stay inside the unlabelled pool: that is the PU
    setting, and no label of theirs is used.
    """
    ok = cov["feat_ok"]
    fp = cov["footprint"]
    lab_mask = ok & fp & visible
    unl_mask = ok & fp & ~visible
    idx_lab = np.flatnonzero(lab_mask.ravel())
    idx_unl = np.flatnonzero(unl_mask.ravel())
    X = np.stack([cov[c].ravel().astype(np.float64) for c in covariates], axis=1)
    rng = np.random.default_rng(seed)
    sub = draw_unlabelled(rng, idx_unl.size, n_unl)
    idx_unl_sub = idx_unl[sub]
    return FoldSample(name=name, X_lab=X[idx_lab], X_unl=X[idx_unl_sub],
                      idx_lab=idx_lab, idx_unl=idx_unl_sub,
                      n_labelled_full=int(idx_lab.size), n_unlabelled_full=int(idx_unl.size))


# ---------------------------------------------------------------------------
# prediction over the whole grid
# ---------------------------------------------------------------------------
def predict_grid(model: MLP, X: np.ndarray, mu: np.ndarray, sd: np.ndarray,
                 shape: tuple[int, int], idx: np.ndarray, chunk: int = 1_000_000) -> np.ndarray:
    """Score every indexed pixel; unindexed pixels get 0."""
    out = np.zeros(X.shape[0], np.float64)
    for a in range(0, idx.size, chunk):
        b = idx[a:a + chunk]
        out[b] = model.prob((X[b] - mu) / sd)
    return out.reshape(shape)


def predict_propensity(fit, X: np.ndarray, mu: np.ndarray, sd: np.ndarray, shape, idx,
                       kind: str, chunk=1_000_000, basis_kind: str = "linear") -> np.ndarray:
    """e(x) over the grid from an EM ``PropensityFit`` or an ``AnchorFit``."""
    out = np.zeros(X.shape[0], np.float64)
    if isinstance(fit, AnchorFit):
        for a in range(0, idx.size, chunk):
            b = idx[a:a + chunk]
            out[b] = fit.predict_e((X[b] - mu) / sd)
        return out.reshape(shape)
    if fit is None or fit.model_e is None:
        return np.full(shape, float(getattr(fit, "ebar", 0.0)))
    for a in range(0, idx.size, chunk):
        b = idx[a:a + chunk]
        Xb = prop.basis((X[b] - mu) / sd, basis_kind)
        out[b] = fit.predict_e(Xb)
    return out.reshape(shape)


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------
def _disk(r: float) -> np.ndarray:
    n = int(np.ceil(r))
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return (x * x + y * y) <= r * r


def emit_dots(score: np.ndarray, allowed: np.ndarray, budget: int, *,
              nms_px: float = NMS_PX, seed: int = EM_SEED,
              tie_jitter: float = 1e-12) -> np.ndarray:
    """Top-``budget`` strict local maxima of ``score`` inside ``allowed``.

    Strict local maximality inside a ``nms_px`` disk gives a minimum separation
    of ~``nms_px`` between dots, which is the geometry of the family's
    best-scoring live rasters (min distance 3.00 px).  Ties are broken by a
    deterministic seeded jitter of size ``tie_jitter`` so that flat plateaus
    cannot produce two dots inside the same NMS disk.
    """
    s = np.asarray(score, np.float64).copy()
    s[~allowed] = -np.inf
    if not np.isfinite(s[allowed]).any():
        raise ValueError("no finite scores inside the allowed mask")
    rng = np.random.default_rng(seed)
    jitter = np.zeros_like(s)
    ys, xs = np.nonzero(allowed)
    jitter[ys, xs] = rng.random(ys.size) * tie_jitter
    s = s + jitter
    s[~allowed] = -np.inf
    fill = -np.inf
    work = np.where(np.isfinite(s), s, fill)
    mx = ndi.maximum_filter(work, footprint=_disk(nms_px), mode="constant", cval=fill)
    peaks = allowed & np.isfinite(work) & (work >= mx)
    n_peaks = int(peaks.sum())
    if n_peaks <= budget:
        return peaks
    vals = work[peaks]
    keep = np.argsort(-vals, kind="stable")[:budget]
    out = np.zeros(work.shape, bool)
    py, px = np.nonzero(peaks)
    out[py[keep], px[keep]] = True
    return out


def allowed_mask(cov: dict, visible: np.ndarray, *, peel_px: int = PEEL_PX) -> np.ndarray:
    """Pixels that may carry mass: in footprint, covariates valid, off the visible
    catalogue and at least ``peel_px`` away from it."""
    base = cov["feat_ok"] & cov["footprint"] & ~visible
    if peel_px > 0 and visible.any():
        d = ndi.distance_transform_edt(~visible)
        # ``>= peel_px`` gives a minimum catalogue distance of exactly peel_px
        # pixels (300 m at peel_px=3), which is the geometry of the family's
        # best-scoring live rasters (measured min distance 3.00 px).
        base &= d >= peel_px
    return base


# ---------------------------------------------------------------------------
# arm fitting
# ---------------------------------------------------------------------------
def propensity_choice(sample: FoldSample, X_ref: np.ndarray, *, mu: np.ndarray,
                      sd: np.ndarray, c: float = 1.0, basis_kind: str = "linear",
                      covariate_names: tuple[str, ...] = (),
                      em_iters: int = 8, em_pi_init: float = 0.023,
                      em_init: str = "scar_identity", run_em: bool = True,
                      rule: str = "anchor_primary") -> dict:
    """Estimate e(x) two ways and pick by a pre-registered, data-driven rule.

    1. ``anchor``: the two-inventory propensity of :mod:`gems65.anchor` --
       catalogue pixels (this fold's *visible* ones) vs reference-inventory fault
       pixels that the catalogue does not contain.  Direction identified by data,
       scale set by one documented parameter ``c``.
    2. ``em``: Bekker & Davis (PMLR v94, 2018) EM on (labelled, unlabelled)
       alone -- the estimator the brief names.

    Selection rule (written before any holdout number was computed): use the EM
    propensity only if its *ordering* agrees with the anchor on the pooled
    two-inventory sample (Spearman rho > 0).  Otherwise the EM is recorded as
    non-identified for this fold -- the mirror-factorisation failure documented
    in :mod:`gems65.anchor` -- and the anchored propensity is used instead.
    Both are always returned so the receipt shows what was rejected and why.
    """
    X_lab = (sample.X_lab - mu) / sd
    X_unl = (sample.X_unl - mu) / sd
    X_ref = (np.asarray(X_ref, float) - mu) / sd
    anchor = fit_anchor(X_lab, X_ref, c=c, basis_kind=basis_kind,
                        covariate_names=covariate_names)
    X_two = np.vstack([X_lab, X_ref])
    e_two_anchor = anchor.predict_e(X_two)
    out = {"anchor": anchor, "c": c, "chosen": "anchor", "rule": rule,
           "spearman_em_vs_anchor_two_inventory": None,
           "em": None, "em_reason": None, "em_std_e_two_inventory": None,
           "anchor_std_e_two_inventory": float(np.std(e_two_anchor)),
           "em_variance_ratio_vs_anchor": None}
    if run_em:
        em = prop.em_propensity(X_lab, X_unl, basis_kind=basis_kind, n_iter=em_iters,
                                tol=1e-4, pi_init=em_pi_init, init=em_init,
                                u_weight=sample.n_unlabelled_full / float(X_unl.shape[0]),
                                n_unl_population=float(sample.n_unlabelled_full))
        q_two = anchor.model.predict_proba(prop.basis(X_two, basis_kind))[:, 1]
        e_two_em = em.predict_e(prop.basis(X_two, basis_kind))
        from scipy.stats import spearmanr
        rho = float(spearmanr(e_two_em, q_two).statistic)
        out["em"] = em
        out["spearman_em_vs_anchor_two_inventory"] = rho
        e_two_em_all = e_two_em
        sd_em = float(np.std(e_two_em))
        sd_an = float(np.std(e_two_anchor))
        out["em_std_e_two_inventory"] = sd_em
        out["anchor_std_e_two_inventory"] = sd_an
        out["em_variance_ratio_vs_anchor"] = (sd_em / sd_an) if sd_an > 0 else None
        if rule == "anchor_primary":
            # The brief: "anchor its scale with exhaustively mapped quadrangles if a
            # public index exists ... the propensity is not uniquely identifiable from
            # PU data alone, so otherwise report it as a sensitivity analysis."  A
            # public index DOES exist here (the state geologic map fault inventory),
            # so the anchored propensity is primary and the EM is the sensitivity
            # analysis.  IR-65-PROP-01: the pre-registered "use the EM when its
            # Spearman against the anchor is positive" rule accepted a degenerate
            # near-constant EM propensity (std 0.008 on a 0-1 scale, e in
            # [0.281, 0.296] over the whole footprint), which silently switched the
            # mechanism off.  A sign test cannot detect a variance collapse.
            out["chosen"] = "anchor"
            out["em_reason"] = (
                "anchor primary per the brief (a public reference index exists); the EM is "
                f"reported as a sensitivity arm. EM diagnostics: Spearman vs anchor {rho:+.3f}, "
                f"std(e) {sd_em:.5f} vs anchor std(e) {sd_an:.5f}")
        elif rho > 0:
            out["chosen"] = "em"
            out["em_reason"] = ("EM ordering agrees with the two-inventory anchor "
                                f"(Spearman {rho:+.3f} > 0); EM used as the brief specifies")
        else:
            out["chosen"] = "anchor"
            out["em_reason"] = ("EM converged to a factorisation whose ordering is "
                                f"INVERTED against the two-inventory anchor (Spearman "
                                f"{rho:+.3f}); recorded as non-identified for this fold "
                                "and the anchored propensity used instead")
    return out


def fit_arm(sample: FoldSample, *, arm: str, hidden_units: int = 64, epochs: int = 200,
            lr: float = 3e-2, batch: int = 4096, pi_override: float | None = None,
            basis_kind: str = "linear", scar: bool = False, seed: int = EM_SEED,
            e_source: np.ndarray | None = None, pi_source: float | None = None) -> dict:
    """Fit the propensity EM and one risk arm; return models + receipts.

    ``rho = P(s=1)`` is computed from the *full* population counts of the fold
    (visible catalogue pixels vs. everything else in the footprint), never from
    the unlabelled subsample used for fitting.
    """
    if arm not in ("sar", "nnpu", "scar"):
        raise ValueError("arm must be 'sar', 'nnpu' or 'scar'")
    Xs, mu, sd = standardize(np.vstack([sample.X_lab, sample.X_unl]))
    X_lab = Xs[:sample.X_lab.shape[0]]
    X_unl = Xs[sample.X_lab.shape[0]:]
    rho = sample.n_labelled_full / float(sample.n_labelled_full + sample.n_unlabelled_full)
    use_scar = scar or arm == "scar"
    t0 = time.time()
    u_weight = sample.n_unlabelled_full / float(X_unl.shape[0])
    if e_source is not None:
        # propensity supplied by the caller (anchored / pre-selected); no EM here
        fit = None
        e_lab_arr = np.asarray(e_source, float)
        pi = float(pi_source) if pi_source else 0.023
    else:
        fit = prop.em_propensity(X_lab, X_unl, basis_kind=basis_kind, scar=use_scar,
                                 pi_init=pi_override, u_weight=u_weight,
                                 n_unl_population=float(sample.n_unlabelled_full))
        e_lab_arr = fit.e_labelled
        pi = float(pi_override) if pi_override else float(fit.pi)
    model = MLP(n_in=X_lab.shape[1], n_hidden=hidden_units, seed=seed)
    ebar = float(np.mean(e_lab_arr)) if fit is None else fit.ebar
    e_lab = e_lab_arr if not use_scar else np.full(X_lab.shape[0], ebar)
    if arm == "nnpu" or use_scar:
        info = train(model, X_lab, X_unl, arm="nnpu", rho=rho, pi=pi, epochs=epochs,
                     lr=lr, batch=batch, seed=seed)
        risk = nnpu_risk(model.logits(X_lab), model.logits(X_unl), pi)
    else:
        info = train(model, X_lab, X_unl, arm="sar", rho=rho, pi=pi, e_lab=e_lab,
                     epochs=epochs, lr=lr, batch=batch, clip=CLIP, seed=seed)
        risk = sar_risk(model.logits(X_lab), model.logits(X_unl), e_lab, rho, CLIP)
    return dict(arm=arm, model=model, propensity=fit, mu=mu, sd=sd, pi=pi, rho=rho,
                u_weight=u_weight, ebar=ebar, train_info=info, risk=risk,
                e_labelled=e_lab, seconds=round(time.time() - t0, 2),
                basis_kind=(fit.basis_kind if fit is not None else basis_kind),
                em_converged=(fit.converged if fit is not None else None),
                em_iters=(fit.n_iter if fit is not None else 0),
                em_trace=(fit.trace if fit is not None else []))


# ---------------------------------------------------------------------------
# leakage canary
# ---------------------------------------------------------------------------
def leakage_canary(cov: dict, folds: list, *, covariates=PRIMARY_COVARIATES,
                   auc_limit: float = 0.90) -> dict:
    """AUC of each covariate *alone* against withheld truth, pooled over folds.

    The brief: "AUC above 0.90 means leakage until proven otherwise."  The
    scored domain per fold is ``region & ~masked_known`` (exactly what the
    shared evaluator scores), so the canary measures the same population the
    DTI is computed on.
    """
    rows = {}
    ok = cov["feat_ok"] & cov["footprint"]
    for name in list(covariates) + ["dist_to_visible_catalogue"]:
        scores, labels = [], []
        for fold in folds:
            dom = fold["region"] & ~fold["masked_known"] & ok
            y, x = np.nonzero(dom)
            if y.size == 0:
                continue
            t = fold["truth"][y, x]
            if name == "dist_to_visible_catalogue":
                d = ndi.distance_transform_edt(~fold["visible"])
                v = -d[y, x]      # proximity = higher score
            else:
                v = cov[name][y, x].astype(np.float64)
            scores.append(v)
            labels.append(t.astype(np.int8))
        if not labels or sum(int(l.sum()) for l in labels) == 0:
            rows[name] = {"auc": None, "n": 0, "flag": "no positives in domain"}
            continue
        s = np.concatenate(scores)
        l = np.concatenate(labels)
        auc = float(roc_auc_score(l, s))
        rows[name] = {"auc": auc, "n": int(l.size), "n_truth": int(l.sum()),
                      "auc_above_limit": bool(auc > auc_limit),
                      "flag": "LEAKAGE-UNTIL-PROVEN-OTHERWISE" if auc > auc_limit else "ok"}
    return {"auc_limit": auc_limit, "per_feature": rows,
            "worst_auc": max((r["auc"] for r in rows.values() if r["auc"] is not None),
                             default=None),
            "any_flagged": any(r.get("auc_above_limit", False) for r in rows.values())}


# ---------------------------------------------------------------------------
# scoring helpers
# ---------------------------------------------------------------------------
def score_folds(dots: np.ndarray, folds: list, valid: np.ndarray) -> tuple[dict, np.ndarray]:
    """Sum the shared evaluator's per-block terms over folds (aligned blocks)."""
    terms = None
    per_fold = []
    for k, fold in enumerate(folds):
        res, t = evaluate_holdout.evaluate(dots.astype(np.float64), fold, valid,
                                          block_side=200, origin=(0, 0),
                                          global_shape=valid.shape)
        per_fold.append({"fold": fold["name"], **{kk: res[kk] for kk in
                         ("dti", "tpw", "fpw", "fnw", "n_truth", "n_emitted",
                          "evaluator_version", "evidence_class")}})
        terms = t if terms is None else terms + t
    return {"per_fold": per_fold, "terms": terms}, terms


def restrict_fold(fold: dict, mask: np.ndarray) -> dict:
    """A fold whose scored region is intersected with ``mask`` (tercile analysis)."""
    out = dict(fold)
    out["region"] = fold["region"] & mask
    out["name"] = f"{fold['name']}|restricted"
    return out


def pooled(terms_by_arm: dict, candidate: str, draws: int = 1000) -> dict:
    return evaluate_holdout.pooled_summary(terms_by_arm, draws=draws, candidate=candidate)
