from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_CARD = ROOT / "docs" / "data" / "run-card.json"
MANIFEST = ROOT / "docs" / "downloads" / "submissions_manifest.json"


class RunCardTests(unittest.TestCase):
    """The canonical run card must describe the run that actually happened."""

    def setUp(self) -> None:
        self.card = json.loads(RUN_CARD.read_text(encoding="utf-8"))
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_required_fields_present(self) -> None:
        for key in (
            "hypothesis", "mechanism", "named_non_fault_process_that_could_mimic_it",
            "holdout_dti", "model_comparison", "correlation_overlap_vs_registry",
            "raster_sha256", "validator_output", "submission", "verdict",
        ):
            self.assertIn(key, self.card)

    def test_every_score_is_labelled(self) -> None:
        self.assertEqual(self.card["holdout_dti"]["evidence_label"], "HOLDOUT-DTI")
        self.assertEqual(self.card["holdout_dti"]["alpha"], 0.2)
        self.assertEqual(self.card["holdout_dti"]["beta"], 0.8)
        self.assertEqual(self.card["holdout_dti"]["radius_px"], 3.0)
        # a projection must never be written as a score
        self.assertNotIn("ORGANIZER-CONFIRMED", json.dumps(self.card["holdout_dti"]))

    def test_submission_note_respects_the_140_character_limit(self) -> None:
        self.assertLessEqual(len(self.card["submission"]["note"]), 140)

    def test_card_and_manifest_agree(self) -> None:
        self.assertEqual(self.card["verdict"], "promote" if self.manifest["cleared_to_submit"] else "negative")
        self.assertEqual(self.card["submission"]["name"], self.manifest["files"]["zeros"]["filename"])
        self.assertEqual(self.card["raster_sha256"], self.manifest["files"]["zeros"]["sha256"])

    def test_registry_gate_recorded(self) -> None:
        reg = self.card["correlation_overlap_vs_registry"]
        self.assertEqual(reg["status"], "COMPUTED")
        self.assertLessEqual(reg["max_abs_rank_correlation"], reg["rank_correlation_limit"])
        self.assertLessEqual(reg["max_fraction_of_dots_within_3px"], reg["dot_overlap_limit"])
        self.assertEqual(reg["verdict"], "unique")

    def test_validator_output_is_a_pass(self) -> None:
        v = self.card["validator_output"]
        self.assertEqual(v["status"], "PASS")
        self.assertTrue(v["no_nan_inside_footprint"])
        self.assertTrue(v["values_in_0_1"])
        self.assertTrue(v["crs_shape_transform_match"])
        self.assertTrue(v["single_band_float32"])
        self.assertTrue(v["all_checks_passed_zeros"])
        self.assertTrue(v["all_checks_passed_nan"])

    def test_what_is_not_claimed_is_explicit(self) -> None:
        self.assertIn("No organizer score is claimed", self.card["what_is_not_claimed"])


if __name__ == "__main__":
    unittest.main()
