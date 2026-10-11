from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_CARD = ROOT / "docs" / "data" / "run-card.json"


class RunCardTests(unittest.TestCase):
    def test_canonical_run_card_is_explicitly_negative_and_machine_readable(self) -> None:
        card = json.loads(RUN_CARD.read_text(encoding="utf-8"))

        self.assertEqual(card["verdict"], "negative")
        self.assertIsNone(card["submission"]["name"])
        self.assertIsNone(card["holdout_dti"]["score"])
        self.assertEqual(card["model_comparison"]["status"], "NOT RUN")
        self.assertIsNone(card["correlation_overlap_vs_registry"]["rank_correlation"])
        self.assertEqual(card["validator_output"]["status"], "NOT RUN — no candidate TIFF exists.")
        self.assertIsNone(card["raster_sha256"])

    def test_submission_note_respects_the_140_character_limit(self) -> None:
        card = json.loads(RUN_CARD.read_text(encoding="utf-8"))
        self.assertLessEqual(len(card["submission"]["note"]), 140)


if __name__ == "__main__":
    unittest.main()
