from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARD_PATH = ROOT / "registry" / "run-card.json"
SITE_CARD = ROOT / "docs" / "lane65-corrected-scale" / "data" / "run-card.json"
SUBSITE = ROOT / "docs" / "lane65-corrected-scale"
DOWNLOADS = ROOT / "docs" / "downloads"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LaneRunCardTests(unittest.TestCase):
    """This run's own card (registry/run-card.json).

    The repository's canonical card is docs/data/run_card.json and is tested by
    tests/test_run_card.py; the two are deliberately separate documents.
    """

    def setUp(self) -> None:
        self.card = json.loads(CARD_PATH.read_text(encoding="utf-8"))

    def test_schema_and_negative_verdict_are_explicit(self) -> None:
        self.assertEqual(self.card["schema"], "gems65-run-card/1")
        self.assertEqual(self.card["verdict"], "negative")
        self.assertEqual(self.card["gate"]["verdict"], "negative")
        self.assertFalse(self.card["gate"]["overall_passed"])
        self.assertFalse(self.card["submission"]["okay_to_submit"])
        self.assertIsNone(self.card["submission"]["cleared_artifact_for_upload"])
        self.assertIn("did not pass", self.card["submission"]["reason"])

    def test_submission_note_respects_the_140_character_limit(self) -> None:
        for note in (self.card["submission"]["note"], self.card["raster"]["note"]):
            self.assertLessEqual(len(note), 140)
            self.assertTrue(note.strip())

    def test_primary_raster_hash_matches_the_committed_bytes(self) -> None:
        path = ROOT / self.card["raster"]["primary_file"]
        self.assertTrue(path.is_file(), f"missing primary artifact: {path}")
        self.assertEqual(_sha256(path), self.card["raster"]["primary_sha256"])
        self.assertEqual(path.stat().st_size, self.card["raster"]["primary_bytes"])

    def test_diagnostic_variant_is_recorded_but_not_the_upload_file(self) -> None:
        path = ROOT / self.card["raster"]["diagnostic_nan_file"]
        self.assertTrue(path.is_file())
        self.assertEqual(_sha256(path), self.card["raster"]["diagnostic_nan_sha256"])
        self.assertNotEqual(
            Path(self.card["raster"]["diagnostic_nan_file"]).name,
            Path(self.card["raster"]["primary_file"]).name,
        )

    def test_validator_output_is_positive_for_the_upload_variant_only(self) -> None:
        out = self.card["validator_output"]
        self.assertTrue(out["all_checks_passed"])
        checks = out["checks"]
        self.assertTrue(checks["no_nan_anywhere"], "no NaN anywhere in the upload variant")
        self.assertTrue(checks["in_footprint_range_0_1"])
        self.assertTrue(checks["outside_footprint_zero"])
        self.assertTrue(checks["zero_dots_on_mapped_catalogue"])
        self.assertTrue(checks["transform_matches_sample_submission"])
        receipt = json.loads(
            (DOWNLOADS / f"{self.card['submission']['name']}-receipt.json").read_text()
        )
        self.assertTrue(receipt["files"][Path(self.card["raster"]["primary_file"]).name]["all_checks_passed"])
        self.assertFalse(receipt["gate"]["approved_for_weekly_slot"])
        self.assertFalse(
            receipt["files"][Path(self.card["raster"]["diagnostic_nan_file"]).name]["all_checks_passed"]
        )

    def test_uniqueness_measurements_are_recorded_with_the_rule_false_positive(self) -> None:
        uq = self.card["correlation_overlap_vs_registry"]
        self.assertFalse(uq["duplicate_hash_match"])
        self.assertLess(uq["worst_spearman_abs"], 0.90)
        self.assertTrue(uq["unique_by_hash_and_surface"])
        self.assertIn("false_positive", json.dumps(uq))
        self.assertIn("saturation", json.dumps(uq))

    def test_subsite_copy_of_the_card_is_identical(self) -> None:
        self.assertEqual(CARD_PATH.read_bytes(), SITE_CARD.read_bytes())

    def test_experiments_carry_evidence_class_and_ci(self) -> None:
        exp = {e["id"]: e for e in self.card["experiments"]}
        self.assertEqual(sorted(exp), ["E1", "E2", "E3", "E3b"])
        for experiment in exp.values():
            self.assertTrue(experiment["verdict"])
            self.assertGreater(experiment["cells"], 0)
        for arm in ("E1", "E3"):
            primary = exp[arm]["results"]["mode_all"]
            lo, hi = primary["paired_delta_ci95"]
            self.assertLess(lo, primary["paired_delta"] < hi, f"{arm} CI must bracket its delta")
            self.assertLess(lo, 0.0, f"{arm} stays a tie: interval must include 0")
            self.assertGreater(hi, 0.0, f"{arm} stays a tie: interval must include 0")
        for arm in ("E2", "E3b"):
            r = exp[arm]["results"]
            self.assertGreater(r["paired_delta"], 0.0, f"{arm} is directionally positive")
            self.assertLess(r["paired_delta_ci95"][0], 0.0,
                            f"{arm} must remain non-significant (interval includes 0)")
        self.assertIn("rbf", exp["E3"]["propensity_model"])
        self.assertEqual(exp["E1"]["propensity_model"], "grid")

    def test_propensity_is_non_degenerate_in_the_corrected_experiment(self) -> None:
        e3 = [e for e in self.card["experiments"] if e["id"] == "E3"][0]
        d = e3["propensity_diagnostics"]
        self.assertGreater(d["e_pos_max"] - d["e_pos_min"], 0.05,
                           "the corrected propensity must actually have spread")
        self.assertGreater(d["pool_ratio"], 10.0, "the subsampling ratio must be recorded")
        self.assertLess(d["e_pos_mean"], 0.99, "the fixed point must not collapse to e -> 1")


class SubSiteGateBannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
        self.card_hash = self.card["raster"]["primary_sha256"]

    def test_subsite_home_leads_with_the_do_not_submit_banner(self) -> None:
        home = (SUBSITE / "index.html").read_text(encoding="utf-8")
        banner = home.find("DO NOT SUBMIT THIS RASTER")
        download = home.find("primary", home.find("<h2>Download</h2>") - 400)
        self.assertGreater(banner, 0, "the do-not-submit banner is missing")
        self.assertLess(banner, home.find("<h2>Download</h2>"), "banner must precede the download block")
        self.assertIn(self.card_hash, home, "home page must show the sha256 of the primary artifact")
        self.assertGreaterEqual(download, 0)

    def test_subsite_never_claims_a_cleared_status(self) -> None:
        for page in SUBSITE.glob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("CLEARED", text.replace("says CLEARED", "").replace("CLEARED</strong>", ""),
                             f"{page.name} implies a cleared submission")

    def test_executive_summary_states_the_current_block_first(self) -> None:
        page = (SUBSITE / "executive-summary.html").read_text(encoding="utf-8")
        self.assertIn("do not submit", page.lower())
        self.assertIn("New submission", page)
        self.assertIn("140", page)


if __name__ == "__main__":
    unittest.main()
