"""Propensity-aware empirical risk for PU learning (Bekker, Robberechts & Davis 2019).

    J. Bekker, P. Robberechts and J. Davis, "Beyond the Selected Completely At Random
    Assumption for Positive-Unlabeled Learning", arXiv:1809.03207 (2019).
    https://arxiv.org/abs/1809.03207
    A. Kiryo, G. Niu, M. C. du Plessis and M. Sugiyama, "Positive-Unlabeled Learning
    with Non-Negative Risk Estimator", NeurIPS 2017.

Exact risk under SAR
--------------------
Let ``p(x)`` be the covariate density over the whole footprint (every pixel, inside and
outside the catalogue), ``pi(x) = P(y=1|x)`` the latent fault posterior,
``e(x) = P(s=1|y=1,x)`` the label propensity and ``q = P(s=1) = E_p[pi*e]``.  The two
observable sampling distributions are

    p_L(x) = p(x) pi(x) e(x) / q            (labelled / catalogue pixels)
    p_U(x) = p(x) (1 - pi(x) e(x)) / (1-q)  (unlabelled pixels)

The classification risk we actually want is

    R(f) = E_p[ l(f(x),1) pi(x) ] + E_p[ l(f(x),0) (1 - pi(x)) ]            (*)

Using ``E_{p_L}[g] = E_p[g*pi*e]/q`` we get the three identities

    E_p[ l1*pi ]   = q * E_{p_L}[ l1 / e ]  =  q * E_{p_L}[ w * l1 ]
    E_p[ l0*pi ]   = q * E_{p_L}[ w * l0 ]
    E_p[ l0*pi*e ] = q * E_{p_L}[ l0 ]
    E_p[ l0 ]      = (1-q) E_{p_U}[ l0 ] + q E_{p_L}[ l0 ]

with ``w = 1/e`` the importance weight.  Substituting into (*) gives the
**propensity-aware empirical risk**

    R(f) = q E_{p_L}[ w*l1 ] + (1-q) E_{p_U}[ l0 ] + q E_{p_L}[ (1-w)*l0 ]          (**)

which is exact (no calibration approximation).  Under SCAR, ``e = c`` constant,
``q = pi*c`` and ``w = 1/c``, (**) reduces to the classic unbiased PU (uPU) risk of
du Plessis et al. (2014) with the ``E_{p_L}[l0] = E_{p_U}[l0]`` approximation dropped.

Non-negative (nnPU) guard
-------------------------
Rewrite (**) by splitting the third term:

    R(f) = [ q E_{p_L}[ w*l1 ] + (1-q) E_{p_U}[ l0 ] - q E_{p_L}[ w*l0 ] ]
           + q E_{p_L}[ l0 ]
         =   excess(f)                                            +  anchor(f)

For SCAR (``w = 1``) the bracket is exactly Kiryo et al.'s
``pi*E[ l1 ] + E_U[ l0 ] - pi*E[ l0 ]``, the component that overfitting can drive
negative.  The nnPU estimator truncates it at zero while always keeping the anchor:

    R_nnpu(f) = max(0, excess(f)) + anchor(f)                                       (***)

Training follows Kiryo et al.'s ramp-up: first minimise the unbiased risk
``excess + anchor`` (which may be negative), then re-minimise (***) starting from that
solution.

Clipping
--------
Importance weights are clipped at 10 -- ``w = min(1/e, 10)`` -- a preregistered
protocol choice, not a result of the cited papers.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

WEIGHT_CLIP = 10.0


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))


@dataclass
class PURiskFit:
    theta: np.ndarray
    surface: np.ndarray          # pi_hat on the supplied full grid
    risk_u: float                # unbiased (possibly negative) risk
    risk_nnpu: float             # non-negative risk
    prior_q: float
    mean_weight_labelled: float
    n_labelled: int
    n_unlabelled: int
    kind: str                    # 'sar' or 'nnpu'


def _terms(theta, X_lab, X_unl, w_lab, q):
    """Return (excess, anchor, d_excess, d_anchor) for the linear score ``theta``."""
    n_l, n_u = X_lab.shape[0], X_unl.shape[0]
    a = q / max(n_l, 1)
    b = (1.0 - q) / max(n_u, 1)
    z_l = X_lab @ theta
    z_u = X_unl @ theta
    l1_l = np.logaddexp(0.0, -z_l)
    l0_l = np.logaddexp(0.0, z_l)
    l0_u = np.logaddexp(0.0, z_u)
    s_l = _sigmoid(z_l)
    s_u = _sigmoid(z_u)
    excess = a * float(np.sum(w_lab * l1_l)) + b * float(np.sum(l0_u)) - a * float(np.sum(w_lab * l0_l))
    anchor = a * float(np.sum(l0_l))
    # d l1/dz = s-1 ; d l0/dz = s
    d_excess = -(X_lab.T @ (a * w_lab)) + X_unl.T @ (b * s_u)
    d_anchor = X_lab.T @ (a * s_l)
    return excess, anchor, d_excess, d_anchor


def _fit_linear(X_lab, X_unl, w_lab, q, maxiter=300):
    """Minimise the non-negative propensity-aware PU risk over linear scores."""
    n_l, n_u = X_lab.shape[0], X_unl.shape[0]
    a = q / max(n_l, 1)
    b = (1.0 - q) / max(n_u, 1)
    zl = X_lab @ np.zeros(X_lab.shape[1])
    zu = X_unl @ np.zeros(X_unl.shape[1])
    l1_l0 = np.logaddexp(0.0, -zl)
    l0_l0 = np.logaddexp(0.0, zl)
    l0_u0 = np.logaddexp(0.0, zu)
    excess0 = a * float(np.sum(w_lab * l1_l0)) + b * float(np.sum(l0_u0)) - a * float(np.sum(w_lab * l0_l0))
    anchor0 = a * float(np.sum(l0_l0))

    def obj_u(theta):
        e, an, _, _ = _terms(theta, X_lab, X_unl, w_lab, q)
        return e + an

    def grad_u(theta):
        _, _, de, da = _terms(theta, X_lab, X_unl, w_lab, q)
        return de + da

    def obj_nn(theta):
        e, an, _, _ = _terms(theta, X_lab, X_unl, w_lab, q)
        return max(0.0, e) + an

    def grad_nn(theta):
        e, _, de, da = _terms(theta, X_lab, X_unl, w_lab, q)
        return de if e > 0 else da

    theta0 = np.zeros(X_lab.shape[1], dtype=np.float64)
    # phase 1 -- unbiased risk (Kiryo ramp-up)
    r1 = minimize(obj_u, theta0, jac=grad_u, method="L-BFGS-B",
                  options=dict(maxiter=maxiter, ftol=1e-12, gtol=1e-10))
    # phase 2 -- non-negative risk, warm-started from phase 1
    r2 = minimize(obj_nn, r1.x, jac=grad_nn, method="L-BFGS-B",
                  options=dict(maxiter=maxiter, ftol=1e-12, gtol=1e-10))
    return r2.x, float(excess0), float(anchor0)


def fit_pu_surface(
    X_full: np.ndarray,
    labelled_idx: np.ndarray,
    e: np.ndarray,
    kind: str = "sar",
    q: float | None = None,
    maxiter: int = 300,
    subsample_unlabelled: int = 400_000,
    rng: np.random.Generator | None = None,
) -> PURiskFit:
    """Fit the latent fault posterior ``pi(x)`` with the propensity-aware PU risk.

    Parameters
    ----------
    X_full : (n, d) standardised design matrix.  Labelled positives first, then the
        unlabelled rows.
    labelled_idx : row indices of the labelled positives inside ``X_full``.
    e : (n_labelled,) label-propensity surface from SAR-EM.  For the nnPU baseline pass
        an array of ones -- no importance weighting, which is the standard uPU/nnPU risk.
    kind : 'sar' (propensity-aware, w = 1/e) or 'nnpu' (SCAR, w = 1).
    q : P(s=1).  Defaults to the empirical catalogue rate over ``X_full``.
    """
    rng = rng or np.random.default_rng(0)
    n = X_full.shape[0]
    lab = np.zeros(n, bool)
    lab[np.asarray(labelled_idx, dtype=np.int64)] = True
    n_l = int(lab.sum())
    if q is None:
        q = float(n_l / n)
    e = np.clip(np.asarray(e, dtype=np.float64), 1e-6, 1.0)
    if e.size == n_l:
        w_lab = np.clip(1.0 / e, 0.0, WEIGHT_CLIP)
    else:                                  # constant propensity (SCAR baseline)
        w_lab = np.full(n_l, float(np.clip(1.0 / float(e.ravel()[0]), 0.0, WEIGHT_CLIP)))

    unl = np.flatnonzero(~lab)
    if unl.size > subsample_unlabelled:
        unl = rng.choice(unl, size=subsample_unlabelled, replace=False)
    X_lab = X_full[lab]
    X_unl = X_full[unl]

    theta, e0, a0 = _fit_linear(X_lab, X_unl, w_lab, q, maxiter=maxiter)
    surf = _sigmoid(X_full @ theta)
    ex, an, _, _ = _terms(theta, X_lab, X_unl, w_lab, q)
    return PURiskFit(
        theta=theta,
        surface=surf,
        risk_u=float(ex + an),
        risk_nnpu=float(max(0.0, ex) + an),
        prior_q=float(q),
        mean_weight_labelled=float(w_lab.mean()),
        n_labelled=n_l,
        n_unlabelled=int(unl.size),
        kind=kind,
    )
