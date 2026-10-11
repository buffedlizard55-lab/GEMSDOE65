import tempfile
import unittest
from pathlib import Path

from scripts.audit_lane_readiness import audit


class LaneReadinessTests(unittest.TestCase):
    def test_empty_checkout_is_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            result = audit(Path(temp))
        self.assertEqual(result["gate"], "negative")
        self.assertEqual(len(result["blockers"]), 6)
        self.assertIn("missing prior-raster registry", result["blockers"])

    def test_presence_is_not_a_scientific_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relpath in (
                "data/training_features.tif",
                "data/labels.tif",
                "data/sample_submission.tif",
                "scripts/evaluate_holdout.py",
                "scripts/submission_writer.py",
                "registry/rasters.json",
            ):
                path = root / relpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"presence-fixture-only")
            result = audit(root)
        self.assertEqual(result["gate"], "prerequisites-present")
        self.assertEqual(result["blockers"], [])
        self.assertIn("does not authorize a TIF", result["action"])

    def test_recognizes_documented_cached_data_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relpath in (
                "data/gems-geodawn-numerical-features.tif",
                "data/existing_faults.tif",
                "data/example_submission.tif",
                "evaluate_holdout.py",
                "submission_writer.py",
                "data/evidence/rasters.json",
            ):
                path = root / relpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"presence-fixture-only")
            result = audit(root)
        self.assertEqual(result["gate"], "prerequisites-present")
        self.assertEqual(result["checks"]["competition_inputs"]["labels"]["path"], "data/existing_faults.tif")


if __name__ == "__main__":
    unittest.main()
