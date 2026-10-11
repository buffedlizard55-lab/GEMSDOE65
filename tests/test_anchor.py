"""The propensity's DIRECTION is identified only by a second inventory.

These tests pin down the identifiability finding that drives the whole lane:

1. the Bekker & Davis EM on PU data alone recovers the *product* g(x)e(x) but its
   propensity ordering can be mirrored -- and the mirrored solution fits the
   observed data essentially as well (a formal non-identifiability demonstration);
2. :func:`gems65.anchor.fit_anchor` recovers the true propensity ordering from a
   second, independent inventory of the same faults, for every scale parameter c;
3. the selection rule used by the lane driver (use the EM only when its ordering
   agrees with the anchor) therefore picks the correct branch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import propensity as prop          # noqa: E402
from gems65.anchor import C_GRID, e_from_q, fit_anchor   # noqa: E402


def _simulate(rng, n=200_000, d=4, pi=0.06, c_ref=0.5):
    """Two inventories of the same fault population, both covariate-biased.

    ``s``  = catalogue (first inventory) label;  ``s2`` = reference inventory.
    The reference inventory is *only* used to anchor, never as a positive.
    """
    X = rng.normal(size=(n, d))
    g = prop.sigmoid(1.4 * X[:, 0] - 1.1 * X[:, 1] + 0.7 * X[:, 2] - 0.4)
    y = (rng.random(n) < pi * g / g.mean()).astype(int)
    e = np.clip(prop.sigmoid(1.8 * X[:, 0] + 1.2 * X[:, 2] - 0.6), 0.05, 0.95)
    s = ((y == 1) & (rng.random(n) < e)).astype(int)
    s2 = ((y == 1) & (rng.random(n) < c_ref)).astype(int)
    return X, y, s, s2, e, g


def test_em_direction_is_not_identified():
    """Both branches fit the observed data; the EM alone cannot choose."""
    rng = np.random.default_rng(17)
    X, y, s, s2, e, g = _simulate(rng)
    lab = s == 1
    fits = [prop.em_propensity(X[lab], X[~lab], basis_kind="linear", n_iter=25,
                               init=init, pi_init=pi0)
            for init, pi0 in (("flat", 0.06), ("scar_identity", None))]
    corr = [float(np.corrcoef(f.predict_e(X[~lab]), e[~lab])[0, 1]) for f in fits]
    ll = [prop.observed_loglik(f.model_g.predict_proba(f.Xb_lab)[:, 1],
                               f.model_g.predict_proba(f.Xb_unl)[:, 1],
                               f.e_labelled, f.predict_e(X[~lab])) for f in fits]
    # a correct-direction and a mirrored branch both occur ...
    assert max(corr) > 0.5, corr
    assert min(corr) < -0.5, corr
    # ... and their observed-data log-likelihoods are within ~2 % of each other,
    # i.e. the data cannot separate them.  This is the non-identifiability claim.
    assert abs(max(ll) - min(ll)) < 0.02 * abs(max(ll)), ll


def test_anchor_recovers_true_propensity_direction():
    """A second inventory fixes the sign for every sensitivity value of c."""
    rng = np.random.default_rng(17)
    X, y, s, s2, e, g = _simulate(rng)
    cat = np.flatnonzero(s == 1)
    ref = np.flatnonzero((s2 == 1) & (s == 0))     # reference inventory, off-catalogue
    assert cat.size > 1000 and ref.size > 1000
    for c in C_GRID:
        a = fit_anchor(X[cat], X[ref], c=c)
        e_hat = a.predict_e(X[~(s == 1)])
        r = float(np.corrcoef(e_hat, e[~(s == 1)])[0, 1])
        assert r > 0.6, f"c={c}: anchored propensity correlates only {r:.3f}"
        # the anchor must order the two inventories the right way round
        assert a.e_on_catalogue_mean > a.e_on_reference_mean


def test_e_from_q_is_monotone_and_inverts():
    q = np.linspace(1e-6, 1 - 1e-6, 999)
    for c in C_GRID:
        e = e_from_q(q, c)
        assert np.all(np.diff(e) > 0), c
        assert np.all((e > 0) & (e < 1))
        # round trip: q must equal e / (e + c(1-e))
        assert np.allclose(e / (e + c * (1 - e)), q, atol=1e-6), c
    for bad in (0.0, -0.1, 1.5):
        try:
            e_from_q(q, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"c={bad} must be rejected")


def test_selection_rule_prefers_the_agreeing_branch():
    """The driver's rule (Spearman(e_EM, q_anchor) > 0) must pick the true branch."""
    rng = np.random.default_rng(23)
    X, y, s, s2, e, g = _simulate(rng, n=120_000)
    cat = np.flatnonzero(s == 1)
    ref = np.flatnonzero((s2 == 1) & (s == 0))
    a = fit_anchor(X[cat], X[ref], c=1.0)
    X_two = np.vstack([X[cat], X[ref]])
    q_two = a.model.predict_proba(prop.basis(X_two, "linear"))[:, 1]
    picks = []
    for init, pi0 in (("flat", 0.06), ("scar_identity", None), ("flat", 0.15)):
        f = prop.em_propensity(X[cat], X[~(s == 1)], basis_kind="linear", n_iter=25,
                               init=init, pi_init=pi0)
        rho = float(spearmanr(f.predict_e(X_two), q_two).statistic)
        chosen = "em" if rho > 0 else "anchor"
        e_sel = f.predict_e(X_two) if chosen == "em" else a.predict_e(X_two)
        picks.append((init, pi0, rho, chosen,
                      float(np.corrcoef(e_sel, e[np.concatenate([cat, ref])])[0, 1])))
    for init, pi0, rho, chosen, corr in picks:
        assert corr > 0.3, (init, pi0, rho, chosen, corr)
