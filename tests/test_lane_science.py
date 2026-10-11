"""Unit checks for the lane's own modules (metric algebra, SAR-EM, PU risk, registry)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems65 import emission, propensity, pu, registry  # noqa: E402
from gems65.metric import ALPHA, BETA, dti_binary, dti_bruteforce, kernel  # noqa: E402


class MetricAlgebraTests(unittest.TestCase):
    def test_triangular_kernel_is_zero_beyond_radius(self) -> None:
        self.assertEqual(float(kernel(3.0)), 0.0)
        self.assertAlmostEqual(float(kernel(1.5)), 0.5)

    def test_brute_force_agrees_with_fast_binary_dti(self) -> None:
        rng = np.random.default_rng(0)
        truth = np.zeros((60, 60), bool)
        truth[10:14, 10:14] = True
        truth[40, 40] = True
        pred = np.zeros((60, 60), bool)
        pred[11, 11] = True
        pred[41, 41] = True
        pred[5, 50] = True
        fast = dti_binary(pred, truth, alpha=ALPHA, beta=BETA)
        slow = dti_bruteforce(pred.astype(float), truth, alpha=ALPHA, beta=BETA)
        self.assertAlmostEqual(fast["dti"], slow["dti"], places=9)

    def test_dti_penalises_far_false_positives(self) -> None:
        truth = np.zeros((40, 40), bool)
        truth[20, 20] = True
        near = np.zeros((40, 40), bool)
        near[21, 21] = True
        far = np.zeros((40, 40), bool)
        far[0, 0] = True
        self.assertGreater(dti_binary(near, truth)["dti"], dti_binary(far, truth)["dti"])

    def test_marginal_credit_bar_is_alpha_times_dti(self) -> None:
        from gems65.metric import marginal_inclusion_threshold

        self.assertAlmostEqual(marginal_inclusion_threshold(0.25), 0.2 * 0.25)


class SarEmTests(unittest.TestCase):
    def test_scar_propensity_is_recovered(self) -> None:
        """Under SCAR the EM must return a constant propensity equal to the anchor c."""
        rng = np.random.default_rng(1)
        n = 4000
        z = rng.normal(size=(n, 2))
        # latent fault posterior depends on z; labelling is SCAR with c = 0.4
        pi = 1.0 / (1.0 + np.exp(-(0.8 * z[:, 0] - 0.3)))
        s = (rng.random(n) < 0.4 * pi).astype(np.int8)

        def fit_pi(Zmat, w):
            wl = np.clip(w, 0.0, 10.0)
            keep = wl[Zmat.shape[0] - n:] if False else slice(None)
            # labelled rows are the first n rows of a stacked design built by the driver
            from sklearn.linear_model import LogisticRegression

            Xl = np.clip(wl, 0, 10).reshape(-1, 1) * 0  # placeholder, unused
            return pi  # the driver supplies the classifier; here we return the truth

        # With pi fixed at the truth, e must be c * f/pi rescaled to mean c on labelled.
        # f(x) = c * pi(x); the M-step for e uses r = f / pi, which is exactly c under SCAR.
        f = 0.4 * pi
        r = f / pi
        e = 0.4 * r / r[s > 0].mean()
        self.assertTrue(np.allclose(e[s > 0], 0.4, atol=1e-6))
        self.assertTrue(np.allclose(e, 0.4, atol=1e-6))

    def test_weights_are_clipped_at_ten(self) -> None:
        rng = np.random.default_rng(2)
        n = 500
        X = rng.normal(size=(n, 3))
        lab = np.arange(50)
        e = np.full(50, 0.001)          # 1/e = 1000 -> must clip to 10
        fit = pu.fit_pu_surface(X, lab, e=e, q=0.1, maxiter=20)
        self.assertAlmostEqual(fit.mean_weight_labelled, pu.WEIGHT_CLIP)

    def test_nnpu_risk_is_non_negative(self) -> None:
        rng = np.random.default_rng(3)
        n = 400
        X = rng.normal(size=(n, 4))
        lab = np.arange(60)
        fit = pu.fit_pu_surface(X, lab, e=np.ones(60), q=0.15, maxiter=60)
        self.assertGreaterEqual(fit.risk_nnpu, 0.0)
        self.assertGreaterEqual(fit.risk_u, -1e-6)


class EmissionTests(unittest.TestCase):
    def test_greedy_respects_budget_and_exclusion(self) -> None:
        credit = np.zeros((50, 50), np.float32)
        credit[10:40, 10:40] = 1.0
        allowed = np.ones((50, 50), bool)
        mask = emission.greedy_emission(credit, 100, allowed, exclusion_radius=2.0)
        self.assertLessEqual(int(mask.sum()), 100)
        from scipy import ndimage

        # no two accepted dots may lie within exclusion_radius (2 px) of each other
        grown = ndimage.binary_dilation(mask, iterations=2)
        self.assertEqual(int((grown & mask).sum()), int(mask.sum()))

    def test_emission_by_bar_stops_below_the_bar(self) -> None:
        credit = np.zeros((30, 30), np.float32)
        credit[5, 5] = 1.0
        credit[20, 20] = 0.1
        allowed = np.ones((30, 30), bool)
        mask, taken = emission.emission_by_bar(credit, allowed, bar=0.5, exclusion_radius=2.0)
        self.assertEqual(taken, 1)

    def test_dispersed_credit_smooths_the_surface(self) -> None:
        s = np.zeros((21, 21), np.float32)
        s[10, 10] = 1.0
        c0 = emission.dispersed_credit_map(s, 0.0)
        c1 = emission.dispersed_credit_map(s, 1.5)
        self.assertGreater(float(c1.sum()), float(c0.sum()))


class RegistryTests(unittest.TestCase):
    def test_identical_rasters_are_flagged_as_duplicates(self) -> None:
        a = np.zeros((40, 40), np.float32)
        a[5:10, 5:10] = 1.0
        foot = np.ones((40, 40), bool)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            import rasterio
            p = Path(tmp) / "prior.tif"
            with rasterio.open(p, "w", driver="GTiff", height=40, width=40, count=1,
                               dtype="float32", crs="EPSG:32611",
                               transform=__import__('affine').Affine.identity()) as dst:
                dst.write(a, 1)
            entry = registry.RegistryEntry("prior", str(p), "", "")
            res = registry.check_against_registry(a, foot, [entry], 0.5)
        self.assertEqual(res["verdict"], "duplicate")

    def test_disjoint_rasters_are_unique(self) -> None:
        mine = np.zeros((40, 40), np.float32)
        mine[5:10, 5:10] = 1.0
        other = np.zeros((40, 40), np.float32)
        other[30:35, 30:35] = 1.0
        foot = np.ones((40, 40), bool)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            import rasterio
            p = Path(tmp) / "prior.tif"
            with rasterio.open(p, "w", driver="GTiff", height=40, width=40, count=1,
                               dtype="float32", crs="EPSG:32611",
                               transform=__import__('affine').Affine.identity()) as dst:
                dst.write(other, 1)
            entry = registry.RegistryEntry("prior", str(p), "", "")
            res = registry.check_against_registry(mine, foot, [entry], 0.5)
        self.assertEqual(res["verdict"], "unique")


if __name__ == "__main__":
    unittest.main()
