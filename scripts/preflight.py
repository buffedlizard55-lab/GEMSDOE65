#!/usr/bin/env python3
"""Fail-closed inventory for the GEMS project prerequisites.

This script deliberately does not train, score, download, validate, or write a
GeoTIFF. It exists so an absent shared template/data dependency cannot be
mistaken for a completed pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_PATHS = (
    "data/training_features.tif",
    "data/labels.tif",
    "data/sample_submission.tif",
    "scripts/download_competition_data.sh",
    "scripts/prepare_data.py",
    "scripts/evaluate_holdout.py",
    "scripts/submission_writer.py",
    "scripts/validate_submission.py",
)


def inspect_repository(root: Path) -> dict[str, Any]:
    """Report path presence only; presence never means data are verified."""
    root = root.resolve()
    missing = [relative for relative in REQUIRED_PATHS if not (root / relative).is_file()]
    registry = root / "registry"
    registry_rasters = sorted(registry.rglob("*.tif")) if registry.is_dir() else []
    if not registry_rasters:
        missing.append("registry/**/*.tif (prior-raster comparison set)")

    candidates_dir = root / "docs" / "downloads"
    candidates = (
        sorted(str(path.relative_to(root)) for path in candidates_dir.glob("*.tif"))
        if candidates_dir.is_dir()
        else []
    )

    return {
        "status": "BLOCKED" if missing or not candidates else "REQUIRES_VALIDATION",
        "root": str(root),
        "missing_prerequisites": missing,
        "registry_raster_count": len(registry_rasters),
        "candidate_tiffs_found": candidates,
        "submission_ready": False,
        "scope": "Path inventory only; no hashes, raster metadata, score, or validation were checked.",
        "next_action": (
            "Reuse the authenticated official data and the shared template cache/evaluator/writer/validator; "
            "then run the blocked holdout, leakage, uniqueness, and format gates. Do not synthesize a TIFF."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    report = inspect_repository(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Status: {report['status']}")
        print("Submission ready: NO")
        print("Scope: path inventory only; no data/raster validation was run.")
        print("Missing prerequisites:")
        for relative in report["missing_prerequisites"]:
            print(f"  - {relative}")
        print("Candidate TIFFs:")
        for candidate in report["candidate_tiffs_found"]:
            print(f"  - {candidate}")
        if not report["candidate_tiffs_found"]:
            print("  - none; do not submit")
    return 0 if report["status"] == "REQUIRES_VALIDATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
