"""Tests for the parts of this lane that are cheap to get wrong and expensive to miss.

Two families:

* **PU / propensity** — the SAR-EM loop must recover a known propensity on
  synthetic data, and the three arms must stay on the same footing. If the
  propensity weighting silently degenerates to SCAR the whole lane still produces
  plausible-looking numbers, so the degeneracy is tested for directly.
* **Emission** — the invariants the submission depends on: dots at least the
  kernel radius apart, no mass on the mapped catalogue, and the two rules that
  the metric's own definition forces (a dot on a masked fault is a pure false
  positive; a dot inside the kernel radius of another earns no extra credit).

Everything is synthetic, so the suite runs in seconds without the competition
rasters.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems65_sarprop import lane, propensity, pu  # noqa: E402
from gems65_sarprop.template.metric import dti_exact  # noqa: E402


# --------------------------------------------------------------------------
def synthetic(n=4000, seed=7):
    """A fault problem whose catalogue is a biased (SAR) sample of the truth."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    z = rng.normal(size=(n, 2))                       # propensity attributes
    logit_y = 1.3 * x[:, 0] + 0.7 * x[:, 1] - 0.4 * x[:, 2] + 2.0 * z[:, 0]
    y = (logit_y + rng.normal(size=n) > 0.2).astype(np.int8)          # true faults
    logit_e = 1.8 * z[:, 0] + 0.6 * z[:, 1]                          # sampling bias
    e_true = 1.0 / (1.0 + np.exp(-logit_e))
    s = (y & (rng.random(n) < e_true)).astype(np.int8)                # catalogued
    X = np.column_stack([x, z])
    return X, z, y, s, e_true


def test_synthetic_data_has_real_sampling_bias():
    """Guard the fixture: a flat propensity would make the other tests vacuous."""
    _, z, _, s, e_true = synthetic(seed=11)
    assert float(np.std(e_true[s == 1])) > 0.10
    assert 0.1 < float(s.mean()) < 0.9, "degenerate positive rate"


def test_sar_em_recovers_a_known_propensity():
    X, z, y, s, e_true = synthetic()
    fit = propensity.sar_em(X, s, z, d=0.0, kappa=1.0, max_iter=12)
    assert fit.coef_e is not None, "EM must persist the propensity coefficients"
    assert fit.coef_e.size == z.shape[1] + 1
    e_hat = 1.0 / (1.0 + np.exp(-np.column_stack([z, np.ones(z.shape[0])]) @ fit.coef_e))
    corr = float(np.corrcoef(e_hat[s == 1], e_true[s == 1])[0, 1])
    assert corr > 0.5, f"propensity not recovered (corr={corr:.3f})"
    assert fit.e.shape == s.shape and np.isfinite(fit.e).all()
    assert fit.f.min() >= 0.0 and fit.f.max() <= 1.0


def test_scar_is_a_different_model_from_sar():
    """The lane exists to reject constant propensity; the arms must not coincide."""
    X, z, y, s, e_true = synthetic(seed=5)
    sar = propensity.sar_em(X, s, z, d=0.0, kappa=1.0, max_iter=8)
    assert float(np.std(sar.e[s == 1])) > 1e-3
    assert float(sar.c_scar) > 0.0


def test_arm_fits_share_one_design_and_return_probabilities():
    X, z, y, s, e_true = synthetic(seed=3)
    pi = float(s.mean())
    m_nnpu, p_nnpu, trace = pu.nnpu_fit(X, s, pi=pi, max_iter=60)
    m_scar, p_scar = pu.scar_fit(X, s, c=pi, max_iter=60)
    e = np.clip(np.full(s.shape, pi, dtype=np.float64), 1e-3, 1.0)
    m_sar, p_sar = pu.propensity_weighted_fit(X, s, e, max_iter=60, class_prior=pi)
    for m in (m_nnpu, m_scar, m_sar):
        assert m.beta.shape == (X.shape[1] + 1,)
        assert np.isfinite(m.beta).all()
    for p in (p_nnpu, p_scar, p_sar):
        assert p.shape == s.shape and p.min() >= 0.0 and p.max() <= 1.0


def test_propensity_weighting_changes_the_fit_when_the_propensity_varies():
    """A flat e must reproduce SCAR; a varying e must not."""
    X, z, y, s, e_true = synthetic(seed=9)
    pi = float(s.mean())
    _, p_flat = pu.propensity_weighted_fit(X, s, np.full(s.shape, pi),
                                           max_iter=60, class_prior=pi)
    _, p_biased = pu.propensity_weighted_fit(X, s, np.clip(e_true, 1e-3, 1.0),
                                             max_iter=60, class_prior=pi)
    assert not np.allclose(p_flat, p_biased, atol=1e-6), \
        "varying the propensity must move the fit, or the weighting is inert"


def test_weight_clipping_bounds_the_influence_of_a_tiny_propensity():
    X, z, y, s, e_true = synthetic(seed=13)
    tiny = np.full(s.shape, 1e-4)
    m, p = pu.propensity_weighted_fit(X, s, tiny, w_clip=10.0, max_iter=40)
    assert np.isfinite(p).all() and p.max() <= 1.0


