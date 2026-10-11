"""Verification tests for the duplicate / lane-drift detector.

The most important test in this repo after the metric: a FALSE lane-drift signal stops the lane and
destroys a good submission, while a MISSED one ships a duplicate.  IR-65-003 records that the first
implementation produced rho = 0.9717 for two statistically independent binary dot fields.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import dupcheck as DC
from gems65 import grid as G


def test_spearman_independent_dot_fields_is_zero() -> None:
    """Two independent 0.73%-density binary fields (the real submission regime) must give rho ~ 0."""
    rng = np.random.default_rng(0)
    n = 2_000_000
    a = (rng.random(n) < 0.00735).astype(np.float32)
    b = (rng.random(n) < 0.00735).astype(np.float32)
    mask = np.ones(n, bool)
    rho = DC.spearman_subsample(a, b, mask, n=400_000, seed=1)
    assert abs(rho) < 0.02, f"independent fields gave rho={rho:.4f} (IR-65-003 regression)"
    print(f"ok  test_spearman_independent_dot_fields_is_zero (rho={rho:+.4f})")


def test_spearman_matches_scipy() -> None:
    from scipy.stats import spearmanr
    rng = np.random.default_rng(4)
    n = 200_000
    x = np.where(rng.random(n) < 0.1, rng.random(n), 0.0).astype(np.float32)
    y = np.clip(0.6 * x + 0.4 * rng.random(n), 0, 1).astype(np.float32)
    mask = np.ones(n, bool)
    mine = DC.spearman_subsample(x, y, mask, n=n)
    ref = float(spearmanr(x, y).statistic)
    assert abs(mine - ref) < 1e-6, (mine, ref)
    print(f"ok  test_spearman_matches_scipy (mine={mine:.6f} scipy={ref:.6f})")


def test_spearman_identical_is_one() -> None:
    rng = np.random.default_rng(9)
    n = 100_000
    x = (rng.random(n) < 0.01).astype(np.float32)
    rho = DC.spearman_subsample(x, x.copy(), np.ones(n, bool), n=n)
    assert abs(rho - 1.0) < 1e-9, rho
    print(f"ok  test_spearman_identical_is_one")


def test_dot_overlap_self_is_one_and_shifted_decays() -> None:
    """Deterministic, well-separated dots (spacing 20 px) so chance proximity cannot contaminate.

    The first version of this test used 300 uniform random dots in a 200x200 grid: at that density
    ~19% of candidate dots fall within 3 px of SOME registry dot by chance alone, so the '4 px shift
    -> 0 overlap' assertion was wrong, not the code.
    """
    H = W = 200
    ys, xs = np.meshgrid(np.arange(10, H - 10, 20), np.arange(10, W - 10, 20), indexing="ij")
    ys, xs = ys.ravel(), xs.ravel()
    m = np.zeros((H, W), bool)
    m[ys, xs] = True
    r = DC.dot_overlap(m.astype(np.float32), m.astype(np.float32))
    assert abs(r["frac_candidate_dots_within_3px_of_registry"] - 1.0) < 1e-12, r
    assert r["exact_coincident_dots"] == int(m.sum())
    m2 = np.zeros_like(m)
    m2[ys + 4, xs] = True          # 4 px shift > 3 px radius, and no chance neighbours exist
    r2 = DC.dot_overlap(m.astype(np.float32), m2.astype(np.float32))
    assert r2["frac_candidate_dots_within_3px_of_registry"] == 0.0, r2
    assert r2["exact_coincident_dots"] == 0
    m3 = np.zeros_like(m)
    m3[ys + 3, xs] = True          # exactly at the radius -> counted (<= is the protocol reading)
    r3 = DC.dot_overlap(m.astype(np.float32), m3.astype(np.float32))
    assert r3["frac_candidate_dots_within_3px_of_registry"] == 1.0, r3
    print("ok  test_dot_overlap_self_is_one_and_shifted_decays (<=3 px inclusive, 4 px excluded)")


def test_verdict_flags_drift_at_the_protocol_thresholds() -> None:
    recs = [
        {"status": "compared", "registry": "a", "spearman_surface": 0.95,
         "frac_candidate_dots_within_3px_of_registry": 0.10, "identical_bytes": False},
        {"status": "compared", "registry": "b", "spearman_surface": 0.30,
         "frac_candidate_dots_within_3px_of_registry": 0.80, "identical_bytes": False},
        {"status": "compared", "registry": "c", "spearman_surface": 0.20,
         "frac_candidate_dots_within_3px_of_registry": 0.20, "identical_bytes": False},
    ]
    for r in recs:
        r["DUPLICATE_rho_gt_0.90"] = r["spearman_surface"] > 0.90
        r["DUPLICATE_overlap_gt_70pct"] = r["frac_candidate_dots_within_3px_of_registry"] > 0.70
        r["lane_drift"] = bool(r["identical_bytes"] or r["DUPLICATE_rho_gt_0.90"]
                               or r["DUPLICATE_overlap_gt_70pct"])
    v = DC.verdict(recs)
    assert v["lane_drift_detected"] is True
    assert sorted(v["lane_drift_against"]) == ["a", "b"]
    assert v["unique_submission"] is False
    assert abs(v["max_spearman_surface"] - 0.95) < 1e-12
    assert abs(v["max_dot_overlap_3px"] - 0.80) < 1e-12
    print("ok  test_verdict_flags_drift_at_the_protocol_thresholds (rho>0.90 OR overlap>70%)")


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    fails = 0
    for fn in ALL:
        try:
            fn()
        except Exception as exc:
            fails += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(ALL) - fails}/{len(ALL)} dupcheck tests passed")
    raise SystemExit(1 if fails else 0)
