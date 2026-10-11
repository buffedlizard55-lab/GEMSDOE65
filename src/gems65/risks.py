"""Matched empirical-risk arms for the PU comparison.

Three arms share one model class (L2 logistic regression, trained by full-batch
gradient descent on a weighted log loss) and differ **only** in the weight
schedule that encodes the risk.  Everything else -- features, folds, budget,
optimiser, seed, initialisation -- is identical, so any difference in the
blocked-holdout DTI is attributable to the risk/selection model under test.

Arms
----
``nnpu``
    Non-negative PU risk (du Plessis et al. 2014; Kiryo et al. 2017).  In the
    row-weight form used here the unbiased part is, for labeled positives,
    ``(y=1, weight +pi)`` and ``(y=0, weight -pi)``, and for unlabeled rows
    ``(y=0, weight 1)``.  Kiryo's correction sets the negative-term gradient to
    zero whenever the empirical negative part is below zero::

        R_nn = pi E_P[l+] + max(0, E_U[l-] - pi E_P[l-]).

``prop``
    Propensity-weighted estimator of Bekker, Robberechts & Davis (2019),
    Definition 2 (arXiv:1809.03207)::

        R_hat = (1/n) sum_i [ s_i ( (1/e_i) d1(yhat_i) + (1 - 1/e_i) d0(yhat_i) )
                              + (1 - s_i) d0(yhat_i) ]

    with ``d1 = -ln yhat`` and ``d0 = -ln(1 - yhat)`` (log loss).  The inverse
    propensity weights ``1/e_i`` are clipped at 10, as specified by this lane's
    protocol.  Every labeled positive therefore also contributes a *negative*
    row with weight ``1 - w_i``, which is what makes the estimator unbiased
    under SAR.

``scar``
    Selected-Completely-At-Random control arm: the same estimator with a
    constant weight ``w = 1/mean(e)`` (clipped at 10) instead of per-instance
    weights.  It isolates "using propensity at all" from "using it per
    instance"; it is reported, not gated on.

The class prior ``pi`` used by ``nnpu`` is the plug-in estimate from the same
SAR-EM fit for every arm, so the comparison never varies the prior.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["WeightSchedule", "fit_weighted_logistic", "schedule"]

WEIGHT_CLIP = 10.0           # lane protocol: inverse-propensity weights <= 10


def _log1pexp(x: np.ndarray) -> np.ndarray:
    """Numerically stable ``log(1 + exp(x))``."""
    return np.logaddexp(0.0, x)


@dataclass
class WeightSchedule:
    """Per-row label/weight rows for one empirical risk."""

    rows_label: np.ndarray          # float in {0,1}
    rows_weight: np.ndarray         # may be negative
    kind: str
    uses_propensity: bool
    weight_clip: float = WEIGHT_CLIP
    metadata: dict = field(default_factory=dict)


def schedule(kind: str, s: np.ndarray, e: np.ndarray, pi: float) -> WeightSchedule:
    """Build the row schedule for one arm.

    ``s`` is the PU label vector, ``e`` the fitted propensity for each row and
    ``pi`` the class prior.  Unlabeled rows always contribute a negative row of
    weight 1 (base term); labeled rows contribute a positive row plus, for the
    propensity arms, a negative row.
    """
    s = np.asarray(s, np.int8)
    e = np.asarray(e, np.float64)
    labeled = s == 1
    n = s.size
    rows_label = np.concatenate([np.ones(n), np.zeros(n)])
    if kind == "nnpu":
        w_pos = np.where(labeled, pi, 0.0)
        w_neg = np.where(labeled, -pi, 1.0)
        w = np.concatenate([w_pos, w_neg])
        return WeightSchedule(rows_label, w, kind, False,
                              metadata=dict(pi=float(pi)))
    if kind in ("prop", "scar"):
        if kind == "prop":
            inv = np.clip(1.0 / np.maximum(e, 1e-6), 0.0, WEIGHT_CLIP)
            used = inv[labeled].mean() if labeled.any() else 0.0
        else:
            used = float(min(1.0 / max(e.mean(), 1e-6), WEIGHT_CLIP))
            inv = np.full(n, used)
        w_pos = np.where(labeled, inv, 0.0)
        w_neg = np.where(labeled, 1.0 - inv, 1.0)
        w = np.concatenate([w_pos, w_neg])
        return WeightSchedule(rows_label, w, kind, True,
                              metadata=dict(mean_inverse_weight=float(used),
                                            pi=float(pi),
                                            prop_min=float(e.min()),
                                            prop_max=float(e.max())))
    raise ValueError(f"unknown arm '{kind}'")


def fit_weighted_logistic(X: np.ndarray, sched: WeightSchedule, *,
                          l2: float = 1e-3, iters: int = 900, lr: float = 0.35,
                          momentum: float = 0.9, seed: int = 0,
                          nnpu_clamp: bool = False) -> dict:
    """Minimise a row-weighted logistic log loss by full-batch gradient descent.

    Returns the coefficient vector plus the optimisation diagnostics.  When
    ``nnpu_clamp`` is set (the ``nnpu`` arm) the gradient of the negative rows
    contributed by labeled positives is set to zero in any iteration where the
    empirical negative part is below zero -- the gradient of ``max(0, .)``.
    """
    X = np.asarray(X, np.float64)
    n, d = X.shape
    y = sched.rows_label.astype(np.float64)
    w = sched.rows_weight.astype(np.float64)
    if y.size != 2 * X.shape[0]:
        raise ValueError("schedule must carry two rows (positive/negative) per instance")
    Xd = np.vstack([X, X])
    yd = np.concatenate([y, y])
    wd = w.copy()
    n_signed = n                       # first n rows are the positive-labelled rows
    scale = float(np.abs(w).sum()) or 1.0

    theta = np.zeros(d, np.float64)
    vel = np.zeros(d, np.float64)
    best = dict(loss=np.inf, theta=theta.copy(), iteration=0)
    rng = np.random.default_rng(seed)
    theta += rng.normal(0.0, 0.01, size=d)

    for it in range(1, iters + 1):
        z = Xd @ theta
        # rows are stacked [positive rows ; negative rows]
        label_pos = np.concatenate([np.ones(n), np.zeros(n)])
        loss_rows = np.where(label_pos > 0, _log1pexp(-z), _log1pexp(z))
        ww = wd.copy()
        if nnpu_clamp:
            # empirical negative part: unlabeled-originated negative rows minus
            # the negative rows contributed by labeled positives
            neg_idx = slice(n, 2 * n)
            pos_contrib = float((ww[:n] * loss_rows[:n]).sum())
            unl = wd[neg_idx] > 0
            unl_mass = float(wd[neg_idx][unl].sum()) or 1.0
            unl_loss = float((ww[neg_idx][unl] * loss_rows[neg_idx][unl]).sum())
            pos_mass = float(np.abs(ww[:n]).sum()) or 1.0
            pos_loss = float((np.abs(ww[:n]) * loss_rows[:n]).sum())
            negative_part = unl_loss / unl_mass - pos_loss / pos_mass
            if negative_part < 0.0:
                ww[neg_idx] = np.where(wd[neg_idx] > 0, wd[neg_idx], 0.0)
        loss = float((ww * loss_rows).sum()) / scale + l2 * float(theta @ theta)
        grad = (Xd.T @ (ww * (1.0 / (1.0 + np.exp(-z)) - np.where(label_pos > 0, 1.0, 0.0)))) / scale
        grad += 2.0 * l2 * theta
        vel = momentum * vel - lr * grad
        theta = theta + vel
        if loss < best["loss"]:
            best = dict(loss=loss, theta=theta.copy(), iteration=it)
        if it % 100 == 0 and np.abs(vel).max() < 1e-7:
            break

    return dict(theta=best["theta"], loss=best["loss"], iterations=best["iteration"],
                arm=sched.kind, clip=sched.weight_clip, metadata=sched.metadata,
                n_rows=int(X.shape[0]))


def predict_proba(X: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """Sigmoid of the linear score (clip is applied by the caller)."""
    return 1.0 / (1.0 + np.exp(-(np.asarray(X, np.float64) @ np.asarray(theta, np.float64))))
