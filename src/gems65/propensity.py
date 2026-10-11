"""Propensity estimation for SAR positive-unlabeled data (Bekker & Davis, 2018).

``e(x) = P(s = 1 | y = 1, x)`` is the probability that a *fault* pixel at ``x``
made it into the published catalogue.  Under SCAR (the assumption every previous
lane in this family makes, implicitly) ``e(x) = e0`` is a constant; under SAR it
varies with the covariates, which is exactly the Great Basin mapping bias the
brief describes (steep, range-front, LiDAR-covered, finely-mapped ground is
over-represented in the catalogue).

EM (Bekker & Davis, "Learning from Positive and Unlabeled Data with a
Selection Bias", PMLR v94, 2018)
--------------------------------------------------------------------------
Latent variable: ``y`` for the unlabelled pixels.  With class posterior
``g(x) = P(y=1|x)`` and propensity ``e(x)``,

    E-step   r_i = P(y=1 | x_i, s_i=0) = g_i (1-e_i) / ( g_i (1-e_i) + (1-g_i) )
    M-step   pi  = ( n_L + sum_U r_i ) / n
             g   <- weighted logistic fit on {labelled: y=1, w=1}
                                    U {y=1, w=r_i} U {y=0, w=1-r_i}
             e   <- weighted logistic fit of P(s=1 | y=1, x) on
                    {labelled: s=1, w=1} U {unlabelled: s=0, w=r_i}
                    (unlabelled pixels are in the ``y=1`` population only with
                    probability ``r_i``; the ones with weight ``1-r_i`` are not
                    positives and are therefore *not* used for ``e``)

Iterated to a fixed point.  The result is a *parametric* propensity: it is not
uniquely identified from PU data alone, so ``em_propensity`` returns the whole
trajectory (``pi``, mean ``e``, log-likelihood-ish diagnostic) and the caller
sweeps ``pi_init``, the propensity basis (linear / quadratic) and the SCAR
fallback, reporting the spread as a sensitivity analysis rather than claiming a
point identification.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression

from .risks import sigmoid   # re-exported so callers do not need both modules

E_FLOOR = 0.02      # propensity is bounded away from 0: no covariate makes a fault unmappable
E_CEIL = 0.995


def _logit_fit(X: np.ndarray, target: np.ndarray, weight: np.ndarray, C: float = 1.0,
               max_iter: int = 2000) -> LogisticRegression:
    m = LogisticRegression(C=C, max_iter=max_iter, solver="lbfgs", fit_intercept=True)
    keep = weight > 0
    if keep.sum() < 10 or len(np.unique(target[keep])) < 2:
        raise ValueError("degenerate logistic fit: need two classes with positive weight")
    m.fit(X[keep], target[keep], sample_weight=weight[keep])
    return m


def basis(X: np.ndarray, kind: str = "linear") -> np.ndarray:
    """Propensity design matrix.  ``quadratic`` adds squares and pairwise products."""
    X = np.asarray(X, float)
    if kind == "linear":
        return X
    if kind == "quadratic":
        d = X.shape[1]
        cols = [X, X ** 2]
        for i in range(d):
            for j in range(i + 1, d):
                cols.append((X[:, i] * X[:, j])[:, None])
        return np.hstack(cols)
    raise ValueError("kind must be 'linear' or 'quadratic'")


@dataclass
class PropensityFit:
    pi: float
    ebar: float                  # E_x[e(x)] over the *population* (footprint) estimate
    e_labelled: np.ndarray       # e at the labelled pixels
    e_unlabelled: np.ndarray     # e at the unlabelled pixels
    responsibilities: np.ndarray
    model_e: LogisticRegression
    model_g: LogisticRegression
    Xb_lab: np.ndarray
    Xb_unl: np.ndarray
    trace: list
    converged: bool
    basis_kind: str
    n_iter: int
    u_weight: float = 1.0
    n_unl_population: float = 0.0

    def e_all(self) -> np.ndarray:
        return np.concatenate([self.e_labelled, self.e_unlabelled])

    def predict_e(self, Xb: np.ndarray) -> np.ndarray:
        return np.clip(self.model_e.predict_proba(Xb)[:, 1], E_FLOOR, E_CEIL)


def em_propensity(X_lab: np.ndarray, X_unl: np.ndarray, *, pi_init: float | None = None,
                  n_iter: int = 40, tol: float = 1e-5, basis_kind: str = "linear",
                  C_e: float = 1.0, C_g: float = 1.0, e_floor: float = E_FLOOR,
                  scar: bool = False, u_weight: float = 1.0,
                  n_unl_population: float | None = None,
                  init: str = "scar_identity") -> PropensityFit:
    """Run the SAR EM.  ``scar=True`` forces ``e(x) = e0`` (the SCAR fallback).

    ``u_weight`` is the population weight of one unlabelled *subsample* row:
    ``n_unl_population / len(X_unl)``.  Every unlabelled row enters the pi
    update and both M-step logistic fits with that weight, so the EM estimates
    population quantities from a subsample.  Without it, pi collapses onto the
    subsample's labelled fraction (measured: pi = 0.867 with a 20,000-row
    subsample of a 5.1 M-pixel unlabelled population, when the truth is ~0.02;
    caught by ``tests/test_propensity_subsample.py``).
    """
    if u_weight <= 0:
        raise ValueError("u_weight must be positive")
    if n_unl_population is None:
        n_unl_population = X_unl.shape[0] * u_weight
    if init not in ("scar_identity", "flat"):
        raise ValueError("init must be 'scar_identity' or 'flat'")
    X_lab = np.asarray(X_lab, float)
    X_unl = np.asarray(X_unl, float)
    if X_lab.ndim != 2 or X_unl.ndim != 2 or X_lab.shape[1] != X_unl.shape[1]:
        raise ValueError("covariate matrices must be 2-D with equal width")
    n_lab, n_unl = X_lab.shape[0], X_unl.shape[0]
    Xb_lab = basis(X_lab, basis_kind)
    Xb_unl = basis(X_unl, basis_kind)
    Xb_all = np.vstack([Xb_lab, Xb_unl])

    # SCAR initialisation, on population counts: e0 = nL / (nL + pi * nU_pop)
    pi = float(pi_init) if pi_init else 0.02
    pi = float(np.clip(pi, 1e-4, 0.5))
    e0 = n_lab / max(1e-9, n_lab + pi * n_unl_population)
    e0 = float(np.clip(e0, e_floor, E_CEIL))

    if scar:
        # SCAR fallback: e(x) = e0 constant.  Only g is fitted, by EM with the
        # constant propensity, so the arm is comparable to the SAR EM.
        e_lab = np.full(n_lab, e0)
        e_unl = np.full(n_unl, e0)
        r = np.full(n_unl, 0.5)
        model_g = None
        for _ in range(8):
            model_g = _fit_g(Xb_lab, Xb_unl, r, C=C_g, u_weight=u_weight)
            g_unl = model_g.predict_proba(Xb_unl)[:, 1]
            r_new = _responsibility(g_unl, e_unl)
            if np.max(np.abs(r_new - r)) < tol:
                r = r_new
                break
            r = r_new
        pi_new = float((n_lab + u_weight * r.sum()) / (n_lab + n_unl_population))
        return PropensityFit(pi=pi_new, ebar=e0, e_labelled=e_lab, e_unlabelled=e_unl,
                             responsibilities=r, model_e=None, model_g=model_g,
                             Xb_lab=Xb_lab, Xb_unl=Xb_unl,
                             trace=[{"iter": 0, "pi": pi_new, "e0": e0, "scar": True,
                                     "e_mean": e0, "r_mean": float(r.mean())}],
                             u_weight=u_weight,
                             converged=True, basis_kind="SCAR-constant", n_iter=1)

    # --- stage 0: SCAR warm start -------------------------------------------
    # IDENTIFIABILITY, stated plainly: the observed-data likelihood is
    #     L = sum_L log(g e) + sum_U log(1 - g e),
    # i.e. it depends on g(x)*e(x) = P(s=1|x) ONLY.  Any factorisation of the
    # same product fits equally well, so the propensity is *not* identified from
    # PU data alone; what breaks the tie is the parametric class (logistic g,
    # logistic e on the same small covariate set), pi, and the initialisation.
    # Two hazards follow, and both were measured here:
    #   (a) starting g at P(s=1|x) and feeding it straight into the
    #       responsibility step converges to a MIRRORED fixed point
    #       (Spearman(e_hat, e_true) = -0.899 on synthetic data);
    #   (b) starting from an unweighted subsample inflates pi to the subsample's
    #       labelled fraction (pi = 0.867 measured where the truth was ~0.02).
    # Stage 0 therefore uses the exact SCAR identity  g(x) = P(s=1|x) / e0,
    # which is correct by construction when e is constant, and pi/e0 are
    # population-weighted.
    rho = n_lab / float(n_lab + n_unl_population)
    if init == "scar_identity":
        q_target = np.concatenate([np.ones(n_lab), np.zeros(n_unl)])
        q_weight = np.concatenate([np.ones(n_lab), np.full(n_unl, u_weight)])
        model_q = _logit_fit(Xb_all, q_target, q_weight, C=C_g)
        q_unl = model_q.predict_proba(Xb_unl)[:, 1]
        g0 = np.clip(q_unl / max(e0, 1e-6), 1e-6, 0.999)
        r = _responsibility(g0, np.full(n_unl, e0))
        model_g = _fit_g(Xb_lab, Xb_unl, r, C=C_g, u_weight=u_weight)
    elif init == "flat":
        r = np.full(n_unl, 0.5)
        model_g = _fit_g(Xb_lab, Xb_unl, r, C=C_g, u_weight=u_weight)
    else:
        raise ValueError("init must be 'scar_identity' or 'flat'")
    for _ in range(6):
        r_new = _responsibility(model_g.predict_proba(Xb_unl)[:, 1], np.full(n_unl, e0))
        if np.max(np.abs(r_new - r)) < tol:
            r = r_new
            break
        r = r_new
        model_g = _fit_g(Xb_lab, Xb_unl, r, C=C_g, u_weight=u_weight)
    pi = float((n_lab + u_weight * r.sum()) / (n_lab + n_unl_population))
    pi = float(np.clip(pi, 1e-4, 0.5))
    e0 = float(np.clip(rho / pi, e_floor, E_CEIL)) if pi > 0 else e0

    # --- stage 1: SAR EM ----------------------------------------------------
    model_e = None
    trace = []
    converged = False
    for it in range(n_iter):
        g_unl = model_g.predict_proba(Xb_unl)[:, 1]
        e_unl = np.full(n_unl, e0) if model_e is None else model_e.predict_proba(Xb_unl)[:, 1]
        e_unl = np.clip(e_unl, e_floor, E_CEIL)
        r = _responsibility(g_unl, e_unl)
        pi_new = float((n_lab + u_weight * r.sum()) / (n_lab + n_unl_population))

        # M-step for g
        model_g = _fit_g(Xb_lab, Xb_unl, r, C=C_g, u_weight=u_weight)
        # M-step for e: P(s=1 | y=1, x)
        Xe = np.vstack([Xb_lab, Xb_unl])
        te = np.concatenate([np.ones(n_lab), np.zeros(n_unl)])
        we = np.concatenate([np.ones(n_lab), u_weight * r])
        if we.sum() > 0 and (r > 0).sum() >= 50:
            model_e = _logit_fit(Xe, te, we, C=C_e)
            e_lab = np.clip(model_e.predict_proba(Xb_lab)[:, 1], e_floor, E_CEIL)
        else:
            e_lab = np.full(n_lab, e0)
        ebar = float(np.concatenate([e_lab, e_unl]).mean())
        trace.append({"iter": it, "pi": pi_new, "ebar": ebar,
                      "e_lab_mean": float(e_lab.mean()), "e_lab_min": float(e_lab.min()),
                      "e_lab_max": float(e_lab.max()), "r_mean": float(r.mean()),
                      "r_sum": float(r.sum())})
        if abs(pi_new - pi) < tol and it > 2:
            pi = pi_new
            converged = True
            break
        pi = pi_new

    g_unl = model_g.predict_proba(Xb_unl)[:, 1]
    e_unl = np.clip(model_e.predict_proba(Xb_unl)[:, 1], e_floor, E_CEIL)
    e_lab = np.clip(model_e.predict_proba(Xb_lab)[:, 1], e_floor, E_CEIL)
    r = _responsibility(g_unl, e_unl)
    return PropensityFit(pi=pi, ebar=float(np.concatenate([e_lab, e_unl]).mean()),
                         e_labelled=e_lab, e_unlabelled=e_unl, responsibilities=r,
                         model_e=model_e, model_g=model_g, Xb_lab=Xb_lab, Xb_unl=Xb_unl,
                         trace=trace, converged=converged, basis_kind=basis_kind,
                         n_iter=len(trace), u_weight=u_weight,
                         n_unl_population=float(n_unl_population))


def observed_loglik(g_lab: np.ndarray, g_unl: np.ndarray, e_lab: np.ndarray,
                    e_unl: np.ndarray, u_weight: float = 1.0) -> float:
    """sum_L log(g e) + sum_U log(1 - g e): the *observed* likelihood.

    Reported because it is the only quantity the PU data can actually score, and
    it is invariant to the (g, e) factorisation -- the formal statement of the
    non-identifiability the brief warns about.
    """
    pe_lab = np.clip(np.asarray(g_lab) * np.asarray(e_lab), 1e-12, 1 - 1e-12)
    pe_unl = np.clip(np.asarray(g_unl) * np.asarray(e_unl), 1e-12, 1 - 1e-12)
    return float(np.log(pe_lab).sum() + u_weight * np.log1p(-pe_unl).sum())


def _responsibility(g: np.ndarray, e: np.ndarray) -> np.ndarray:
    """``P(y=1|x,s=0) = g(1-e) / (g(1-e) + 1-g)`` (SAR E-step)."""
    g = np.clip(g, 1e-9, 1 - 1e-9)
    num = g * (1.0 - e)
    den = num + (1.0 - g)
    return np.clip(num / np.maximum(den, 1e-12), 0.0, 1.0)


def _fit_g(Xb_lab: np.ndarray, Xb_unl: np.ndarray, r: np.ndarray, C: float = 1.0,
           u_weight: float = 1.0) -> LogisticRegression:
    """Weighted logistic fit of the class posterior ``g(x)=P(y=1|x)``.

    Design: labelled pixels enter as ``y=1`` with weight 1; every unlabelled
    pixel enters twice, once as ``y=1`` with weight ``r_i`` and once as ``y=0``
    with weight ``1-r_i``.  Rows with zero weight are dropped by ``_logit_fit``.
    """
    n_lab, n_unl = Xb_lab.shape[0], Xb_unl.shape[0]
    if r.shape[0] != n_unl:
        raise ValueError("responsibilities must have one entry per unlabelled pixel")
    X = np.vstack([Xb_lab, Xb_unl, Xb_unl])
    y = np.concatenate([np.ones(n_lab), np.ones(n_unl), np.zeros(n_unl)])
    w = np.concatenate([np.ones(n_lab), u_weight * r, u_weight * (1.0 - r)])
    return _logit_fit(X, y, w, C=C, max_iter=3000)
