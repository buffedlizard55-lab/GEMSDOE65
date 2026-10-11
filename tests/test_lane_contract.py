"""Contract tests for the GEMSDOE65 lane.

These tests never touch competition rasters: they use small synthetic catalogues
and synthetic metric terms so that the *rules* of the lane -- covariance of the
emission, fold-safety of the derived channels, the two-sided promotion gate -- are
checked independently of the data.  No test here scores a model or asserts a
leaderboard value.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems65 import lane  # noqa: E402
from gems57 import evaluate_holdout  # noqa: E402
from gems57.metric import ALPHA, BETA  # noqa: E402

import run_lane  # noqa: E402


def two_parallel_traces(shape=(60, 120), gap=10, offset=0):
    cat = np.zeros(shape, bool)
    cat[20 + offset, 5:115] = True
    cat[20 + gap, 5:115] = True
    return cat


class ChannelSetTests(unittest.TestCase):
    def test_catalogue_channels_are_only_in_the_catalogue_sets(self):
        local = {c["key"] for c in lane.channel_set("local")}
        joint = {c["key"] for c in lane.channel_set("local+fault")}
        self.assertFalse(local & set(lane.CATALOGUE_CHANNEL_KEYS))
        self.assertTrue(joint & set(lane.CATALOGUE_CHANNEL_KEYS))
        self.assertTrue(local <= joint)
        self.assertEqual(len(lane.PHYSICAL_CHANNELS),
                         len([c for c in lane.CHANNELS
                              if c["key"] not in lane.CATALOGUE_CHANNEL_KEYS]))

    def test_unknown_channel_set_is_rejected(self):
        with self.assertRaises(ValueError):
            lane.channel_set("everything-i-like")


class SplayBandTests(unittest.TestCase):
    def test_band_recovers_a_known_inter_trace_spacing(self):
        info = lane.splay_band(two_parallel_traces(gap=10), sample=500, k=64)
        self.assertAlmostEqual(info["center_px"], 10.0, delta=0.5)
        self.assertGreater(info["half_width_px"], 0.5)
        self.assertLess(info["half_width_px"], 3.0)

    def test_band_is_seeded_and_component_based(self):
        cat = two_parallel_traces(gap=7)
        a = lane.splay_band(cat, sample=200, k=64, seed=1)
        b = lane.splay_band(cat, sample=200, k=64, seed=1)
        self.assertEqual(a["center_px"], b["center_px"])
        self.assertEqual(a["n_pairs"], b["n_pairs"])


class CalibrationTests(unittest.TestCase):
    def test_calibrate_surface_matches_mass_and_keeps_ranking(self):
        prob = np.array([[0.1, 0.4], [0.9, 0.2]], np.float32)
        active = np.array([[True, True], [True, True]])
        out = lane.calibrate_surface(prob, active, target_mass=0.5)
        self.assertAlmostEqual(float(out.sum()), 0.5, places=6)
        order = np.argsort(prob.ravel())
        self.assertTrue(np.all(np.diff(out.ravel()[order]) >= -1e-6))

    def test_calibrate_surface_never_exceeds_the_target_after_clipping(self):
        prob = np.array([[0.005, 0.9]], np.float32)
        out = lane.calibrate_surface(prob, np.ones(prob.shape, bool), target_mass=100.0)
        self.assertLessEqual(float(out.sum()), 100.0)
        self.assertLessEqual(float(out.max()), 1.0)

    def test_calibrate_surface_rejects_empty_mass(self):
        with self.assertRaises(ValueError):
            lane.calibrate_surface(np.zeros((3, 3), np.float32),
                                   np.ones((3, 3), bool), target_mass=1.0)


class WireSurfaceTests(unittest.TestCase):
    def test_band_variant_is_a_bump_between_the_traces(self):
        cat = two_parallel_traces(gap=10)
        fp = np.ones(cat.shape, bool)
        fp[0, 0] = False                     # one cell outside the footprint
        surf, info = lane.wire_surface(cat, fp, variant="band", rangefront=None)
        self.assertEqual(surf.shape, cat.shape)
        self.assertEqual(float(surf[~fp].max()), 0.0)
        mid = surf[25, 60]
        far = surf[0, 0]
        self.assertGreater(mid, far)
        self.assertGreaterEqual(float(surf.min()), 0.0)
        self.assertLessEqual(float(surf.max()), 1.0)
        self.assertAlmostEqual(info["center_px"], 10.0, delta=0.5)

    def test_range_front_variant_needs_the_covariate(self):
        cat = two_parallel_traces()
        with self.assertRaises(ValueError):
            lane.wire_surface(cat, np.ones(cat.shape, bool), variant="band_rf")

    def test_rangefront_scale_is_a_catalogue_quantile(self):
        cat = two_parallel_traces()
        rf = np.linspace(0.0, 1000.0, cat.size, dtype=np.float32).reshape(cat.shape)
        lam = lane.rangefront_scale_m(cat, rf, quantile=0.5)
        self.assertGreater(lam, 0.0)
        self.assertLess(lam, 1000.0)


class EmissionTests(unittest.TestCase):
    def test_emit_for_arm_never_places_a_dot_outside_allowed(self):
        prob = np.random.default_rng(0).random((40, 40)).astype(np.float32)
        allowed = np.zeros((40, 40), bool)
        allowed[10:30, 10:30] = True
        alloc = lane.emit_for_arm(prob, allowed, k_truth=50, max_dots=200, mass=50)
        self.assertFalse(np.any(alloc.emitted & ~allowed))
        self.assertEqual(int(alloc.emitted.sum()), alloc.n_dots)

    def test_emit_for_arm_is_deterministic(self):
        prob = np.random.default_rng(1).random((30, 30)).astype(np.float32)
        allowed = np.ones((30, 30), bool)
        first = lane.emit_for_arm(prob, allowed, 20, max_dots=100, mass=20)
        second = lane.emit_for_arm(prob, allowed, 20, max_dots=100, mass=20)
        self.assertTrue(np.array_equal(first.emitted, second.emitted))


def synthetic_pooled(candidate_dti, baseline_dti, tercile_candidate, tercile_baseline):
    """Minimal structures accepted by run_lane.gate_decision."""
    pooled = {
        "scores": {"wire": {"dti": candidate_dti}, "nnpu": {"dti": baseline_dti}},
        "paired_differences": {"nnpu": {"delta": candidate_dti - baseline_dti,
                                        "ci95": [0.0, 0.0]}},
    }
    per_fold = [{"per_fold": {"wire": {"high_propensity_tercile": {"dti": tercile_candidate}},
                              "nnpu": {"high_propensity_tercile": {"dti": tercile_baseline}}}}]
    return pooled, per_fold


class GateTests(unittest.TestCase):
    def test_gate_needs_both_conditions(self):
        pooled, per_fold = synthetic_pooled(0.10, 0.02, 0.0, 0.0)
        self.assertTrue(run_lane.gate_decision(pooled, per_fold, arm="wire",
                                               baseline="nnpu")["met"])
        pooled, per_fold = synthetic_pooled(0.10, 0.02, 0.0, 0.05)
        gate = run_lane.gate_decision(pooled, per_fold, arm="wire", baseline="nnpu")
        self.assertFalse(gate["met"])
        self.assertFalse(gate["high_propensity_tercile"]["no_loss"])
        pooled, per_fold = synthetic_pooled(0.01, 0.02, 0.5, 0.1)
        gate = run_lane.gate_decision(pooled, per_fold, arm="wire", baseline="nnpu")
        self.assertFalse(gate["met"])
        self.assertFalse(gate["overall"]["higher_overall"])


class EvidenceLabelTests(unittest.TestCase):
    def test_every_pooled_score_carries_the_evidence_label_and_version(self):
        def arm(tp, fp_w, fn):
            a = np.zeros((3, 4), float)
            a[:, 0], a[:, 1], a[:, 2], a[:, 3] = tp, fp_w, fn, 10.0
            return a                      # identical integer truth counts per block
        out = evaluate_holdout.pooled_summary({"wire": arm(3.0, 1.0, 7.0),
                                               "nnpu": arm(1.5, 2.0, 8.5)},
                                              candidate="wire", draws=25)
        for arm in ("wire", "nnpu"):
            self.assertEqual(out["scores"][arm]["evidence_class"], "HOLDOUT-DTI")
            self.assertEqual(out["scores"][arm]["evaluator_version"],
                             evaluate_holdout.VERSION)
            self.assertEqual(out["scores"][arm]["withheld_positive_pixels"], 30)
            self.assertEqual(len(out["scores"][arm]["ci95"]), 2)

    def test_metric_weights_are_the_published_ones(self):
        self.assertEqual((ALPHA, BETA), (0.2, 0.8))


def passing_card(**overrides):
    """A card fixture that satisfies every discriminating condition."""
    uniq = {"verdict": "negative", "duplicate_count": 4,
            "byte_unique_among_checked": True, "pixel_unique_among_checked": True,
            "worst_spearman_full_footprint": 0.04, "worst_jaccard_dot_sets": 0.004,
            "registry_rasters_checked": 62, "complete_accessible_scan": False,
            "literal_test_demonstration": {"random_dots_inside_union_mean": 0.99999,
                                           "random_dots_inside_densest_mean": 0.736,
                                           "union_coverage_fraction": 0.99999}}
    card = {"gate": {"met": True}, "forced": False,
            "files": {"x-zeros.tif": {"validator_passed": True,
                                      "in_range_inside_footprint": True,
                                      "nan_inside_footprint": 0,
                                      "positive_on_catalogue": 0}},
            "uniqueness": uniq}
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(card.get(key), dict):
            card[key].update(value)
        else:
            card[key] = value
    return card


class VerdictTests(unittest.TestCase):
    def test_verdict_never_clears_a_failed_or_forced_card(self):
        card = passing_card(gate={"met": False})
        self.assertFalse(run_lane._verdict(card)["download_cleared"])
        card = passing_card(forced=True, gate={"met": False})
        verdict = run_lane._verdict(card)
        self.assertFalse(verdict["download_cleared"])
        self.assertIn("DO NOT SUBMIT", verdict["one_line"])

    def test_verdict_requires_validator_range_and_no_identity(self):
        card = passing_card()
        verdict = run_lane._verdict(card)
        self.assertTrue(verdict["download_cleared"])
        self.assertTrue(verdict["literal_overlap_rule_degenerate"])
        self.assertIn("DOWNLOAD AND SUBMIT", verdict["one_line"])
        self.assertFalse(run_lane._verdict(passing_card(
            files={"x-zeros.tif": {"validator_passed": False,
                                   "in_range_inside_footprint": True,
                                   "nan_inside_footprint": 0,
                                   "positive_on_catalogue": 0}}))["download_cleared"])
        self.assertFalse(run_lane._verdict(passing_card(
            uniqueness={"pixel_unique_among_checked": False}))["download_cleared"])
        self.assertFalse(run_lane._verdict(passing_card(
            uniqueness={"worst_spearman_full_footprint": 0.99}))["download_cleared"])
        self.assertFalse(run_lane._verdict(passing_card(
            uniqueness={"worst_jaccard_dot_sets": 0.8}))["download_cleared"])

    def test_literal_overlap_rule_only_clears_when_provably_degenerate(self):
        card = passing_card(uniqueness={"literal_test_demonstration":
                                        {"random_dots_inside_union_mean": 0.10,
                                         "random_dots_inside_densest_mean": 0.10}})
        verdict = run_lane._verdict(card)
        self.assertFalse(verdict["literal_overlap_rule_degenerate"])
        self.assertFalse(verdict["download_cleared"])


class RegistryIndexTests(unittest.TestCase):
    def test_index_is_complete_machine_readable_inventory(self):
        path = ROOT / "data" / "registry" / "registry_index.json"
        if not path.is_file():
            self.skipTest("registry index not built in this checkout")
        index = json.loads(path.read_text())
        self.assertFalse(index["complete_accessible_scan"],
                         "the staged set must not claim a complete public inventory")
        self.assertTrue(index["rasters"])
        for entry in index["rasters"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(entry["sources"])
            self.assertTrue(entry["cache_file"].endswith(".tif"))


if __name__ == "__main__":
    unittest.main()
