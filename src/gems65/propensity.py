"""SAR-EM propensity estimation (Bekker & Davis, PMLR v94, 2018).

    J. Bekker and J. Davis, "Learning from Positive and Unlabeled Data under the
    Selected At Random Assumption", ICML 2018, PMLR 94.
    https://proceedings.mlr.press/v94/bekker18a.html

Model
-----
For every footprint pixel we observe covariates ``x`` and a catalogue indicator
``s`` (1 = the pixel is in the supplied fault catalogue).  Let ``y`` be the latent
"a real fault is present here" indicator.  Under the **Selected At Random (SAR)**
assumption the labelling mechanism depends only on observables:

    P(s = 1 | x) = e(x) * P(y = 1 | x) = e(x) * pi(x)                (1)

with ``e(x) = P(s = 1 | y = 1, x)`` the *label propensity* and ``pi(x)`` the
latent fault posterior.  ``f(x) := P(s = 1 | x)`` is the only one of the three
that is directly observable, so (1) is one equation in two unknowns.

Identifiability
---------------
SAR-EM therefore fixes the **mean propensity over the true positive population**

    c := E_{x | y = 1}[ e(x) ]                                        (2)

which is exactly the SCAR constant when ``e`` does not depend on ``x``.  ``c`` is
not identifiable from PU data alone: a public index of *exhaustively mapped*
quadrangles would anchor it, and the USGS 7.5-minute map index is a map-frame
grid rather than a completeness certificate (see ``docs/IRREGULARITIES.md``,
IR-65-007).  This module therefore returns ``c``-indexed propensity surfaces and
the driver reports them as a **sensitivity analysis**, never as a calibrated
probability.

Algorithm (SAR-EM)
------------------
Given ``c``:

1. ``e_0(x) = c`` (SCAR start).
2. **M-step (classifier).**  Fit ``pi`` by importance-weighted PU learning with
   weights ``1 / e`` on the labelled positives (see :mod:`gems65.pu`).
3. **M-step (propensity).**  ``r(x) = f_hat(x) / pi(x)`` and
   ``e_{t+1}(x) = clip( c * r(x) / mean_{x in labelled}(r(x)),  e_min, 1 )``.
   The rescaling enforces (2); the clip keeps ``e`` a probability.
4. Iterate to convergence of ``e`` (or ``max_iter``).

``f_hat`` is estimated by logistic regression of ``s`` on the covariates over the
whole footprint, i.e. the conditional labelled rate, which is the observable
quantity in (1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class PropensityResult:
    e: np.ndarray                      # (H, W) float32 propensity surface
    c: float                           # anchoring constant used
    f_hat: np.ndarray                  # observable labelled-rate surface
    pi: np.ndarray                    # latent fault posterior from the last M-step
    n_iter: int
    converged: bool
    delta_history: list[float] = field(default_factory=list)
    labelled_mean_e: float = float("nan")
    e_min: float = float("nan")
    e_max: float = float("nan")


def fit_labelled_rate(Z: np.ndarray, s: np.ndarray, sample_weight: np.ndarray | None = None) -> Callable[[np.ndarray], np.ndarray]:
    """Logistic estimate of ``f(x) = P(s = 1 | x)`` on the whole footprint.

    ``Z`` is (n, d) standardised covariates, ``s`` the 0/1 catalogue indicator.
    Returns a predictor callable.
    """
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(C=1.0, max_iter=300, solver="lbfgs")
    clf.fit(Z, s, sample_weight=sample_weight)
    return clf.predict_proba


def sar_em(
    Z: np.ndarray,
    s: np.ndarray,
    footprint: np.ndarray,
    fit_pi: Callable[[np.ndarray, np.ndarray], np.ndarray],
    c: float,
    max_iter: int = 25,
    tol: float = 1e-4,
    e_floor_quantile: float = 0.0,
    log=print,
) -> PropensityResult:
    """Run SAR-EM at anchoring constant ``c``.

    Parameters
    ----------
    Z : (n, d) standardised propensity covariates for the n footprint pixels.
    s : (n,) 0/1 catalogue indicator.
    fit_pi : callable ``(Z, weights) -> pi`` returning the latent fault posterior
        for every row of ``Z``.  ``weights`` are the importance weights ``1/e``
        (already clipped) to use on the labelled positives.  This is the hook the
        propensity-aware empirical risk plugs into.
    c : mean propensity over the true-positive population (the SCAR constant).
    """
    n = Z.shape[0]
    lab = s > 0
    n_lab = int(lab.sum())
    if n_lab == 0:
        raise ValueError("no labelled positives in the footprint")

    f_pred = fit_labelled_rate(Z, s)
    f_hat = np.clip(f_pred(Z)[:, 1], 1e-6, 1.0).astype(np.float64)

    e = np.full(n, float(c), dtype=np.float64)
    e_min = max(1e-4, float(np.quantile(f_hat[lab], 0.01)))
    pi = np.full(n, float(s.mean()), dtype=np.float64)
    hist: list[float] = []
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        # ---- M-step 1: latent fault posterior with importance weights 1/e -------
        w = np.zeros(n, dtype=np.float64)
        w[lab] = 1.0 / np.clip(e[lab], e_min, 1.0)
        w = np.clip(w, 0.0, 10.0)                     # preregistered clip at 10
        pi_new = np.asarray(fit_pi(Z, w), dtype=np.float64)
        pi_new = np.clip(pi_new, 1e-6, 1.0)

        # ---- M-step 2: propensity, rescaled to enforce E_{y=1}[e] = c ----------
        r = f_hat / pi_new
        denom = float(r[lab].mean())
        if not np.isfinite(denom) or denom <= 0:
            break
        e_new = np.clip(c * r / denom, e_min, 1.0)
        delta = float(np.max(np.abs(e_new - e)))
        hist.append(delta)
        e, pi = e_new, pi_new
        if log is not None and (it == 1 or it % 5 == 0 or delta < tol):
            log(f"  sar-em iter {it:2d}  max|de| = {delta:.3e}  "
                f"e: min {e.min():.4f} med {np.median(e):.4f} max {e.max():.4f}")
        if delta < tol:
            converged = True
            break

    return PropensityResult(
        e=e.astype(np.float32),
        c=float(c),
        f_hat=f_hat.astype(np.float32),
        pi=pi.astype(np.float32),
        n_iter=it,
        converged=converged,
        delta_history=hist,
        labelled_mean_e=float(e[lab].mean()),
        e_min=float(e.min()),
        e_max=float(e.max()),
    )
