"""SAR-EM: propensity estimation under the Selected At Random assumption.

Implements the EM algorithm of Bekker & Davis (2018), "Learning from Positive
and Unlabeled Data under the Selected At Random Assumption", PMLR v94:8-22
(https://proceedings.mlr.press/v94/bekker18a.html).  The equations below are
transcribed from that paper; every deliberate choice made here (decay
schedule, floor, optimiser, convergence window) is marked as a protocol
choice, not as something the paper prescribes.

Model
-----
``s = 1`` marks an example that carries a label (catalogue membership);
``y`` is the unknown true class (true fault).  ``e(x) = P(s=1 | y=1, x_e)``
depends only on a declared covariate subset ``x_e``.

E-step (paper Sec. 4.1)::

    P(y=1 | x, s=1) = 1
    P(y=1 | x, s=0) = f(x) (1 - e(x_e)) / [ f(x) (1 - e(x_e)) + (1 - f(x)) ]

M-step (paper Sec. 4.1, split over the two models)::

    max_theta  E_{y|x,s} log P(y|x,theta)      -> weighted classifier on y_hat
    max_phi    E_{y|x,s} log P(s|y,x_e,phi)    -> weighted propensity model in
                                                  which the labeled positives
                                                  carry weight 1 and the
                                                  unlabeled carry weight y_hat

Initialization is Algorithm 2 of the paper: fit ``f`` for ``s``; set
``c = 1 / max f(x[s==0])`` (Elkan & Noto estimator 3); train ``f`` on the
positive/unlabeled duplicate construction with weights ``w`` and target ``y``;
train ``e`` on the duplicated construction that returns ``c`` for any input.

Identifiability
---------------
PU data alone do not identify the propensity scale: a lower ``e`` with a higher
class prior explains the same labels.  This module therefore reports ``e`` as
an object that is only meaningful *relative to* the class-prior estimate that
accompanies it, and the lane reports it as a sensitivity analysis unless a
public exhaustive-mapping anchor exists.  None is claimed in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.linear_model import LogisticRegression

__all__ = ["SarEmResult", "sar_em", "fit_logistic"]

MAX_EPS = 1e-6


def fit_logistic(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None,
                 *, C: float = 1.0, seed: int = 0) -> LogisticRegression:
    """Fit an L2 logistic regression with non-negative sample weights.

    Used for every sub-problem of SAR-EM.  ``sklearn`` requires ``w >= 0``;
    every construction below duplicates rows so that weights stay non-negative
    (this is also how the reference algorithm's duplicate constructions work).
    """
    X = np.asarray(X, np.float64)
    y = np.asarray(y, np.int8)
    w = None if w is None else np.asarray(w, np.float64)
    if w is not None and (w < 0).any():
        raise ValueError("sample weights must be non-negative in SAR-EM sub-problems")
    clf = LogisticRegression(C=C, solver="lbfgs", max_iter=1000, random_state=seed,
                             fit_intercept=True)
    clf.fit(X, y, sample_weight=w)
    return clf


def _prob(clf: LogisticRegression, X: np.ndarray) -> np.ndarray:
    return clf.predict_proba(np.asarray(X, np.float64))[:, 1]


@dataclass
class SarEmResult:
    """Fitted propensity model plus the diagnostics the lane must report."""

    model: LogisticRegression                 # e(x_e) = P(s=1 | y=1, x_e)
    classifier: LogisticRegression            # f(x)   = P(y=1 | x)
    propensity_labeled: np.ndarray            # e(x_e) for every input row
    alpha_plug_in: float                      # mean fitted P(y=1|x)
    c_mean_labeled: float                     # mean e over labeled rows
    n_labeled: int
    n_unlabeled: int
    iterations: int
    converged: bool
    history: list = field(default_factory=list)
    paper: str = "Bekker & Davis 2018, PMLR v94:8-22"

    def predict_e(self, Xe: np.ndarray) -> np.ndarray:
        return _prob(self.model, Xe)


def mean_abs_slope(history_rows: np.ndarray) -> float:
    """Mean absolute least-squares slope of the propensity predictions.

    ``history_rows`` has shape ``(n_iterations, n_examples)``.  For every example
    the least-squares slope of its propensity prediction against the iteration
    index is computed; the convergence statistic is the mean of their absolute
    values, exactly the quantity in Sec. 4.4 of the paper.
    """
    arr = np.asarray(history_rows, np.float64)
    n = arr.shape[0]
    if n < 2:
        return float("inf")
    i = np.arange(n, dtype=np.float64)
    denom = n * (i * i).sum() - i.sum() ** 2
    if denom == 0:
        return float("inf")
    slopes = (n * (i[:, None] * arr).sum(axis=0) - i.sum() * arr.sum(axis=0)) / denom
    return float(np.mean(np.abs(slopes)))


def sar_em(X: np.ndarray, Xe: np.ndarray, s: np.ndarray, *,
           n_iter: int = 25, decay: float = 0.5, e_floor: float = 1e-3,
           eps: float = 5e-3, window: int = 4, C: float = 1.0,
           seed: int = 0) -> SarEmResult:
    """Run SAR-EM and return the fitted propensity and classifier models.

    Parameters
    ----------
    X
        Attributes used by the classifier (all covariates may be included).
    Xe
        Propensity covariates; a *declared subset* of ``X`` columns in practice
        (prototype/constraint of the SAR assumption).
    s
        1 for labeled (catalogue) examples, 0 for unlabeled.
    decay, e_floor
        Protocol choices.  The paper (Sec. 4.2) states that the predicted
        propensity scores "can simply be decayed at every iteration during the
        expectation step" to encourage local certainty; the geometric schedule
        ``decay**t`` and the floor ``e_floor`` are this lane's concrete choice.
    eps, window
        Convergence: mean absolute least-squares slope of the propensity
        predictions over the last ``window`` iterations below ``eps``
        (paper Sec. 4.4), or ``n_iter`` reached.

    Returns
    -------
    SarEmResult
    """
    X = np.asarray(X, np.float64)
    Xe = np.asarray(Xe, np.float64)
    s = np.asarray(s, np.int8)
    if X.shape[0] != s.size or Xe.shape[0] != s.size:
        raise ValueError("X, Xe and s must share the row count")
    if not np.isin(s, (0, 1)).all():
        raise ValueError("s must be binary")

    labeled = s == 1
    unlabeled = ~labeled
    n_lab, n_unl = int(labeled.sum()), int(unlabeled.sum())
    if n_lab == 0 or n_unl == 0:
        raise ValueError("SAR-EM needs both labeled and unlabeled rows")

    # ---- Algorithm 2: initialization -------------------------------------
    f = fit_logistic(X, s, None, C=C, seed=seed)
    s_hat = np.clip(_prob(f, X[unlabeled]), MAX_EPS, 1.0 - MAX_EPS)
    c = float(min(1.0, 1.0 / max(s_hat.max(), MAX_EPS)))
    y_hat_unl = np.clip(((1.0 - c) / max(c, MAX_EPS)) * s_hat / (1.0 - s_hat), 0.0, 1.0)

    Xw = np.vstack([X[labeled], X[unlabeled], X[unlabeled]])
    yw = np.concatenate([np.ones(n_lab, np.int8), np.ones(n_unl, np.int8),
                         np.zeros(n_unl, np.int8)])
    ww = np.concatenate([np.ones(n_lab), y_hat_unl, 1.0 - y_hat_unl])
    f = fit_logistic(Xw, yw, ww, C=C, seed=seed)

    Xew = np.vstack([Xe, Xe])
    sw = np.concatenate([np.ones(s.size, np.int8), np.zeros(s.size, np.int8)])
    w_prop = np.concatenate([np.full(s.size, c), np.full(s.size, 1.0 - c)])
    e_model = fit_logistic(Xew, sw, w_prop, C=C, seed=seed)

    history: list[dict] = []
    e_unl_hist: list[np.ndarray] = []
    converged = False
    it = 0
    for it in range(1, n_iter + 1):
        # ---- E-step -------------------------------------------------------
        e_raw = np.clip(_prob(e_model, Xe[unlabeled]), e_floor, 1.0)
        e_eff = np.clip(e_raw * (decay ** (it - 1)), e_floor, 1.0)   # protocol choice
        f_unl = np.clip(_prob(f, X[unlabeled]), MAX_EPS, 1.0 - MAX_EPS)
        num = f_unl * (1.0 - e_eff)
        y_hat_unl = np.clip(num / (num + (1.0 - f_unl)), 0.0, 1.0)

        # ---- M-step -------------------------------------------------------
        y_hat_full = np.empty(s.size, np.float64)
        y_hat_full[labeled] = 1.0          # observed labels: y = 1 with certainty
        y_hat_full[unlabeled] = y_hat_unl  # E-step expectation
        Xw = np.vstack([X, X])
        yw = np.concatenate([np.ones(s.size, np.int8), np.zeros(s.size, np.int8)])
        w_hat = np.concatenate([y_hat_full, 1.0 - y_hat_full])
        f = fit_logistic(Xw, yw, w_hat, C=C, seed=seed)

        Xew = np.vstack([Xe[labeled], Xe[unlabeled]])
        sw = np.concatenate([np.ones(n_lab, np.int8), np.zeros(n_unl, np.int8)])
        w_prop = np.concatenate([np.ones(n_lab), y_hat_unl])
        e_model = fit_logistic(Xew, sw, w_prop, C=C, seed=seed)

        e_all = np.clip(_prob(e_model, Xe), e_floor, 1.0)
        e_unl_hist.append(e_all[unlabeled].copy())
        slope = (mean_abs_slope(np.stack(e_unl_hist[-window:]))
                 if len(e_unl_hist) >= window else float("inf"))
        history.append(dict(iteration=it, c_hat=float(e_all[labeled].mean()),
                            e_mean=float(e_all.mean()), mean_abs_slope=slope,
                            mean_y_hat_unlabeled=float(y_hat_unl.mean())))
        if len(e_unl_hist) >= window and slope < eps:
            converged = True
            break

    e_final = np.clip(_prob(e_model, Xe), e_floor, 1.0)
    f_final = np.clip(_prob(f, X), MAX_EPS, 1.0 - MAX_EPS)
    return SarEmResult(
        model=e_model,
        classifier=f,
        propensity_labeled=e_final,
        alpha_plug_in=float(f_final.mean()),
        c_mean_labeled=float(e_final[labeled].mean()),
        n_labeled=n_lab,
        n_unlabeled=n_unl,
        iterations=it,
        converged=converged,
        history=history,
    )
