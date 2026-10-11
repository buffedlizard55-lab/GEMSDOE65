"""Regression test: the SAR EM must estimate population quantities from a
subsampled unlabelled pool.

Caught in the smoke run of this lane: with a 20,000-row subsample of a
5,116,066-pixel unlabelled population the EM returned ``pi = 0.867`` (and
``e ~ 0.83``) because every unlabelled row was treated as one population
member.  The true pi in that simulation is ~0.02.  With ``u_weight`` set to the
population/subsample ratio the estimate is correct.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import propensity as prop          # noqa: E402


def _population(rng, n=200_000, d=4, pi=0.03):
    X = rng.normal(size=(n, d))
    g = prop.sigmoid(1.5 * X[:, 0] - 1.0 * X[:, 1] + 0.6 * X[:, 2])
    y = (rng.random(n) < pi * g / g.mean()).astype(int)
    e = np.clip(prop.sigmoid(1.6 * X[:, 0] + 1.0 * X[:, 3] - 0.5), 0.05, 0.95)
    s = ((y == 1) & (rng.random(n) < e)).astype(int)
    return X, y, s, e


def test_pi_from_subsample_matches_population():
    rng = np.random.default_rng(101)
    X, y, s, e = _population(rng)
    pi_true = float(y.mean())
    lab = s == 1
    unl_idx = np.flatnonzero(~lab)
    sub = rng.choice(unl_idx, size=6_000, replace=False)
    Xl, Xu = X[lab], X[sub]
    w = unl_idx.size / float(sub.size)

    fit_w = prop.em_propensity(Xl, Xu, u_weight=w, n_unl_population=float(unl_idx.size),
                               n_iter=12, tol=1e-4)
    fit_bad = prop.em_propensity(Xl, Xu, u_weight=1.0, n_iter=12, tol=1e-4)

    assert abs(fit_w.pi - pi_true) < 0.02, (fit_w.pi, pi_true)
    # the unweighted version must be demonstrably wrong (the retired behaviour)
    assert fit_bad.pi > pi_true + 0.1, (fit_bad.pi, pi_true)
    # propensity must be a probability of being labelled given a fault: < 1
    assert 0.0 < fit_w.ebar < 1.0
    # The EM's propensity is only identified up to the mirror (see
    # tests/test_anchor.py::test_em_direction_is_not_identified): assert that the
    # ordering is recovered in MAGNITUDE and that the product g*e -- which is what
    # the observed-data likelihood depends on -- is recovered in sign and size.
    e_hat = fit_w.predict_e(Xu)
    assert abs(np.corrcoef(e_hat, e[sub])[0, 1]) > 0.5
    g_hat = fit_w.model_g.predict_proba(fit_w.Xb_unl)[:, 1]
    prod_hat = g_hat * e_hat
    prod_true = np.clip((pi_true * _g(X[sub]) / _g(X).mean()) * e[sub], 1e-6, 1 - 1e-6)
    assert np.corrcoef(prod_hat, prod_true)[0, 1] > 0.5


def _g(X):
    return prop.sigmoid(1.5 * X[:, 0] - 1.0 * X[:, 1] + 0.6 * X[:, 2])


def test_full_sample_and_subsample_agree():
    """Weighted subsampling must not change the answer much vs the full pool."""
    rng = np.random.default_rng(202)
    X, y, s, e = _population(rng, n=120_000, pi=0.04)
    lab = s == 1
    Xl, Xu_full = X[lab], X[~lab]
    fit_full = prop.em_propensity(Xl, Xu_full, n_iter=10, tol=1e-4)
    sub = rng.choice(Xu_full.shape[0], size=8_000, replace=False)
    fit_sub = prop.em_propensity(Xl, Xu_full[sub], u_weight=Xu_full.shape[0] / 8_000,
                                 n_unl_population=float(Xu_full.shape[0]),
                                 n_iter=10, tol=1e-4)
    assert abs(fit_full.pi - fit_sub.pi) < 0.02, (fit_full.pi, fit_sub.pi)
    assert abs(fit_full.ebar - fit_sub.ebar) < 0.10, (fit_full.ebar, fit_sub.ebar)
