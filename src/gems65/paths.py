"""Repository path constants for the GEMSDOE65 SAR-PU lane."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
BRIDGE = DATA / "bridge"          # committed: official grid rasters (2 MB total)
CACHE = ROOT / ".cache"           # git-ignored: 400 MB feature stack, external layers, registry
FEATURES_TIF = CACHE / "features" / "training_features.tif"
EXTERNAL = CACHE / "external"
REGISTRY = CACHE / "registry"
COVARIATE_CACHE = CACHE / "covariates_px5.npz"

EVIDENCE = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"

# Official grid files (sha256-pinned in registry/data_pins.json).
SAMPLE_SUBMISSION = BRIDGE / "sample_submission.tif"
LABELS = BRIDGE / "labels.tif"
EXISTING_FAULTS = BRIDGE / "existing_faults.tif"


def ensure_dirs() -> None:
    for d in (CACHE, CACHE / "features", EXTERNAL, REGISTRY, EVIDENCE, DOCS, DOWNLOADS,
              DOCS / "research", DOCS / "assets", ROOT / "tests"):
        d.mkdir(parents=True, exist_ok=True)