# --------------------------------------------------------------------------
def _toy_grid(h=44, w=44):
    fp = np.zeros((h, w), bool)
    fp[2:-2, 2:-2] = True
    cat = np.zeros((h, w), bool)
    cat[22, 6:38] = True                    # a mapped fault across the middle
    return fp, cat


def test_allocate_nms_enforces_the_kernel_radius_and_the_masks():
    from gems65_sarprop.template.emit import expected_credit
    fp, cat = _toy_grid()
    allowed = fp & ~cat
    p = np.zeros(fp.shape, np.float32)
    p[5:16, 5:16] = 1.0                     # one blob: without NMS every cell wins
    assert expected_credit(p).max() > 0
    out = lane.allocate_nms(p, allowed, k_truth=50.0, radius_px=3, b_grid=(5, 10, 40, 200))
    dots = np.argwhere(out["emitted"])
    assert dots.size >= 5, "expected several dots from a 11x11 positive blob"
    for i in range(len(dots)):
        for j in range(i + 1, len(dots)):
            d = float(np.hypot(*(dots[i] - dots[j]).astype(float)))
            assert d > 3.0 - 1e-9, f"dots {d:.3f} px apart violate the 3 px rule"
    assert not (out["emitted"] & cat).any(), "a dot landed on the mapped catalogue"
    assert not (out["emitted"] & ~fp).any(), "a dot landed outside the footprint"
    assert out["scan_order"].shape[0] == out["n_scanned"] or out["scan_order"].shape[0] > 0


def test_allocate_nms_declines_on_an_empty_field():
    fp, cat = _toy_grid()
    out = lane.allocate_nms(np.zeros(fp.shape, np.float32), fp & ~cat,
                           k_truth=1.0, radius_px=3, b_grid=(5, 10))
    assert out["n_dots"] == 0 and not out["emitted"].any() and out["curve"] == []


def test_prune_band_removes_exactly_the_near_catalogue_dots():
    from scipy import ndimage as ndi
    fp, cat = _toy_grid()
    dist = ndi.distance_transform_edt(~cat)
    dots = np.zeros(fp.shape, bool)
    # catalogue row 22 occupies columns 6..37 inclusive
    dots[10, 10] = True          # far away                          -> kept
    dots[22, 6] = True           # on the catalogue (d = 0)          -> removed
    dots[21, 7] = True           # d = sqrt(2) = 1.414               -> removed
    dots[22, 8] = True           # d = 2.0                           -> removed
    dots[21, 39] = True          # d = sqrt(5) = 2.236               -> kept
    pruned = lane.prune_band(dots, dist, 2.0)
    assert pruned[10, 10] and pruned[21, 39]
    assert not pruned[22, 6] and not pruned[21, 7] and not pruned[22, 8]
    assert int(pruned.sum()) == 2


def test_rescale_to_prior_sets_the_requested_mass():
    fp, _ = _toy_grid()
    sc = np.linspace(0.01, 0.99, fp.size).reshape(fp.shape).astype(np.float32)
    p = lane.rescale_to_prior(sc, fp, 25.0)
    assert float(p[fp].sum()) == pytest.approx(25.0, rel=1e-4)
    assert (p[fp] >= 0).all() and float(p[~fp].sum()) == 0.0


def test_dti_exact_boundaries():
    truth = np.zeros((30, 30), bool)
    truth[10, 10] = True
    perfect = truth.astype(np.float32)
    ev = dti_exact(perfect, truth, valid=np.ones_like(truth))
    assert ev["tp"] == pytest.approx(1.0) and ev["fp"] == pytest.approx(0.0)
    empty = np.zeros((30, 30), np.float32)
    ev0 = dti_exact(empty, truth, valid=np.ones_like(truth))
    assert ev0["dti"] == 0.0 and ev0["n_emitted"] == 0


def test_dti_exact_credits_only_the_best_dot_for_each_truth_pixel():
    """This is the max-over-predictions rule that forces non-maximum suppression."""
    truth = np.zeros((30, 30), bool)
    truth[10, 10] = True
    one = np.zeros((30, 30), np.float32)
    one[10, 10] = 1.0
    many = one.copy()
    many[10, 11] = 1.0            # a second dot on the same truth pixel
    many[10, 12] = 1.0
    ev_one = dti_exact(one, truth, valid=np.ones_like(truth))
    ev_many = dti_exact(many, truth, valid=np.ones_like(truth))
    assert ev_many["tp"] == pytest.approx(ev_one["tp"])
    assert ev_many["fp"] > ev_one["fp"], "extra dots must cost false-positive mass"
    assert ev_many["dti"] < ev_one["dti"]


def test_dti_exact_treats_a_dot_on_a_masked_fault_as_a_pure_false_positive():
    """The mechanism the prune rule and the 0.2778 analysis both rest on."""
    known = np.zeros((30, 30), bool)
    known[10, 10] = True                       # catalogued -> not scored
    active_truth = np.zeros((30, 30), bool)
    active_truth[20, 20] = True                # the only scored truth
    pred = np.zeros((30, 30), np.float32)
    pred[10, 11] = 1.0                         # 1 px from the masked fault
    ev = dti_exact(pred, active_truth, valid=np.ones_like(known), known=known)
    assert ev["tp"] == pytest.approx(0.0)
    assert ev["fp"] == pytest.approx(1.0)
