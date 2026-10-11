"""Anchoring the SAR propensity with a second public fault inventory.

Why this module exists
----------------------
``tests/test_risks.py`` and ``tests/test_propensity_subsample.py`` demonstrate
numerically what the brief warns about: **the propensity is not identified from
PU data alone.**  On synthetic data with a known ``e(x)``, the Bekker & Davis EM
returns solutions whose ``e`` correlates ``-0.94`` with the truth (a mirrored
factorisation) and solutions whose ``e`` correlates ``+0.90``, and their
observed-data log-likelihoods differ by ~1 %.  The reason is structural:

    L_observed = sum_L log(g(x) e(x)) + sum_U log(1 - g(x) e(x))

depends on the *product* ``g(x) e(x) = P(s=1|x)`` only, so any re-factorisation
of the same product fits equally well.  The parametric class does not exclude the
mirror (a logistic ``e`` mirrored about 0.5 is still logistic).

The anchor
----------
Two independent public fault inventories of the same ground are available in
this sandbox, both hash-pinned:

* the competition catalogue ``labels.tif`` / ``existing_faults.tif`` -- verified
  here to be the USGS QFaults/INGENIOUS compilation: 96.54 % of its pixels are
  covered by rasterised QFaults trace segments at median distance 0 px
  (max 1 px, ``evidence/catalogue_identity.json``);
* the mirrored state-geologic-map fault raster ``sgmc_faults_100m.tif``, whose
  pixels overlap the catalogue by only 4.5 %.

Treat the state-geologic-map pixels that lie more than 300 m from the catalogue
(``SGoff``) as a *reference sample of faults the catalogue missed*.  For a fault
pixel ``x`` let ``e(x)`` be the catalogue propensity and ``c`` the reference
inventory's propensity.  Then

    q(x) = P(x in catalogue | x in catalogue U SGoff) = e / (e + c (1 - e))

and inverting gives a **one-parameter family**

    e(x; c) = c q(x) / (1 - q(x) + c q(x)).                                   (*)

``q`` is fitted by logistic regression on the two inventories' pixels, so the
*ordering* of ``e`` is identified by data; ``c`` (the completeness of the
reference inventory) sets only the scale and is swept as the sensitivity
analysis the brief asks for.  ``e`` is monotone increasing in ``q`` for every
``c in (0, 1]``, which is asserted in the tests.

Assumptions, stated so they can be attacked
------------------------------------------
A1. ``SGoff`` is a fair sample of faults in environments where the catalogue is
    incomplete (i.e. the reference inventory's propensity ``c`` is constant in
    ``x``).  If the state maps are themselves biased -- they are bedrock-
    exposure maps, so they under-sample buried basin faults -- then ``c`` is not
    constant and (*) over-corrects toward exposed ground.  This is the named
    non-fault process that could mimic the hypothesis.
A2. The two inventories select independently given ``x``.
A3. Rasterisation at 100 m does not systematically move one inventory relative
    to the other (checked: median catalogue-to-QFaults-trace distance 0 px).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression

from .propensity import basis

C_GRID = (0.25, 0.5, 1.0)     # reference-inventory completeness sensitivity


def e_from_q(q: np.ndarray, c: float) -> np.ndarray:
    """Invert ``q = e/(e + c(1-e))`` -> ``e = c q / (1 - q + c q)`` (equation *)."""
    q = np.clip(np.asarray(q, float), 1e-9, 1 - 1e-9)
    if not 0.0 < c <= 1.0:
        raise ValueError("c must be in (0, 1]")
    return c * q / (1.0 - q + c * q)


@dataclass
class AnchorFit:
    model: LogisticRegression
    basis_kind: str
    c: float
    n_catalogue: int
    n_reference: int
    q_on_catalogue_mean: float
    q_on_reference_mean: float
    e_on_catalogue_mean: float
    e_on_reference_mean: float
    spearman_q_vs_covariates: dict

    def predict_e(self, X: np.ndarray, c: float | None = None) -> np.ndarray:
        cc = self.c if c is None else c
        Xb = basis(np.asarray(X, float), self.basis_kind)
        return e_from_q(self.model.predict_proba(Xb)[:, 1], cc)

    def predict_q(self, X: np.ndarray) -> np.ndarray:
        Xb = basis(np.asarray(X, float), self.basis_kind)
        return self.model.predict_proba(Xb)[:, 1]


def fit_anchor(X_cat: np.ndarray, X_ref: np.ndarray, *, c: float = 1.0,
               basis_kind: str = "linear", C: float = 1.0,
               covariate_names: tuple[str, ...] = ()) -> AnchorFit:
    """Fit ``q(x)`` = P(catalogue | catalogue U reference, x) and invert to ``e``."""
    from scipy.stats import spearmanr

    X_cat = np.asarray(X_cat, float)
    X_ref = np.asarray(X_ref, float)
    if X_cat.shape[1] != X_ref.shape[1]:
        raise ValueError("covariate width mismatch")
    if X_cat.shape[0] < 50 or X_ref.shape[0] < 50:
        raise ValueError("need at least 50 pixels in each inventory sample")
    X = np.vstack([X_cat, X_ref])
    y = np.concatenate([np.ones(X_cat.shape[0]), np.zeros(X_ref.shape[0])])
    Xb = basis(X, basis_kind)
    m = LogisticRegression(C=C, max_iter=3000, solver="lbfgs")
    m.fit(Xb, y)
    q = m.predict_proba(Xb)[:, 1]
    e = e_from_q(q, c)
    n_cat = X_cat.shape[0]
    sp = {}
    for j, name in enumerate(covariate_names or tuple(f"x{i}" for i in range(X.shape[1]))):
        sp[name] = float(spearmanr(q, X[:, j]).statistic)
    return AnchorFit(model=m, basis_kind=basis_kind, c=c, n_catalogue=n_cat,
                     n_reference=int(X_ref.shape[0]),
                     q_on_catalogue_mean=float(q[:n_cat].mean()),
                     q_on_reference_mean=float(q[n_cat:].mean()),
                     e_on_catalogue_mean=float(e[:n_cat].mean()),
                     e_on_reference_mean=float(e[n_cat:].mean()),
                     spearman_q_vs_covariates=sp)
