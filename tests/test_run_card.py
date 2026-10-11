from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RunCardTests(unittest.TestCase):
    def test_blocked_run_card_is_explicit_and_machine_readable(self) -> None:
        card = json.loads((ROOT / "evidence" / "run_card.json").read_text())

        self.assertEqual(card["verdict"], "negative")
        self.assertFalse(card["download_permitted"])
        self.assertIsNone(card["submission_name"])
        self.assertEqual(card["holdout_dti"]["status"], "NOT_RUN")
        self.assertIsNone(card["holdout_dti"]["pooled_value"])
        self.assertEqual(card["registry_comparison"]["status"], "NOT_RUN")
        self.assertEqual(card["validator_output"]["status"], "NOT_RUN")
        self.assertIsNone(card["raster_sha256"])

    def test_submission_note_is_within_charter_limit(self) -> None:
        card = json.loads((ROOT / "evidence" / "run_card.json").read_text())
        self.assertLessEqual(len(card["submission_note"]), 140)


if __name__ == "__main__":
    unittest.main()
