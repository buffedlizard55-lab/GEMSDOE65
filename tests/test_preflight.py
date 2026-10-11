from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.preflight import REQUIRED_PATHS, inspect_repository


class PreflightTests(unittest.TestCase):
    def test_empty_repository_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = inspect_repository(Path(temporary))

        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["submission_ready"])
        self.assertEqual(report["candidate_tiffs_found"], [])
        self.assertIn("data/training_features.tif", report["missing_prerequisites"])
        self.assertIn("registry/**/*.tif (prior-raster comparison set)", report["missing_prerequisites"])
        self.assertIn("path inventory only", report["scope"].lower())

    def test_missing_items_are_reported_by_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in REQUIRED_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            report = inspect_repository(root)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("registry/**/*.tif (prior-raster comparison set)", report["missing_prerequisites"])
        self.assertEqual(report["registry_raster_count"], 0)

    def test_complete_path_inventory_still_requires_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in REQUIRED_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            registry_raster = root / "registry" / "example.tif"
            registry_raster.parent.mkdir(parents=True, exist_ok=True)
            registry_raster.touch()
            candidate = root / "docs" / "downloads" / "candidate.tif"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.touch()

            report = inspect_repository(root)

        self.assertEqual(report["status"], "REQUIRES_VALIDATION")
        self.assertFalse(report["submission_ready"])
        self.assertEqual(report["registry_raster_count"], 1)
        self.assertEqual(report["candidate_tiffs_found"], ["docs/downloads/candidate.tif"])
        self.assertIn("Path inventory only", report["scope"])

    def test_non_tiff_download_files_are_not_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            downloads = root / "docs" / "downloads"
            downloads.mkdir(parents=True)
            (downloads / "notes.txt").touch()

            report = inspect_repository(root)

        self.assertEqual(report["candidate_tiffs_found"], [])
        self.assertEqual(report["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
