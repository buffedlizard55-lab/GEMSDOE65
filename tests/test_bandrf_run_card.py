"""Run-card contract: the card is machine-readable, self-consistent and honest.

The tests no longer assert a frozen *negative* verdict (that was correct only while
the lane had no candidate).  They now assert the invariants that must hold for any
verdict: the decision is derivable from the fields, the evidence labels are
explicit, the submission note respects the 140-character limit, and a cleared
verdict is impossible without a passing validator and a duplicate basis.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_CARD = ROOT / "docs" / "lane65-bandrf" / "data" / "run-card.json"
sys.path.insert(0, str(ROOT / "scripts"))


class RunCardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = json.loads(RUN_CARD.read_text(encoding="utf-8"))

    def test_verdict_is_machine_readable_and_self_consistent(self) -> None:
        card = self.card
        verdict = card["verdict"]
        self.assertIn("download_cleared", verdict)
        self.assertIn("one_line", verdict)
        self.assertTrue(verdict["one_line"].startswith(("DOWNLOAD AND SUBMIT", "DO NOT SUBMIT")))
        if verdict["download_cleared"]:
            self.assertTrue(verdict["gate_met"])
            self.assertTrue(verdict["validator_passed"])
            self.assertEqual(verdict["literal_overlap_flags"] > 0,
                             verdict["literal_overlap_rule_degenerate"])
            self.assertLessEqual(verdict["uniqueness_worst_spearman"] or 0.0, 0.90)
            # The recommended upload is the canonical NaN-outside encoding; the zeros-outside
            # diagnostic is published beside it, fails the canonical outside-footprint check by
            # design, and must therefore never be the recommended file.
            self.assertTrue(any(name.endswith("-nan.tif") for name in card["files"]))
            primary = next(rec for name, rec in card["files"].items() if name.endswith("-nan.tif"))
            self.assertTrue(primary["validator_passed"])
            self.assertTrue(primary["in_range_inside_footprint"])
            self.assertEqual(primary["nan_inside_footprint"], 0)
            self.assertEqual(primary["positive_on_catalogue"], 0)
            diagnostics = [rec for name, rec in card["files"].items() if name.endswith("-zeros.tif")]
            if diagnostics:
                self.assertFalse(diagnostics[0]["validator_passed"])
        else:
            self.assertTrue(any(token in verdict["one_line"].lower()
                                for token in ("did not clear", "not met", "do not submit")))

    def test_gate_records_both_conditions_and_the_mandated_comparison(self) -> None:
        gate = self.card["gate"]
        self.assertTrue(gate["overall"]["higher_overall"])
        self.assertIn("no_loss", gate["high_propensity_tercile"])
        self.assertTrue(gate["met"] == (gate["overall"]["higher_overall"]
                                        and gate["high_propensity_tercile"]["no_loss"]))
        self.assertIn("paired_delta_ci95", gate["mandated_arm_comparison"])

    def test_submission_note_respects_the_140_character_limit(self) -> None:
        receipt = self.card.get("writer_receipt") or {}
        note = receipt.get("note")
        if note is None:
            note = (self.card.get("emission") or {}).get("note", "")
        self.assertLessEqual(len(note), 140)

    def test_uniqueness_section_carries_the_measured_comparison(self) -> None:
        uniq = self.card.get("uniqueness") or {}
        self.assertIn("worst_spearman_full_footprint", uniq)
        self.assertIn("registry_rasters_checked", uniq)
        demo = uniq.get("literal_test_demonstration") or {}
        self.assertGreater(demo.get("random_dots_inside_union_mean", 0.0), 0.0)

    def test_every_reported_number_carries_a_holdout_label(self) -> None:
        holdout = json.loads((ROOT / "evidence" / "lane65-bandrf" / "lane_holdout.json").read_text())
        self.assertEqual(holdout["evidence_class"], "HOLDOUT-DTI")
        for arm, score in holdout["pooled_wire"]["scores"].items():
            self.assertEqual(score["evidence_class"], "HOLDOUT-DTI")
            self.assertEqual(len(score["ci95"]), 2)
            self.assertGreater(score["withheld_positive_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
