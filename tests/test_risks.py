"""Verification of the SAR risk algebra, the nnPU baseline and the SAR EM.

These tests are the anti-hallucination layer: every equation used by the lane is
checked against a Monte-Carlo ground truth generated from a known data-generating
process, not against a citation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import propensity as prop          # noqa: E402
from gems65.risks import (W_CLIP, MLP, loss_l0, loss_l1, nnpu_risk, sar_risk,  # noqa: E402
                          sigmoid, train)
from gems57 import metric                      # noqa: E402


# ---------------------------------------------------------------------------
# 1. the official metric: worked example from the competition problem page
# ---------------------------------------------------------------------------
def test_official_worked_example():
    """TP_w=3.00, FP_w=1.89, FN_w=2.00 -> 0.60 (competition page 967).

    The exact value of the published formula is 3/(3 + 0.2*1.89 + 0.8*2) =
    0.6026516674, which the problem page rounds to 0.60.  Both are asserted so
    the rounding is explicit rather than fudged.
    """
    exact = 3.0 / (3.0 + 0.2 * 1.89 + 0.8 * 2.0)
    assert abs(metric.dti_from_components(3.00, 1.89, 2.00) - exact) < 1e-12
    assert round(metric.dti_from_components(3.00, 1.89, 2.00), 2) == 0.60


def test_metric_matches_bruteforce():
    rng = np.random.default_rng(0)
    truth = np.zeros((12, 12), bool)
    truth[rng.integers(0, 12, 8), rng.integers(0, 12, 8)] = True
    pred = np.zeros((12, 12))
    ys, xs = rng.integers(0, 12, 15), rng.integers(0, 12, 15)
    pred[ys, xs] = rng.random(15)
    a = metric.dti_exact(pred, truth)
    b = metric.dti_bruteforce(pred, truth)
    assert abs(a["dti"] - b["dti"]) < 1e-9
    assert abs(a["tp"] - b["tp"]) < 1e-9
    assert abs(a["fp"] - b["fp"]) < 1e-9


# ---------------------------------------------------------------------------
# 2. losses / sigmoid sanity
# ---------------------------------------------------------------------------
def test_losses():
    z = np.array([-20.0, -1.0, 0.0, 1.0, 20.0])
    p = sigmoid(z)
    assert np.allclose(loss_l1(z), -np.log(np.clip(p, 1e-300, 1)), atol=1e-9)
    assert np.allclose(loss_l0(z), -np.log(np.clip(1 - p, 1e-300, 1)), atol=1e-9)
    assert np.all(np.isfinite(loss_l1(z))) and np.all(np.isfinite(loss_l0(z)))


# ---------------------------------------------------------------------------
# 3. SAR risk estimator is unbiased for the true risk when e(x) is not clipped
# ---------------------------------------------------------------------------
def _true_g(X):
    """The class model of :func:`_simulate` (so the identified product g*e is testable)."""
    return sigmoid(1.4 * X[:, 0] - 1.1 * X[:, 1] + 0.7 * X[:, 2] - 0.4)


def _simulate(rng, n_pop=400_000, d=3, pi=0.06):
    """Known DGP: y ~ Bernoulli(pi) with a class-conditional mean shift, and a
    covariate-dependent propensity e(x) in (0.05, 0.95)."""
    X = rng.normal(size=(n_pop, d))
    g = sigmoid(1.4 * X[:, 0] - 1.1 * X[:, 1] + 0.7 * X[:, 2] - 0.4)
    y = (rng.random(n_pop) < pi * g / g.mean()).astype(int)
    e = np.clip(sigmoid(1.8 * X[:, 0] + 1.2 * X[:, 2] - 0.6), 0.05, 0.95)
    s = ((y == 1) & (rng.random(n_pop) < e)).astype(int)
    return X, y, s, e


def test_sar_risk_unbiased_no_clipping():
    """R_SAR estimated from (labelled, unlabelled) must equal the true risk."""
    rng = np.random.default_rng(7)
    X, y, s, e = _simulate(rng)
    # a fixed "model": z = f(x) is a deterministic function of x
    z = 0.8 * X[:, 0] - 0.5 * X[:, 1] + 0.2
    l1, l0 = loss_l1(z), loss_l0(z)
    true_risk = float(np.mean(np.where(y == 1, l1, l0)))

    lab = s == 1
    unl = s == 0
    rho = float(s.mean())            # P(s=1): observable, no unobservable quantity
    est = sar_risk(z[lab], z[unl], e[lab], rho, clip=1e9)  # no clipping
    # Monte-Carlo error at n=4e5 is ~1e-3
    assert abs(est["risk"] - true_risk) < 4e-3, (est["risk"], true_risk)


def test_wrong_normaliser_pi_ebar_is_detected():
    """The pi*E[e] normaliser is biased when g and e correlate; rho is not.

    Regression guard for the error recorded in risks.py's docstring.
    """
    rng = np.random.default_rng(29)
    X, y, s, e = _simulate(rng, n_pop=400_000, pi=0.06)
    g = sigmoid(1.4 * X[:, 0] - 1.1 * X[:, 1] + 0.7 * X[:, 2] - 0.4)
    z = 0.8 * X[:, 0] - 0.5 * X[:, 1] + 0.2
    l1, l0 = loss_l1(z), loss_l0(z)
    true_risk = float(np.mean(np.where(y == 1, l1, l0)))
    lab, unl = s == 1, s == 0
    good = sar_risk(z[lab], z[unl], e[lab], float(s.mean()), clip=1e9)["risk"]
    # reproduce the retired estimator by scaling with pi*E[e] instead of rho
    w = 1.0 / e[lab]
    v = (1.0 - e[lab]) / e[lab]
    a = float(y.mean()) * float(e.mean())
    bad = a * np.mean(w * l1[lab] - v * l0[lab]) + (1 - a) * np.mean(l0[unl])
    assert abs(good - true_risk) < 4e-3
    assert abs(bad - true_risk) > 5e-3, "the retired normaliser should be measurably biased"


def test_scar_reduction_matches_true_risk():
    """With e(x) = e0 constant the SAR risk reduces to the SCAR identity."""
    rng = np.random.default_rng(11)
    n = 300_000
    X = rng.normal(size=(n, 2))
    pi = 0.05
    y = (rng.random(n) < pi).astype(int)
    e0 = 0.3
    s = ((y == 1) & (rng.random(n) < e0)).astype(int)
    z = X[:, 0] - 0.3 * X[:, 1]
    l1, l0 = loss_l1(z), loss_l0(z)
    true_risk = float(np.mean(np.where(y == 1, l1, l0)))
    lab, unl = s == 1, s == 0
    est = sar_risk(z[lab], z[unl], np.full(int(lab.sum()), e0), float(s.mean()), clip=1e9)
    assert abs(est["risk"] - true_risk) < 6e-3


def test_nnpu_is_unbiased_on_the_mixture_it_assumes():
    """Kiryo's nnPU risk is exact when the unlabelled pool is the full mixture.

    The published estimator treats U ~ (1-pi)p0 + pi p1 (labelled positives are
    NOT removed from U).  Checked against the true risk on that population.
    """
    rng = np.random.default_rng(3)
    n = 400_000
    pi = 0.05
    X = rng.normal(size=(n, 2))
    g = sigmoid(1.2 * X[:, 0] - 0.8 * X[:, 1])
    y = (rng.random(n) < pi * g / g.mean()).astype(int)
    z = 0.7 * X[:, 0] + 0.2
    l1, l0 = loss_l1(z), loss_l0(z)
    true_risk = float(np.mean(np.where(y == 1, l1, l0)))
    # L = a labelled-rate subsample of the positives; U = the whole population
    e0 = 0.4
    lab = (y == 1) & (rng.random(n) < e0)
    est = nnpu_risk(z[lab], z, pi)
    assert est["non_negative_active"] is False
    assert abs(est["risk"] - true_risk) < 5e-3, (est["risk"], true_risk)


def test_nnpu_is_biased_when_labelled_positives_are_removed():
    """Documented limitation of the baseline: removing L from U biases nnPU.

    This is why the lane reports the nnPU arm as a *baseline* rather than as an
    unbiased risk, and why the SAR arm uses the rho normaliser instead.
    """
    rng = np.random.default_rng(31)
    n = 400_000
    pi, e0 = 0.05, 0.4
    X = rng.normal(size=(n, 2))
    g = sigmoid(1.2 * X[:, 0] - 0.8 * X[:, 1])
    y = (rng.random(n) < pi * g / g.mean()).astype(int)
    z = 0.7 * X[:, 0] + 0.2
    l1, l0 = loss_l1(z), loss_l0(z)
    true_risk = float(np.mean(np.where(y == 1, l1, l0)))
    lab = (y == 1) & (rng.random(n) < e0)
    est = nnpu_risk(z[lab], z[~lab], pi)     # U excludes the labelled positives
    assert abs(est["risk"] - true_risk) > 1e-3, "expected the published-baseline bias"


def test_clipping_is_reported():
    rng = np.random.default_rng(5)
    z = rng.normal(size=5000)
    e = rng.uniform(0.01, 1.0, size=5000)
    r = sar_risk(z, z, e, 0.05, clip=W_CLIP)
    assert r["frac_clipped_w"] > 0.0
    assert r["w_max"] <= W_CLIP + 1e-12


# ---------------------------------------------------------------------------
# 4. gradients: analytic vs numerical, for both arms
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arm", ["sar", "nnpu"])
def test_gradients_match_finite_differences(arm):
    from gems65.risks import _dz_nnpu, _dz_sar
    rng = np.random.default_rng(2)
    n_l, n_u, d = 40, 60, 3
    Xl, Xu = rng.normal(size=(n_l, d)), rng.normal(size=(n_u, d))
    e_lab = rng.uniform(0.1, 1.0, n_l)
    pi, rho = 0.06, float(n_l / (n_l + n_u))
    m = MLP(n_in=d, n_hidden=5, seed=1)

    def risk_fn():
        zl, zu = m.logits(Xl), m.logits(Xu)
        if arm == "sar":
            return sar_risk(zl, zu, e_lab, rho, W_CLIP)["risk"]
        return nnpu_risk(zl, zu, pi)["risk"]

    # analytic
    pre_l, h_l, z_l = m._forward(Xl)
    pre_u, h_u, z_u = m._forward(Xu)
    if arm == "sar":
        dz_l, dz_u = _dz_sar(z_l, z_u, e_lab, rho, W_CLIP)
    else:
        dz_l, dz_u = _dz_nnpu(z_l, z_u, pi)
    gl = m._backward(Xl, pre_l, h_l, dz_l * z_l.size)
    gu = m._backward(Xu, pre_u, h_u, dz_u * z_u.size)
    analytic = [a + b for a, b in zip(gl, gu)]

    # numerical on a few entries
    eps = 1e-6
    for arr_idx, name in ((0, "W1"), (2, "W2")):
        A = getattr(m, name)
        flat = A.ravel()
        for k in (0, min(3, flat.size - 1)):
            orig = flat[k]
            flat[k] = orig + eps
            rp = risk_fn()
            flat[k] = orig - eps
            rm = risk_fn()
            flat[k] = orig
            num = (rp - rm) / (2 * eps)
            ana = analytic[arr_idx].ravel()[k]
            assert abs(num - ana) < 3e-3 * max(1.0, abs(ana)), (arm, name, k, num, ana)


# ---------------------------------------------------------------------------
# 5. the SAR EM recovers a known covariate-dependent propensity
# ---------------------------------------------------------------------------
def test_em_recovers_known_propensity():
    rng = np.random.default_rng(17)
    X, y, s, e = _simulate(rng, n_pop=120_000, pi=0.06)
    pi_true = float(y.mean())
    lab = s == 1
    g_true = _true_g(X[~lab])
    Xl, Xu = X[lab], X[~lab]
    fit = prop.em_propensity(Xl, Xu, basis_kind="linear", n_iter=25)
    e_hat_unl = fit.predict_e(Xu)
    # The EM identifies only the product g*e, so its propensity ordering can come
    # out MIRRORED (tests/test_anchor.py pins the direction with a second public
    # inventory and measures the near-equal observed likelihoods of both branches).
    # What the estimator guarantees alone is the magnitude of the ordering and the
    # sign/size of the identified product.
    r = float(np.corrcoef(e_hat_unl, e[~lab])[0, 1])
    assert abs(r) > 0.6, f"EM propensity correlates only {r:.3f} with the truth"
    g_hat = fit.model_g.predict_proba(fit.Xb_unl)[:, 1]
    assert np.corrcoef(g_hat * e_hat_unl, np.clip(pi_true * g_true / g_true.mean() * e[~lab],
                                                 1e-9, 1 - 1e-9))[0, 1] > 0.5
    assert 0.0 < fit.pi < 0.5
    assert fit.ebar > 0


def test_em_scar_fallback_is_constant():
    rng = np.random.default_rng(19)
    X, y, s, e = _simulate(rng, n_pop=60_000, pi=0.05)
    lab = s == 1
    fit = prop.em_propensity(X[lab], X[~lab], scar=True)
    assert fit.model_e is None
    assert np.allclose(fit.e_labelled, fit.ebar)
    assert fit.basis_kind == "SCAR-constant"


# ---------------------------------------------------------------------------
# 6. training moves the risk in the right direction
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arm", ["sar", "nnpu"])
def test_training_reduces_risk(arm):
    rng = np.random.default_rng(23)
    X, y, s, e = _simulate(rng, n_pop=60_000, pi=0.06)
    lab = s == 1
    Xl, Xu = X[lab][:5000], X[~lab][:20000]
    Xs, mu, sd = None, X.mean(0), X.std(0)
    Xl = (Xl - mu) / sd
    Xu = (Xu - mu) / sd
    m = MLP(n_in=X.shape[1], n_hidden=16, seed=4)
    e_lab = np.clip(e[lab][:5000], 0.05, 1.0)
    pi = float(y.mean())
    rho = float(lab.mean())

    def risk():
        zl, zu = m.logits(Xl), m.logits(Xu)
        return (sar_risk(zl, zu, e_lab, rho, W_CLIP)["risk"] if arm == "sar"
                else nnpu_risk(zl, zu, pi)["risk"])

    r0 = risk()
    train(m, Xl, Xu, arm=arm, rho=rho, pi=pi, e_lab=e_lab,
          epochs=40, lr=1e-2, batch=512, seed=4)
    r1 = risk()
    assert r1 < r0, (arm, r0, r1)
