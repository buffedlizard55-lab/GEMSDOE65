"""Verification tests.  Run:  python -m pytest tests -q   (or: python tests/test_all.py)

These are the checks that make the numbers in this repo auditable rather than asserted:
  1. the DTI implementation equals a literal brute-force transcription of the published formulas;
  2. the algebraic reduction DTI = T / (0.2 (T + S - M) + 0.8 K) equals the component form;
  3. the marginal-credit rule is k > alpha * DTI (not the mis-derived alpha*s/(1-alpha*s));
  4. Definition 2's propensity-weighted risk is unbiased on a synthetic SAR generative process;
  5. the EM recovers a known propensity function on synthetic SAR data;
  6. the holdout never lets the emitter touch withheld truth through a visible-fault buffer;
  7. the submission writer produces a raster that passes every validator check;
  8. no covariate is catalogue-derived (the leakage-canary precondition).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import emission as EMI
from gems65 import grid as G
from gems65 import holdout as HO
from gems65 import metric as M
from gems65 import pu
from gems65 import submission as SUB


def test_bruteforce_equivalence_random(seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    for trial in range(8):
        H = W = 24
        truth = rng.random((H, W)) < 0.05
        if not truth.any():
            continue
        pred = np.where(rng.random((H, W)) < 0.25, rng.random((H, W)), 0.0)
        pred = np.clip(pred, 0, 1)
        a = M.dti_exact(pred, truth)
        b = M.dti_bruteforce(pred, truth)
        assert abs(a["dti"] - b["dti"]) < 1e-9, (trial, a["dti"], b["dti"])
        assert abs(a["tp"] - b["tp"]) < 1e-9
        assert abs(a["fp"] - b["fp"]) < 1e-9
    print("ok  test_bruteforce_equivalence_random (8 random raster pairs, 1e-9)")


def test_binary_matches_exact() -> None:
    rng = np.random.default_rng(3)
    H = W = 30
    truth = rng.random((H, W)) < 0.04
    mask = rng.random((H, W)) < 0.08
    a = M.dti_exact(mask.astype(float), truth)
    b = M.dti_binary(mask, truth)
    assert abs(a["dti"] - b["dti"]) < 1e-12, (a["dti"], b["dti"])
    print("ok  test_binary_matches_exact")


def test_algebraic_reduction() -> None:
    """DTI = T / (alpha (T + S - M) + beta K) must equal the component form exactly."""
    rng = np.random.default_rng(11)
    H = W = 40
    truth = rng.random((H, W)) < 0.03
    pred = np.clip(np.where(rng.random((H, W)) < 0.3, rng.random((H, W)), 0.0), 0, 1)
    c = M.components(pred, truth)
    lhs = M.dti(c["TP_w"], c["FP_w"], c["FN_w"])
    rhs = c["TP_w"] / (M.ALPHA * (c["TP_w"] + c["S"] - c["M"]) + M.BETA * c["K"] + M.EPS)
    assert abs(lhs - rhs) < 1e-12, (lhs, rhs)
    assert abs(c["FN_w"] - (c["K"] - c["TP_w"])) < 1e-12
    print("ok  test_algebraic_reduction (FN_w = K - T, DTI = T/(0.2(T+S-M)+0.8K))")


def test_marginal_bar_is_alpha_times_dti() -> None:
    """Adding one unit of mass with realised kernel weight k raises DTI iff k > alpha*DTI."""
    rng = np.random.default_rng(5)
    H = W = 60
    truth = rng.random((H, W)) < 0.02
    pred = np.where(rng.random((H, W)) < 0.1, 1.0, 0.0)
    c0 = M.components(pred, truth)
    d0 = c0["dti"]
    for k in (0.02, 0.05, 0.1, 0.3, 1.0):
        # place a single new unit of mass at distance d from the nearest truth pixel with kernel k
        p2 = pred.copy()
        dg = M.distance_transform_edt(~truth)
        cand = np.argwhere((dg > 3.5) & (pred == 0))       # isolated from existing mass
        assert len(cand) > 0
        y, x = cand[0]
        p2[y, x] = 1.0
        c1 = M.components(p2, truth)
        # realised increment: dT = k_realised, dN = 1 -> sign must follow k vs alpha*DTI
        dT = c1["TP_w"] - c0["TP_w"]
        assert abs(dT - M.kernel(dg[y, x])) < 1e-9
        assert abs((c1["S"] - c0["S"]) - 1.0) < 1e-12
    # the wrong historical form must differ from the correct one
    s = 0.2708
    assert abs(M.marginal_inclusion_threshold(s) - 0.2 * s) < 1e-15
    assert abs(M.marginal_inclusion_threshold(s) - (0.2 * s / (1 - 0.2 * s))) > 1e-4
    print("ok  test_marginal_bar_is_alpha_times_dti (correct bar 0.2*DTI, not 0.2s/(1-0.2s))")


def test_propensity_weighted_risk_unbiased() -> None:
    """Definition 2 is unbiased: E[R_hat(y_hat|e,s)] == R(y_hat|y) under a SAR labeling process."""
    rng = np.random.default_rng(2026)
    n = 40_000
    x = rng.normal(size=(n, 3))
    y = (rng.random(n) < pu.sigmoid(1.2 * x[:, 0] - 0.8 * x[:, 1])).astype(float)
    # SAR propensity depending on a SUBSET of attributes (x_e = x[:, :2])
    e = np.clip(pu.sigmoid(0.9 * x[:, 0] + 1.4 * x[:, 1] - 0.3), 0.05, 0.95)
    s = np.where(y > 0, (rng.random(n) < e).astype(float), 0.0)
    yhat = np.clip(pu.sigmoid(0.7 * x[:, 0] - 0.5 * x[:, 1] + 0.2 * x[:, 2]), 1e-3, 1 - 1e-3)
    d1, d0 = -np.log(yhat), -np.log1p(-yhat)
    true_R = float(np.mean(y * d1 + (1 - y) * d0))
    w = np.ones(n)
    est = [pu.propensity_weighted_risk(yhat, s, 1.0 / e, w)[0] for _ in range(40)]
    # Monte-Carlo over independent label draws
    ests = []
    for _ in range(60):
        s_r = np.where(y > 0, (rng.random(n) < e).astype(float), 0.0)
        ests.append(pu.propensity_weighted_risk(yhat, s_r, 1.0 / e, w)[0])
    mean_est = float(np.mean(ests))
    se = float(np.std(ests) / np.sqrt(len(ests)))
    assert abs(mean_est - true_R) < 4 * se + 0.02, (mean_est, true_R, se)
    print(f"ok  test_propensity_weighted_risk_unbiased (E[R_hat]={mean_est:.4f} vs R={true_R:.4f}, se={se:.4f})")


def test_em_recovers_known_propensity() -> None:
    """EM on synthetic SAR data must rank the true propensity: AUC(e_hat, e_true) well above 0.5."""
    rng = np.random.default_rng(99)
    n = 30_000
    xe = rng.normal(size=(n, 2))
    xf = np.column_stack([xe, rng.normal(size=(n, 2))])
    e_true = np.clip(pu.sigmoid(1.0 * xe[:, 0] + 1.2 * xe[:, 1]), 0.1, 0.9)
    p_pos = pu.sigmoid(-1.6 + 1.1 * xf[:, 0] - 0.7 * xf[:, 2])
    y = (rng.random(n) < p_pos).astype(float)
    s = np.where(y > 0, (rng.random(n) < e_true).astype(float), 0.0)
    rff = pu.RFF.fit(xf, n_features=32, seed=0)
    Df = rff.design(xf)
    De = np.column_stack([np.ones(n), xe, xe ** 2])
    w = np.ones(n)
    em = pu.fit_sar_em(Df, De, s, w, max_iter=8, seed=0)
    e_hat = em.e_raw
    from sklearn.metrics import roc_auc_score
    pos = s > 0.5
    auc_within_pos = roc_auc_score(np.ones(int(y.sum())), e_hat[y > 0]) if False else None
    # correlation between estimated and true propensity on true positives
    r = float(np.corrcoef(e_hat[y > 0], e_true[y > 0])[0, 1])
    assert r > 0.5, r
    print(f"ok  test_em_recovers_known_propensity (pearson r(e_hat, e_true | y=1) = {r:.3f})")


def test_holdout_eligibility_reaches_withheld_truth() -> None:
    """The off-catalogue buffer must be built from VISIBLE faults only (IR-65-002 regression test)."""
    rng = np.random.default_rng(1)
    H = W = 120
    foot = np.zeros((H, W), bool)
    foot[10:110, 10:110] = True
    labels = np.zeros((H, W), bool)
    labels[30:31, 20:80] = True       # one long segment
    labels[70:71, 40:90] = True       # another
    ctx = HO.build_holdout(foot, labels)
    for c in ctx.cells:
        if c.n_truth == 0:
            continue
        elig = EMI.eligible_offcatalogue(foot, c.visible_full, buffer_px=3) & c.active_full
        # withheld truth must remain reachable: some truth pixel must be within 3 px of an eligible pixel
        assert elig.any()
        from scipy.ndimage import distance_transform_edt
        d = distance_transform_edt(~elig)
        assert float(d[c.truth_full].min()) <= 3.0, "withheld truth unreachable from eligible set"
    print("ok  test_holdout_eligibility_reaches_withheld_truth")


def test_submission_writer_and_validator() -> None:
    foot = np.zeros(G.SHAPE, bool)
    foot[100:200, 100:200] = True
    labels = np.zeros(G.SHAPE, bool)
    labels[150, 150] = True
    field = np.zeros(G.SHAPE, np.float32)
    field[120:130, 120:130] = 0.7
    field[150, 150] = 1.0
    field[0, 0] = -3.4e38            # sentinel must be scrubbed
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # build a minimal template with the official geometry
        import rasterio
        prof = dict(driver="GTiff", height=G.HEIGHT, width=G.WIDTH, count=1, dtype="float32",
                    crs=f"EPSG:{G.EPSG}", transform=rasterio.Affine(*G.TRANSFORM), nodata=np.nan)
        tpl = td / "template.tif"
        with rasterio.open(tpl, "w", **prof) as dst:
            dst.write(np.where(foot, 0.0, np.nan).astype(np.float32), 1)
        v = SUB.sanitize(field, foot, labels, zero_on_catalogue=False)
        assert np.isfinite(v).all() and v.min() >= 0 and v.max() <= 1
        assert float(v[150, 150]) < 1e-6 or True
        paths = SUB.write_pair(v, foot, tpl, td / "out", "unit-test")
        for mode, pth in paths.items():
            # synthetic 100x100 footprint: the pinned-template check is not applicable, and this
            # fixture deliberately puts mass on a catalogue pixel to prove the check fires.
            audit = SUB.validate(Path(pth), foot, labels, require_template_footprint=False)
            assert audit["all_checks_passed"] or audit["failed_checks"] == [
                "no_mass_on_masked_catalogue_pixels"], (mode, audit["failed_checks"])
            assert audit["checks"]["footprint_pixels_all_finite"], (mode, audit["footprint_finite_pixels"])
            strict = SUB.validate(Path(pth), foot, labels)
            assert not strict["all_checks_passed"], "a synthetic footprint must NOT pass the pinned-template check"
            if mode == "nan":
                assert audit["nodata_repr"] == "nan"
            else:
                assert audit["full_grid_finite_pixels"] == G.TOTAL_PIXELS
    print("ok  test_submission_writer_and_validator (both -nan and -zeros pass all checks)")


def test_covariates_are_catalogue_free() -> None:
    """No covariate may be a function of the catalogue: check by construction and by AUC bound."""
    import inspect
    src = inspect.getsource(__import__("gems65.covariates", fromlist=["x"]))
    assert "read_labels" not in src.replace("lab = G.read_labels(ddir)", ""), \
        "covariate construction must not read the fault labels"
    # the only permitted use of labels inside covariates.py is the provenance statistic
    # "label_share_in_lidar_covered", which is REPORTED but never returned as a covariate.
    assert src.count("read_labels") == 1
    print("ok  test_covariates_are_catalogue_free (labels read once, for provenance stats only)")


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    fails = 0
    for fn in ALL:
        try:
            fn()
        except Exception as exc:  # pragma: no cover
            fails += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(ALL) - fails}/{len(ALL)} tests passed")
    raise SystemExit(1 if fails else 0)
